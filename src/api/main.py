# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import contextlib
import os
import sys
import token
import jwt as pyjwt

from azure.ai.projects.aio import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AccessToken

import fastapi
from fastapi.staticfiles import StaticFiles
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from logging_config import configure_logging

enable_trace = False
logger = None

# class SimpleTokenCredential:
#     def __init__(self, token, expires_on):
#         self._token = token
#         self._expires_on = expires_on

#     def get_token(self, *scopes, **kwargs):
#         return AccessToken(self._token, self._expires_on)


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    agent = None

    proj_endpoint = os.environ.get("AZURE_EXISTING_AIPROJECT_ENDPOINT")
    agent_id = os.environ.get("AZURE_EXISTING_AGENT_ID")
    auth_required = os.getenv("AUTHORIZED_AAD_GROUPS", "") != ""

    app.state.proj_endpoint = proj_endpoint
    app.state.agent_id = agent_id
    app.state.auth_required = auth_required

    try:
        ai_project = AIProjectClient(
            credential=DefaultAzureCredential(exclude_shared_token_cache_credential=True),
            endpoint=proj_endpoint,
            api_version = "2025-05-15-preview" # Evaluations yet not supported on stable (api_version="2025-05-01")
        )
        logger.info("Created AIProjectClient")

        if enable_trace:
            application_insights_connection_string = ""
            try:
                application_insights_connection_string = await ai_project.telemetry.get_connection_string()
            except Exception as e:
                e_string = str(e)
                logger.error("Failed to get Application Insights connection string, error: %s", e_string)
            if not application_insights_connection_string:
                logger.error("Application Insights was not enabled for this project.")
                logger.error("Enable it via the 'Tracing' tab in your AI Foundry project page.")
                exit()
            else:
                os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true" # Enable content recording for telemetry
                from azure.monitor.opentelemetry import configure_azure_monitor
                from azure.ai.projects import enable_telemetry
                enable_telemetry(destination=sys.stdout)
                configure_azure_monitor(connection_string=application_insights_connection_string)
                app.state.application_insights_connection_string = application_insights_connection_string
                logger.info("Configured Application Insights for tracing.")

        if agent_id:
            try: 
                agent = await ai_project.agents.get_agent(agent_id)
                logger.info("Agent already exists, skipping creation")
                logger.info(f"Fetched agent, agent ID: {agent.id}")
                logger.info(f"Fetched agent, model name: {agent.model}")
            except Exception as e:
                logger.error(f"Error fetching agent: {e}", exc_info=True)

        if not agent:
            # Fallback to searching by name
            agent_name = os.environ["AZURE_AI_AGENT_NAME"]
            agent_list = ai_project.agents.list_agents()
            if agent_list:
                async for agent_object in agent_list:
                    if agent_object.name == agent_name:
                        agent = agent_object
                        logger.info(f"Found agent by name '{agent_name}', ID={agent_object.id}")
                        break

        if not agent:
            raise RuntimeError("No agent found. Ensure qunicorn.py created one or set AZURE_EXISTING_AGENT_ID.")

        app.state.ai_project = ai_project
        app.state.agent = agent
        
        yield

    except Exception as e:
        logger.error(f"Error during startup: {e}", exc_info=True)
        raise RuntimeError(f"Error during startup: {e}")

    finally:
        try:
            await ai_project.close()
            logger.info("Closed AIProjectClient")
        except Exception as e:
            logger.error("Error closing AIProjectClient", exc_info=True)


def create_app():
    if not os.getenv("RUNNING_IN_PRODUCTION"):
        load_dotenv(override=True)

    global logger
    logger = configure_logging(os.getenv("APP_LOG_FILE", ""))

    enable_trace_string = os.getenv("ENABLE_AZURE_MONITOR_TRACING", "")
    global enable_trace
    enable_trace = False
    if enable_trace_string == "":
        enable_trace = False
    else:
        enable_trace = str(enable_trace_string).lower() == "true"
    if enable_trace:
        logger.info("Tracing is enabled.")
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor
        except ModuleNotFoundError:
            logger.error("Required libraries for tracing not installed.")
            logger.error("Please make sure azure-monitor-opentelemetry is installed.")
            exit()
    else:
        logger.info("Tracing is not enabled")

    directory = os.path.join(os.path.dirname(__file__), "static")
    app = fastapi.FastAPI(lifespan=lifespan)

    if enable_trace:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)  # Instrument FastAPI for OpenTelemetry

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Adjust this to your frontend's origin in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    auth_required = os.getenv("AUTHORIZED_AAD_GROUPS", "") != ""
    if auth_required:
        logger.info("Authorization is enabled.")
        # Authorization middleware
        @app.middleware("http")
        async def authorization_middleware(request: Request, call_next):
            access_token = request.headers.get("x-ms-token-aad-access-token")
            id_token = request.headers.get("x-ms-token-aad-id-token")
            if not id_token:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Unauthorized"}
                )

            logger.info(f"x-ms-token-aad-access-token:{access_token}")
            logger.info(f"x-ms-token-aad-id-token:{id_token}")

            # decode without verifying signature; still returns claims and PyJWT will still
            # raise if token is expired when options don't disable exp check
            claims = pyjwt.decode(id_token, options={"verify_signature": False})
            claims_groups = claims.get("groups", [])
            authorized_groups = set(claims_groups)
            required_groups = set(os.getenv("AUTHORIZED_AAD_GROUPS", "").split(","))

            if not authorized_groups.intersection(required_groups):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Forbidden"}
                )

            # When authentication is enabled it uses the user's access token to create the AIProjectClient
            decoded_token = pyjwt.decode(access_token, options={"verify_signature": False})
            request.state.decoded_token = decoded_token
            
            # simple_token_credential = SimpleTokenCredential(token=access_token, expires_on=decoded_token["exp"])
            # user_ai_project = AIProjectClient(
            #     credential=simple_token_credential,
            #     endpoint=request.app.state.proj_endpoint,
            #     api_version = "2025-05-15-preview" # Evaluations yet not supported on stable (api_version="2025-05-01")
            # )
            # logger.info("Created User AIProjectClient")
            # request.state.user_ai_project = user_ai_project

            # # When authentication is enabled it is assumed the Agent is already created
            # user_agent = user_ai_project.agents.get_agent(request.app.state.agent_id)
            # request.state.user_agent = user_agent

            response = await call_next(request)
            return response

    app.mount("/static", StaticFiles(directory=directory), name="static")
    
    # Mount React static files
    # Uncomment the following lines if you have a React frontend
    # react_directory = os.path.join(os.path.dirname(__file__), "static/react")
    # app.mount("/static/react", StaticFiles(directory=react_directory), name="react")

    from . import routes  # Import routes
    app.include_router(routes.router)

    # Global exception handler for any unhandled exceptions
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception occurred", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )
    
    return app
