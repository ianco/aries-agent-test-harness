import asyncio
import asyncpg
import functools
import json
import logging
import os
import random
import subprocess
import sys
import prompt_toolkit
from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.eventloop.defaults import use_asyncio_event_loop
from prompt_toolkit.patch_stdout import patch_stdout
from timeit import default_timer

import pygments
from pygments.filter import Filter
from pygments.lexer import Lexer
from pygments.lexers.data import JsonLdLexer
from prompt_toolkit.formatted_text import FormattedText, PygmentsTokens

from aiohttp import (
    web,
    ClientSession,
    ClientRequest,
    ClientResponse,
    ClientError,
    ClientTimeout,
)

from utils import require_indy, flatten, log_json, log_msg, log_timer, output_reader, prompt_loop, read_operations


LOGGER = logging.getLogger(__name__)

DEFAULT_POSTGRES = bool(os.getenv("POSTGRES"))
DEFAULT_INTERNAL_HOST = "127.0.0.1"
DEFAULT_EXTERNAL_HOST = "localhost"

START_TIMEOUT = float(os.getenv("START_TIMEOUT", 30.0))

RUN_MODE = os.getenv("RUNMODE")

GENESIS_URL = os.getenv("GENESIS_URL")
LEDGER_URL = os.getenv("LEDGER_URL")

if RUN_MODE == "docker":
    DEFAULT_INTERNAL_HOST = os.getenv("DOCKERHOST") or "host.docker.internal"
    DEFAULT_EXTERNAL_HOST = DEFAULT_INTERNAL_HOST
elif RUN_MODE == "pwd":
    DEFAULT_EXTERNAL_HOST = os.getenv("DOCKERHOST") or "host.docker.internal"


async def default_genesis_txns():
    genesis = None
    try:
        if GENESIS_URL:
            async with ClientSession() as session:
                async with session.get(GENESIS_URL) as resp:
                    genesis = await resp.text()
        elif RUN_MODE == "docker":
            async with ClientSession() as session:
                async with session.get(
                    f"http://{DEFAULT_EXTERNAL_HOST}:9000/genesis"
                ) as resp:
                    genesis = await resp.text()
        else:
            with open("local-genesis.txt", "r") as genesis_file:
                genesis = genesis_file.read()
    except Exception:
        LOGGER.exception("Error loading genesis transactions:")
    return genesis


