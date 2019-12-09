import asyncio
import asyncpg
import functools
import json
import logging
import os
import random
import subprocess
import sys
from timeit import default_timer
from ctypes import cdll
from time import sleep

from aiohttp import (
    web,
    ClientSession,
    ClientRequest,
    ClientResponse,
    ClientError,
    ClientTimeout,
)

from agent_backchannel import AgentBackchannel, default_genesis_txns, RUN_MODE, START_TIMEOUT
from utils import require_indy, flatten, log_json, log_msg, log_timer, output_reader, prompt_loop, file_ext, create_uuid
from storage import store_resource, get_resource, delete_resource, pop_resource, get_resources, clear_resource

from vcx.api.connection import Connection
from vcx.api.credential_def import CredentialDef
from vcx.api.issuer_credential import IssuerCredential
from vcx.api.proof import Proof
from vcx.api.schema import Schema
from vcx.api.utils import vcx_agent_provision
from vcx.api.vcx_init import vcx_init_with_config
from vcx.state import State, ProofState


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


# 'agency_url': URL of the agency
# 'agency_did':  public DID of the agency
# 'agency_verkey': public verkey of the agency
# 'wallet_name': name for newly created encrypted wallet
# 'wallet_key': encryption key for encoding wallet
# 'payment_method': method that will be used for payments
provisionConfig = {
    'agency_url': 'http://localhost:9090',
    'agency_did': 'VsKV7grR1BUE29mG2Fm2kX',
    'agency_verkey': 'Hezce2UWMZ3wUhVkh2LfKSs8nDzWwzs2Win7EzNN3YaR',
    'wallet_name': 'faber_wallet',
    'wallet_key': '123',
    'payment_method': 'null',
    'enterprise_seed': '000000000000000000000000Trustee1',
    'protocol_type': '2.0',
    'communication_method': 'aries'
}


def state_text(connection_state):
    if connection_state == State.OfferSent:
        return "invitation"
    elif connection_state == State.RequestReceived:
        return "request"
    elif connection_state == State.Unfulfilled:
        return "response"
    elif connection_state == State.Accepted:
        return "active"
    return str(connection_state)


