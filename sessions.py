from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from agent_runner import (
    AgentConfigurationError,
    AgentRequestError,
    run_gm_agent,
    run_gm_agent_with_tool_results,
)
from combat import calculate_attack_damage
from characters import (
    add_condition,
    add_inventory_item,
    adjust_armor,
    adjust_money,
    adjust_resource,
    apply_damage,
    apply_heal,
    remove_condition,
    remove_inventory_item,
    roll_character_check,
)
from dice import roll_cyberpunk_check
from models import (
    AgentTurnRequest,
    AgentTurnResult,
    Character,
    CharacterArmorRequest,
    CharacterConditionRemoveRequest,
    CharacterConditionRequest,
    CombatAttackRequest,
    CombatAttackResult,
    CombatDamageRequest,
    CombatDamageResult,
    CombatParticipant,
    CombatSetTurnRequest,
    CombatStartRequest,
    CombatState,
    CombatStateResult,
    CombatUpdateParticipantRequest,
    CharacterDamageRequest,
    CharacterHealRequest,
    CharacterInventoryRequest,
    CharacterMoneyRequest,
    CharacterResourceRequest,
    CharacterRollRequest,
    CharacterStateChangeResult,
    GMContext,
    Session,
    SessionCheckActionRequest,
    SessionCheckActionResult,
    SessionCreate,
    SessionEvent,
    SessionEventCreate,
    SessionStateUpdate,
    SessionUpdate,
)
from storage import CHARACTERS_FILE, SESSIONS_FILE, read_json, write_json
from tool_executor import execute_agent_tool_calls


router = APIRouter(prefix="/api/sessions", tags=["会话"])


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _load_sessions() -> dict[str, dict]:
    return read_json(SESSIONS_FILE, default={})


def _save_sessions(sessions: dict[str, dict]) -> None:
    write_json(SESSIONS_FILE, sessions)


def _load_characters() -> dict[str, dict]:
    return read_json(CHARACTERS_FILE, default={})


def _get_session(sessions: dict[str, dict], session_id: str) -> Session:
    raw = sessions.get(session_id)
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到会话：{session_id}",
        )

    return Session(**raw)


def _store_session(sessions: dict[str, dict], session: Session) -> None:
    sessions[session.id] = session.model_dump()
    _save_sessions(sessions)


def _ensure_character_in_session(session: Session, character_id: str) -> None:
    if character_id not in session.character_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"角色不在当前会话中：{character_id}",
        )


def _append_event(session: Session, event: SessionEvent) -> Session:
    data = session.model_dump()
    data["events"].append(event.model_dump())
    data["updated_at"] = _now()
    return Session(**data)


def _apply_session_updates(session: Session, updates: dict) -> Session:
    data = session.model_dump()
    for key, value in updates.items():
        if value is not None:
            data[key] = value
    data["updated_at"] = _now()
    return Session(**data)


def _get_character_name(character_id: str) -> str:
    raw = _load_characters().get(character_id)
    if raw is None:
        return character_id
    return Character(**raw).name


def _roll_initiative(character_id: str) -> int:
    raw = _load_characters().get(character_id)
    if raw is None:
        return 0
    character = Character(**raw)
    stat = character.stats.get("反应", character.stats.get("REF", 0))
    return roll_cyberpunk_check(stat=stat, skill=0)["total"]


def _store_combat_state_event(
    *,
    session: Session,
    combat_state: CombatState,
    event_type: str,
    title: str,
    content: str,
    metadata: dict,
) -> CombatStateResult:
    sessions = _load_sessions()
    data = session.model_dump()
    data["combat_state"] = combat_state.model_dump()
    data["updated_at"] = _now()
    updated_session = Session(**data)
    event = SessionEvent(
        id=uuid4().hex,
        created_at=_now(),
        type=event_type,
        title=title,
        content=content,
        character_ids=[participant.character_id for participant in combat_state.participants],
        metadata=metadata,
    )
    updated_session = _append_event(updated_session, event)
    _store_session(sessions, updated_session)
    return CombatStateResult(
        session=updated_session,
        combat_state=combat_state,
        event=event,
    )


