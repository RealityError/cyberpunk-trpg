from pydantic import BaseModel, Field


class CheckRollRequest(BaseModel):
    label: str = Field(default="check", min_length=1, max_length=80)
    stat: int = Field(ge=0, le=20)
    skill: int = Field(ge=0, le=20)
    modifier: int = Field(default=0, ge=-20, le=20)
    dv: int | None = Field(default=None, ge=0, le=50)


class CheckRollResult(BaseModel):
    label: str
    base_roll: int
    extra_roll: int | None
    critical: str | None
    stat: int
    skill: int
    modifier: int
    total: int
    dv: int | None
    success: bool | None


class HealthResponse(BaseModel):
    status: str
    service: str
