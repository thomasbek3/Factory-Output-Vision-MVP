from contextlib import asynccontextmanager
import time

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import api_router
from app.api.ws_routes import ws_router
from app.core.logging import configure_logging
from app.core.settings import get_frontend_dist_path
from app.db.database import init_db
from app.services.video_runtime import VideoRuntime
from app.web.routes import web_router
from app.workers.vision_worker import VisionWorker


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging()
        init_db()
        app.state.video_runtime = VideoRuntime()
        app.state.vision_worker = VisionWorker(app.state.video_runtime)
        app.state.started_at = time.time()
        app.state.vision_worker.start()
        try:
            yield
        finally:
            app.state.vision_worker.stop()

    app = FastAPI(title="Factory Vision Output Counter", version="0.1.0", lifespan=lifespan)

    app.include_router(web_router)
    app.include_router(ws_router)
    app.include_router(api_router, prefix="/api")

    frontend_assets_dir = get_frontend_dist_path() / "assets"
    if frontend_assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=frontend_assets_dir), name="frontend-assets")

    return app


app = create_app()
