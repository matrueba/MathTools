"""Session routes: the cross-project session list, detail, transcript and stats."""

from fastapi import APIRouter, HTTPException

from ..data import DataStore
from ..serializers import serialize_message, serialize_session, serialize_totals


class SessionsRouter:
    """/sessions and /stats — the flat, cross-project view of agent sessions."""

    def __init__(self, data_store: DataStore):
        self.data_store = data_store
        self.router = APIRouter()
        self.router.add_api_route("/stats", self.stats, methods=["GET"])
        self.router.add_api_route("/sessions", self.list_sessions, methods=["GET"])
        self.router.add_api_route(
            "/sessions/{session_id}", self.session_detail, methods=["GET"]
        )
        self.router.add_api_route(
            "/sessions/{session_id}/messages", self.session_messages, methods=["GET"]
        )

    def stats(self) -> dict:
        """Headline metrics for the dashboard stat row."""
        sessions, totals = self.data_store.load_sessions()
        return serialize_totals(totals, sessions)

    def list_sessions(self) -> dict:
        """All known sessions, most recently active first."""
        raw, _ = self.data_store.load_sessions()
        ordered = sorted(raw, key=lambda s: s.get("mtime", 0), reverse=True)
        return {"sessions": [serialize_session(s) for s in ordered]}

    def session_detail(self, session_id: str) -> dict:
        raw, _ = self.data_store.load_sessions()
        for s in raw:
            if s.get("SessionId") == session_id:
                return serialize_session(s)
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    def session_messages(self, session_id: str) -> dict:
        """Chat transcript for one session."""
        raw, _ = self.data_store.load_sessions()
        if not any(s.get("SessionId") == session_id for s in raw):
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        return {
            "sessionId": session_id,
            "messages": [
                serialize_message(m) for m in self.data_store.load_chat(session_id)
            ],
        }
