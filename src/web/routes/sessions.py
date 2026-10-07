"""
Session routes, nested under the project and agent that own them.

There is no flat, cross-project session list: a session is only reachable as
/projects/{project_id}/agents/{agent_id}/sessions/{session_id}, so every
lookup is scoped and an id from another project or agent is a 404.
"""

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..data import DataStore
from ..runners.claude import (
    DEFAULT_PERMISSION_MODE,
    PERMISSION_MODES,
    ClaudeRunner,
    SessionBusyError,
)
from ..serializers import serialize_message, serialize_session, summarize_sessions

BASE = "/projects/{project_id}"


class PromptRequest(BaseModel):
    prompt: str
    permissionMode: str = DEFAULT_PERMISSION_MODE


class SessionsRouter:
    """/projects/{id}/agents[/{agent}/sessions[/{session}[/messages|/prompt]]]."""

    def __init__(self, data_store: DataStore, claude_runner: ClaudeRunner | None = None):
        self.data_store = data_store
        self.claude_runner = claude_runner or ClaudeRunner()
        self.router = APIRouter()
        self.router.add_api_route(
            f"{BASE}/agents/{{agent_id}}/sessions",
            self.agent_sessions,
            methods=["GET"],
        )
        self.router.add_api_route(
            f"{BASE}/agents/{{agent_id}}/sessions/{{session_id}}",
            self.session_detail,
            methods=["GET"],
        )
        self.router.add_api_route(
            f"{BASE}/agents/{{agent_id}}/sessions/{{session_id}}/messages",
            self.session_messages,
            methods=["GET"],
        )
        self.router.add_api_route(
            f"{BASE}/agents/{{agent_id}}/sessions/{{session_id}}/interactions",
            self.session_interactions,
            methods=["GET"],
        )
        self.router.add_api_route(
            f"{BASE}/agents/{{agent_id}}/sessions/{{session_id}}/history",
            self.session_history,
            methods=["GET"],
        )
        self.router.add_api_route(
            f"{BASE}/agents/{{agent_id}}/sessions/{{session_id}}/prompt",
            self.session_prompt,
            methods=["POST"],
        )

    # ── Lookups shared by every route ──────────────────────────────────────
    def _project(self, project_id: str) -> dict:
        project = self.data_store.find_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
        return project

    def _agent(self, agent_id: str) -> dict:
        agent = self.data_store.find_agent(agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        return agent

    def _session(self, project_id: str, agent_id: str, session_id: str) -> dict:
        project, agent = self._project(project_id), self._agent(agent_id)
        sessions, _ = self.data_store.project_sessions(project)
        for s in sessions:
            if s.get("SessionId") == session_id and s.get("AI") == agent["tag"]:
                return s
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found for {agent_id} in {project_id}",
        )

    # ── Routes ─────────────────────────────────────────────────────────────
    def agent_sessions(self, project_id: str, agent_id: str) -> dict:
        """One agent's sessions in this project, most recent first."""
        project, agent = self._project(project_id), self._agent(agent_id)
        sessions, _ = self.data_store.project_sessions(project)
        owned = sorted(
            (s for s in sessions if s.get("AI") == agent["tag"]),
            key=lambda s: s.get("mtime", 0),
            reverse=True,
        )
        return {
            "projectId": project_id,
            "agentId": agent_id,
            "stats": summarize_sessions(owned),
            "sessions": [serialize_session(s) for s in owned],
        }

    def session_detail(self, project_id: str, agent_id: str, session_id: str) -> dict:
        return serialize_session(self._session(project_id, agent_id, session_id))

    def session_messages(self, project_id: str, agent_id: str, session_id: str) -> dict:
        """Chat transcript for one session."""
        self._session(project_id, agent_id, session_id)
        return {
            "sessionId": session_id,
            "messages": [
                serialize_message(m) for m in self.data_store.load_chat(session_id)
            ],
        }

    def session_interactions(self, project_id: str, agent_id: str, session_id: str) -> dict:
        """The agent → subagent graph of one session (mock-backed for now)."""
        self._session(project_id, agent_id, session_id)
        return self.data_store.load_interactions(agent_id, session_id)

    def session_history(self, project_id: str, agent_id: str, session_id: str) -> dict:
        """
        The session's conversation so far, in the chat event vocabulary, so the
        Agent tab can show it before (or instead of) continuing the session.
        """
        session = self._session(project_id, agent_id, session_id)
        events = self.data_store.load_history(agent_id, session_id)
        if events is None:
            raise HTTPException(status_code=501, detail=f"History for {agent_id} is not supported yet")
        return {"sessionId": session_id, "live": bool(session.get("PIDs")), "events": events}

    async def session_prompt(
        self, project_id: str, agent_id: str, session_id: str, body: PromptRequest
    ) -> StreamingResponse:
        """
        Send a prompt to the session's agent and stream its turn back.

        The response is NDJSON — one UI event per line, see `runners/claude.py`
        — so the browser can render the turn while it runs. Only Claude Code
        can be driven so far.
        """
        session = self._session(project_id, agent_id, session_id)
        if agent_id != "claude":
            raise HTTPException(status_code=501, detail=f"Prompting {agent_id} is not supported yet")
        prompt = body.prompt.strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt is empty")
        if body.permissionMode not in PERMISSION_MODES:
            raise HTTPException(
                status_code=400, detail=f"Unknown permission mode {body.permissionMode!r}"
            )
        # Open in a terminal or editor: a second writer would fork the session
        # or interleave turns with the person using it there.
        if session.get("PIDs"):
            raise HTTPException(
                status_code=409,
                detail="This session is open in another Claude Code client; close it there first",
            )
        # Checked here as well as in the runner so a busy session is a clean
        # 409 instead of a stream that fails after the headers went out.
        if self.claude_runner.is_running(session_id):
            raise HTTPException(status_code=409, detail="This session is already running a prompt")

        cwd = session.get("ProjectPath") or self.data_store.find_project(project_id)["path"]

        async def lines():
            try:
                async for event in self.claude_runner.stream(
                    session_id, cwd, prompt, body.permissionMode
                ):
                    yield json.dumps(event) + "\n"
            except SessionBusyError:
                yield json.dumps(
                    {"type": "error", "message": "This session is already running a prompt"}
                ) + "\n"

        return StreamingResponse(lines(), media_type="application/x-ndjson")
