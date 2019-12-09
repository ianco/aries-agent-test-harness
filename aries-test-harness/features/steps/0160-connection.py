from behave import *
import json
from agent_backchannel_client import agent_backchannel_GET, agent_backchannel_POST, connection_status, agent_backchannel_start_agent, agent_backchannel_stop_agent, agent_backchannel_agent_status


@given('"{agent}" is defined and running')
def step_impl(context, agent):
    agent_url = context.config.userdata.get(agent)
    assert agent_url is not None and 0 < len(agent_url)

    (resp_status, resp_text) = agent_backchannel_agent_status(agent_url)
    assert resp_status == 200

    resp_json = json.loads(resp_text)
    assert resp_json["status"] == "active"

    context.running_agents[agent] = agent_url

@given('we have two agents "{inviter}" and "{invitee}"')
def step_impl(context, inviter, invitee):
    context.execute_steps(u'''
       Given "''' + inviter + '''" is defined and running
         And "''' + invitee + '''" is defined and running
    ''')
    inviter_url = context.config.userdata.get(inviter)
    invitee_url = context.config.userdata.get(invitee)
    assert inviter_url is not None and 0 < len(inviter_url)
    assert invitee_url is not None and 0 < len(invitee_url)

@when('"{inviter}" generates a connection invitation')
def step_impl(context, inviter):
    inviter_url = context.config.userdata.get(inviter)

    (resp_status, resp_text) = agent_backchannel_POST(inviter_url + "/agent/command/", "connection", operation="create-invitation")
    assert resp_status == 200

    resp_json = json.loads(resp_text)
    context.inviter_invitation = resp_json["invitation"]
    context.inviter_connection_id = resp_json["connection_id"]

    # get connection and verify status
    assert connection_status(inviter_url, context.inviter_connection_id, "invitation")

@when('"{invitee}" receives the connection invitation')
def step_impl(context, invitee):
    invitee_url = context.config.userdata.get(invitee)

    data = context.inviter_invitation
    (resp_status, resp_text) = agent_backchannel_POST(invitee_url + "/agent/command/", "connection", operation="receive-invitation", data=data)
    assert resp_status == 200

    resp_json = json.loads(resp_text)
    context.invitee_connection_id = resp_json["connection_id"]

    # get connection and verify status
    assert connection_status(invitee_url, context.invitee_connection_id, ["invitation", "request"])

@when('"{invitee}" sends a connection response')
def step_impl(context, invitee):
    invitee_url = context.config.userdata.get(invitee)
    invitee_connection_id = context.invitee_connection_id

    # get connection and verify status
    assert connection_status(invitee_url, invitee_connection_id, ["invitation", "request"])

    (resp_status, resp_text) = agent_backchannel_POST(invitee_url + "/agent/command/", "connection", operation="accept-invitation", id=invitee_connection_id)
    assert resp_status == 200

    # get connection and verify status
    assert connection_status(invitee_url, invitee_connection_id, "request")

@when('"{inviter}" accepts the connection response')
def step_impl(context, inviter):
    inviter_url = context.config.userdata.get(inviter)
    inviter_connection_id = context.inviter_connection_id

    # get connection and verify status
    assert connection_status(inviter_url, inviter_connection_id, ["invitation", "request"])

    (resp_status, resp_text) = agent_backchannel_POST(inviter_url + "/agent/command/", "connection", operation="accept-request", id=inviter_connection_id)
    assert resp_status == 200

    # get connection and verify status
    assert connection_status(inviter_url, inviter_connection_id, ["request", "response"])

@when('"{invitee}" sends a response ping')
def step_impl(context, invitee):
    invitee_url = context.config.userdata.get(invitee)
    invitee_connection_id = context.invitee_connection_id

    # get connection and verify status
    assert connection_status(invitee_url, invitee_connection_id, ["request", "response"])

    data = {"comment": "Hello from " + invitee}
    (resp_status, resp_text) = agent_backchannel_POST(invitee_url + "/agent/command/", "connection", operation="send-ping", id=invitee_connection_id, data=data)
    assert resp_status == 200

    # get connection and verify status
    assert connection_status(invitee_url, invitee_connection_id, "active")

@when('"{inviter}" receives the response ping')
def step_impl(context, inviter):
    # extra step to force status to 'active' for VCX
    inviter_url = context.config.userdata.get(inviter)
    inviter_connection_id = context.inviter_connection_id

    data = {"comment": "Hello from " + inviter}
    (resp_status, resp_text) = agent_backchannel_POST(inviter_url + "/agent/command/", "connection", operation="send-ping", id=inviter_connection_id, data=data)
    assert resp_status == 200

    # get connection and verify status
    assert connection_status(inviter_url, inviter_connection_id, "active")

@then('"{inviter}" and "{invitee}" have a connection')
def step_impl(context, inviter, invitee):
    inviter_url = context.config.userdata.get(inviter)
    inviter_connection_id = context.inviter_connection_id
    invitee_url = context.config.userdata.get(invitee)
    invitee_connection_id = context.invitee_connection_id

    # get connection and verify status
    assert connection_status(inviter_url, inviter_connection_id, "active")

    # get connection and verify status
    assert connection_status(invitee_url, invitee_connection_id, "active")


@given('"{sender}" and "{receiver}" have an existing connection')
def step_impl(context, sender, receiver):
    context.execute_steps(u'''
       Given we have two agents "''' + sender + '''" and "''' + receiver + '''"
        When "''' + sender + '''" generates a connection invitation
         And "''' + receiver + '''" receives the connection invitation
         And "''' + receiver + '''" sends a connection response
         And "''' + sender + '''" accepts the connection response
         And "''' + receiver + '''" sends a response ping
         And "''' + sender + '''" receives the response ping
        Then "''' + sender + '''" and "''' + receiver + '''" have a connection
    ''')

@when('"{sender}" sends a trust ping')
def step_impl(context, sender):
    sender_url = context.config.userdata.get(sender)
    sender_connection_id = context.inviter_connection_id

    # get connection and verify status
    assert connection_status(sender_url, sender_connection_id, "active")

    data = {"comment": "Hello from " + sender}
    (resp_status, resp_text) = agent_backchannel_POST(sender_url + "/agent/command/", "connection", operation="send-ping", id=sender_connection_id, data=data)
    assert resp_status == 200

    # get connection and verify status
    assert connection_status(sender_url, sender_connection_id, "active")

@then('"{receiver}" receives the trust ping')
def step_impl(context, receiver):
    # TODO
    pass