class VCXAgentBackchannel(AgentBackchannel):
    def __init__(
        self, 
        ident: str,
        backchannel_port: int, 
        genesis_data: str = None,
        params: dict = {}
    ):
        super().__init__(
            ident,
            backchannel_port,
            genesis_data,
            params
        )
        self.config = None

    async def start_agent(self):
        log_msg("vcx start_agent()")

        # start VCX agent sub-process 
        await self.start_vcx()

        self.agent_running = True

        log_msg(200, '{"status": "active"}')
        return (200, '{"status": "active"}')

    async def stop_agent(self):
        await self.stop_vcx()

        self.agent_running = False
        
        log_msg(200, '{"status": "inactive"}')
        return (200, '{"status": "inactive"}')

    async def agent_status(self):
        await asyncio.sleep(0.1)
        if self.agent_running:
            return (200, '{"status": "active"}')
        else:
            return (200, '{"status": "inactive"}')

    async def start_vcx(self):
        if not self.config:
            payment_plugin = cdll.LoadLibrary('libnullpay' + file_ext())
            payment_plugin.nullpay_init()

            print("Provision an agent and wallet, get back configuration details")
            config = await vcx_agent_provision(json.dumps(provisionConfig))
            self.config = json.loads(config)
            # Set some additional configuration options specific to faber
            self.config['institution_name'] = 'Faber'
            self.config['institution_logo_url'] = 'http://robohash.org/234'
            self.config['genesis_path'] = 'local-genesis.txt'

        print("Initialize libvcx with new configuration")
        await vcx_init_with_config(json.dumps(self.config))

    async def stop_vcx(self):
        clear_resource()
        pass

    async def make_agent_POST_request(
        self, op, rec_id=None, data=None, text=False, params=None
    ) -> (int, str):
        if op["topic"] == "connection":
            operation = op["operation"]
            if operation == "create-invitation":
                connection_id = create_uuid()

                connection = await Connection.create(connection_id)
                await connection.connect('{"use_public_did": true}')
                invitation = await connection.invite_details(False)

                store_resource(connection_id, "connection", connection)
                connection_dict = await connection.serialize()

                resp_status = 200
                resp_text = json.dumps({"connection_id": connection_id, "invitation": invitation, "connection": connection_dict})

                return (resp_status, resp_text)

            elif operation == "receive-invitation":
                connection_id = create_uuid()

                connection = await Connection.create_with_details(connection_id, json.dumps(data))
                await connection.connect('{"use_public_did": true}')
                connection_state = await connection.update_state()
                store_resource(connection_id, "connection", connection)
                connection_dict = await connection.serialize()

                resp_status = 200
                resp_text = json.dumps({"connection_id": connection_id, "invitation": data, "connection": connection_dict})

                return (resp_status, resp_text)

            elif (operation == "accept-invitation" 
                or operation == "accept-request"
                or operation == "remove"
                or operation == "start-introduction"
                or operation == "send-ping"
            ):
                connection_id = rec_id
                connection = get_resource(rec_id, "connection")
                if connection:
                    # wait for a small period just in case ...
                    await asyncio.sleep(0.1)
                    # make sure we have latest & greatest connection state
                    await connection.update_state()
                    store_resource(connection_id, "connection", connection)
                    connection_dict = await connection.serialize()
                    connection_state = await connection.get_state()

                    resp_status = 200
                    resp_text = json.dumps({"connection_id": rec_id, "state": state_text(connection_state), "connection": connection_dict})
                    return (resp_status, resp_text)

        return (404, '404: Not Found\n\n'.encode('utf8'))

    async def make_agent_GET_request(
        self, op, rec_id=None, text=False, params=None
    ) -> (int, str):
        if op["topic"] == "connection":
            if rec_id:
                log_msg("Getting connection for", rec_id)
                connection = get_resource(rec_id, "connection")

                if connection:
                    connection_dict = await connection.serialize()
                    connection_state = await connection.get_state()

                    resp_status = 200
                    resp_text = json.dumps({"connection_id": rec_id, "state": state_text(connection_state), "connection": connection_dict})
                    return (resp_status, resp_text)

            else:
                log_msg("Getting connections")
                connections = get_resources("connection")
                log_msg(connections)
                ret_connections = []
                for connection_id in connections:
                    connection = connections[connection_id]
                    connection_dict = await connection.serialize()
                    connection_state = await connection.get_state()
                    ret_connections.append({"connection_id": connection_id, "state": state_text(connection_state), "connection": connection_dict})

                resp_status = 200
                resp_text = json.dumps(ret_connections)
                log_msg(resp_status, resp_text)
                return (resp_status, resp_text)

        log_msg("Returning 404")

        return (404, '404: Not Found\n\n'.encode('utf8'))

    async def make_agent_GET_request_response(
        self, topic, rec_id=None, text=False, params=None
    ) -> (int, str):
        if topic == "connection" and rec_id:
            connection = get_resource(rec_id, "connection")
            connection_state = await connection.update_state()
            store_resource(rec_id, "connection", connection)

            resp_status = 200
            connection_dict = await connection.serialize()
            resp_text = json.dumps({"connection_id": rec_id, "connection": connection_dict})

            return (resp_status, resp_text)

        return (404, '404: Not Found\n\n'.encode('utf8'))


async def main(start_port: int, show_timing: bool = False):

    genesis = await default_genesis_txns()
    if not genesis:
        print("Error retrieving ledger genesis transactions")
        sys.exit(1)

    agent = None

    try:
        agent = VCXAgentBackchannel(
            "vcx", start_port, genesis_data=genesis
        )

        # start backchannel (common across all types of agents)
        await agent.listen_backchannel(start_port)

        await agent.register_did()

        await agent.start_agent()

        print("Running; ^C to break ...")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass

    finally:
        terminated = True
        try:
            if agent:
                await agent.stop_vcx()
        except Exception:
            LOGGER.exception("Error terminating agent:")
            terminated = False

    await asyncio.sleep(0.1)

    if not terminated:
        os._exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Runs a Faber demo agent.")
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8040,
        metavar=("<port>"),
        help="Choose the starting port number to listen on",
    )
    args = parser.parse_args()

    require_indy()

    try:
        asyncio.get_event_loop().run_until_complete(main(args.port))
    except KeyboardInterrupt:
        os._exit(1)
