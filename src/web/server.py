"""
FastAPI backend for the MathTools web dashboard.

Data is mocked for now (see `mock_data.py`); the route handlers already speak
the monitoring session contract, so wiring in the real `ClaudeSource` later
means swapping `DataStore.load_agent_sessions` and nothing else — see `data.py`.

Routes are grouped by resource under `routes/`, each a small class that
registers its own endpoints in `__init__` (constructor) and implements each
one as a method — the FastAPI equivalent of an Express Router. `create_app()`
only wires those routers together; it holds no route logic of its own.
"""

from constants.general import VERSION
from constants.web import DB_PATH, DEV_ORIGINS, WEB_HOST, WEB_PORT, FRONTEND_DIST_DIR
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging


from .data import DataStore
from .events import EventHub
from .db import Database, ProjectStore
from .paths import repo_root
from .routes import (
    AgentsRouter,
    EventsRouter,
    FilesystemRouter,
    HealthRouter,
    ProjectsRouter,
    SessionsRouter,
)
from .spa import mount_frontend



def create_app(db_path: str | None = None):
    """
    Build the FastAPI application by wiring up each resource's router.

    `db_path` overrides DB_PATH so tests can point at a throwaway file.
    """

    app = FastAPI(
        title="MathTools Agent Management",
        version=VERSION,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # One DataStore instance shared by every router, so a per-request cache
    # (once there is a real backing store) only has to live in one place.
    database = Database(db_path or DB_PATH)
    database.init_schema()
    data_store = DataStore(ProjectStore(database))
    # Exposed so tests can reach the store the routes actually use.
    app.state.data_store = data_store
    app.state.event_hub = EventHub(data_store)
    routers = [
        HealthRouter(),
        AgentsRouter(data_store),
        ProjectsRouter(data_store),
        SessionsRouter(data_store),
        EventsRouter(app.state.event_hub),
        FilesystemRouter(),
    ]
    for router in routers:
        app.include_router(router.router, prefix="/api")

    # Serve the built frontend when it exists. In development you run the
    # Vite dev server instead, which proxies /api back here.
    mount_frontend(app, repo_root())

    return app


class _Server(uvicorn.Server):
    """uvicorn.Server that ends the live-update streams as soon as it is told to stop."""

    def __init__(self, config: uvicorn.Config, hub: EventHub):
        super().__init__(config)
        self.hub = hub

    def handle_exit(self, sig, frame) -> None:
        self.hub.close()
        super().handle_exit(sig, frame)


class MathToolsServer:
    """Launches the dashboard; this is what the `mathtools` command runs."""

    def __init__(self, host: str = WEB_HOST, port: int = WEB_PORT):
        self.host = host
        self.port = port

    def run_server(self) -> None:
        app = create_app()
        config = uvicorn.Config(
            app,
            host=self.host,
            port=self.port,
            log_level="warning",
            # Backstop for responses that are not SSE streams, such as an
            # agent turn still streaming: they get this long to finish.
            timeout_graceful_shutdown=2,
        )
        try:
            _Server(config, app.state.event_hub).run()
        except KeyboardInterrupt:
            logging.error("Dashboard stopped.")


# `uvicorn web.server:app --reload` for backend-only development.
def __getattr__(name):
    if name == "app":
        return create_app()
    raise AttributeError(name)
