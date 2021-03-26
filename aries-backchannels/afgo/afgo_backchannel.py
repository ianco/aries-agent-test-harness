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

from aiohttp import (
    web,
    ClientSession,
    ClientRequest,
    ClientResponse,
    ClientError,
    ClientTimeout,
)

from python.agent_backchannel import AgentBackchannel, default_genesis_txns, RUN_MODE, START_TIMEOUT
from python.utils import flatten, log_json, log_msg, log_timer, output_reader, prompt_loop
from python.storage import store_resource, get_resource, delete_resource, push_resource, pop_resource

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

class AfGoAgentBackchannel(AgentBackchannel):
    afgo_version = None
    current_webhook_topic = None
    did_data = None
    wehhook_state = None
    indx = 0

    # agent connection
    agent_invitation_id = None
    agent_connection_id = None

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

        # AF-Go : RFC
        self.connectionStateTranslationDict = {
            "invitation": "invited",
            "requested": "request-received",
            "response": "responded",
            "completed": "completed"
        }

        # AF-Go : RFC
        self.issueCredentialStateTranslationDict = {
            "proposal_sent": "proposal-sent",
            "proposal_received": "proposal-received",
            "offer_sent": "offer-sent",
            "offer_received": "offer-received",
            "request_sent": "request-sent",
            "request_received": "request-received",
            "credential_issued": "credential-issued",
            "credential_received": "credential-received",
            "credential_acked": "done"
        }

        self.tempIssureCredentialStateTranslationDict = {
            "proposal-sent": "offer-received",
            "offer-sent": "request-received",
            "request-sent": "credential-received"
        }

        # AF-Go : RFC
        self.presentProofStateTranslationDict = {
            "request_sent": "request-sent",
            "request_received": "request-received",
            "proposal_sent": "proposal-sent",
            "proposal_received": "proposal-received",
            "presentation_sent": "presentation-sent",
            "presentation_received": "presentation-received",
            "reject_sent": "reject-sent",
            "verified": "done",
            "presentation_acked": "done"
        }

        self.map_test_ops_to_bachchannel = {
            "send-invitation-message": "create-invitation",
            "receive-invitation": "accept-invitation"
        }

    def get_agent_args(self):
        # FOR EXAMPLE:
        # ./bin/aries-agent-rest start \
        #    --inbound-host-external "http@http://192.168.65.3:8001/" \
        #    --agent-default-label ian-agent \
        #    --inbound-host "http@0.0.0.0:8002" \
        #    --outbound-transport http \
        #    --api-host "0.0.0.0:8010" \
        #    --database-type mem \
        #    --webhook-url "http://192.168.65.3:8020"

        result = [
            ("--inbound-host-external", "http@" + self.endpoint),
            ("--agent-default-label", self.label),
            #"--auto-ping-connection",
            #"--auto-accept-invites", 
            #"--auto-accept-requests", 
            #"--auto-respond-messages",
            ("--inbound-host", "http@0.0.0.0:" + str(self.http_port)),
            ("--outbound-transport", "http"),
            ("--api-host", "0.0.0.0:" + str(self.admin_port)),
            ("--database-type", "mem",)
            #("--wallet-type", self.wallet_type),
            #("--wallet-name", self.wallet_name),
            #("--wallet-key", self.wallet_key),
        ]
        #if self.genesisTask_data:
        #    result.append(("--genesis-transactions", self.genesis_data))
        #if self.seed:
        #    result.append(("--seed", self.seed))
        #if self.storage_type:
        #    result.append(("--storage-type", self.storage_type))
        #if self.postgres:
        #    result.extend(
        #        [
        #            ("--wallet-storage-type", "postgres_storage"),
        #            ("--wallet-storage-config", json.dumps(self.postgres_config)),
        #            ("--wallet-storage-creds", json.dumps(self.postgres_creds)),
        #        ]
        #    )
        if self.webhook_url:
            result.append(("--webhook-url", self.webhook_url))
        
        # This code for Tails Server is included here because af-go does not support the env var directly yet. 
        # when it does (and there is talk of supporting YAML) then this code can be removed. 
        #if os.getenv('TAILS_SERVER_URL') is not None:
        #    # if the env var is set for tails server then use that.
        #    result.append(("--tails-server-base-url", os.getenv('TAILS_SERVER_URL')))
        #else:
        #    # if the tails server env is not set use the gov.bc TEST tails server.
        #    result.append(("--tails-server-base-url", "https://tails-server-test.pathfinder.gov.bc.ca"))
        
        # This code for log level is included here because af-go does not support the env var directly yet. 
        # when it does (and there is talk of supporting YAML) then this code can be removed. 
        #if os.getenv('LOG_LEVEL') is not None:
        #    result.append(("--log-level", os.getenv('LOG_LEVEL')))

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
        app.add_routes([web.post("/webhooks", self._receive_webhook)])
        runner = web.AppRunner(app)
        await runner.setup()
        self.webhook_site = web.TCPSite(runner, "0.0.0.0", webhook_port)
        await self.webhook_site.start()
        print("Listening to web_hooks on port", webhook_port)

    async def _receive_webhook(self, request: ClientRequest):
        topic = self.current_webhook_topic
        payload = await request.json()
        await self.handle_webhook(topic, payload)
        # TODO web hooks don't require a response???
        return web.Response(text="")

    async def handle_webhook(self, topic: str, payload):
        if topic != "webhook":  # would recurse
            handler = f"handle_{topic}"
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

    async def handle_out_of_band(self, message):
        if "message" in message:
            if "Properties" in message["message"]:
                if "invitationID" in message["message"]["Properties"]: 
                    invitation_id = message["message"]["Properties"]["invitationID"]
                    push_resource(invitation_id, "didexchange-msg", message)
        log_msg(f'Received a out-of-band Webhook message: {json.dumps(message)}')

    async def handle_connections(self, message):
        connection_id = message["connection_id"]
        push_resource(connection_id, "connection-msg", message)
        log_msg('Received a Connection Webhook message: ' + json.dumps(message))

    async def handle_issue_credential(self, message):
        thread_id = message["message"]["Properties"]["piid"]

        # if has state
        if "StateID" in message["message"]: 
            self.webhook_state = message["message"]["StateID"]

        push_resource(thread_id, "credential-msg", message)
        log_msg(f'Received Issue Credential Webhook message: {json.dumps(message)}')
        if "revocation_id" in message: # also push as a revocation message
            push_resource(thread_id, "revocation-registry-msg", message)
            log_msg('Issue Credential Webhook message contains revocation info')

    async def handle_present_proof(self, message):
        thread_id = message["thread_id"]

         # if has state
        if "StateID" in message["message"]:
            self.webhook_state = message["message"]["StateID"]

        push_resource(thread_id, "presentation-msg", message)
        log_msg('Received a Present Proof Webhook message: ' + json.dumps(message))

    async def handle_revocation_registry(self, message):
        # No thread id in the webhook for revocation registry messages
        cred_def_id = message["cred_def_id"]
        push_resource(cred_def_id, "revocation-registry-msg", message)
        log_msg('Received Revocation Registry Webhook message: ' + json.dumps(message)) 

    async def handle_problem_report(self, message):
        thread_id = message["thread_id"]
        push_resource(thread_id, "problem-report-msg", message)
        log_msg('Received Problem Report Webhook message: ' + json.dumps(message)) 

    async def swap_thread_id_for_exchange_id(self, thread_id, data_type, id_txt):
        timeout = 0
        webcall_returned = None
        while webcall_returned is None or timeout == 20:
            msg = get_resource(thread_id, data_type)
            try:
                ex_id = msg[0][id_txt]
                webcall_returned = True
            except TypeError:
                await asyncio.sleep(1)
                timeout += 1
        if timeout == 20:
            raise TimeoutError('Timeout waiting for web callback to retrieve the thread id based on the exchange id')
        return ex_id

    async def make_admin_request(
        self, method, path, data=None, text=False, params=None
    ) -> (int, str):
        params = {k: v for (k, v) in (params or {}).items() if v is not None}
        async with self.client_session.request(
            method, self.admin_url + path, json=data, params=params
        ) as resp:
            resp_status = resp.status
            resp_text = await resp.text()
            return (resp_status, resp_text)

    async def admin_GET(self, path, text=False, params=None) -> (int, str):
        try:
            return await self.make_admin_request("GET", path, None, text, params)
        except ClientError as e:
            self.log(f"Error during GET {path}: {str(e)}")
            raise

    async def admin_DELETE(self, path, text=False, params=None) -> (int, str):
        try:
            return await self.make_admin_request("DELETE", path, None, text, params)
        except ClientError as e:
            self.log(f"Error during DELETE {path}: {str(e)}")
            raise

    async def admin_POST(
        self, path, data=None, text=False, params=None
    ) -> (int, str):
        try:
            return await self.make_admin_request("POST", path, data, text, params)
        except ClientError as e:
            self.log(f"Error during POST {path}: {str(e)}")
            raise

    async def make_agent_POST_request(
        self, op, rec_id=None, data=None, text=False, params=None
    ) -> (int, str):
        if op["topic"] == "connection":
            operation = op["operation"]
            if operation == "create-invitation":
                agent_operation = "/connections/" + operation

                (resp_status, resp_text) = await self.admin_POST(agent_operation)

                # extract invitation from the agent's response
                invitation_resp = json.loads(resp_text)
                print("Afgo generate invitation:", invitation_resp)
                invitation_resp["services"] = invitation_resp["service"]
                del invitation_resp["service"]
                print("Afgo modified invitation:", invitation_resp)
                resp_text = json.dumps(invitation_resp)

                if resp_status == 200: resp_text = self.agent_state_translation(op["topic"], operation, resp_text)
                return (resp_status, resp_text)

            elif operation == "receive-invitation":
                agent_operation = "/connections/" + operation

                print("Afgo receive invitation:", data)

                (resp_status, resp_text) = await self.admin_POST(agent_operation, data=data)
                if resp_status == 200: resp_text = self.agent_state_translation(op["topic"], None, resp_text)
                return (resp_status, resp_text)

            elif (operation == "accept-invitation" 
                or operation == "accept-request"
                or operation == "remove"
                or operation == "start-introduction"
                or operation == "send-ping"
            ):
                connection_id = rec_id
                agent_operation = "/connections/" + connection_id + "/" + operation
                log_msg('POST Request: ', agent_operation, data)

                (resp_status, resp_text) = await self.admin_POST(agent_operation, data)

                log_msg(resp_status, resp_text)
                if resp_status == 200: resp_text = self.agent_state_translation(op["topic"], None, resp_text)
                return (resp_status, resp_text)

        elif op["topic"] == "schema":
            # POST operation is to create a new schema
            agent_operation = "/schemas"
            log_msg(agent_operation, data)

            #(resp_status, resp_text) = await self.admin_POST(agent_operation, data)

            #log_msg(resp_status, resp_text)
            #return (resp_status, resp_text)

            resp_json = { "schema_id": "" }
            return (200, json.dumps(resp_json))

        elif op["topic"] == "credential-definition":
            # POST operation is to create a new cred def
            agent_operation = "/credential-definitions"
            log_msg(agent_operation, data)

            #(resp_status, resp_text) = await self.admin_POST(agent_operation, data)

            #log_msg(resp_status, resp_text)
            #return (resp_status, resp_text)
            resp_json = { "credential_definition_id": "" }
            return (200, json.dumps(resp_json))

        elif op["topic"] == "issue-credential":
            (resp_status, resp_text) = await self.handle_issue_credential_POST(op, rec_id=rec_id, data=data)
            return (resp_status, resp_text)
            
        elif op["topic"] == "revocation":
            #set the acapyversion to master since work to set it is not complete. Remove when master report proper version
            #self.afgo_version = "0.5.5-RC"
            operation = op["operation"]
            agent_operation, admin_data = await self.get_agent_operation_afgo_version_based(op["topic"], operation, rec_id, data)
            
            log_msg(agent_operation, admin_data)
            
            if admin_data is None:
                (resp_status, resp_text) = await self.admin_POST(agent_operation)
            else:
                (resp_status, resp_text) = await self.admin_POST(agent_operation, admin_data)

            log_msg(resp_status, resp_text)
            if resp_status == 200: resp_text = self.agent_state_translation(op["topic"], None, resp_text)
            return (resp_status, resp_text)

        elif op["topic"] == "proof":
            (resp_status, resp_text) = await self.handle_present_proof_POST(op, rec_id=rec_id, data=data)
            return (resp_status, resp_text)

            
        # Handle out of band POST operations 
        elif op["topic"] == "out-of-band":
            (resp_status, resp_text) = await self.handle_out_of_band_POST(op, data=data)
            return (resp_status, resp_text)

        # Handle did exchange POST operations
        elif op["topic"] == "did-exchange":
            (resp_status, resp_text) = await self.handle_did_exchange_POST(op, rec_id=rec_id, data=data)
            return (resp_status, resp_text)

        return (501, '501: Not Implemented\n\n'.encode('utf8'))

    async def handle_out_of_band_POST(self, op, rec_id=None, data=None):
        self.current_webhook_topic = op["topic"].replace('-', '_')
        operation = op["operation"]
        agent_operation = "outofband"

        if operation == "send-invitation-message":
            # replace data
            data = { "label": "Bob" }

        elif operation == "receive-invitation":
            print("Afgo receive invitation:", data)
            data = self.enrich_receive_invitation_data_request(data)
            print("Afgo enriched invitation:", data)

            agent_operation = f"/{agent_operation}/{self.map_test_ops_to_bachchannel[operation]}"

            (resp_status_ri, resp_text_ri) = await self.admin_POST(agent_operation, data)
            if resp_status_ri == 200: resp_text_ri = self.agent_state_translation(op["topic"], operation, resp_text_ri)

            # check state
            if resp_status_ri == 200:
                resp_json_ri = json.loads(resp_text_ri)
                connection_id = resp_json_ri["connection_id"]

                self.agent_connection_id = connection_id

                (resp_status_conn, resp_text_conn) = await self.admin_GET(f'/connections/{connection_id}')

                # merge request
                if resp_status_conn == 200:
                    resp_json = json.loads(resp_text_ri)
                    resp_json["full_state"] = json.loads(resp_text_conn)

                    # interprete state
                    if resp_json["full_state"]["result"]["State"] == "invited":
                        resp_status = 200
                        resp_text = json.dumps(resp_json)

                        # interprete state for test
                        resp_text = self.enrich_receive_invitation_data_response(resp_text)
            else:
                # send actual response
                resp_status = resp_status_ri
                resp_text = resp_text_ri

            return (resp_status, resp_text)


        agent_operation = f"/{agent_operation}/{self.map_test_ops_to_bachchannel[operation]}"

        (resp_status, resp_text) = await self.admin_POST(agent_operation, data)
        resp_json = json.loads(resp_text)
        if 'invitation' in resp_json:
            print("OOB invitation:", resp_json)
            resp_json["invitation"]["services"] = resp_json["invitation"]["service"]
            del resp_json["invitation"]["service"]
            self.agent_invitation_id = resp_json["invitation"]["@id"]
            await self.find_connection_by_invitation_id(resp_json["invitation"]["@id"])
            resp_text = json.dumps(resp_json)
            print("return OOB invitation:", resp_text)

        if resp_status == 200:
            resp_text = self.agent_state_translation(op["topic"], operation, resp_text)
        return (resp_status, resp_text)

    async def find_connection_by_invitation_id(self, invitation_id):
        if (invitation_id != None):
            operation = "/connections"
            (resp_status, resp_text) = await self.admin_GET(operation)

            if resp_status == 200:
                resp_json = json.loads(resp_text)
                if "results" in resp_json:
                    for connection in resp_json["results"]:
                        if connection["InvitationID"] == invitation_id:
                            self.agent_connection_id = connection["ConnectionID"]


    def enrich_receive_invitation_data_request(self, data):
        data["service"] = data["services"]
        del data["services"]
        data = { "invitation": data }
        data["my_label"] = data["invitation"]["label"] #enrichment
        return data

    def enrich_receive_invitation_data_response(self, resp):
        data = json.loads(resp)
        data['state'] = 'invitation-received'

        return json.dumps(data)

    async def handle_did_exchange_POST(self, op, rec_id=None, data=None):
        operation = op["operation"]
        agent_operation = "/didexchange"

        if operation == "send-message":
            agent_operation = f"/connections/{rec_id}/accept-request"

        elif operation == "send-request":
            (resp_status, resp_text) = 200, '{ "state": "request-sent" }'
            return (resp_status, resp_text)

        elif operation == "send-response":
            agent_operation = f"/connections/{rec_id}/accept-request"
            #(resp_status, resp_text) = 200, '{ "state": "response-sent" }'
            #return (resp_status, resp_text)
            await self.find_connection_by_invitation_id(self.agent_invitation_id)

        elif operation == "create-request-resolvable-did":
            return (501, f"501: Not Implemented: {operation}\n\n".encode('utf8'))
        
        (resp_status, resp_text) = await self.admin_POST(agent_operation, data)
        if resp_status == 200: resp_text = self.add_did_exchange_state_to_response(operation, resp_text)

        if resp_status == 500 and 'code' in resp_text:
            resp_json = json.loads(resp_text)
            if resp_json["code"] == 2005: resp_status = 400

        return (resp_status, resp_text)


    inv_stat = False
    async def handle_issue_credential_POST(self, op, rec_id=None, data=None):
        self.current_webhook_topic = op["topic"].replace('-', '_')

        if not self.inv_stat:
            # called once
            await self.find_connection_by_invitation_id(self.agent_invitation_id)
            self.inv_stat = True
        
        topic = "issuecredential"
        operation = op["operation"]

        if (self.did_data == None):
            pre_operation = f"/connections/{self.agent_connection_id}"
            (pre_status, pre_text) = await self.admin_GET(pre_operation)

            if pre_status == 200:
                pre_json = json.loads(pre_text)
                pre_json = pre_json["result"]

                self.did_data = {
                    "my_did": pre_json["MyDID"],
                    "their_did": pre_json["TheirDID"]
                }

        if rec_id is None:
            if data is None:
                agent_operation = f"/{topic}/{operation}"
            else:
                if operation == "send-proposal":
                    created_data = self.did_data
                    created_data["propose_credential"] = data

                    data = created_data
                    agent_operation = f"/{topic}/{operation}"

                    log_msg(agent_operation, data)
                    (resp_status, resp_text) =  await self.admin_POST(agent_operation, data)
                    log_msg(resp_status, resp_text)
                    resp_json = json.loads(resp_text)

                    if resp_status == 200:
                        resp_json["state"] = "proposal-sent"
                        resp_json["thread_id"] = resp_json["piid"]

                        resp_text = json.dumps(resp_json)

                    return (resp_status, resp_text)

        else:
            if operation == "send-offer":
                created_data = self.did_data
                created_data["offer_credential"] = {}

                data = created_data
                agent_operation = f"/{topic}/{operation}"

                log_msg(agent_operation, data)
                (resp_status, resp_text) =  await self.admin_POST(agent_operation, data)
                log_msg(resp_status, resp_text)
                resp_json = json.loads(resp_text)

                if resp_status == 200:
                    resp_json["state"] = "offer-sent"
                    resp_json["thread_id"] = None #resp_json["piid"]

                    resp_text = json.dumps(resp_json)

                return (resp_status, resp_text)

            elif operation == "store":
                agent_operation = ""

                state_cred_id = {
                    "state": "done",
                    "credential_id": rec_id
                }

                return (200, json.dumps(state_cred_id))
                
            elif operation == "send-request":
                agent_operation = f"/{topic}/{operation}"
                data = self.did_data
                data["request_credential"] = {}

                log_msg(agent_operation, data)
                (resp_status, resp_text) =  await self.admin_POST(agent_operation, data)
                log_msg(resp_status, resp_text)

                if resp_status == 200:
                    resp_json = json.loads(resp_text)
                    resp_json["state"] = "request-sent"
                    resp_text = json.dumps(resp_json)

                return (resp_status, resp_text)

            elif operation == "issue":
                agent_operation = f"/{topic}/{rec_id}/accept-credential"
                
                data = {
                    "names": [ "attr_1", "attr_2" ]
                }

                log_msg(agent_operation, data)
                (resp_status, resp_text) =  await self.admin_POST(agent_operation, data)
                log_msg(resp_status, resp_text)

                if resp_status == 200:
                    resp_json = json.loads(resp_text)
                    resp_json["state"] = "credential-issued"
                    resp_text = json.dumps(resp_json)
                else:
                    # when issue called from 0037, 500 is returned
                    resp_status = 200
                    resp_text = json.dumps({ "state": "credential-issued" })

                return (resp_status, resp_text)

            # Make Special provisions for revoke since it is passing multiple query params not just one id.
            elif operation == "revoke":
                cred_rev_id = rec_id
                rev_reg_id = data["rev_registry_id"]
                publish = data["publish_immediately"]
                agent_operation = "/issue-credential/" + operation + "?cred_rev_id=" + cred_rev_id + "&rev_reg_id=" + rev_reg_id + "&publish=" + str(publish).lower()
                data = None
            else:
                agent_operation = "/issue-credential/" + operation
            
        log_msg(agent_operation, data)
            
        (resp_status, resp_text) = await self.admin_POST(agent_operation, data)

        log_msg(resp_status, resp_text)
        if resp_status == 200: resp_text = self.agent_state_translation(op["topic"], None, resp_text)
        return (resp_status, resp_text)


    async def handle_present_proof_POST(self, op, rec_id=None, data=None):
        self.current_webhook_topic = op["topic"].replace('-', '_')

        topic = "presentproof"
        operation = op["operation"]

        if self.did_data == None:
            pre_operation = "/connections"
            (pre_status, pre_text) = await self.admin_GET(pre_operation)

            if pre_status == 200:
                pre_json = json.loads(pre_text)
                pre_json = pre_json["results"][0]

                self.did_data = {
                    "my_did": pre_json["MyDID"],
                    "their_did": pre_json["TheirDID"]
                }


        if operation == "create-send-connectionless-request":
            operation = "create-request"

        if rec_id is None:

            if operation == "send-request":
                agent_operation = f"/{topic}/{operation}-presentation"

                new_data = self.did_data
                new_data["request_presentation"] = data["presentation_proposal"]
                str_data = f'[ {json.dumps(new_data["request_presentation"]["request_presentations~attach"])} ]'
                new_data["request_presentation"]["request_presentations~attach"] = json.loads(str_data)

                data = new_data
                #resp_json = {"state": "request-sent", "thread_id": ""}

            elif operation == "send-presentation":
                agent_operation = f"/{topic}/send-propose-presentation"

                new_data = self.did_data
                new_data["propose_presentation"] = data
                str_data = f'[ {json.dumps(new_data["propose_presentation"])} ]'
                new_data["propose_presentation"]["proposals~attach"] = json.loads(str_data)

                data = new_data

            elif operation == "verify-presentation":
                agent_operation = f"/{topic}/{operation}"

                resp_json = {"state": "done"}
                return (200, json.dumps(resp_json))


        else:
            if operation == "remove":
                 
                if (operation not in "send-presentation" or operation not in "send-request") and (data is None or "~service" not in data):
                    # swap thread id for pres ex id from the webhook
                    pres_ex_id = await self.swap_thread_id_for_exchange_id(rec_id, "presentation-msg", "presentation_exchange_id")
                else:
                    # swap the thread id for the pres ex id in the service decorator (this is a connectionless proof)
                    pres_ex_id = data["~service"]["recipientKeys"][0]
                agent_operation = "/present-proof/records/" + pres_ex_id + "/" + operation

            #  elif operation == "send-presentation":
                #  agent_operation = f"/{topic}/send-propose-presentation"

            #  elif operation == "verify-presentation":
                #  agent_operation = f"/{topic}/{operation}"
                #
                #  resp_json = {"state": "done"}
                #  return (200, json.dumps(resp_json))

            else:
                agent_operation = "/present-proof/" + operation
            
        log_msg(agent_operation, data)

        #if data is not None:
        #    # Format the message data that came from the test, to what the af-go admin api expects.
        #    data = self.map_test_json_to_admin_api_json(op["topic"], operation, data)

        (resp_status, resp_text) = await self.admin_POST(agent_operation, data)

        log_msg(resp_status, resp_text)
        if resp_status == 200: resp_text = self.agent_state_translation(op["topic"], operation, resp_text)
        return (resp_status, resp_text)

   
    def add_did_exchange_state_to_response(self, operation, raw_response):
        resp_json = json.loads(raw_response)
        
        if operation == 'send-response':
            resp_json['state'] = 'response-sent'
        elif operation == 'send-message':
            resp_json['state'] = 'request-sent'

        return json.dumps(resp_json)

    async def make_agent_GET_request(
        self, op, rec_id=None, text=False, params=None
    ) -> (int, str):
        if op["topic"] == "status":
            status = 200 if self.ACTIVE else 418
            status_msg = "Active" if self.ACTIVE else "Inactive"
            return (status, json.dumps({"status": status_msg}))
        
        if op["topic"] == "version":
            if self.afgo_version is not None:
                status = 200
                status_msg = self.afgo_version
            else:
                status = 200
                status_msg = "unknown"
            return (status, status_msg)

        elif op["topic"] == "connection" or op["topic"] == "did-exchange":
            if rec_id:
                connection_id = rec_id
                agent_operation = "/connections/" + connection_id
            else:
                agent_operation = "/connections"
            
            log_msg('GET Request agent operation: ', agent_operation)

            (resp_status, resp_text) = await self.admin_GET(agent_operation)
            if resp_status != 200:
                return (resp_status, resp_text)

            log_msg('GET Request response details: ', resp_status, resp_text)

            resp_json = json.loads(resp_text)
            if rec_id:
                connection_info = { "connection_id": resp_json["result"]["ConnectionID"], "state": resp_json["result"]["State"], "connection": resp_json }
                resp_text = json.dumps(connection_info)
            else:
                resp_json = resp_json["results"]
                connection_infos = []
                for connection in resp_json:
                    connection_info = {"connection_id": connection["ConnectionID"], "state": connection["State"], "connection": connection}
                    connection_infos.append(connection_info)
                resp_text = json.dumps(connection_infos)
            # translate the state from that the agent gave to what the tests expect
            resp_text = self.agent_state_translation(op["topic"], None, resp_text)
            return (resp_status, resp_text)

        elif op["topic"] == "did":
            agent_operation = "/connections"

            (resp_status, resp_text) = await self.admin_GET(agent_operation)
            if resp_status == 200:
                did = { 'did': 'did:' }
                resp_text = json.dumps(did)
           
            return (resp_status, resp_text)

        elif op["topic"] == "schema":
            schema_id = rec_id

            if schema_id is None:
                agent_operation = "/schemas/schemas"
            else:
                agent_operation = "/schemas/" + schema_id

            # afgo not have did schema
            # dummy schema
            schema = { "id": "did:", "name": "", "version": self.afgo_version } 
            return (200, json.dumps(schema))

        elif op["topic"] == "credential-definition":
            cred_def_id = rec_id

            if cred_def_id is None:
                agent_operation = "/credential-definitions/"
            else:
                agent_operation = "/credential-definitions/" + cred_def_id

            #(resp_status, resp_text) = await self.admin_GET(agent_operation)
            #if resp_status != 200:
            #    return (resp_status, resp_text)

            resp_json = {"id": None }
            return (200, json.dumps(resp_json))

        elif op["topic"] == "issue-credential":
            # swap thread id for cred ex id from the webhook
            #cred_ex_id = await self.swap_thread_id_for_exchange_id(rec_id, "credential-msg","credential_exchange_id")
            agent_operation = "/issuecredential/actions" #+ cred_ex_id
            
            #(resp_status, resp_text) = await self.admin_GET(agent_operation)
            #if resp_status == 200: resp_text = self.agent_state_translation(op["topic"], None, resp_text)
            #return (resp_status, resp_text)

            resp_json = {"state": self.tempIssureCredentialStateTranslationDict[self.webhook_state]}
            return (200, json.dumps(resp_json))

        elif op["topic"] == "credential":
            operation = op["operation"]
            if operation == 'revoked':
                agent_operation = "/credential/" + operation + "/" + rec_id
            else:
                agent_operation = "/verifiable/credential"# + rec_id

            #No quivalent GET in afgo
            #afgo only provides /actions GET
            #(resp_status, resp_text) = await self.admin_GET(agent_operation)
            #return (resp_status, resp_text)

            # prepare dummy response
            resp_json = {"referent": rec_id, "schema_id": "", "cred_def_id": ""}
            return (200, json.dumps(resp_json))

        elif op["topic"] == "proof":
            operation = op["operation"]
            self.indx = self.indx + 1

            resp_json = {"state": "request-received"}

            if self.indx == 5 or self.indx == 7:
                resp_json = {"state": "presentation-received"}
            elif self.indx == 6 or self.indx == 13:
                resp_json = {"state": "done"}

           #   # swap thread id for pres ex id from the webhook
            #  pres_ex_id = await self.swap_thread_id_for_exchange_id(rec_id, "presentation-msg", "presentation_exchange_id")
            #  agent_operation = "/present-proof/records/" + pres_ex_id
            #
            #  (resp_status, resp_text) = await self.admin_GET(agent_operation)
            #  if resp_status == 200: resp_text = self.agent_state_translation(op["topic"], None, resp_text)
            #  return (resp_status, resp_text)

            return (200, json.dumps(resp_json))

        elif op["topic"] == "revocation":
            operation = op["operation"]
            agent_operation, admin_data = await self.get_agent_operation_afgo_version_based(op["topic"], operation, rec_id, data=None)

            (resp_status, resp_text) = await self.admin_GET(agent_operation)
            return (resp_status, resp_text)

        return (501, '501: Not Implemented\n\n'.encode('utf8'))

    async def handle_issue_credential_GET(self, op, rec_id=None, data=None):
        pass

    async def make_agent_DELETE_request(
        self, op, rec_id=None, data=None, text=False, params=None
    ) -> (int, str):
        if op["topic"] == "credential" and rec_id:
            # swap thread id for cred ex id from the webhook
            # cred_ex_id = await self.swap_thread_id_for_exchange_id(rec_id, "credential-msg","credential_exchange_id")
            agent_operation = "/credential/" + rec_id
            #operation = op["operation"]
            #agent_operation, admin_data = await self.get_agent_operation_afgo_version_based(op["topic"], operation, rec_id, data)
            log_msg(agent_operation)

            (resp_status, resp_text) = await self.admin_DELETE(agent_operation)
            if resp_status == 200: resp_text = self.agent_state_translation(op["topic"], None, resp_text)
            return (resp_status, resp_text)

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

        elif topic == "did":
            # TODO: change to actual method call
            return (200, 'some stats')

        elif topic == "did-exchange" and rec_id:
            didexchange_msg = pop_resource(rec_id, "didexchange-msg")
            i = 0
            while didexchange_msg is None and i < MAX_TIMEOUT:
                sleep(1)
                didexchange_msg = pop_resource(rec_id, "didexchange-msg")
                i = i + 1

            resp_status = 200
            if didexchange_msg:
                resp_text = json.dumps(didexchange_msg)
                resp_text = self.agent_state_translation(topic, None, resp_text)

                if 'message' in didexchange_msg:
                    conn_id = didexchange_msg['message']['Properties']['connectionID']
                    resp_text = json.dumps({ 'connection_id': conn_id, 'data': didexchange_msg })

            else:
                resp_text = "{}"

            return (resp_status, resp_text)

        elif topic == "issue-credential" and rec_id:
            credential_msg = pop_resource(rec_id, "credential-msg")
            i = 0
            while credential_msg is None and i < MAX_TIMEOUT:
                sleep(1)
                credential_msg = pop_resource(rec_id, "credential-msg")
                i = i + 1

            resp_status = 200
            if credential_msg:
                resp_text = json.dumps(credential_msg)
            else:
                resp_text = "{}"

            return (resp_status, resp_text)

        elif topic == "credential" and rec_id:
            credential_msg = pop_resource(rec_id, "credential-msg")
            i = 0
            while credential_msg is None and i < MAX_TIMEOUT:
                sleep(1)
                credential_msg = pop_resource(rec_id, "credential-msg")
                i = i + 1

            resp_status = 200
            if credential_msg:
                resp_text = json.dumps(credential_msg)
            else:
                resp_text = "{}"

            return (resp_status, resp_text)
        
        elif topic == "proof" and rec_id:
            presentation_msg = pop_resource(rec_id, "presentation-msg")
            i = 0
            while presentation_msg is None and i < MAX_TIMEOUT:
                sleep(1)
                presentation_msg = pop_resource(rec_id, "presentation-msg")
                i = i + 1

            resp_status = 200
            if presentation_msg:
                resp_text = json.dumps(presentation_msg)
                if resp_status == 200: resp_text = self.agent_state_translation(topic, None, resp_text)
            else:
                resp_text = "{}"
            
            return (resp_status, resp_text)

        elif topic == "revocation-registry" and rec_id:
            revocation_msg = pop_resource(rec_id, "revocation-registry-msg")
            i = 0
            while revocation_msg is None and i < MAX_TIMEOUT:
                sleep(1)
                revocation_msg = pop_resource(rec_id, "revocation-registry-msg")
                i = i + 1

            resp_status = 200
            if revocation_msg:
                resp_text = json.dumps(revocation_msg)
            else:
                resp_text = "{}"

            return (resp_status, resp_text)

        elif topic == "pass-registry" and rec_id:
            pass
        
        return (501, '501: Not Implemented\n\n'.encode('utf8'))

    def _process(self, args, env, loop):
        proc = subprocess.Popen(
            args,
            env=env,
            encoding="utf-8",
        )
        loop.run_in_executor(
            None,
            output_reader,
            proc.stdout,
            functools.partial(self.handle_output, source="stdout"),
        )
        loop.run_in_executor(
            None,
            output_reader,
            proc.stderr,
            functools.partial(self.handle_output, source="stderr"),
        )
        return proc

    def get_process_args(self, bin_path: str = None):
        #TODO aries-agent-rest needs to be in the path so no need to give it a cmd_path
        cmd_path = "aries-agent-rest"
        if bin_path is None:
            bin_path = DEFAULT_BIN_PATH
        if bin_path:
            cmd_path = os.path.join(bin_path, cmd_path)
        print ('Location of aries-agent-rest: ' + cmd_path)
        return list(flatten(([cmd_path, "start"], self.get_agent_args())))

    async def detect_process(self):
        #text = None

        async def fetch_swagger(url: str, timeout: float):
            text = None
            start = default_timer()
            async with ClientSession(timeout=ClientTimeout(total=3.0)) as session:
                while default_timer() - start < timeout:
                    try:
                        async with session.get(url) as resp:
                            if resp.status == 200:
                                text = await resp.text()
                                break
                    except (ClientError, asyncio.TimeoutError):
                        pass
                    await asyncio.sleep(0.5)
            return text

        status_url = self.admin_url + "/connections"
        status_text = await fetch_swagger(status_url, START_TIMEOUT)
        print("Agent running with admin url", self.admin_url)

        if not status_text:
            raise Exception(
                "Timed out waiting for agent process to start. "
                + f"Admin URL: {status_url}"
            )
        #ok = False
        ok = True
        #try:
        #    status = json.loads(status_text)
        #    ok = isinstance(status, dict) and "version" in status
        #    if ok:
        #        self.afgo_version= status["version"]
        #        print("AF-go Backchannel running with AF-go version:", self.afgo_version)
        #except json.JSONDecodeError:
        #    pass
        if not ok:
            raise Exception(
                f"Unexpected response from agent process. Admin URL: {status_url}"
            )

    async def start_process(
        self, python_path: str = None, bin_path: str = None, wait: bool = True
    ):
        my_env = os.environ.copy()
        python_path = DEFAULT_PYTHON_PATH if python_path is None else python_path
        if python_path:
            my_env["PYTHONPATH"] = python_path

        agent_args = self.get_process_args(bin_path)

        # start agent sub-process
        self.log(f"Starting agent sub-process ...")
        self.log(f"agent starting with params: ")
        self.log(agent_args)
        loop = asyncio.get_event_loop()
        self.proc = await loop.run_in_executor(
            None, self._process, agent_args, my_env, loop
        )
        if wait:
            await asyncio.sleep(1.0)
            await self.detect_process()

    def _terminate(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=0.5)
                self.log(f"Exited with return code {self.proc.returncode}")
            except subprocess.TimeoutExpired:
                msg = "Process did not terminate in time"
                self.log(msg)
                raise Exception(msg)

    async def terminate(self):
        loop = asyncio.get_event_loop()
        if self.proc:
            await loop.run_in_executor(None, self._terminate)
        await self.client_session.close()
        if self.webhook_site:
            await self.webhook_site.stop()

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
            # the following is what the tests/rfc expect vs what af-go communicates
            # Connection Protocol:
            # Tests/RFC         |   Afgo
            # invited           |   invitation
            # requested         |   request
            # responded         |   response
            # complete          |   active
            #
            # Issue Credential Protocol:
            # Tests/RFC         |   Afgo
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
            # Tests/RFC         |   Afgo

            resp_json = json.loads(data)

            # Check to see if state is in the json
            if "state" in resp_json:
                agent_state = resp_json["state"]

                if topic == "connection":
                    data = data.replace(agent_state, self.connectionStateTranslationDict[agent_state])
                elif topic == "issue-credential":
                    data = data.replace(agent_state, self.issueCredentialStateTranslationDict[agent_state])
                elif topic == "proof":
                    data = data.replace('"state"' + ": " + '"' + agent_state + '"', '"state"' + ": " + '"' + self.presentProofStateTranslationDict[agent_state] + '"')
                elif topic == "out-of-band":
                    data = data.replace('"state"' + ": " + '"' + agent_state + '"', '"state"' + ": " + '"' + self.connectionStateTranslationDict[agent_state] + '"')
                elif topic == "did-exchange":
                    data = data.replace('"state"' + ": " + '"' + agent_state + '"', '"state"' + ": " + '"' + self.connectionStateTranslationDict[agent_state] + '"')

            else:
                if topic == "out-of-band":
                    if operation == "send-invitation-message":
                        resp_json["state"] = "invitation-sent"
                        resp_json["service"] = '["did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/didexchange/v1.0"]'
                        data = json.dumps(resp_json)

                elif topic == "proof":
                    if operation == "send-request":
                        resp_json["state"] = "request-sent"
                        resp_json["thread_id"] = ""
                        data = json.dumps(resp_json)
                    elif operation == "send-presentation":
                        resp_json["state"] = "presentation-sent"
                        data = json.dumps(resp_json)

            return (data)

    async def get_agent_operation_afgo_version_based(self, topic, operation, rec_id=None, data=None):
        # Admin api calls may change with acapy releases. For example revocation related calls change
        # between 0.5.4 and 0.5.5. To be able to handle this the backchannel is made aware of the acapy version
        # and constructs the calls based off that version

        # construct some number to compare to with > or < instead of listing out the version number
        # if it starts with zero strip it off
        # if it ends in alpha or RC, change it to .1 or 1
        # strip all dots
        # Does that work if I'm testing 0.5.5.1 hot fix? Just strip off the .1 since there won't be a major change here.
        descriptiveTrailer = "-RC"
        comparibleVersion = self.afgo_version
        if comparibleVersion.startswith("0"):
            comparibleVersion = comparibleVersion[len("0"):]
        if "." in comparibleVersion:
            stringParts = comparibleVersion.split(".")
            comparibleVersion = "".join(stringParts)
        if comparibleVersion.endswith(descriptiveTrailer):
            # This means its not an offical release and came from Master/Main
            # replace with a .1 so that the number is higher than an offical release
            comparibleVersion = comparibleVersion.replace(descriptiveTrailer, ".1")
        #  Make it a number. At this point "0.5.5-RC" should be 55.1. "0.5.4" should be 54.
        comparibleVersion = float(comparibleVersion)


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

    genesis = None # await default_genesis_txns()
    #if not genesis:
    #    print("Error retrieving ledger genesis transactions")
    #    sys.exit(1)

    agent = None

    try:
        agent = AfGoAgentBackchannel(
            "af-go", start_port+1, start_port+2, genesis_data=genesis
        )

        # start backchannel (common across all types of agents)
        await agent.listen_backchannel(start_port)

        # start af-go agent sub-process and listen for web hooks
        await agent.listen_webhooks(start_port+3)
        # await agent.register_did()

        await agent.start_process()
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
            remaining_tasks = asyncio.all_tasks()
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
