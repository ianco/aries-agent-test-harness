import asyncio
import asyncpg
import functools
import json
import logging
import os
import random
import sys
from timeit import default_timer
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


def state_text(connection_state):
    return "active"


class PicoAgentBackchannel(AgentBackchannel):
    def __init__(
        self, 
        ident: str,
        backchannel_port: int, 
        pico_url: str,
        pico_eci: str,
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
        self.pico_url = pico_url
        self.pico_eci = pico_eci
        rand_name = str(random.randint(100_000, 999_999))
        self.seed = ("my_seed_000000000000000000000000" + rand_name)[-32:]

    async def start_agent(self):
        log_msg("pico start_agent()")

        # start pico agent sub-process 
        await self.start_pico()

        self.agent_running = True

        log_msg(200, '{"status": "active"}')
        return (200, '{"status": "active"}')

    async def stop_agent(self):
        await self.stop_pico()

        self.agent_running = False
        
        log_msg(200, '{"status": "inactive"}')
        return (200, '{"status": "inactive"}')

    async def agent_status(self):
        await asyncio.sleep(0.1)
        if self.agent_running:
            return (200, '{"status": "active"}')
        else:
            return (200, '{"status": "inactive"}')

    async def start_pico(self):
        # no op, assume pico agent is running
        pass

    async def stop_pico(self):
        clear_resource()
        pass

    async def pico_create_invitation(self):
        create_invite_url = self.pico_url + "/sky/cloud/" + self.pico_eci + "/org.sovrin.agent_bc/invitation"
        print("GET:", create_invite_url)

        (resp_status, resp_text) = await self.admin_GET(create_invite_url)
        if resp_status != 200:
            raise Exception("Error generating invitation")
        print(resp_status, resp_text)

        # returned invite is in url format "http://whatever:port/.../?c_i=...some data..."
        if resp_text[0] == '"':
            invite_url = resp_text[1:-1]
        else:
            invite_url = resp_text
        invite = self.extract_invite_info(invite_url)

        return (invite_url, invite)

    async def pico_receive_invitation(self, invitation):
        receive_invite_url = self.pico_url + "/sky/event/" + self.pico_eci + "/event_id/sovrin/new_invitation"
        print(receive_invite_url)

        receive_invite_url = receive_invite_url + "?c_i=" + self.urlencode_url(invitation)

        (resp_status, resp_text) = await self.admin_GET(receive_invite_url)
        print(resp_status, resp_text)
        if resp_status != 200:
            raise Exception("Error receiving invitation")

    async def pico_list_connections(self):
        list_connections_url = self.pico_url + "/sky/cloud/" + self.pico_eci + "/org.sovrin.agent_bc/connection"

    async def make_admin_request(
        self, method, path, data=None, text=False, params=None
    ) -> (int, str):
        params = {k: v for (k, v) in (params or {}).items() if v is not None}
        print("request:", method, path)
        async with self.client_session.request(
            method, path, json=data, params=params
        ) as resp:
            resp_status = resp.status
            print("Status:", resp_status)
            resp_text = await resp.text()
            print("Text:", resp_text)
            return (resp_status, resp_text)

    async def admin_GET(self, path, text=False, params=None) -> (int, str):
        try:
            return await self.make_admin_request("GET", path, None, text, params)
        except ClientError as e:
            self.log(f"Error during GET {path}: {str(e)}")
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
                connection_id = create_uuid()

                (invitation_url, invitation) = await self.pico_create_invitation()
                print(invitation_url, invitation)

                connection = {"id": connection_id, "invitation": invitation, "invitation_url": invitation_url}

                store_resource(connection_id, "connection", connection)

                resp_status = 200
                resp_text = json.dumps({"connection_id": connection_id, "invitation": invitation, "invitation_url": invitation_url, "connection": connection})

                return (resp_status, resp_text)

            elif operation == "receive-invitation":
                connection_id = create_uuid()

                if "invitation_url" in data and 0 < len(data["invitation_url"]):
                    invitation_url = data["invitation_url"]
                    invitation = self.extract_invite_info(invitation_url)
                elif "invitation" in data and 0 < len(data["invitation"]):
                    return (500, '500: No Invitation URL Provided\n\n'.encode('utf8'))
                else:
                    return (500, '500: No Invitation Provided\n\n'.encode('utf8'))

                print(invitation_url)
                print(invitation)
                await self.pico_receive_invitation(invitation_url)

                connection = {"id": connection_id, "invitation": invitation, "invitation_url": invitation_url}

                store_resource(connection_id, "connection", connection)

                resp_status = 200
                resp_text = json.dumps({"connection_id": connection_id, "invitation": invitation, "invitation_url": invitation_url, "connection": connection})

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
                    # TODO no op for now
                    resp_status = 200
                    resp_text = json.dumps({"connection_id": rec_id, "state": "active", "connection": connection_dict})
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
                    resp_status = 200
                    resp_text = json.dumps({"connection_id": rec_id, "state": "active", "connection": connection})
                    return (resp_status, resp_text)

            else:
                log_msg("Getting connections")
                connections = get_resources("connection")
                log_msg(connections)
                ret_connections = []
                for connection_id in connections:
                    connection = connections[connection_id]
                    ret_connections.append({"connection_id": connection_id, "state": "active", "connection": connection})

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
            # TODO no-op for now
            connection = get_resource(rec_id, "connection")
            resp_status = 200
            resp_text = json.dumps({"connection_id": rec_id, "connection": connection})

            return (resp_status, resp_text)

        return (404, '404: Not Found\n\n'.encode('utf8'))


async def main(start_port: int, pico_url: str, pico_eci: str, show_timing: bool = False):

    genesis = await default_genesis_txns()
    if not genesis:
        print("Error retrieving ledger genesis transactions")
        sys.exit(1)

    agent = None

    try:
        agent = PicoAgentBackchannel(
            "pico", start_port, pico_url, pico_eci, genesis_data=genesis
        )

        # start backchannel (common across all types of agents)
        await agent.listen_backchannel(start_port)

        await agent.register_did(agent.seed)

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
                await agent.stop_pico()
        except Exception:
            LOGGER.exception("Error terminating agent:")
            terminated = False

    await asyncio.sleep(0.1)

    if not terminated:
        os._exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Runs a Pico agent backchannel.")
    parser.add_argument(
        "-u",
        "--url",
        type=str,
        default="http://localhost:8080",
        metavar=("<url>"),
        help="Specify the url of the pico agent",
    )
    parser.add_argument(
        "-e",
        "--eci",
        type=str,
        default="TODO",
        metavar=("<eci>"),
        help="Specify the ECI of the pico agent",
    )
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
        asyncio.get_event_loop().run_until_complete(main(args.port, args.url, args.eci))
    except KeyboardInterrupt:
        os._exit(1)
