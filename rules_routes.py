from fastapi import APIRouter

from rules_loader import (
    load_combat_actions,
    load_cover_hp,
    load_difficulty_values,
    load_ranged_dv,
    load_skills,
    load_stats,
)


router = APIRouter(prefix="/api/rules", tags=["规则"])


@router.get("")
def get_rules_index() -> dict[str, str]:
    return {
        "stats": "/api/rules/stats",
        "skills": "/api/rules/skills",
        "difficulty_values": "/api/rules/difficulty-values",
        "ranged_dv": "/api/rules/ranged-dv",
        "cover": "/api/rules/cover",
        "combat_actions": "/api/rules/combat-actions",
    }


@router.get("/stats")
def get_stats() -> list[dict]:
    return load_stats()


@router.get("/skills")
def get_skills() -> list[dict]:
    return load_skills()


@router.get("/difficulty-values")
def get_difficulty_values() -> list[dict]:
    return load_difficulty_values()


@router.get("/ranged-dv")
def get_ranged_dv() -> list[dict]:
    return load_ranged_dv()


@router.get("/cover")
def get_cover_hp() -> list[dict]:
    return load_cover_hp()


@router.get("/combat-actions")
def get_combat_actions() -> list[dict]:
    return load_combat_actions()
