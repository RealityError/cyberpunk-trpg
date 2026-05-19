import json
from functools import lru_cache
from pathlib import Path
from typing import Any


RULES_DIR = Path(__file__).resolve().parent / "rules"


def _load_rule_file(filename: str) -> list[dict[str, Any]]:
    path = RULES_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_name(name: str) -> str:
    return name.strip().casefold()


def _match_entry_name(entry: dict[str, Any], name: str) -> bool:
    normalized_name = _normalize_name(name)
    candidates = [entry.get("name", ""), *entry.get("aliases", [])]
    return any(_normalize_name(candidate) == normalized_name for candidate in candidates)


def _resolve_value(values: dict[str, int], candidates: list[str]) -> int:
    for candidate in candidates:
        if candidate in values:
            return values[candidate]

    normalized_values = {
        _normalize_name(key): value
        for key, value in values.items()
    }
    for candidate in candidates:
        value = normalized_values.get(_normalize_name(candidate))
        if value is not None:
            return value

    return 0


@lru_cache
def load_stats() -> list[dict[str, Any]]:
    return _load_rule_file("stats.json")


@lru_cache
def load_skills() -> list[dict[str, Any]]:
    return _load_rule_file("skills.json")


@lru_cache
def load_difficulty_values() -> list[dict[str, Any]]:
    return _load_rule_file("difficulty_values.json")


@lru_cache
def load_ranged_dv() -> list[dict[str, Any]]:
    return _load_rule_file("ranged_dv.json")


@lru_cache
def load_cover_hp() -> list[dict[str, Any]]:
    return _load_rule_file("cover_hp.json")


@lru_cache
def load_combat_actions() -> list[dict[str, Any]]:
    return _load_rule_file("combat_actions.json")


def find_stat(name: str) -> dict[str, Any] | None:
    for stat in load_stats():
        if _match_entry_name(stat, name):
            return stat
    return None


def find_skill(name: str) -> dict[str, Any] | None:
    for skill in load_skills():
        if _match_entry_name(skill, name):
            return skill
    return None


def get_stat_by_id(stat_id: str) -> dict[str, Any] | None:
    for stat in load_stats():
        if stat.get("id") == stat_id:
            return stat
    return None


def resolve_stat_for_skill(skill_name: str) -> dict[str, Any] | None:
    skill = find_skill(skill_name)
    if skill is None:
        return None
    return get_stat_by_id(skill["stat_id"])


def resolve_character_stat(character_stats: dict[str, int], stat_name: str) -> tuple[str, int]:
    stat = find_stat(stat_name)
    display_name = stat["name"] if stat is not None else stat_name
    candidates = [stat_name]
    if stat is not None:
        candidates = [stat["name"], *stat.get("aliases", []), stat_name]
    return display_name, _resolve_value(character_stats, candidates)


def resolve_character_skill(character_skills: dict[str, int], skill_name: str) -> tuple[str, int]:
    skill = find_skill(skill_name)
    display_name = skill["name"] if skill is not None else skill_name
    candidates = [skill_name]
    if skill is not None:
        candidates = [skill["name"], *skill.get("aliases", []), skill_name]
    return display_name, _resolve_value(character_skills, candidates)
