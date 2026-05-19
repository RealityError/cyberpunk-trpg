from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from dice import roll_cyberpunk_check
from models import (
    Character,
    CharacterCheckRollResult,
    CharacterArmorRequest,
    CharacterConditionRemoveRequest,
    CharacterConditionRequest,
    CharacterCreate,
    CharacterDamageRequest,
    CharacterHealRequest,
    CharacterInventoryRequest,
    CharacterMoneyRequest,
    CharacterResourceRequest,
    CharacterRollRequest,
    CharacterStateChangeResult,
    CharacterUpdate,
    Condition,
    InventoryItem,
)
from rules_loader import resolve_character_skill, resolve_character_stat, resolve_stat_for_skill
from storage import CHARACTERS_FILE, read_json, write_json


router = APIRouter(prefix="/api/characters", tags=["角色"])


def _load_characters() -> dict[str, dict]:
    return read_json(CHARACTERS_FILE, default={})


def _save_characters(characters: dict[str, dict]) -> None:
    write_json(CHARACTERS_FILE, characters)


def _get_character(characters: dict[str, dict], character_id: str) -> Character:
    raw = characters.get(character_id)
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到角色：{character_id}",
        )

    return Character(**raw)


def _store_character(character: Character) -> None:
    characters = _load_characters()
    characters[character.id] = character.model_dump()
    _save_characters(characters)


def apply_damage(character_id: str, payload: CharacterDamageRequest) -> Character:
    characters = _load_characters()
    character = _get_character(characters, character_id)
    data = character.model_dump()
    armor_sp = data["armor_sp"]
    damage_after_armor = payload.amount if payload.ignore_armor else max(payload.amount - armor_sp, 0)
    old_hp = data["current_hp"]
    data["current_hp"] = max(payload.minimum_hp, old_hp - damage_after_armor)
    if payload.ablate_armor and damage_after_armor > 0 and armor_sp > 0 and not payload.ignore_armor:
        data["armor_sp"] = armor_sp - 1

    updated = Character(**data)
    characters[character_id] = updated.model_dump()
    _save_characters(characters)
    return updated


def apply_heal(character_id: str, payload: CharacterHealRequest) -> Character:
    characters = _load_characters()
    character = _get_character(characters, character_id)
    data = character.model_dump()
    data["current_hp"] = min(data["max_hp"], data["current_hp"] + payload.amount)
    updated = Character(**data)
    characters[character_id] = updated.model_dump()
    _save_characters(characters)
    return updated


def adjust_armor(character_id: str, payload: CharacterArmorRequest) -> Character:
    characters = _load_characters()
    character = _get_character(characters, character_id)
    data = character.model_dump()
    data["armor_sp"] = max(0, min(50, data["armor_sp"] + payload.amount))
    updated = Character(**data)
    characters[character_id] = updated.model_dump()
    _save_characters(characters)
    return updated


def add_condition(character_id: str, payload: CharacterConditionRequest) -> Character:
    characters = _load_characters()
    character = _get_character(characters, character_id)
    data = character.model_dump()
    conditions = [
        condition
        for condition in data["conditions"]
        if condition["name"] != payload.condition.name
    ]
    conditions.append(payload.condition.model_dump())
    data["conditions"] = conditions
    updated = Character(**data)
    characters[character_id] = updated.model_dump()
    _save_characters(characters)
    return updated


def remove_condition(character_id: str, payload: CharacterConditionRemoveRequest) -> Character:
    characters = _load_characters()
    character = _get_character(characters, character_id)
    data = character.model_dump()
    data["conditions"] = [
        condition
        for condition in data["conditions"]
        if condition["name"] != payload.name
    ]
    updated = Character(**data)
    characters[character_id] = updated.model_dump()
    _save_characters(characters)
    return updated


def adjust_money(character_id: str, payload: CharacterMoneyRequest) -> Character:
    characters = _load_characters()
    character = _get_character(characters, character_id)
    data = character.model_dump()
    data["eurobucks"] = max(0, data["eurobucks"] + payload.amount)
    updated = Character(**data)
    characters[character_id] = updated.model_dump()
    _save_characters(characters)
    return updated


def add_inventory_item(character_id: str, payload: CharacterInventoryRequest) -> Character:
    characters = _load_characters()
    character = _get_character(characters, character_id)
    data = character.model_dump()
    inventory = data["inventory"]
    for item in inventory:
        if item["name"] == payload.name:
            item["quantity"] += payload.quantity
            if payload.notes:
                item["notes"] = payload.notes
            break
    else:
        inventory.append(InventoryItem(**payload.model_dump()).model_dump())

    data["inventory"] = inventory
    updated = Character(**data)
    characters[character_id] = updated.model_dump()
    _save_characters(characters)
    return updated


