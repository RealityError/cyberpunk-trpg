import characters
import sessions
from models import CharacterCreate, SessionCreate
from tool_executor import execute_agent_tool_calls

from tests.conftest import patch_storage


def test_tool_executor_blocks_non_whitelisted_calls(storage_dir):
    patch_storage(storage_dir)
    character = characters.create_character(CharacterCreate(name="runner", role="solo", max_hp=40))
    session = sessions.create_session(
        SessionCreate(name="工具测试", scene="街巷", character_ids=[character.id])
    )

    results = execute_agent_tool_calls(
        session_id=session.id,
        calls=[{"method": "DELETE", "path": f"/api/sessions/{session.id}", "body": {}}],
        run_check_action=sessions.run_check_action,
        tool_handlers=sessions._build_tool_handlers(session.id),
    )

    assert results[0].executed is False
    assert "白名单" in results[0].error
