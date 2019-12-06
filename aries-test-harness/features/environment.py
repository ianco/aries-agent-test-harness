from behave.model_core import Status

from agent_backchannel_client import agent_backchannel_stop_agent, agent_backchannel_agent_status

def before_scenario(context, scenario):
    context.running_agents = {}
    
def after_scenario(context, scenario):
    print(scenario.status)

    if scenario.status == Status.failed:
        print('more details:...')

    if context.running_agents:
        for agent in context.running_agents:
            agent_url = context.running_agents[agent]
            (resp_status, resp_text) = agent_backchannel_stop_agent(agent_url)
