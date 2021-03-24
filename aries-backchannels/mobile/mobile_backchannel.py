import asyncio
import functools
import json
import logging
import os
import random
import subprocess
import sys
import uuid
from timeit import default_timer
from time import sleep
from operator import itemgetter
from qrcode import QRCode
import base64

from aiohttp import (
    web,
    ClientSession,
    ClientRequest,
    ClientResponse,
    ClientError,
    ClientTimeout,
)

from python.agent_backchannel import AgentBackchannel, default_genesis_txns, RUN_MODE, START_TIMEOUT
from python.utils import require_indy, flatten, log_json, log_msg, log_timer, output_reader, prompt_loop
from python.storage import store_resource, get_resource, delete_resource, push_resource, pop_resource, pop_resource_latest

#from helpers.jsonmapper.json_mapper import JsonMapper

LOGGER = logging.getLogger(__name__)

MAX_TIMEOUT = 5

DEFAULT_BIN_PATH = "../venv/bin"
DEFAULT_PYTHON_PATH = ".."

if RUN_MODE == "docker":
    DEFAULT_BIN_PATH = "./bin"
    DEFAULT_PYTHON_PATH = "."
elif RUN_MODE == "pwd":
    DEFAULT_BIN_PATH = "./bin"
    DEFAULT_PYTHON_PATH = "."

