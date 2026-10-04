"""GET /events — the dashboard's live-update stream (Server-Sent Events)."""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..events import EventHub


class EventsRouter:
    """One long-lived SSE response per browser tab; see `events.py`."""

    def __init__(self, hub: EventHub):
        self.hub = hub
        self.router = APIRouter()
        self.router.add_api_route("/events", self.events, methods=["GET"])

    async def events(self) -> StreamingResponse:
        return StreamingResponse(
            self.hub.stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                # Stops nginx-style proxies from buffering the stream.
                "X-Accel-Buffering": "no",
            },
        )
