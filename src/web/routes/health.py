"""Liveness route."""

from fastapi import APIRouter

from constants.general import VERSION


class HealthRouter:
    """GET /health — used by the frontend's error state to tell "backend is down" apart from other failures."""

    def __init__(self):
        self.router = APIRouter()
        self.router.add_api_route("/health", self.health, methods=["GET"])

    def health(self) -> dict:
        return {"status": "ok", "version": VERSION, "mock": True}