class MobileAgentBackchannel(AgentBackchannel):
    def __init__(
        self, 
        ident: str,
        http_port: int,
        admin_port: int,
        genesis_data: str = None,
        params: dict = {}
    ):
        super().__init__(
            ident,
            http_port,
            admin_port,
            genesis_data,
            params
        )
        self.connection_state = "n/a"

    def get_agent_args(self):
        result = [
            ("--endpoint", self.endpoint),
            ("--label", self.label),
            #"--auto-ping-connection",
            #"--auto-accept-invites", 
            #"--auto-accept-requests", 
            #"--auto-respond-messages",
            ("--inbound-transport", "http", "0.0.0.0", str(self.http_port)),
            ("--outbound-transport", "http"),
            ("--admin", "0.0.0.0", str(self.admin_port)),
            "--admin-insecure-mode",
            "--public-invites",
            ("--wallet-type", self.wallet_type),
            ("--wallet-name", self.wallet_name),
            ("--wallet-key", self.wallet_key),
        ]

        if self.get_acapy_version_as_float() > 56:
            result.append(("--auto-provision", "--recreate-wallet"))

        if self.genesis_data:
            result.append(("--genesis-transactions", self.genesis_data))
        if self.seed:
            result.append(("--seed", self.seed))
        if self.storage_type:
            result.append(("--storage-type", self.storage_type))
        if self.postgres:
            result.extend(
                [
                    ("--wallet-storage-type", "postgres_storage"),
                    ("--wallet-storage-config", json.dumps(self.postgres_config)),
                    ("--wallet-storage-creds", json.dumps(self.postgres_creds)),
                ]
            )
        if self.webhook_url:
            result.append(("--webhook-url", self.webhook_url))
        
        # This code for Tails Server is included here because aca-py does not support the env var directly yet. 
        # when it does (and there is talk of supporting YAML) then this code can be removed. 
        if os.getenv('TAILS_SERVER_URL') is not None:
            # if the env var is set for tails server then use that.
            result.append(("--tails-server-base-url", os.getenv('TAILS_SERVER_URL')))
        else:
            # if the tails server env is not set use the gov.bc TEST tails server.
            result.append(("--tails-server-base-url", "https://tails-server-test.pathfinder.gov.bc.ca"))
        
        if os.getenv('EMIT-NEW-DIDCOMM-PREFIX') is not None:
            # if the env var is set for tails server then use that.
            result.append(("--emit-new-didcomm-prefix"))

        if os.getenv('EMIT-NEW-DIDCOMM-MIME-TYPE') is not None:
            # if the env var is set for tails server then use that.
            result.append(("--emit-new-didcomm-mime-type"))

        # This code for log level is included here because aca-py does not support the env var directly yet. 
        # when it does (and there is talk of supporting YAML) then this code can be removed. 
        if os.getenv('LOG_LEVEL') is not None:
            result.append(("--log-level", os.getenv('LOG_LEVEL')))

        #if self.extra_args:
        #    result.extend(self.extra_args)

        return result

    async def listen_webhooks(self, webhook_port):
        self.webhook_port = webhook_port
        if RUN_MODE == "pwd":
            self.webhook_url = f"http://localhost:{str(webhook_port)}/webhooks"
        else:
            self.webhook_url = (
                f"http://{self.external_host}:{str(webhook_port)}/webhooks"
            )
        app = web.Application()
        app.add_routes([web.post("/webhooks/topic/{topic}/", self._receive_webhook)])
        runner = web.AppRunner(app)
        await runner.setup()
        self.webhook_site = web.TCPSite(runner, "0.0.0.0", webhook_port)
        await self.webhook_site.start()
        print("Listening to web_hooks on port", webhook_port)

    async def _receive_webhook(self, request: ClientRequest):
        topic = request.match_info["topic"]
        payload = await request.json()
        await self.handle_webhook(topic, payload)
        # TODO web hooks don't require a response???
        return web.Response(text="")

    async def handle_webhook(self, topic: str, payload):
        if topic != "webhook":  # would recurse
            handler = f"handle_{topic}"

            # Remove this handler change when bug is fixed. 
            if handler == "handle_oob-invitation":
                handler = "handle_oob_invitation"

            method = getattr(self, handler, None)
            # put a log message here
            log_msg('Passing webhook payload to handler ' + handler)
            if method:
                await method(payload)
            else:
                log_msg(
                    f"Error: agent {self.ident} "
                    f"has no method {handler} "
                    f"to handle webhook on topic {topic}"
                )
        else:
            log_msg('in webhook, topic is: ' + topic + ' payload is: ' + json.dumps(payload))

    async def handle_connections(self, message):
        if "invitation_msg_id" in message:
            # This is an did-exchange message based on a Non-Public DID invitation
            invitation_id = message["invitation_msg_id"]
            push_resource(invitation_id, "didexchange-msg", message)
        elif "request_id" in message:
            # This is a did-exchange message based on a Public DID non-invitation
            request_id = message["request_id"]
            push_resource(request_id, "didexchange-msg", message)
        else:
            connection_id = message["connection_id"]
            push_resource(connection_id, "connection-msg", message)
        log_msg('Received a Connection Webhook message: ' + json.dumps(message))

    async def handle_issue_credential(self, message):
        thread_id = message["thread_id"]
        push_resource(thread_id, "credential-msg", message)
        log_msg('Received Issue Credential Webhook message: ' + json.dumps(message)) 
        if "revocation_id" in message: # also push as a revocation message 
            push_resource(thread_id, "revocation-registry-msg", message)
            log_msg('Issue Credential Webhook message contains revocation info') 

    async def handle_present_proof(self, message):
        thread_id = message["thread_id"]
        push_resource(thread_id, "presentation-msg", message)
        log_msg('Received a Present Proof Webhook message: ' + json.dumps(message))

    async def handle_revocation_registry(self, message):
        # No thread id in the webhook for revocation registry messages
        cred_def_id = message["cred_def_id"]
        push_resource(cred_def_id, "revocation-registry-msg", message)
        log_msg('Received Revocation Registry Webhook message: ' + json.dumps(message)) 

    async def handle_oob_invitation(self, message):
        # No thread id in the webhook for revocation registry messages
        invitation_id = message["invitation_id"]
        push_resource(invitation_id, "oob-inviation-msg", message)
        log_msg('Received Out of Band Invitation Webhook message: ' + json.dumps(message)) 

    async def handle_problem_report(self, message):
        thread_id = message["thread_id"]
        push_resource(thread_id, "problem-report-msg", message)
        log_msg('Received Problem Report Webhook message: ' + json.dumps(message)) 

    async def make_agent_POST_request(
        self, op, rec_id=None, data=None, text=False, params=None
    ) -> (int, str):
        print("make_agent_POST_request:", op)

        if op["topic"] == "connection":
            operation = op["operation"]
            if operation == "receive-invitation":
                self.connection_state = "invited"
                print("=================================================================")

                message_bytes = json.dumps(data).encode('ascii')
                base64_bytes = base64.b64encode(message_bytes)
                base64_message = base64_bytes.decode('ascii')
                invitation_url = data["serviceEndpoint"] + "?c_i=" + base64_message

                qr = QRCode(border=1)
                qr.add_data(invitation_url)
                log_msg(
                    "Use the following JSON to accept the invite from another demo agent."
                    " Or use the QR code to connect from a mobile agent."
                )
                log_msg(
                    json.dumps(data), label="Invitation Data:", color=None
                )
                qr.print_ascii(invert=True)
                log_msg(
                    "If you can't scan the QR code here is the url."
                )
                print("Invitation url:", invitation_url)
                print("=================================================================")

                return (200, '{"result": "ok", "connection_id": "1", "state": "' + self.connection_state + '"}')

            elif (operation == "accept-invitation" 
                or operation == "accept-request"
                or operation == "remove"
                or operation == "start-introduction"
                or operation == "send-ping"
            ):
                self.connection_state = "requested"
                return (200, '{"result": "ok", "connection_id": "1", "state": "' + self.connection_state + '"}')

        elif op["topic"] == "issue-credential":
            operation = op["operation"]
            if operation == "send-request":
                print("=================================================================")
                print("Please respond to the Credential Offer!")
                print("=================================================================")
                return (200, '{"result": "ok", "thread_id": "1", "state": "request-sent"}')
            elif operation == "store":
                return (200, '{"result": "ok", "thread_id": "1", "credential_id": "' + rec_id + '", "state": "done"}')
            else:
                return (200, '{"result": "ok", "thread_id": "1", "state": "N/A"}')

        elif op["topic"] == "proof":
            operation = op["operation"]
            if operation == "send-presentation":
                print("=================================================================")
                print("Please respond to the Proof Request!")
                print("=================================================================")
                return (200, '{"result": "ok", "thread_id": "1", "state": "presentation-sent"}')
            else:
                return (200, '{"result": "ok", "thread_id": "1", "state": "N/A"}')

        return (501, '501: Not Implemented\n\n'.encode('utf8'))


    async def make_agent_GET_request(
        self, op, rec_id=None, text=False, params=None
    ) -> (int, str):
        print("make_agent_GET_request:", op)
        if op["topic"] == "status":
            status = 200 if self.ACTIVE else 418
            status_msg = "Active" if self.ACTIVE else "Inactive"
            return (status, json.dumps({"status": status_msg}))

        elif op["topic"] == "connection":
            return (200, '{"result": "ok", "connection_id": "1", "state": "N/A"}')

        elif op["topic"] == "issue-credential":
            return (200, '{"result": "ok", "credential_id": "' + rec_id + '", "state": "N/A"}')

        elif op["topic"] == "credential":
            return (200, '{"result": "ok", "credential_id": "' + rec_id + '", "state": "N/A"}')

        elif op["topic"] == "proof":
            return (200, '{"result": "ok", "thread_id": "' + rec_id + '", "state": "N/A"}')

        if op["topic"] == "version":
            return (200, '{"result": "ok"}')

        return (501, '501: Not Implemented\n\n'.encode('utf8'))

    async def make_agent_DELETE_request(
        self, op, rec_id=None, data=None, text=False, params=None
    ) -> (int, str):

        return (501, '501: Not Implemented\n\n'.encode('utf8'))

    async def make_agent_GET_request_response(
        self, topic, rec_id=None, text=False, params=None
    ) -> (int, str):
        if topic == "connection" and rec_id:
            connection_msg = pop_resource(rec_id, "connection-msg")
            i = 0
            while connection_msg is None and i < MAX_TIMEOUT:
                sleep(1)
                connection_msg = pop_resource(rec_id, "connection-msg")
                i = i + 1

            resp_status = 200
            if connection_msg:
                resp_text = json.dumps(connection_msg)
            else:
                resp_text = "{}"

            return (resp_status, resp_text)

        return (501, '501: Not Implemented\n\n'.encode('utf8'))

    def map_test_json_to_admin_api_json(self, topic, operation, data):
        # If the translation of the json get complicated in the future we might want to consider a switch to JsonMapper or equivalent.
        #json_mapper = JsonMapper()
        # map_specification = {
        #     'name': ['person_name']
        # }
        #JsonMapper(test_json).map(map_specification)

        if topic == "proof":

            if operation == "send-request" or operation == "create-request":
                if operation == "send-proposal":
                    request_type = "presentation_proposal"
                    attachment = "presentations~attach"
                else:
                    request_type = "proof_request"
                    attachment = "request_presentations~attach"
                
                if data.get("presentation_proposal", {}).get(attachment, {}).get("data", {}).get("requested_attributes") is None:
                    requested_attributes = {}
                else:
                    requested_attributes = data["presentation_proposal"][attachment]["data"]["requested_attributes"]

                if data.get("presentation_proposal", {}).get(attachment, {}).get("data", {}).get("requested_predicates") is None:
                    requested_predicates = {}
                else:
                    requested_predicates = data["presentation_proposal"][attachment]["data"]["requested_predicates"]

                if data.get("presentation_proposal", {}).get(attachment, {}).get("data", {}).get("name") is None:
                    proof_request_name = "test proof"
                else:
                    proof_request_name = data["presentation_proposal"][attachment]["data"]["name"]

                if data.get("presentation_proposal", {}).get(attachment, {}).get("data", {}).get("version") is None:
                    proof_request_version = "1.0"
                else:
                    proof_request_version = data["presentation_proposal"][attachment]["data"]["version"]

                if data.get("presentation_proposal", {}).get(attachment, {}).get("data", {}).get("non_revoked") is None:
                    non_revoked = None
                else:
                    non_revoked = data["presentation_proposal"][attachment]["data"]["non_revoked"]
                
                if "connection_id" in data:
                    admin_data = {
                        "comment": data["presentation_proposal"]["comment"],
                        "trace": False,
                        "connection_id": data["connection_id"],
                        request_type: {
                            "name": proof_request_name,
                            "version": proof_request_version,
                            "requested_attributes": requested_attributes,
                            "requested_predicates": requested_predicates
                        }
                    }
                else:
                    admin_data = {
                        "comment": data["presentation_proposal"]["comment"],
                        "trace": False,
                        request_type: {
                            "name": proof_request_name,
                            "version": proof_request_version,
                            "requested_attributes": requested_attributes,
                            "requested_predicates": requested_predicates
                        }
                    }
                if non_revoked is not None:
                    admin_data[request_type]["non_revoked"] = non_revoked

            # Make special provisions for proposal. The names are changed in this operation. Should be consistent imo.
            # this whole condition can be removed for V2.0 of the protocol. It will look like more of a send-request in 2.0.
            elif operation == "send-proposal":

                request_type = "presentation_proposal"
                
                if data.get("presentation_proposal", {}).get("requested_attributes") == None:
                    requested_attributes = []
                else:
                    requested_attributes = data["presentation_proposal"]["requested_attributes"]

                if data.get("presentation_proposal", {}).get("requested_predicates") == None:
                    requested_predicates = []
                else:
                    requested_predicates = data["presentation_proposal"]["requested_predicates"]
                
                admin_data = {
                        "comment": data["presentation_proposal"]["comment"],
                        "trace": False,
                        request_type: {
                            "@type": data["presentation_proposal"]["@type"],
                            "attributes": requested_attributes,
                            "predicates": requested_predicates
                        }
                    }

                if "connection_id" in data:
                    admin_data["connection_id"] = data["connection_id"]

            elif operation == "send-presentation":
                
                if data.get("requested_attributes") == None:
                    requested_attributes = {}
                else:
                    requested_attributes = data["requested_attributes"]

                if data.get("requested_predicates") == None:
                    requested_predicates = {}
                else:
                    requested_predicates = data["requested_predicates"]

                if data.get("self_attested_attributes") == None:
                    self_attested_attributes = {}
                else:
                    self_attested_attributes = data["self_attested_attributes"]

                admin_data = {
                    "comment": data["comment"],
                    "requested_attributes": requested_attributes,
                    "requested_predicates": requested_predicates,
                    "self_attested_attributes": self_attested_attributes
                }

            else:
                admin_data = data

            # Add on the service decorator if it exists.
            if "~service" in data: 
                admin_data["~service"] = data["~service"]

            return (admin_data)

    def agent_state_translation(self, topic, operation, data):
            # This method is used to translate the agent states passes back in the responses of operations into the states the 
            # test harness expects. The test harness expects states to be as they are written in the Protocol's RFC.
            # the following is what the tests/rfc expect vs what aca-py communicates
            # Connection Protocol:
            # Tests/RFC         |   Aca-py
            # invited           |   invitation
            # requested         |   request
            # responded         |   response
            # complete          |   active
            #
            # Issue Credential Protocol:
            # Tests/RFC         |   Aca-py
            # proposal-sent     |   proposal_sent
            # proposal-received |   proposal_received
            # offer-sent        |   offer_sent
            # offer_received    |   offer_received
            # request-sent      |   request_sent
            # request-received  |   request_received
            # credential-issued |   issued
            # credential-received | credential_received
            # done              |   credential_acked
            #
            # Present Proof Protocol:
            # Tests/RFC         |   Aca-py

            resp_json = json.loads(data)
            # Check to see if state is in the json
            if "state" in resp_json:
                agent_state = resp_json["state"]

                # if "did_exchange" in topic:
                #     if "rfc23_state" in resp_json:
                #         rfc_state = resp_json["rfc23_state"]
                #     else:
                #         rfc_state = resp_json["connection"]["rfc23_state"]
                #     data = data.replace('"state"' + ": " + '"' + agent_state + '"', '"state"' + ": " + '"' + rfc_state + '"')
                # else:
                # Check the thier_role property in the data and set the calling method to swap states to the correct role for DID Exchange
                if "their_role" in data:
                    #if resp_json["connection"]["their_role"] == "invitee":
                    if "invitee" in data:
                        de_state_trans_method = self.didExchangeResponderStateTranslationDict
                    elif "inviter" in data:
                        de_state_trans_method = self.didExchangeRequesterStateTranslationDict
                else:
                    # make the trans method any one, since it doesn't matter. It's probably Out of Band.
                    de_state_trans_method = self.didExchangeResponderStateTranslationDict

                if topic == "connection":
                    # if the response contains invitation id, swap out the connection states for the did exchange states
                    if "invitation_msg_id" in data:
                        data = data.replace('"state"' + ": " + '"' + agent_state + '"', '"state"' + ": " + '"' + de_state_trans_method[agent_state] + '"')
                    else:
                        data = data.replace(agent_state, self.connectionStateTranslationDict[agent_state])
                elif topic == "issue-credential":
                    data = data.replace(agent_state, self.issueCredentialStateTranslationDict[agent_state])
                elif topic == "proof":
                    data = data.replace('"state"' + ": " + '"' + agent_state + '"', '"state"' + ": " + '"' + self.presentProofStateTranslationDict[agent_state] + '"')
                elif topic == "out-of-band":
                    data = data.replace('"state"' + ": " + '"' + agent_state + '"', '"state"' + ": " + '"' + de_state_trans_method[agent_state] + '"')
                elif topic == "did-exchange":
                    data = data.replace('"state"' + ": " + '"' + agent_state + '"', '"state"' + ": " + '"' + de_state_trans_method[agent_state] + '"')
            return (data)

    async def get_agent_operation_acapy_version_based(self, topic, operation, rec_id=None, data=None):
        # Admin api calls may change with acapy releases. For example revocation related calls change
        # between 0.5.4 and 0.5.5. To be able to handle this the backchannel is made aware of the acapy version
        # and constructs the calls based off that version

        # construct some number to compare to with > or < instead of listing out the version number
        comparibleVersion = self.get_acapy_version_as_float()

        if (topic == "revocation"):
            if operation == "revoke":
                if comparibleVersion > 54:
                    agent_operation = "/revocation/" + operation
                    if "cred_ex_id" in data:
                        admindata = {
                            "cred_ex_ed": data["cred_ex_id"],
                        }
                    else:
                        admindata = {
                            "cred_rev_id": data["cred_rev_id"],
                            "rev_reg_id": data["rev_registry_id"],
                            "publish": str(data["publish_immediately"]).lower(),
                        }
                    data = admindata
                else:
                    agent_operation = "/issue-credential/" + operation

                    if (data is not None): # Data should be included with 0.5.4 or lower acapy. Then it takes them as inline parameters.
                        cred_rev_id = data["cred_rev_id"]
                        rev_reg_id = data["rev_registry_id"]
                        publish = data["publish_immediately"]
                        agent_operation = agent_operation + "?cred_rev_id=" + cred_rev_id + "&rev_reg_id=" + rev_reg_id + "&publish=" + rev_reg_id + str(publish).lower()
                        data = None
            elif operation == "credential-record":
                    agent_operation = "/revocation/" + operation
                    if "cred_ex_id" in data:
                        cred_ex_id = data["cred_ex_id"]
                        agent_operation = agent_operation + "?cred_ex_id=" + cred_ex_id
                    else:
                        cred_rev_id = data["cred_rev_id"]
                        rev_reg_id = data["rev_registry_id"]
                        agent_operation = agent_operation + "?cred_rev_id=" + cred_rev_id + "&rev_reg_id=" + rev_reg_id
                        data = None
        #elif (topic == "credential"):


        return agent_operation, data