def _load_combat_state(session: Session) -> CombatState:
    if session.combat_state is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前会话没有进行中的战斗。",
        )
    return CombatState(**session.combat_state)


@router.get("", response_model=list[Session])
def list_sessions() -> list[Session]:
    sessions = _load_sessions()
    result = [Session(**raw) for raw in sessions.values()]
    return sorted(result, key=lambda session: session.updated_at, reverse=True)


@router.post("", response_model=Session, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreate) -> Session:
    sessions = _load_sessions()
    now = _now()
    session = Session(
        id=uuid4().hex,
        events=[],
        created_at=now,
        updated_at=now,
        **payload.model_dump(),
    )
    _store_session(sessions, session)
    return session


@router.get("/{session_id}", response_model=Session)
def get_session(session_id: str) -> Session:
    sessions = _load_sessions()
    return _get_session(sessions, session_id)


@router.put("/{session_id}", response_model=Session)
def update_session(session_id: str, payload: SessionUpdate) -> Session:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    updated = _apply_session_updates(session, payload.model_dump(exclude_unset=True))
    _store_session(sessions, updated)
    return updated


@router.delete("/{session_id}")
def delete_session(session_id: str) -> dict:
    sessions = _load_sessions()
    _get_session(sessions, session_id)
    del sessions[session_id]
    _save_sessions(sessions)
    return {"deleted": session_id}


@router.get("/{session_id}/events", response_model=list[SessionEvent])
def list_session_events(session_id: str) -> list[SessionEvent]:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    return session.events


@router.post("/{session_id}/events", response_model=SessionEvent, status_code=status.HTTP_201_CREATED)
def add_session_event(session_id: str, payload: SessionEventCreate) -> SessionEvent:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    event = SessionEvent(
        id=uuid4().hex,
        created_at=_now(),
        **payload.model_dump(),
    )

    updated = _append_event(session, event)
    _store_session(sessions, updated)
    return event


@router.put("/{session_id}/state", response_model=Session)
def update_session_state(session_id: str, payload: SessionStateUpdate) -> Session:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    updated = _apply_session_updates(session, payload.model_dump(exclude_unset=True))
    _store_session(sessions, updated)
    return updated


@router.get("/{session_id}/gm-context", response_model=GMContext)
def get_gm_context(session_id: str, recent_event_limit: int = 10) -> GMContext:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    raw_characters = _load_characters()
    characters: list[Character] = []
    missing_character_ids: list[str] = []

    for character_id in session.character_ids:
        raw = raw_characters.get(character_id)
        if raw is None:
            missing_character_ids.append(character_id)
            continue
        characters.append(Character(**raw))

    return GMContext(
        session=session,
        characters=characters,
        recent_events=session.events[-recent_event_limit:],
        missing_character_ids=missing_character_ids,
        rules={
            "stats": "/api/rules/stats",
            "skills": "/api/rules/skills",
            "difficulty_values": "/api/rules/difficulty-values",
            "ranged_dv": "/api/rules/ranged-dv",
            "cover": "/api/rules/cover",
            "combat_actions": "/api/rules/combat-actions",
        },
        guidance=[
            "GM agent 负责叙事、提问和推进场景，规则执行应交给 API。",
            "需要检定时优先调用角色检定接口，让系统自动匹配属性和技能。",
            "场景变化、检定结果和重要选择应写入事件日志，避免上下文丢失。",
            "不确定规则时先读取规则接口或 docs/rules 中的中文规则说明。",
        ],
    )


