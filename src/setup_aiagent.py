import os

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient, enable_telemetry
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import DeepResearchTool, MessageRole, ThreadMessage


load_dotenv()

try:
    project_client = AIProjectClient(
        endpoint=os.environ["PROJECT_ENDPOINT"],
        credential=DefaultAzureCredential(),
    )
    
    # conn_id =  project_client.connections.get(name=os.environ["BING_CONNECTION_NAME"]).id
    conn_id = os.environ["AZURE_BING_CONNECTION_ID"]
    agent_name = os.environ["AZURE_AI_AGENT_NAME"]

    # Initialize a Deep Research tool with Bing Connection ID and Deep Research model deployment name
    deep_research_tool = DeepResearchTool(
        bing_grounding_connection_id=conn_id,
        deep_research_model=os.environ["DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME"],
    )

    # Create Agent with the Deep Research tool and process Agent run
    with project_client:

        with project_client.agents as agents_client:

            agent = agents_client.create_agent(
                model=os.environ["AZURE_AI_AGENT_DEPLOYMENT_NAME"],
                name=agent_name,
                instructions="You are an Agent that assists that helping user to do deep research based on the topic user provided. Ask clarification question is preferred if need more detail before you do the research.  Please always include the reference.",
                tools=deep_research_tool.definitions,
            )

            print(f"Created agent with ID: {agent.id}")
            
            # Record successful agent creation metrics      
            print(f"Agent {agent.name} created successfully with ID: {agent.id}")          
    
except Exception as e:
    # Record failed agent creation metrics
    raise Exception(status_code=422, detail=str(e))