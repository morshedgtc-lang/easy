from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from app.utils.auth import decode_access_token
from app.utils.ws_manager import ws_manager

router = APIRouter(tags=["ws"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token", "")
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub", 0))
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)
