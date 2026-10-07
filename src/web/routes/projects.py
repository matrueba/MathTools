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
from ..harness import SCOPES, HarnessError, install_harness
from ..serializers import serialize_harness


class HarnessInstall(BaseModel):
    """Body of POST /projects/{id}/harness/{provider}. Defaults: local, every component."""

    scope: str = "local"
    components: list[str] | None = None


class ProjectCreate(BaseModel):
    """Body of POST /projects. `name` defaults to the repository folder name."""

    path: str
    name: str | None = None


class ProjectsRouter:
    """
    /projects — git repositories with agent activity.

    Also owns /projects/{id}/harness: what is deployed into a project, per
    provider, read from disk, and the install/update action that deploys it.
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

        found = self.data_store.load_harness(project["path"])

        providers = []
        for provider in AGENT_PROVIDERS:
            state = found.get(provider["id"]) or {}
            providers.append(serialize_harness(
                provider,
                state.get("detected"),
                ENVIRONMENTS.get(provider["env"]) if provider.get("env") else None,
                state.get("existing"),
                state.get("roots"),
            ))
        return {"projectId": project_id, "projectPath": project["path"], "providers": providers}

    def install_harness(
        self, project_id: str, provider_id: str, payload: HarnessInstall | None = None
    ) -> dict:
        """
        Install or update a provider's harness in this project.

        Downloads the framework repositories from GitHub and writes the chosen
        components (see harness.py). A plain `def`, so FastAPI runs it in its
        threadpool and the download does not block the event loop.
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

        payload = payload or HarnessInstall()
        if payload.scope not in SCOPES:
            raise HTTPException(status_code=400, detail=f"Unknown scope {payload.scope!r}")
        supported = [dest for _, _, dest, _ in env["sources"]]
        components = payload.components or supported
        unknown = [c for c in components if c not in supported]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"{provider['label']} has no component {', '.join(unknown)}",
            )

        try:
            result = install_harness(provider["env"], payload.scope, components, project["path"])
        except HarnessError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return {
            "status": "installed",
            "projectId": project_id,
            "provider": provider_id,
            "scope": payload.scope,
            "target": result["root"],
            "components": components,
            "written": len(result["written"]),
            "removed": result["removed"],
        }