@router.post("/{session_id}/actions/check", response_model=SessionCheckActionResult)
def run_check_action(
    session_id: str,
    payload: SessionCheckActionRequest,
) -> SessionCheckActionResult:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    _ensure_character_in_session(session, payload.character_id)

    roll = roll_character_check(
        payload.character_id,
        CharacterRollRequest(
            stat_name=payload.stat_name,
            skill_name=payload.skill_name,
            modifier=payload.modifier,
            dv=payload.dv,
        ),
    )
    if roll.success is True:
        outcome = "成功"
    elif roll.success is False:
        outcome = "失败"
    else:
        outcome = "已掷骰"

    dv_text = "无目标难度" if roll.dv is None else f"DV {roll.dv}"
    event = SessionEvent(
        id=uuid4().hex,
        created_at=_now(),
        type="检定",
        title=payload.title or roll.label,
        content=(
            f"{roll.character_name} 尝试：{payload.intent}。"
            f"使用 {roll.stat_name}+{roll.skill_name} 检定，结果 {roll.total}，{dv_text}，{outcome}。"
        ),
        character_ids=[payload.character_id],
        metadata={
            "intent": payload.intent,
            "roll": roll.model_dump(),
        },
    )
    updated = _append_event(session, event)
    _store_session(sessions, updated)
    return SessionCheckActionResult(
        session_id=session_id,
        outcome=outcome,
        roll=roll,
        event=event,
    )


def _record_character_state_event(
    *,
    session_id: str,
    character: Character,
    event_type: str,
    title: str,
    content: str,
    metadata: dict,
) -> CharacterStateChangeResult:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    _ensure_character_in_session(session, character.id)
    event = SessionEvent(
        id=uuid4().hex,
        created_at=_now(),
        type=event_type,
        title=title,
        content=content,
        character_ids=[character.id],
        metadata=metadata,
    )
    updated = _append_event(session, event)
    _store_session(sessions, updated)
    return CharacterStateChangeResult(character=character, event=event)


@router.post("/{session_id}/characters/{character_id}/damage", response_model=CharacterStateChangeResult)
def damage_session_character(
    session_id: str,
    character_id: str,
    payload: CharacterDamageRequest,
) -> CharacterStateChangeResult:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    _ensure_character_in_session(session, character_id)
    character = apply_damage(character_id, payload)
    return _record_character_state_event(
        session_id=session_id,
        character=character,
        event_type="伤害",
        title=payload.source,
        content=f"{character.name} 受到 {payload.amount} 点伤害，当前 HP {character.current_hp}/{character.max_hp}，护甲 SP {character.armor_sp}。",
        metadata=payload.model_dump(),
    )


@router.post("/{session_id}/characters/{character_id}/heal", response_model=CharacterStateChangeResult)
def heal_session_character(
    session_id: str,
    character_id: str,
    payload: CharacterHealRequest,
) -> CharacterStateChangeResult:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    _ensure_character_in_session(session, character_id)
    character = apply_heal(character_id, payload)
    return _record_character_state_event(
        session_id=session_id,
        character=character,
        event_type="治疗",
        title=payload.source,
        content=f"{character.name} 恢复 {payload.amount} 点 HP，当前 HP {character.current_hp}/{character.max_hp}。",
        metadata=payload.model_dump(),
    )


@router.post("/{session_id}/characters/{character_id}/armor", response_model=CharacterStateChangeResult)
def adjust_session_character_armor(
    session_id: str,
    character_id: str,
    payload: CharacterArmorRequest,
) -> CharacterStateChangeResult:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    _ensure_character_in_session(session, character_id)
    character = adjust_armor(character_id, payload)
    return _record_character_state_event(
        session_id=session_id,
        character=character,
        event_type="护甲",
        title=payload.source,
        content=f"{character.name} 的护甲调整 {payload.amount}，当前 SP {character.armor_sp}。",
        metadata=payload.model_dump(),
    )


@router.post("/{session_id}/characters/{character_id}/conditions", response_model=CharacterStateChangeResult)
def add_session_character_condition(
    session_id: str,
    character_id: str,
    payload: CharacterConditionRequest,
) -> CharacterStateChangeResult:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    _ensure_character_in_session(session, character_id)
    character = add_condition(character_id, payload)
    return _record_character_state_event(
        session_id=session_id,
        character=character,
        event_type="状态",
        title=f"获得状态：{payload.condition.name}",
        content=f"{character.name} 获得状态：{payload.condition.name}。",
        metadata=payload.model_dump(),
    )


