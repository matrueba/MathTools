"""
FastAPI backend for the MathTools web dashboard.

Data is mocked for now (see `mock_data.py`); the route handlers already speak
the monitoring session contract, so wiring in the real `ClaudeSource` later
means swapping `DataStore.load_sessions` and nothing else — see `data.py`.

Routes are grouped by resource under `routes/`, each a small class that
registers its own endpoints in `__init__` (constructor) and implements each
one as a method — the FastAPI equivalent of an Express Router. `create_app()`
only wires those routers together; it holds no route logic of its own.
"""

from constants.general import VERSION
from constants.web import DEV_ORIGINS, WEB_HOST, WEB_PORT

from .data import DataStore
from .paths import repo_root
from .routes import AgentsRouter, HealthRouter, ProjectsRouter, SessionsRouter
from .spa import mount_frontend

# Re-exported: tests and other modules import path resolution through here.
_repo_root = repo_root


def create_app():
    """Build the FastAPI application by wiring up each resource's router."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(
        title="MathTools Agent Control",
        version=VERSION,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    # The Vite dev server runs on its own origin during development.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # One DataStore instance shared by every router, so a per-request cache
    # (once there is a real backing store) only has to live in one place.
    data_store = DataStore()
    routers = [
        HealthRouter(),
        AgentsRouter(data_store),
        ProjectsRouter(data_store),
        SessionsRouter(data_store),
    ]
    for router in routers:
        app.include_router(router.router, prefix="/api")

    # Serve the built frontend when it exists. In development you run the
    # Vite dev server instead, which proxies /api back here.
    mount_frontend(app, repo_root())

    return app


class WebDashboard:
    """Launches the dashboard from the `mathtools` main menu."""

    def __init__(self, host: str = WEB_HOST, port: int = WEB_PORT):
        self.host = host
        self.port = port

    def run_web_dashboard(self) -> None:
        from utils.ui import console

        try:
            import uvicorn
        except ImportError:
            console.print(
                "\n[bold red]✗ Web dependencies are not installed.[/]\n"
                "  Install them with: [bold]pip install 'matrueba-sdd-installer[web]'[/]"
            )
            return

        from constants.web import FRONTEND_DIST_DIR

        dist_dir = repo_root() / FRONTEND_DIST_DIR
        url = f"http://{self.host}:{self.port}"

        console.print(f"\n[bold bright_magenta]🌐  Agent Control Dashboard[/]")
        console.print(f"[dim]   API:[/] [bright_cyan]{url}/api/docs[/]")

        if dist_dir.is_dir():
            console.print(f"[dim]   UI :[/] [bright_cyan]{url}[/]")
        else:
            console.print(
                f"[dim]   UI :[/] [yellow]frontend not built[/] "
                f"[dim]— run `npm install && npm run build` in src/frontend,[/]\n"
                f"[dim]        or `npm run dev` for the Vite dev server on :5173[/]"
            )

        console.print("[dim]   Press Ctrl+C to stop.[/]\n")

        try:
            uvicorn.run(create_app(), host=self.host, port=self.port, log_level="warning")
        except KeyboardInterrupt:
            console.print("\n[dim]Dashboard stopped.[/]")


# `uvicorn web.server:app --reload` for backend-only development.
def __getattr__(name):
    if name == "app":
        return create_app()
    raise AttributeError(name)
