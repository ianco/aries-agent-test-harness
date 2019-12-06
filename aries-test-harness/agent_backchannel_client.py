import asyncio
from aiohttp import (
    web,
    ClientSession,
    ClientRequest,
    ClientResponse,
    ClientError,
    ClientTimeout,
)
import json
from time import sleep


######################################################################
# coroutine utilities
######################################################################

def run_coroutine(coroutine):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coroutine())
    finally:
        loop.close()

def run_coroutine_with_args(coroutine, *args):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coroutine(*args))
    finally:
        loop.close()

def run_coroutine_with_kwargs(coroutine, *args, **kwargs):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coroutine(*args, **kwargs))
    finally:
        loop.close()


async def make_agent_backchannel_request(
    method, path, data=None, text=False, params=None
) -> (int, str):
    params = {k: v for (k, v) in (params or {}).items() if v is not None}
    client_session: ClientSession = ClientSession()
    async with client_session.request(
        method, path, json=data, params=params
    ) as resp:
        resp_status = resp.status
        resp_text = await resp.text()
        await client_session.close()
        return (resp_status, resp_text)


def agent_backchannel_start_agent(url) -> (int, str):
    backchannel_url = url + "/backchannel/command/start-agent/"
    (resp_status, resp_text) = run_coroutine_with_kwargs(make_agent_backchannel_request, "POST", backchannel_url)
    return (resp_status, resp_text)
    

def agent_backchannel_stop_agent(url) -> (int, str):
    backchannel_url = url + "/backchannel/command/stop-agent/"
    (resp_status, resp_text) = run_coroutine_with_kwargs(make_agent_backchannel_request, "POST", backchannel_url)
    return (resp_status, resp_text)

    
def agent_backchannel_agent_status(url) -> (int, str):
    backchannel_url = url + "/backchannel/command/agent-status/"
    (resp_status, resp_text) = run_coroutine_with_kwargs(make_agent_backchannel_request, "GET", backchannel_url)
    return (resp_status, resp_text)

    
def agent_backchannel_GET(url, topic, operation=None, id=None, data=None) -> (int, str):
    agent_url = url + topic + "/"
    if id:
        agent_url = agent_url + id
    (resp_status, resp_text) = run_coroutine_with_kwargs(make_agent_backchannel_request, "GET", agent_url)
    return (resp_status, resp_text)


def agent_backchannel_POST(url, topic, operation=None, id=None, data=None) -> (int, str):
    agent_url = url + topic + "/"
    payload = {}
    if data:
        payload["data"] = data
    if operation:
        payload["operation"] = operation
    if id:
        payload["id"] = id
    (resp_status, resp_text) = run_coroutine_with_kwargs(make_agent_backchannel_request, "POST", agent_url, data=payload)
    return (resp_status, resp_text)


def connection_status(agent_url, connection_id, status_txt):
    sleep(0.2)
    state = "None"
    if type(status_txt) != list:
        status_txt = [status_txt]
    for i in range(5):
        (resp_status, resp_text) = agent_backchannel_GET(agent_url + "/agent/command/", "connection", id=connection_id)
        if resp_status == 200:
            resp_json = json.loads(resp_text)
            state = resp_json["state"]
            if state in status_txt:
                return True
        sleep(0.2)
    print("From", agent_url, "Expected state", status_txt, "but received", state)
    return False