@router.post("/{session_id}/characters/{character_id}/conditions/remove", response_model=CharacterStateChangeResult)
def remove_session_character_condition(
    session_id: str,
    character_id: str,
    payload: CharacterConditionRemoveRequest,
) -> CharacterStateChangeResult:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    _ensure_character_in_session(session, character_id)
    character = remove_condition(character_id, payload)
    return _record_character_state_event(
        session_id=session_id,
        character=character,
        event_type="状态",
        title=f"移除状态：{payload.name}",
        content=f"{character.name} 移除状态：{payload.name}。",
        metadata=payload.model_dump(),
    )


@router.post("/{session_id}/characters/{character_id}/money", response_model=CharacterStateChangeResult)
def adjust_session_character_money(
    session_id: str,
    character_id: str,
    payload: CharacterMoneyRequest,
) -> CharacterStateChangeResult:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    _ensure_character_in_session(session, character_id)
    character = adjust_money(character_id, payload)
    return _record_character_state_event(
        session_id=session_id,
        character=character,
        event_type="金钱",
        title=payload.reason,
        content=f"{character.name} 的欧元调整 {payload.amount}，当前余额 {character.eurobucks}。",
        metadata=payload.model_dump(),
    )


@router.post("/{session_id}/characters/{character_id}/inventory/add", response_model=CharacterStateChangeResult)
def add_session_character_inventory(
    session_id: str,
    character_id: str,
    payload: CharacterInventoryRequest,
) -> CharacterStateChangeResult:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    _ensure_character_in_session(session, character_id)
    character = add_inventory_item(character_id, payload)
    return _record_character_state_event(
        session_id=session_id,
        character=character,
        event_type="物品",
        title=f"获得物品：{payload.name}",
        content=f"{character.name} 获得物品：{payload.name} x{payload.quantity}。",
        metadata=payload.model_dump(),
    )


@router.post("/{session_id}/characters/{character_id}/inventory/remove", response_model=CharacterStateChangeResult)
def remove_session_character_inventory(
    session_id: str,
    character_id: str,
    payload: CharacterInventoryRequest,
) -> CharacterStateChangeResult:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    _ensure_character_in_session(session, character_id)
    character = remove_inventory_item(character_id, payload)
    return _record_character_state_event(
        session_id=session_id,
        character=character,
        event_type="物品",
        title=f"失去物品：{payload.name}",
        content=f"{character.name} 失去物品：{payload.name} x{payload.quantity}。",
        metadata=payload.model_dump(),
    )


@router.post("/{session_id}/characters/{character_id}/resources", response_model=CharacterStateChangeResult)
def adjust_session_character_resource(
    session_id: str,
    character_id: str,
    payload: CharacterResourceRequest,
) -> CharacterStateChangeResult:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    _ensure_character_in_session(session, character_id)
    character = adjust_resource(character_id, payload)
    return _record_character_state_event(
        session_id=session_id,
        character=character,
        event_type="资源",
        title=payload.reason,
        content=f"{character.name} 的{payload.name}调整 {payload.amount}。",
        metadata=payload.model_dump(),
    )


