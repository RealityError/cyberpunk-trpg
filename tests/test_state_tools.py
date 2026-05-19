import characters
import sessions
from models import CharacterCreate, SessionCreate
from tool_executor import execute_agent_tool_calls

from tests.conftest import patch_storage


def test_state_tools_update_character_and_write_events(storage_dir):
    patch_storage(storage_dir)
    character = characters.create_character(
        CharacterCreate(
            name="runner",
            role="solo",
            stats={"LUCK": 6},
            max_hp=40,
            armor_sp=11,
            eurobucks=100,
        )
    )
    session = sessions.create_session(
        SessionCreate(name="状态测试", scene="街巷", character_ids=[character.id])
    )
    base = f"/api/sessions/{session.id}/characters/{character.id}"
    calls = [
        {"method": "POST", "path": base + "/damage", "body": {"amount": 15, "source": "命中"}},
        {"method": "POST", "path": base + "/heal", "body": {"amount": 3, "source": "急救"}},
        {"method": "POST", "path": base + "/armor", "body": {"amount": 2, "source": "修理"}},
        {
            "method": "POST",
            "path": base + "/conditions",
            "body": {"condition": {"name": "倒地", "description": "不能移动"}},
        },
        {"method": "POST", "path": base + "/inventory/add", "body": {"name": "弹药", "quantity": 10}},
        {"method": "POST", "path": base + "/inventory/remove", "body": {"name": "弹药", "quantity": 4}},
        {"method": "POST", "path": base + "/money", "body": {"amount": -30, "reason": "贿赂"}},
        {"method": "POST", "path": base + "/resources", "body": {"name": "幸运", "amount": -2}},
        {"method": "POST", "path": base + "/conditions/remove", "body": {"name": "倒地"}},
    ]

    results = execute_agent_tool_calls(
        session_id=session.id,
        calls=calls,
        run_check_action=sessions.run_check_action,
        tool_handlers=sessions._build_tool_handlers(session.id),
    )
    updated_character = characters.get_character(character.id)
    updated_session = sessions.get_session(session.id)

    assert all(result.executed for result in results)
    assert updated_character.current_hp == 39
    assert updated_character.armor_sp == 12
    assert updated_character.eurobucks == 70
    assert updated_character.luck_current == 4
    assert updated_character.inventory[0].quantity == 6
    assert updated_character.conditions == []
    assert len(updated_session.events) == len(calls)