async def main(start_port: int, show_timing: bool = False, interactive: bool = True):

    genesis = None

    agent = None
    try:
        print("Starting mobile backchannel ...")
        agent = MobileAgentBackchannel(
            "mobile", start_port+1, start_port+2, genesis_data=genesis
        )

        # start backchannel (common across all types of agents)
        await agent.listen_backchannel(start_port)

        agent.activate()

        # now wait ...
        if interactive:
            async for option in prompt_loop(
                "(X) Exit? [X] "
            ):
                if option is None or option in "xX":
                    break
        else:
            print("Press Ctrl-C to exit ...")
            remaining_tasks = asyncio.Task.all_tasks()
            await asyncio.gather(*remaining_tasks)

    finally:
        terminated = True
        try:
            if agent:
                await agent.terminate()
        except Exception:
            LOGGER.exception("Error terminating agent:")
            terminated = False

    await asyncio.sleep(0.1)

    if not terminated:
        os._exit(1)

def str2bool(v):
    if isinstance(v, bool):
       return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Runs a Faber demo agent.")
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8020,
        metavar=("<port>"),
        help="Choose the starting port number to listen on",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        type=str2bool,
        default=True,
        metavar=("<interactive>"),
        help="Start agent interactively",
    )
    args = parser.parse_args()

    try:
        asyncio.get_event_loop().run_until_complete(main(start_port=args.port, interactive=args.interactive))
    except KeyboardInterrupt:
        os._exit(1)