@router.post("/{session_id}/combat/damage", response_model=CombatDamageResult)
def apply_session_combat_damage(
    session_id: str,
    payload: CombatDamageRequest,
) -> CombatDamageResult:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    _ensure_character_in_session(session, payload.target_character_id)
    raw_characters = _load_characters()
    target = Character(**raw_characters[payload.target_character_id])
    damage = calculate_attack_damage(
        damage=payload.damage,
        armor_sp=target.armor_sp,
        ignore_armor=payload.ignore_armor,
        half_armor=payload.half_armor,
        ablate_armor=payload.ablate_armor,
        minimum_hp=payload.minimum_hp,
        current_hp=target.current_hp,
    )

    data = target.model_dump()
    data["current_hp"] = damage["new_hp"]
    data["armor_sp"] = damage["new_armor_sp"]
    if damage["critical_injury"] is not None:
        injury_name = damage["critical_injury"]["name"]
        data["conditions"] = [
            condition
            for condition in data["conditions"]
            if condition["name"] != injury_name
        ]
        data["conditions"].append(
            {
                "name": injury_name,
                "description": "重伤",
                "source": payload.source,
                "modifiers": {},
            }
        )

    updated_target = Character(**data)
    raw_characters[payload.target_character_id] = updated_target.model_dump()
    write_json(CHARACTERS_FILE, raw_characters)

    critical_text = ""
    if damage["critical_injury"] is not None:
        critical_text = f"，触发重伤：{damage['critical_injury']['name']}"
    event = SessionEvent(
        id=uuid4().hex,
        created_at=_now(),
        type="伤害",
        title=payload.source,
        content=(
            f"{updated_target.name} 承受 {payload.damage} 伤害，掷骰 {damage['damage_roll']['rolls']}，"
            f"总伤害 {damage['damage_roll']['total']}，有效护甲 {damage['effective_armor']}，"
            f"实际 HP 伤害 {damage['hp_damage']}，当前 HP {updated_target.current_hp}/{updated_target.max_hp}，"
            f"护甲 SP {updated_target.armor_sp}{critical_text}。"
        ),
        character_ids=[updated_target.id],
        metadata={
            "request": payload.model_dump(),
            "damage": damage,
        },
    )
    updated_session = _append_event(session, event)
    _store_session(sessions, updated_session)
    return CombatDamageResult(
        target=updated_target,
        damage=damage,
        event=event,
    )


@router.post("/{session_id}/combat/attack", response_model=CombatAttackResult)
def run_session_combat_attack(
    session_id: str,
    payload: CombatAttackRequest,
) -> CombatAttackResult:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    _ensure_character_in_session(session, payload.attacker_character_id)
    _ensure_character_in_session(session, payload.target_character_id)
    attack = run_check_action(
        session_id,
        SessionCheckActionRequest(
            character_id=payload.attacker_character_id,
            skill_name=payload.skill_name,
            stat_name=payload.stat_name,
            modifier=payload.modifier,
            dv=payload.dv,
            intent=payload.intent,
            title=payload.source,
        ),
    )
    hit = attack.roll.success
    damage_result = None
    if hit is True and payload.damage:
        damage_result = apply_session_combat_damage(
            session_id,
            CombatDamageRequest(
                target_character_id=payload.target_character_id,
                damage=payload.damage,
                source=payload.source,
                ignore_armor=payload.ignore_armor,
                half_armor=payload.half_armor,
                ablate_armor=payload.ablate_armor,
            ),
        )

    return CombatAttackResult(
        attack=attack,
        damage=damage_result,
        hit=hit,
    )


@router.post("/{session_id}/combat/start", response_model=CombatStateResult)
def start_session_combat(
    session_id: str,
    payload: CombatStartRequest,
) -> CombatStateResult:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    participants: list[CombatParticipant] = []
    for participant in payload.participants:
        _ensure_character_in_session(session, participant.character_id)
        initiative = participant.initiative
        if initiative is None:
            initiative = _roll_initiative(participant.character_id)
        participants.append(
            CombatParticipant(
                character_id=participant.character_id,
                name=participant.name or _get_character_name(participant.character_id),
                initiative=initiative,
                has_acted=False,
                notes=participant.notes,
            )
        )

    participants.sort(key=lambda item: item.initiative, reverse=True)
    current_turn_index = min(payload.current_turn_index, len(participants) - 1)
    combat_state = CombatState(
        active=True,
        round=payload.round,
        current_turn_index=current_turn_index,
        participants=participants,
        notes=payload.notes,
    )
    current = combat_state.participants[combat_state.current_turn_index]
    return _store_combat_state_event(
        session=session,
        combat_state=combat_state,
        event_type="战斗",
        title="战斗开始",
        content=f"战斗开始。当前回合：{current.name}。",
        metadata=payload.model_dump(),
    )


