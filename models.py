from typing import Any

from pydantic import BaseModel, Field


class CheckRollRequest(BaseModel):
    label: str = Field(default="检定", min_length=1, max_length=80)
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


class Weapon(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    damage: str = Field(default="", max_length=40)
    notes: str = Field(default="", max_length=500)


class InventoryItem(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    quantity: int = Field(default=1, ge=0, le=9999)
    notes: str = Field(default="", max_length=500)


class Condition(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    source: str = Field(default="", max_length=120)
    modifiers: dict[str, int] = Field(default_factory=dict)


class CharacterBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    role: str = Field(default="", max_length=80)
    stats: dict[str, int] = Field(default_factory=dict)
    skills: dict[str, int] = Field(default_factory=dict)
    max_hp: int = Field(default=10, ge=1, le=200)
    current_hp: int | None = Field(default=None, ge=0, le=200)
    armor_sp: int = Field(default=0, ge=0, le=50)
    weapons: list[Weapon] = Field(default_factory=list)
    inventory: list[InventoryItem] = Field(default_factory=list)
    eurobucks: int = Field(default=0, ge=0, le=1_000_000)
    conditions: list[Condition] = Field(default_factory=list)
    death_save_penalty: int = Field(default=0, ge=0, le=20)
    humanity: int | None = Field(default=None, ge=0, le=100)
    luck_current: int | None = Field(default=None, ge=0, le=20)
    notes: str = Field(default="", max_length=5000)


class CharacterCreate(CharacterBase):
    pass


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    role: str | None = Field(default=None, max_length=80)
    stats: dict[str, int] | None = None
    skills: dict[str, int] | None = None
    max_hp: int | None = Field(default=None, ge=1, le=200)
    current_hp: int | None = Field(default=None, ge=0, le=200)
    armor_sp: int | None = Field(default=None, ge=0, le=50)
    weapons: list[Weapon] | None = None
    inventory: list[InventoryItem] | None = None
    eurobucks: int | None = Field(default=None, ge=0, le=1_000_000)
    conditions: list[Condition] | None = None
    death_save_penalty: int | None = Field(default=None, ge=0, le=20)
    humanity: int | None = Field(default=None, ge=0, le=100)
    luck_current: int | None = Field(default=None, ge=0, le=20)
    notes: str | None = Field(default=None, max_length=5000)


class Character(CharacterBase):
    id: str
    current_hp: int = Field(ge=0, le=200)


class CharacterRollRequest(BaseModel):
    stat_name: str | None = Field(default=None, min_length=1, max_length=80)
    skill_name: str = Field(min_length=1, max_length=80)
    modifier: int = Field(default=0, ge=-20, le=20)
    dv: int | None = Field(default=None, ge=0, le=50)


class CharacterCheckRollResult(CheckRollResult):
    character_id: str
    character_name: str
    stat_name: str
    skill_name: str


class SessionEventCreate(BaseModel):
    type: str = Field(default="记录", min_length=1, max_length=80)
    title: str = Field(default="事件", min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=5000)
    character_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionEvent(SessionEventCreate):
    id: str
    created_at: str


class SessionBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scene: str = Field(default="", max_length=5000)
    character_ids: list[str] = Field(default_factory=list)
    gm_notes: str = Field(default="", max_length=5000)
    state_summary: str = Field(default="", max_length=5000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    combat_state: dict[str, Any] | None = None


class SessionCreate(SessionBase):
    pass


class SessionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    scene: str | None = Field(default=None, max_length=5000)
    character_ids: list[str] | None = None
    gm_notes: str | None = Field(default=None, max_length=5000)
    state_summary: str | None = Field(default=None, max_length=5000)
    metadata: dict[str, Any] | None = None
    combat_state: dict[str, Any] | None = None


class SessionStateUpdate(BaseModel):
    scene: str | None = Field(default=None, max_length=5000)
    character_ids: list[str] | None = None
    gm_notes: str | None = Field(default=None, max_length=5000)
    state_summary: str | None = Field(default=None, max_length=5000)
    metadata: dict[str, Any] | None = None
    combat_state: dict[str, Any] | None = None


class Session(SessionBase):
    id: str
    events: list[SessionEvent] = Field(default_factory=list)
    created_at: str
    updated_at: str


class GMContext(BaseModel):
    session: Session
    characters: list[Character]
    recent_events: list[SessionEvent]
    missing_character_ids: list[str]
    rules: dict[str, str]
    guidance: list[str]


class SessionCheckActionRequest(BaseModel):
    character_id: str = Field(min_length=1, max_length=80)
    skill_name: str = Field(min_length=1, max_length=80)
    stat_name: str | None = Field(default=None, min_length=1, max_length=80)
    modifier: int = Field(default=0, ge=-20, le=20)
    dv: int | None = Field(default=None, ge=0, le=50)
    intent: str = Field(min_length=1, max_length=1000)
    title: str | None = Field(default=None, max_length=120)


class SessionCheckActionResult(BaseModel):
    session_id: str
    outcome: str
    roll: CharacterCheckRollResult
    event: SessionEvent


class CharacterStateChangeResult(BaseModel):
    character: Character
    event: SessionEvent | None = None


class CombatDamageRequest(BaseModel):
    target_character_id: str = Field(min_length=1, max_length=80)
    damage: str = Field(min_length=2, max_length=40)
    source: str = Field(default="伤害", max_length=120)
    ignore_armor: bool = False
    half_armor: bool = False
    ablate_armor: bool = True
    minimum_hp: int = Field(default=0, ge=0, le=200)
    notes: str = Field(default="", max_length=1000)


class CombatDamageResult(BaseModel):
    target: Character
    damage: dict[str, Any]
    event: SessionEvent


class CombatAttackRequest(BaseModel):
    attacker_character_id: str = Field(min_length=1, max_length=80)
    target_character_id: str = Field(min_length=1, max_length=80)
    skill_name: str = Field(min_length=1, max_length=80)
    stat_name: str | None = Field(default=None, min_length=1, max_length=80)
    modifier: int = Field(default=0, ge=-20, le=20)
    dv: int | None = Field(default=None, ge=0, le=50)
    damage: str | None = Field(default=None, min_length=2, max_length=40)
    source: str = Field(default="攻击", max_length=120)
    ignore_armor: bool = False
    half_armor: bool = False
    ablate_armor: bool = True
    intent: str = Field(default="攻击目标", max_length=1000)


class CombatAttackResult(BaseModel):
    attack: SessionCheckActionResult
    damage: CombatDamageResult | None = None
    hit: bool | None


class CombatParticipantInput(BaseModel):
    character_id: str = Field(min_length=1, max_length=80)
    initiative: int | None = Field(default=None, ge=-20, le=100)
    name: str | None = Field(default=None, max_length=80)
    notes: str = Field(default="", max_length=500)


class CombatStartRequest(BaseModel):
    participants: list[CombatParticipantInput] = Field(min_length=1)
    round: int = Field(default=1, ge=1, le=999)
    current_turn_index: int = Field(default=0, ge=0)
    notes: str = Field(default="", max_length=1000)


class CombatParticipant(BaseModel):
    character_id: str
    name: str
    initiative: int
    has_acted: bool = False
    notes: str = ""


class CombatState(BaseModel):
    active: bool = True
    round: int = Field(default=1, ge=1, le=999)
    current_turn_index: int = Field(default=0, ge=0)
    participants: list[CombatParticipant] = Field(default_factory=list)
    notes: str = ""


class CombatStateResult(BaseModel):
    session: Session
    combat_state: CombatState
    event: SessionEvent


class CombatSetTurnRequest(BaseModel):
    current_turn_index: int = Field(ge=0)


class CombatUpdateParticipantRequest(BaseModel):
    character_id: str = Field(min_length=1, max_length=80)
    initiative: int | None = Field(default=None, ge=-20, le=100)
    has_acted: bool | None = None
    notes: str | None = Field(default=None, max_length=500)


class CharacterDamageRequest(BaseModel):
    amount: int = Field(gt=0, le=500)
    ignore_armor: bool = False
    ablate_armor: bool = True
    minimum_hp: int = Field(default=0, ge=0, le=200)
    source: str = Field(default="伤害", max_length=120)
    notes: str = Field(default="", max_length=1000)


class CharacterHealRequest(BaseModel):
    amount: int = Field(gt=0, le=500)
    source: str = Field(default="治疗", max_length=120)
    notes: str = Field(default="", max_length=1000)


class CharacterArmorRequest(BaseModel):
    amount: int = Field(ge=-50, le=50)
    source: str = Field(default="护甲调整", max_length=120)
    notes: str = Field(default="", max_length=1000)


class CharacterConditionRequest(BaseModel):
    condition: Condition


class CharacterConditionRemoveRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class CharacterMoneyRequest(BaseModel):
    amount: int = Field(ge=-1_000_000, le=1_000_000)
    reason: str = Field(default="金钱变化", max_length=120)


class CharacterInventoryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    quantity: int = Field(default=1, ge=0, le=9999)
    notes: str = Field(default="", max_length=500)


class CharacterResourceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    amount: int = Field(ge=-100, le=100)
    reason: str = Field(default="资源变化", max_length=120)


class AgentTurnRequest(BaseModel):
    player_message: str = Field(min_length=1, max_length=5000)
    write_event: bool = True
    update_session_state: bool = True
    execute_tools: bool = True
    resolve_tools_with_agent: bool = True


class ToolExecutionResult(BaseModel):
    call: dict[str, Any]
    executed: bool
    result: dict[str, Any] | None = None
    error: str | None = None


class AgentTurnResult(BaseModel):
    session_id: str
    model: str
    usage: dict[str, Any]
    response: dict[str, Any]
    tool_results: list[ToolExecutionResult] = Field(default_factory=list)
    followup_model: str | None = None
    followup_usage: dict[str, Any] | None = None
    followup_response: dict[str, Any] | None = None
    followup_event: SessionEvent | None = None
    player_event: SessionEvent | None = None
    event: SessionEvent | None = None
    session: Session | None = None
