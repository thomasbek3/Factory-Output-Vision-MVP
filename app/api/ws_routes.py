import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

ws_router = APIRouter()


@ws_router.websocket("/ws/metrics")
async def ws_metrics(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            payload = websocket.app.state.vision_worker.get_metrics_payload()
            await websocket.send_json(payload)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return