@router.post("/{session_id}/combat/next-turn", response_model=CombatStateResult)
def advance_session_combat_turn(session_id: str) -> CombatStateResult:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    combat_state = _load_combat_state(session)
    if not combat_state.participants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="战斗没有参与者。",
        )

    current = combat_state.participants[combat_state.current_turn_index]
    current.has_acted = True
    next_index = combat_state.current_turn_index + 1
    if next_index >= len(combat_state.participants):
        next_index = 0
        combat_state.round += 1
        for participant in combat_state.participants:
            participant.has_acted = False

    combat_state.current_turn_index = next_index
    next_participant = combat_state.participants[next_index]
    return _store_combat_state_event(
        session=session,
        combat_state=combat_state,
        event_type="战斗",
        title="推进回合",
        content=f"进入第 {combat_state.round} 轮，当前回合：{next_participant.name}。",
        metadata={"previous_character_id": current.character_id, "next_character_id": next_participant.character_id},
    )


@router.post("/{session_id}/combat/set-turn", response_model=CombatStateResult)
def set_session_combat_turn(
    session_id: str,
    payload: CombatSetTurnRequest,
) -> CombatStateResult:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    combat_state = _load_combat_state(session)
    if payload.current_turn_index >= len(combat_state.participants):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="回合索引超出参与者范围。",
        )
    combat_state.current_turn_index = payload.current_turn_index
    current = combat_state.participants[combat_state.current_turn_index]
    return _store_combat_state_event(
        session=session,
        combat_state=combat_state,
        event_type="战斗",
        title="设置当前回合",
        content=f"当前回合设置为：{current.name}。",
        metadata=payload.model_dump(),
    )


@router.post("/{session_id}/combat/participants", response_model=CombatStateResult)
def update_session_combat_participant(
    session_id: str,
    payload: CombatUpdateParticipantRequest,
) -> CombatStateResult:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    combat_state = _load_combat_state(session)
    for participant in combat_state.participants:
        if participant.character_id != payload.character_id:
            continue
        if payload.initiative is not None:
            participant.initiative = payload.initiative
        if payload.has_acted is not None:
            participant.has_acted = payload.has_acted
        if payload.notes is not None:
            participant.notes = payload.notes
        combat_state.participants.sort(key=lambda item: item.initiative, reverse=True)
        combat_state.current_turn_index = min(combat_state.current_turn_index, len(combat_state.participants) - 1)
        return _store_combat_state_event(
            session=session,
            combat_state=combat_state,
            event_type="战斗",
            title="更新战斗参与者",
            content=f"更新战斗参与者：{_get_character_name(payload.character_id)}。",
            metadata=payload.model_dump(),
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"未找到战斗参与者：{payload.character_id}",
    )


@router.post("/{session_id}/combat/end", response_model=CombatStateResult)
def end_session_combat(session_id: str) -> CombatStateResult:
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    combat_state = _load_combat_state(session)
    combat_state.active = False
    result = _store_combat_state_event(
        session=session,
        combat_state=combat_state,
        event_type="战斗",
        title="战斗结束",
        content="战斗结束。",
        metadata={},
    )
    sessions = _load_sessions()
    updated_session = _get_session(sessions, session_id)
    data = updated_session.model_dump()
    data["combat_state"] = None
    data["updated_at"] = _now()
    final_session = Session(**data)
    _store_session(sessions, final_session)
    return CombatStateResult(
        session=final_session,
        combat_state=combat_state,
        event=result.event,
    )


