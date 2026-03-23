from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from app.core.settings import get_frontend_dist_path

web_router = APIRouter()


def _frontend_index_path() -> Path:
    return get_frontend_dist_path() / "index.html"


def _has_frontend_build() -> bool:
    return _frontend_index_path().exists()


def _react_response() -> Response:
    if _has_frontend_build():
        return FileResponse(_frontend_index_path())
    return HTMLResponse(
        content=(
            "<!doctype html><html><body><h1>Frontend build not available</h1>"
            "<p>Run <code>npm run build</code> in <code>frontend/</code> or use the Vite dev server.</p>"
            "</body></html>"
        ),
        status_code=503,
    )


@web_router.get("/", include_in_schema=False)
def root() -> Response:
    return _react_response()


@web_router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> Response:
    return _react_response()


@web_router.get("/wizard", response_class=HTMLResponse, include_in_schema=False)
def wizard() -> Response:
    return _react_response()


@web_router.get("/wizard/welcome", response_class=HTMLResponse, include_in_schema=False)
def wizard_welcome() -> Response:
    return RedirectResponse(url="/wizard", status_code=307)


@web_router.get("/troubleshooting", response_class=HTMLResponse, include_in_schema=False)
def troubleshooting() -> Response:
    return _react_response()


@web_router.get("/app", response_class=HTMLResponse, include_in_schema=False)
@web_router.get("/app/dashboard", response_class=HTMLResponse, include_in_schema=False)
@web_router.get("/app/wizard", response_class=HTMLResponse, include_in_schema=False)
@web_router.get("/app/troubleshooting", response_class=HTMLResponse, include_in_schema=False)
def react_aliases() -> Response:
    return _react_response()


@web_router.get("/legacy", include_in_schema=False)
def legacy_root() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=307)


@web_router.get("/legacy/wizard/welcome", include_in_schema=False)
def legacy_wizard_welcome() -> RedirectResponse:
    return RedirectResponse(url="/wizard", status_code=307)


@web_router.get("/legacy/dashboard", include_in_schema=False)
def legacy_dashboard() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=307)


@web_router.get("/legacy/troubleshooting", include_in_schema=False)
def legacy_troubleshooting() -> RedirectResponse:
    return RedirectResponse(url="/troubleshooting", status_code=307)
