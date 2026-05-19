import characters
import sessions
from models import CharacterCreate, CombatAttackRequest, CombatDamageRequest, CombatStartRequest, SessionCreate
from tool_executor import execute_agent_tool_calls

from tests.conftest import patch_storage


def test_combat_damage_and_attack_flow(storage_dir):
    patch_storage(storage_dir)
    attacker = characters.create_character(
        CharacterCreate(name="attacker", role="solo", stats={"REF": 8}, skills={"手枪": 6}, max_hp=40)
    )
    target = characters.create_character(
        CharacterCreate(name="target", role="enemy", max_hp=40, armor_sp=11)
    )
    session = sessions.create_session(
        SessionCreate(name="战斗测试", scene="街巷", character_ids=[attacker.id, target.id])
    )

    attack = sessions.run_session_combat_attack(
        session.id,
        CombatAttackRequest(
            attacker_character_id=attacker.id,
            target_character_id=target.id,
            skill_name="手枪",
            dv=1,
            damage="3d6",
            source="射击",
        ),
    )

    assert attack.hit is True
    assert attack.damage is not None
    assert len(sessions.get_session(session.id).events) == 2

    miss = sessions.run_session_combat_attack(
        session.id,
        CombatAttackRequest(
            attacker_character_id=attacker.id,
            target_character_id=target.id,
            skill_name="手枪",
            dv=50,
            damage="3d6",
            source="射击",
        ),
    )

    assert miss.hit is False
    assert miss.damage is None


def test_combat_turn_state_lifecycle(storage_dir):
    patch_storage(storage_dir)
    first = characters.create_character(CharacterCreate(name="a", role="solo", stats={"REF": 8}, max_hp=40))
    second = characters.create_character(CharacterCreate(name="b", role="enemy", stats={"REF": 6}, max_hp=30))
    session = sessions.create_session(
        SessionCreate(name="回合测试", scene="街巷", character_ids=[first.id, second.id])
    )

    started = sessions.start_session_combat(
        session.id,
        CombatStartRequest(
            participants=[
                {"character_id": first.id, "initiative": 10},
                {"character_id": second.id, "initiative": 20},
            ]
        ),
    )
    assert started.combat_state.participants[0].character_id == second.id

    turn_one = sessions.advance_session_combat_turn(session.id)
    assert turn_one.combat_state.current_turn_index == 1
    turn_two = sessions.advance_session_combat_turn(session.id)
    assert turn_two.combat_state.current_turn_index == 0
    assert turn_two.combat_state.round == 2

    ended = sessions.end_session_combat(session.id)
    assert ended.combat_state.active is False
    assert sessions.get_session(session.id).combat_state is None


def test_combat_damage_tool_is_whitelisted(storage_dir):
    patch_storage(storage_dir)
    target = characters.create_character(CharacterCreate(name="target", role="enemy", max_hp=40, armor_sp=11))
    session = sessions.create_session(
        SessionCreate(name="工具测试", scene="街巷", character_ids=[target.id])
    )
    call = {
        "method": "POST",
        "path": f"/api/sessions/{session.id}/combat/damage",
        "body": {"target_character_id": target.id, "damage": "2d6", "source": "测试伤害"},
    }

    results = execute_agent_tool_calls(
        session_id=session.id,
        calls=[call],
        run_check_action=sessions.run_check_action,
        tool_handlers=sessions._build_tool_handlers(session.id),
    )

    assert results[0].executed is True
    assert "damage" in results[0].result