def _build_tool_handlers(session_id: str):
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    handlers = {}
    handlers[("POST", f"/api/sessions/{session_id}/combat/damage")] = (
        lambda body: apply_session_combat_damage(
            session_id,
            CombatDamageRequest(**body),
        )
    )
    handlers[("POST", f"/api/sessions/{session_id}/combat/attack")] = (
        lambda body: run_session_combat_attack(
            session_id,
            CombatAttackRequest(**body),
        )
    )
    handlers[("POST", f"/api/sessions/{session_id}/combat/start")] = (
        lambda body: start_session_combat(
            session_id,
            CombatStartRequest(**body),
        )
    )
    handlers[("POST", f"/api/sessions/{session_id}/combat/next-turn")] = (
        lambda body: advance_session_combat_turn(session_id)
    )
    handlers[("POST", f"/api/sessions/{session_id}/combat/set-turn")] = (
        lambda body: set_session_combat_turn(
            session_id,
            CombatSetTurnRequest(**body),
        )
    )
    handlers[("POST", f"/api/sessions/{session_id}/combat/participants")] = (
        lambda body: update_session_combat_participant(
            session_id,
            CombatUpdateParticipantRequest(**body),
        )
    )
    handlers[("POST", f"/api/sessions/{session_id}/combat/end")] = (
        lambda body: end_session_combat(session_id)
    )
    for character_id in session.character_ids:
        handlers[("POST", f"/api/sessions/{session_id}/characters/{character_id}/damage")] = (
            lambda body, cid=character_id: damage_session_character(
                session_id,
                cid,
                CharacterDamageRequest(**body),
            )
        )
        handlers[("POST", f"/api/sessions/{session_id}/characters/{character_id}/heal")] = (
            lambda body, cid=character_id: heal_session_character(
                session_id,
                cid,
                CharacterHealRequest(**body),
            )
        )
        handlers[("POST", f"/api/sessions/{session_id}/characters/{character_id}/armor")] = (
            lambda body, cid=character_id: adjust_session_character_armor(
                session_id,
                cid,
                CharacterArmorRequest(**body),
            )
        )
        handlers[("POST", f"/api/sessions/{session_id}/characters/{character_id}/conditions")] = (
            lambda body, cid=character_id: add_session_character_condition(
                session_id,
                cid,
                CharacterConditionRequest(**body),
            )
        )
        handlers[("POST", f"/api/sessions/{session_id}/characters/{character_id}/conditions/remove")] = (
            lambda body, cid=character_id: remove_session_character_condition(
                session_id,
                cid,
                CharacterConditionRemoveRequest(**body),
            )
        )
        handlers[("POST", f"/api/sessions/{session_id}/characters/{character_id}/money")] = (
            lambda body, cid=character_id: adjust_session_character_money(
                session_id,
                cid,
                CharacterMoneyRequest(**body),
            )
        )
        handlers[("POST", f"/api/sessions/{session_id}/characters/{character_id}/inventory/add")] = (
            lambda body, cid=character_id: add_session_character_inventory(
                session_id,
                cid,
                CharacterInventoryRequest(**body),
            )
        )
        handlers[("POST", f"/api/sessions/{session_id}/characters/{character_id}/inventory/remove")] = (
            lambda body, cid=character_id: remove_session_character_inventory(
                session_id,
                cid,
                CharacterInventoryRequest(**body),
            )
        )
        handlers[("POST", f"/api/sessions/{session_id}/characters/{character_id}/resources")] = (
            lambda body, cid=character_id: adjust_session_character_resource(
                session_id,
                cid,
                CharacterResourceRequest(**body),
            )
        )
    return handlers


