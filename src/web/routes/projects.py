"""
Project routes: repositories, their sessions grouped by provider, and harness
state (skills/agents/commands the installer has deployed into each one).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from constants.environments import ENVIRONMENTS
from constants.web import AGENT_PROVIDERS

from ..data import DataStore, InvalidProjectError
from ..db import DuplicateProjectError
from ..serializers import serialize_harness


class ProjectCreate(BaseModel):
    """Body of POST /projects. `name` defaults to the repository folder name."""

    path: str
    name: str | None = None


class ProjectsRouter:
    """
    /projects — git repositories with agent activity.

    Also owns /projects/{id}/harness: what the installer has deployed into a
    project, per provider, and a (simulated) install/update action.
    """

    def __init__(self, data_store: DataStore):
        self.data_store = data_store
        self.router = APIRouter()
        self.router.add_api_route("/projects", self.list_projects, methods=["GET"])
        self.router.add_api_route(
            "/projects", self.create_project, methods=["POST"], status_code=201
        )
        self.router.add_api_route(
            "/projects/{project_id}", self.project_detail, methods=["GET"]
        )
        self.router.add_api_route(
            "/projects/{project_id}/harness", self.project_harness, methods=["GET"]
        )
        self.router.add_api_route(
            "/projects/{project_id}/harness/{provider_id}",
            self.install_harness,
            methods=["POST"],
        )

    def list_projects(self) -> dict:
        """Git repositories with the agent sessions running inside them."""
        return {"projects": self.data_store.get_projects()}

    def create_project(self, payload: ProjectCreate) -> dict:
        """Register a local git repository as a tracked project."""
        try:
            return self.data_store.register_project(payload.path, payload.name)
        except InvalidProjectError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except DuplicateProjectError as exc:
            raise HTTPException(
                status_code=409, detail="A project with that name or path already exists"
            ) from exc

    def project_detail(self, project_id: str) -> dict:
        """
        One project with its sessions nested under the agent that ran them —
        the same `agents` payload as /projects/{id}/agents, inlined so the
        project page needs a single request.
        """
        project = self.data_store.find_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

        return self.data_store.project_detail(project)

    def project_harness(self, project_id: str) -> dict:
        """
        Skills, agents and commands deployed into this project, per provider.

        Every provider is listed — installed or not — so the UI can offer to
        install the missing ones.
        """
        project = self.data_store.find_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

        installed = self.data_store.load_harness(project["path"])

        return {
            "projectId": project_id,
            "projectPath": project["path"],
            "providers": [
                serialize_harness(
                    provider,
                    installed.get(provider["id"]),
                    ENVIRONMENTS.get(provider["env"]) if provider.get("env") else None,
                )
                for provider in AGENT_PROVIDERS
            ],
        }

    def install_harness(
        self, project_id: str, provider_id: str, payload: dict | None = None
    ) -> dict:
        """
        Install or update a provider's harness in this project.

        NOT WIRED UP: this reports what the installer *would* do and changes
        nothing on disk. Running it for real means calling `download_repo_zips()` and
        `extract_environment()` from `web/installer.py` with the selected
        environment, scope and components.
        """
        project = self.data_store.find_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

        provider = next((p for p in AGENT_PROVIDERS if p["id"] == provider_id), None)
        if provider is None:
            raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")

        env = ENVIRONMENTS.get(provider["env"]) if provider.get("env") else None
        if env is None:
            raise HTTPException(
                status_code=400,
                detail=f"{provider['label']} has no installable environment",
            )

        payload = payload or {}
        scope = payload.get("scope", "local")
        components = payload.get("components") or [
            dest_subpath for _, _, dest_subpath, _ in env["sources"]
        ]

        target = (
            env["global_dir"] if scope == "global"
            else f"{project['path']}/{env['target_dir']}"
        )

        return {
            "status": "simulated",
            "applied": False,
            "detail": "Mock backend — nothing was written to disk.",
            "projectId": project_id,
            "provider": provider_id,
            "scope": scope,
            "target": target,
            "components": components,
        }
