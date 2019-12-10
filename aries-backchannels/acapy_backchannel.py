import asyncio
import asyncpg
import threading
import functools
import json
import logging
import os
import random
import subprocess
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
from utils import require_indy, flatten, log_json, log_msg, log_timer, output_reader, stderr_reader, prompt_loop
from storage import store_resource, get_resource, delete_resource, push_resource, pop_resource, clear_resource


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

class AcaPyAgentBackchannel(AgentBackchannel):
    def __init__(
        self, 
        ident: str,
        backchannel_port: int, 
        http_port: int,
        admin_port: int,
        genesis_data: str = None,
        params: dict = {}
    ):
        super().__init__(
            ident,
            backchannel_port,
            genesis_data,
            params
        )
        self.http_port = http_port
        self.admin_port = admin_port

        if RUN_MODE == "pwd":
            self.endpoint = f"http://{self.external_host}".replace(
                "{PORT}", str(http_port)
            )
        else:
            self.endpoint = f"http://{self.external_host}:{http_port}"
        self.admin_url = f"http://{self.internal_host}:{admin_port}"

        rand_name = str(random.randint(100_000, 999_999))
        self.seed = ("my_seed_000000000000000000000000" + rand_name)[-32:]

        self.storage_type = "indy"
        self.wallet_type = "indy"
        self.wallet_name = self.ident.lower().replace(" ", "") + rand_name
        self.wallet_key = self.ident + rand_name
        self.postgres = False

        # endpoint exposed by ngrok
        #self.endpoint = "https://9f3a6083.ngrok.io"

    def get_agent_args(self):
        result = [
            ("--endpoint", self.endpoint),
            ("--label", self.label),
            "--auto-ping-connection",
            "--auto-accept-invites", 
            "--auto-accept-requests", 
            "--auto-respond-messages",
            ("--inbound-transport", "http", "0.0.0.0", str(self.http_port)),
            ("--outbound-transport", "http"),
            ("--admin", "0.0.0.0", str(self.admin_port)),
            "--admin-insecure-mode",
            ("--wallet-type", self.wallet_type),
            ("--wallet-name", self.wallet_name),
            ("--wallet-key", self.wallet_key),
        ]
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

    async def start_agent(self):
        log_msg("aca-py start_agent()")

        # start aca-py agent sub-process and listen for web hooks
        await self.listen_webhooks(self.backchannel_port+3)
        await self.register_did(self.seed)

        await self.start_process()

        self.agent_running = True

        log_msg(200, '{"status": "active"}')
        return (200, '{"status": "active"}')

    async def stop_agent(self):
        log_msg("aca-py stop_agent()")

        # shutdown agent
        await self.terminate()
        clear_resource()

        self.agent_running = False
        
        log_msg(200, '{"status": "inactive"}')
        return (200, '{"status": "inactive"}')

    async def agent_status(self):
        if self.agent_running:
            try:
                await self.detect_process()
                return (200, '{"status": "active"}')
            except:
                pass
        return (200, '{"status": "inactive"}')

    async def _receive_webhook(self, request: ClientRequest):
        topic = request.match_info["topic"]
        payload = await request.json()
        await self.handle_webhook(topic, payload)
        # TODO web hooks don't require a response???
        return web.Response(text="")

    async def handle_webhook(self, topic: str, payload):
        if topic != "webhook":  # would recurse
            handler = f"handle_{topic}"
            method = getattr(self, handler, None)
            if method:
                await method(payload)
            else:
                log_msg(
                    f"Error: agent {self.ident} "
                    f"has no method {handler} "
                    f"to handle webhook on topic {topic}"
                )

    async def handle_connections(self, message):
        connection_id = message["connection_id"]
        push_resource(connection_id, "connection-msg", message)

        # TODO wait here to determine the response to the web hook?????
        pass

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
                resp_text = json.dumps(invitation_resp)

                return (resp_status, resp_text)

            elif operation == "receive-invitation":
                agent_operation = "/connections/" + operation

                if "invitation" in data and 0 < len(data["invitation"]):
                    invitation = data["invitation"]
                elif "invitation_url" in data and 0 < len(data["invitation_url"]):
                    invitation = self.extract_invite_info(data["invitation_url"])
                else:
                    return (500, '500: No Invitation Provided\n\n'.encode('utf8'))

                (resp_status, resp_text) = await self.admin_POST(agent_operation, data=invitation)

                return (resp_status, resp_text)

            elif (operation == "accept-invitation" 
                or operation == "accept-request"
                or operation == "remove"
                or operation == "start-introduction"
                or operation == "send-ping"
            ):
                connection_id = rec_id
                agent_operation = "/connections/" + connection_id + "/" + operation
                log_msg(agent_operation, data)

                (resp_status, resp_text) = await self.admin_POST(agent_operation, data)

                log_msg(resp_status, resp_text)
                return (resp_status, resp_text)

        return (404, '404: Not Found\n\n'.encode('utf8'))

    async def make_agent_GET_request(
        self, op, rec_id=None, text=False, params=None
    ) -> (int, str):
        if op["topic"] == "connection":
            if rec_id:
                connection_id = rec_id
                agent_operation = "/connections/" + connection_id
            else:
                agent_operation = "/connections"
            
            (resp_status, resp_text) = await self.admin_GET(agent_operation)
            if resp_status != 200:
                return (resp_status, resp_text)

            resp_json = json.loads(resp_text)
            if rec_id:
                connection_info = {"connection_id": resp_json["connection_id"], "state": resp_json["state"], "connection": resp_json}
                resp_text = json.dumps(connection_info)
            else:
                resp_json = resp_json["results"]
                connection_infos = []
                for connection in resp_json:
                    connection_info = {"connection_id": connection["connection_id"], "state": connection["state"], "connection": connection}
                    connection_infos.append(connection_info)
                resp_text = json.dumps(connection_infos)
            return (resp_status, resp_text)

        return (404, '404: Not Found\n\n'.encode('utf8'))

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

        return (404, '404: Not Found\n\n'.encode('utf8'))

    def _process(self, args, env, loop):
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            encoding="utf-8",
        )
        sleep(0.5)
        t1 = threading.Thread(target=output_reader, args=(proc,))
        t1.start()
        t2 = threading.Thread(target=stderr_reader, args=(proc,))
        t2.start()
        return proc

    def get_process_args(self, bin_path: str = None):
        cmd_path = "aca-py"
        if bin_path is None:
            bin_path = DEFAULT_BIN_PATH
        if bin_path:
            cmd_path = os.path.join(bin_path, cmd_path)
        return list(flatten((["python3", cmd_path, "start"], self.get_agent_args())))

    async def detect_process(self):
        text = None

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

        status_url = self.admin_url + "/status"
        status_text = await fetch_swagger(status_url, START_TIMEOUT)
        print("Agent running with admin url", self.admin_url)

        if not status_text:
            raise Exception(
                "Timed out waiting for agent process to start. "
                + f"Admin URL: {status_url}"
            )
        ok = False
        try:
            status = json.loads(status_text)
            ok = isinstance(status, dict) and "version" in status
        except json.JSONDecodeError:
            pass
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
        if self.webhook_site:
            await self.webhook_site.stop()


async def main(start_port: int, show_timing: bool = False):

    genesis = await default_genesis_txns()
    if not genesis:
        print("Error retrieving ledger genesis transactions")
        sys.exit(1)

    agent = None

    try:
        agent = AcaPyAgentBackchannel(
            "aca-py", start_port, start_port+1, start_port+2, genesis_data=genesis
        )

        # start backchannel (common across all types of agents)
        await agent.listen_backchannel(start_port)

        await agent.start_agent()

        print("Running; ^C to break ...")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass

    except Exception as e:
        print(e)
    finally:
        print("Shutting down ...")
        terminated = True
        try:
            if agent:
                await agent.stop_agent()
        except Exception:
            LOGGER.exception("Error terminating agent:")
            terminated = False

    await asyncio.sleep(0.1)

    if not terminated:
        os._exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Runs an ACA-PY agent backchannel.")
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8020,
        metavar=("<port>"),
        help="Choose the starting port number to listen on",
    )
    args = parser.parse_args()

    require_indy()

    try:
        asyncio.get_event_loop().run_until_complete(main(args.port))
    except KeyboardInterrupt:
        os._exit(1)
