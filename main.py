from fastapi import FastAPI

from dice import roll_cyberpunk_check
from models import CheckRollRequest, CheckRollResult, HealthResponse


app = FastAPI(
    title="Cyberpunk TRPG Assistant",
    description="Local FastAPI backend for Cyberpunk-style TRPG tools.",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="cyberpunk-trpg")


@app.get("/")
def index() -> dict:
    return {
        "name": "Cyberpunk TRPG Assistant",
        "docs": "/docs",
        "health": "/health",
        "roll_check": "POST /api/rolls/check",
    }


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