class AgentBackchannel:
    """
    Base class for building Aries agent backchannel adapters for integration into the interoperability test suite.

    Extend this base class and implement hooks to communicate with a specific agent.
    """

    def __init__(
        self, 
        ident: str,
        backchannel_port: int,
        http_port: int,
        admin_port: int,
        genesis_data: str = None,
        params: dict = {}
    ):
        self.ident = ident
        self.backchannel_port = backchannel_port
        self.http_port = http_port
        self.admin_port = admin_port
        self.genesis_data = genesis_data
        self.params = params
        rand_name = str(random.randint(100_000, 999_999))
        self.seed = ("my_seed_000000000000000000000000" + rand_name)[-32:]

        self.internal_host = DEFAULT_INTERNAL_HOST
        self.external_host = DEFAULT_EXTERNAL_HOST
        self.label = ident

        if RUN_MODE == "pwd":
            self.endpoint = f"http://{self.external_host}".replace(
                "{PORT}", str(http_port)
            )
        else:
            self.endpoint = f"http://{self.external_host}:{http_port}"
        self.admin_url = f"http://{self.internal_host}:{admin_port}"

        self.storage_type = "indy"
        self.wallet_type = "indy"
        self.wallet_name = self.ident.lower().replace(" ", "") + rand_name
        self.wallet_key = self.ident + rand_name
        self.did = None
        self.postgres = False

        self.agent_running = False

        self.client_session: ClientSession = ClientSession()


    """
    Setup the backchannel REST services and handlers:
    - REST service to start and stop the agent
    - REST service to query backchannel status
    - REST services to interact with the agent (send commands and request status/state)
    """
    async def listen_backchannel(self, backchannel_port):
        """ 
        Setup the routes to allow the test harness to send commands to and get replies
        from the Agent under test.

        Expected topics include:

            schema                 GET to return a list and POST to create/update
            credential-definition  GET to return a list and POST to create/update
            connection             GET to return a list or single; POST to create/update*
            credential             GET to return a list or single; POST to create/update*
            proof                  GET to return a list or single; POST to create/update*

        GET with no parameters returns all
        GET with an "id" parameter will return a single record
        POST will submit a JSON payload
        POST* will contain an "operation" element within the payload to define the operation
        POST operations on existing records must contain an "id" element
        POST operations will contain a "data" element which is the payload to pass through to the agent

        E.g.:  POST to /agent/command/issue_credential { "operation":"send-proposal", "data":"{...}"}
        E.g.:  POST to /agent/command/issue_credential { "operation":"issue", "id":"<cred exch id>", "data":"{...}"}

        Operations for each topic are:
        """
        operations_str = """
        topic                 | method | operation          | id  | data  | description 
        schema                |  GET   |                    |  Y  |       | Fetch a specific schema by ID
        schema                |  POST  |                    |     |   Y   | Register a schema on the ledger
        credential-definition |  GET   |                    |  Y  |       | Fetch a specific cred def by ID
        credential-definition |  POST  |                    |     |   Y   | Register a cred def on the ledger
        connection            |  GET   |                    |     |       | Get a list of all connections from the agent
        connection            |  GET   |                    |  Y  |       | Get a specific connection from the agent by ID
        connection            |  POST  | create-invitation  |     |       | Create a new invitation
        connection            |  POST  | receive-invitation |     |   Y   | Receive an invitation
        connection            |  POST  | accept-invitation  |  Y  |   Y   | Accept an invitation
        connection            |  POST  | accept-request     |  Y  |   Y   | Accept a connection request
        connection            |  POST  | establish-inbound  |  Y* |       | ???
        connection            |  POST  | remove             |  Y  |       | Remove a connection
        connection            |  POST  | start-introduction |  Y  |   Y   | Start an introcution between two agents
        connection            |  POST  | send-message       |  Y  |   Y   | Send a basic message
        connection            |  POST  | expire-message     |  Y* |       | Expire a basic message
        connection            |  POST  | send-ping          |  Y  |   Y   | Send a trust ping
        credential            |  GET   | records            |     |       | Fetch all credential exchange records
        credential            |  GET   | records            |  Y  |       | Fetch a specific credential exchange record
        credential            |  GET   | mime-types         |  Y  |       | Get mime types associated with a credential's attributes
        credential            |  POST  | send               |     |   Y   | Send a credential, automating the entire flow
        credential            |  POST  | send-proposal      |     |   Y   | Send a credential proposal
        credential            |  POST  | send-offer         |     |   Y   | Send a credential offer
        credential            |  POST  | send-offer         |  Y  |   Y   | Send a credential offer associated with a proposal
        credential            |  POST  | send-request       |  Y  |   Y   | Send a credential request
        credential            |  POST  | issue              |  Y  |   Y   | Issue a credential in response to a request
        credential            |  POST  | store              |  Y  |   Y   | Store a credential
        credential            |  POST  | problem-report     |  Y  |   Y   | Raise a problem report for a credential exchange
        credential            |  POST  | remove             |  Y  |       | Remove an existing credential exchange record
        proof                 |  GET   | records            |     |       | Fetch all proof exchange records
        proof                 |  GET   | records            |  Y  |       | Fetch a specific proof exchange record
        proof                 |  GET   | credentials        |  Y  |       | Fetch credentials from the wallet for a specific proof exchange
        proof                 |  GET   | referent           |  Y* |       | Fetch credentials from the wallet for a specific proof exchange/referent
        proof                 |  POST  | send-proposal      |     |   Y   | Send a proof proposal
        proof                 |  POST  | send-request       |     |   Y   | Send a proof request not bound to a proposal
        proof                 |  POST  | send-request       |  Y  |   Y   | Send a proof request in reference to a proposal
        proof                 |  POST  | send-presentation  |  Y  |   Y   | Send a proof presentation
        proof                 |  POST  | verify-presentation|  Y  |   Y   | Verify a received proof presentation
        proof                 |  POST  | remove             |  Y  |       | Remove an existing proof exchange record          
        """
        self.operations = read_operations(operations_str)

        app = web.Application()
        app.add_routes([web.post("/backchannel/command/{topic}/", self._post_backchannel_command_backchannel)])
        app.add_routes([web.get("/backchannel/command/{topic}/", self._get_backchannel_command_backchannel)])
        app.add_routes([web.get("/backchannel/command/{topic}/{id}", self._get_backchannel_command_backchannel)])

        app.add_routes([web.post("/agent/command/{topic}/", self._post_agent_command_backchannel)])
        app.add_routes([web.get("/agent/command/{topic}/", self._get_agent_command_backchannel)])
        app.add_routes([web.get("/agent/command/{topic}/{id}", self._get_agent_command_backchannel)])

        app.add_routes([web.get("/agent/response/{topic}/", self._get_agent_response_backchannel)])
        app.add_routes([web.get("/agent/response/{topic}/{id}", self._get_agent_response_backchannel)])
        app.add_routes([web.post("/agent/reply/{topic}/", self._post_agent_reply_backchannel)])

        runner = web.AppRunner(app)
        await runner.setup()
        self.backchannel_site = web.TCPSite(runner, "0.0.0.0", backchannel_port)
        await self.backchannel_site.start()
        print("Listening to backchannel on port", backchannel_port)


    async def _post_backchannel_command_backchannel(self, request: ClientRequest):
        topic = request.match_info["topic"]
        log_msg("POST backchannel command", topic)

        if topic == "start-agent":
            if self.agent_running:
                return web.Response(body='500: Agent already running\n\n'.encode('utf8'), status=500)
            (resp_status, resp_text) = await self.start_agent()
            return web.Response(text=resp_text, status=resp_status)
        elif topic == "stop-agent":
            if not self.agent_running:
                return web.Response(body='500: Agent not running\n\n'.encode('utf8'), status=500)
            (resp_status, resp_text) = await self.stop_agent()
            return web.Response(text=resp_text, status=resp_status)

        return web.Response(body='404: Not Found\n\n'.encode('utf8'), status=404)


    async def _get_backchannel_command_backchannel(self, request: ClientRequest):
        topic = request.match_info["topic"]
        log_msg("GET backchannel command", topic)

        if topic == "agent-status":
            (resp_status, resp_text) = await self.agent_status()
            return web.Response(text=resp_text, status=resp_status)

        return web.Response(body='404: Not Found\n\n'.encode('utf8'), status=404)


    def match_agent_operation(self, topic, method, payload=None, rec_id=None):
        """
        Determine which agent operation we are trying to invoke
        """
        data = None
        operation = None
        if payload:
            if "id" in payload:
                rec_id = payload["id"]
            if "operation" in payload:
                operation = payload["operation"]
            if "data" in payload:
                data = payload["data"]
        for op in self.operations:
            if (op["topic"] == topic and op["method"] == method and
                ((rec_id and op["id"] == "Y") or (rec_id is None)) and
                ((method == "GET") or (operation and op["operation"] == operation) or (operation is None)) and
                ((data and op["data"] == "Y") or (data is None))
            ):
                return op

        return None

    async def _post_agent_command_backchannel(self, request: ClientRequest):
        """
        Post a POST command to the agent.
        """
        if not self.agent_running:
            return web.Response(body='500: Agent not running\n\n'.encode('utf8'), status=500)
            
        topic = request.match_info["topic"]
        payload = await request.json()

        operation = self.match_agent_operation(topic, "POST", payload=payload)
        if operation:
            if "data" in payload:
                data = payload["data"]
            else:
                data = None
            if "id" in payload:
                rec_id = payload["id"]
            else:
                rec_id = None

            (resp_status, resp_text) = await self.make_agent_POST_request(operation, rec_id=rec_id, data=data)

            return web.Response(text=resp_text, status=resp_status)

        return web.Response(body='404: Not Found\n\n'.encode('utf8'), status=404)

    async def _get_agent_command_backchannel(self, request: ClientRequest):
        """
        Post a GET command to the agent.
        """
        if not self.agent_running:
            return web.Response(body='500: Agent not running\n\n'.encode('utf8'), status=500)
            
        topic = request.match_info["topic"]
        if "id" in request.match_info:
            rec_id = request.match_info["id"]
        else:
            rec_id = None

        operation = self.match_agent_operation(topic, "GET", rec_id=rec_id)
        if operation:
            (resp_status, resp_text) = await self.make_agent_GET_request(operation, rec_id=rec_id)

            return web.Response(text=resp_text, status=resp_status)

        return web.Response(body='404: Not Found\n\n'.encode('utf8'), status=404)

    async def _get_agent_response_backchannel(self, request: ClientRequest):
        """
        Get a response from the (remote) agent.
        """
        if not self.agent_running:
            return web.Response(body='500: Agent not running\n\n'.encode('utf8'), status=500)
            
        topic = request.match_info["topic"]
        if "id" in request.match_info:
            rec_id = request.match_info["id"]
        else:
            rec_id = None

        (resp_status, resp_text) = await self.make_agent_GET_request_response(topic, rec_id=rec_id)

        return web.Response(text=resp_text, status=resp_status)

    async def _post_agent_reply_backchannel(self, request: ClientRequest):
        """
        Reply to a response from the (remote) agent.
        """
        if not self.agent_running:
            return web.Response(body='500: Agent not running\n\n'.encode('utf8'), status=500)
            
        return web.Response(text="")

    """
    Agent-specific backchannel hooks.
    Override these methods for an agent-specific backchannel implementation.
    """
    async def start_agent(self):
        """
        Override with agent-specific behaviour
        """
        raise NotImplementedError

    async def stop_agent(self):
        """
        Override with agent-specific behaviour
        """
        raise NotImplementedError

    async def agent_status(self):
        """
        Override with agent-specific behaviour
        """
        if self.agent_running:
            return (200, {"status": "active"})
        else:
            return (200, {"status": "inactive"})

    async def make_agent_POST_request(
        self, op, rec_id=None, data=None, text=False, params=None
    ) -> (int, str):
        """
        Override with agent-specific behaviour
        """
        raise NotImplementedError

    async def make_agent_GET_request(
        self, op, rec_id=None, text=False, params=None
    ) -> (int, str):
        """
        Override with agent-specific behaviour
        """
        raise NotImplementedError

    async def make_agent_GET_request_response(
        self, topic, rec_id=None, text=False, params=None
    ) -> (int, str):
        """
        Override with agent-specific behaviour
        """
        raise NotImplementedError

    def log(self, msg):
        print(msg)

    """
    Other utility methods that can be used by agent backchannel implementations.
    """
    def handle_output(self, *output, source: str = None, **kwargs):
        end = "" if source else "\n"
        if source == "stderr":
            color = "fg:ansired"
        elif not source:
            color = self.color or "fg:ansiblue"
        else:
            color = None
        log_msg(*output, color=color, prefix=self.prefix_str, end=end, **kwargs)

    async def register_did(self, ledger_url: str = None, alias: str = None):
        if not ledger_url:
            ledger_url = LEDGER_URL
        if not ledger_url:
            ledger_url = f"http://{self.external_host}:9000"
        data = {"alias": alias or self.ident, "seed": self.seed, "role": "TRUST_ANCHOR"}
        async with self.client_session.post(
            ledger_url + "/register", json=data
        ) as resp:
            if resp.status != 200:
                raise Exception(f"Error registering DID, response code {resp.status}")
            nym_info = await resp.json()
            self.did = nym_info["did"]
        self.log(f"Got DID: {self.did}")

