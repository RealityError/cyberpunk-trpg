from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from characters import router as characters_router
from dice import roll_cyberpunk_check
from models import CheckRollRequest, CheckRollResult, HealthResponse
from rules_routes import router as rules_router
from sessions import router as sessions_router


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

app = FastAPI(
    title="赛博朋克 TRPG 助手",
    description="用于本地跑团辅助的 FastAPI 后端。",
    version="0.1.0",
)

app.include_router(characters_router)
app.include_router(rules_router)
app.include_router(sessions_router)

app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="cyberpunk-trpg")


@app.get("/")
def index() -> dict:
    return {
        "name": "赛博朋克 TRPG 助手",
        "ui": "/ui",
        "docs": "/docs",
        "health": "/health",
        "roll_check": "POST /api/rolls/check",
        "characters": "/api/characters",
        "rules": "/api/rules",
        "sessions": "/api/sessions",
    }


@app.get("/ui", response_class=FileResponse)
def ui() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.post("/api/rolls/check", response_model=CheckRollResult)
def roll_check(payload: CheckRollRequest) -> CheckRollResult:
    result = roll_cyberpunk_check(
        stat=payload.stat,
        skill=payload.skill,
        modifier=payload.modifier,
    )
    success = None if payload.dv is None else result["total"] >= payload.dv

    return CheckRollResult(
        label=payload.label,
        dv=payload.dv,
        success=success,
        **result,
    )
