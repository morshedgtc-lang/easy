import json
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: dict[int, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self._connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int):
        ws_list = self._connections.get(user_id, [])
        if websocket in ws_list:
            ws_list.remove(websocket)
        if not self._connections.get(user_id):
            self._connections.pop(user_id, None)

    async def broadcast(self, event_type: str, data: dict[str, Any]):
        payload = {"type": event_type, "timestamp": datetime.now(timezone.utc).isoformat(), "data": data}
        msg = json.dumps(payload, default=str)
        stale = []
        for uid, ws_list in self._connections.items():
            for ws in ws_list:
                try:
                    await ws.send_text(msg)
                except Exception:
                    stale.append((uid, ws))
        for uid, ws in stale:
            self.disconnect(ws, uid)


ws_manager = ConnectionManager()