def remove_inventory_item(character_id: str, payload: CharacterInventoryRequest) -> Character:
    characters = _load_characters()
    character = _get_character(characters, character_id)
    data = character.model_dump()
    inventory = []
    remaining_to_remove = payload.quantity
    for item in data["inventory"]:
        if item["name"] != payload.name:
            inventory.append(item)
            continue

        original_quantity = item["quantity"]
        removed_quantity = min(original_quantity, remaining_to_remove)
        kept_quantity = original_quantity - removed_quantity
        if kept_quantity > 0:
            item["quantity"] = kept_quantity
            inventory.append(item)
        remaining_to_remove = max(0, remaining_to_remove - removed_quantity)

    data["inventory"] = inventory
    updated = Character(**data)
    characters[character_id] = updated.model_dump()
    _save_characters(characters)
    return updated


def adjust_resource(character_id: str, payload: CharacterResourceRequest) -> Character:
    characters = _load_characters()
    character = _get_character(characters, character_id)
    data = character.model_dump()
    if payload.name == "死亡豁免惩罚":
        data["death_save_penalty"] = max(0, min(20, data["death_save_penalty"] + payload.amount))
    elif payload.name == "人性":
        current = data["humanity"] if data["humanity"] is not None else 0
        data["humanity"] = max(0, min(100, current + payload.amount))
    elif payload.name == "幸运":
        current = data["luck_current"]
        if current is None:
            current = character.stats.get("LUCK", character.stats.get("幸运", 0))
        data["luck_current"] = max(0, min(20, current + payload.amount))
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"未知资源：{payload.name}",
        )

    updated = Character(**data)
    characters[character_id] = updated.model_dump()
    _save_characters(characters)
    return updated


@router.get("", response_model=list[Character])
def list_characters() -> list[Character]:
    characters = _load_characters()
    result = [Character(**raw) for raw in characters.values()]
    return sorted(result, key=lambda character: character.name.casefold())


@router.post("", response_model=Character, status_code=status.HTTP_201_CREATED)
def create_character(payload: CharacterCreate) -> Character:
    characters = _load_characters()
    data = payload.model_dump()
    if data["current_hp"] is None:
        data["current_hp"] = data["max_hp"]

    character = Character(id=uuid4().hex, **data)
    characters[character.id] = character.model_dump()
    _save_characters(characters)
    return character


@router.get("/{character_id}", response_model=Character)
def get_character(character_id: str) -> Character:
    characters = _load_characters()
    return _get_character(characters, character_id)


@router.put("/{character_id}", response_model=Character)
def update_character(character_id: str, payload: CharacterUpdate) -> Character:
    characters = _load_characters()
    character = _get_character(characters, character_id)
    data = character.model_dump()

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if value is not None:
            data[key] = value

    if data["current_hp"] > data["max_hp"]:
        data["current_hp"] = data["max_hp"]

    updated = Character(**data)
    characters[character_id] = updated.model_dump()
    _save_characters(characters)
    return updated


@router.delete("/{character_id}")
def delete_character(character_id: str) -> dict:
    characters = _load_characters()
    _get_character(characters, character_id)
    del characters[character_id]
    _save_characters(characters)
    return {"deleted": character_id}


@router.post("/{character_id}/roll", response_model=CharacterCheckRollResult)
def roll_character_check(
    character_id: str,
    payload: CharacterRollRequest,
) -> CharacterCheckRollResult:
    characters = _load_characters()
    character = _get_character(characters, character_id)
    resolved_skill_name, skill = resolve_character_skill(character.skills, payload.skill_name)

    if payload.stat_name:
        resolved_stat_name, stat = resolve_character_stat(character.stats, payload.stat_name)
    else:
        stat_rule = resolve_stat_for_skill(payload.skill_name)
        if stat_rule is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"技能未录入规则，无法自动匹配属性：{payload.skill_name}",
            )
        resolved_stat_name, stat = resolve_character_stat(character.stats, stat_rule["name"])

    result = roll_cyberpunk_check(
        stat=stat,
        skill=skill,
        modifier=payload.modifier,
    )
    success = None if payload.dv is None else result["total"] >= payload.dv

    return CharacterCheckRollResult(
        label=f"{resolved_stat_name}+{resolved_skill_name}",
        character_id=character.id,
        character_name=character.name,
        stat_name=resolved_stat_name,
        skill_name=resolved_skill_name,
        dv=payload.dv,
        success=success,
        **result,
    )
