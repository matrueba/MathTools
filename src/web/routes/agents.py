"""Agent provider routes: what providers exist and their headline metrics."""

from fastapi import APIRouter, HTTPException

from ..data import DataStore


class AgentsRouter:
    """
    GET /agents — every provider, with metrics across all tracked projects.
    GET /projects/{id}/agents — one project's sessions, grouped by provider.
    """

    def __init__(self, data_store: DataStore):
        self.data_store = data_store
        self.router = APIRouter()
        self.router.add_api_route("/agents", self.list_agents, methods=["GET"])
        self.router.add_api_route(
            "/projects/{project_id}/agents", self.project_agents, methods=["GET"]
        )

    def list_agents(self) -> dict:
        """Providers the UI can offer, each with its own dashboard-style metrics."""
        return self.data_store.agents_overview()

    def project_agents(self, project_id: str) -> dict:
        """The project's sessions, grouped by the agent that ran them."""
        project = self.data_store.find_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
        sessions, _ = self.data_store.project_sessions(project)
        return {
            "projectId": project_id,
            "agents": self.data_store.group_by_provider(sessions),
        }