@router.post("/{session_id}/agent/turn", response_model=AgentTurnResult)
def run_agent_turn(session_id: str, payload: AgentTurnRequest) -> AgentTurnResult:
    context = get_gm_context(session_id)
    try:
        agent_result = run_gm_agent(
            session_id=session_id,
            gm_context=context.model_dump(),
            player_message=payload.player_message,
        )
    except AgentConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except AgentRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    event = None
    player_event = None
    updated_session = None
    sessions = _load_sessions()
    session = _get_session(sessions, session_id)
    response = agent_result["response"]
    should_store_session = False
    tool_results = []
    followup_result = None
    followup_event = None

    if payload.write_event:
        player_event = SessionEvent(
            id=uuid4().hex,
            created_at=_now(),
            type="玩家",
            title="玩家行动",
            content=payload.player_message,
            character_ids=[],
            metadata={},
        )
        session = _append_event(session, player_event)
        should_store_session = True

        raw_event = response.get("event") if isinstance(response, dict) else None
        content = (raw_event or {}).get("content") or response.get("narration") or "GM agent 返回了一次回应。"
        event = SessionEvent(
            id=uuid4().hex,
            created_at=_now(),
            type=(raw_event or {}).get("type", "GM回应"),
            title=(raw_event or {}).get("title", "GM回应"),
            content=content,
            character_ids=[],
            metadata=(raw_event or {}).get("metadata", {}),
        )
        session = _append_event(session, event)
        should_store_session = True

    if payload.update_session_state and isinstance(response, dict):
        updates = {}
        if response.get("state_summary") is not None:
            updates["state_summary"] = response["state_summary"]
        if response.get("gm_notes") is not None:
            updates["gm_notes"] = response["gm_notes"]
        if updates:
            session = _apply_session_updates(session, updates)
            should_store_session = True

    if should_store_session:
        _store_session(sessions, session)
        updated_session = session

    if payload.execute_tools and isinstance(response, dict):
        raw_calls = response.get("recommended_api_calls", [])
        if isinstance(raw_calls, list):
            tool_results = execute_agent_tool_calls(
                session_id=session_id,
                calls=raw_calls,
                run_check_action=run_check_action,
                tool_handlers=_build_tool_handlers(session_id),
            )
            sessions = _load_sessions()
            updated_session = _get_session(sessions, session_id)

    executed_tool_results = [
        result
        for result in tool_results
        if result.executed
    ]
    if payload.resolve_tools_with_agent and executed_tool_results:
        context = get_gm_context(session_id)
        try:
            followup_result = run_gm_agent_with_tool_results(
                session_id=session_id,
                gm_context=context.model_dump(),
                player_message=payload.player_message,
                first_response=response,
                tool_results=[result.model_dump() for result in tool_results],
            )
        except AgentRequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

        followup_response = followup_result["response"]
        if payload.write_event:
            raw_event = followup_response.get("event") if isinstance(followup_response, dict) else None
            content = (
                (raw_event or {}).get("content")
                or followup_response.get("narration")
                or "GM agent 根据工具结果返回了一次结算。"
            )
            followup_event = SessionEvent(
                id=uuid4().hex,
                created_at=_now(),
                type=(raw_event or {}).get("type", "GM结算"),
                title=(raw_event or {}).get("title", "GM结算"),
                content=content,
                character_ids=[],
                metadata=(raw_event or {}).get("metadata", {}),
            )
            sessions = _load_sessions()
            session = _get_session(sessions, session_id)
            session = _append_event(session, followup_event)
            _store_session(sessions, session)
            updated_session = session

        if payload.update_session_state and isinstance(followup_response, dict):
            updates = {}
            if followup_response.get("state_summary") is not None:
                updates["state_summary"] = followup_response["state_summary"]
            if followup_response.get("gm_notes") is not None:
                updates["gm_notes"] = followup_response["gm_notes"]
            if updates:
                sessions = _load_sessions()
                session = _get_session(sessions, session_id)
                session = _apply_session_updates(session, updates)
                _store_session(sessions, session)
                updated_session = session

    return AgentTurnResult(
        session_id=session_id,
        model=agent_result["model"],
        usage=agent_result["usage"],
        response=response,
        tool_results=tool_results,
        followup_model=None if followup_result is None else followup_result["model"],
        followup_usage=None if followup_result is None else followup_result["usage"],
        followup_response=None if followup_result is None else followup_result["response"],
        followup_event=followup_event,
        player_event=player_event,
        event=event,
        session=updated_session,
    )
