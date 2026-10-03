"""Agent provider routes: what providers exist and their headline metrics."""

from fastapi import APIRouter

from constants.web import AGENT_PROVIDERS

from ..data import DataStore
from ..serializers import summarize_sessions


class AgentsRouter:
    """GET /agents — every provider, each with its own dashboard-style metrics."""

    def __init__(self, data_store: DataStore):
        self.data_store = data_store
        self.router = APIRouter()
        self.router.add_api_route("/agents", self.list_agents, methods=["GET"])

    def list_agents(self) -> dict:
        """
        Providers the UI can offer, each with its own dashboard-style metrics.

        A provider with no sessions still reports a zeroed stats block, so the
        UI renders the same layout for every card.
        """
        sessions, _ = self.data_store.load_sessions()

        result = []
        for provider in AGENT_PROVIDERS:
            owned = [s for s in sessions if s.get("AI") == provider["tag"]]
            result.append({
                **provider,
                "sessionCount": len(owned),
                "stats": summarize_sessions(owned),
            })

        return {"agents": result}
