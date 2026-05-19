import characters
import sessions
from models import CharacterCreate, SessionCreate, SessionEventCreate

from tests.conftest import patch_storage


def test_gm_context_includes_session_character_and_events(storage_dir):
    patch_storage(storage_dir)
    character = characters.create_character(
        CharacterCreate(name="边缘行者", role="独狼", max_hp=40)
    )
    session = sessions.create_session(
        SessionCreate(name="第一局", scene="雨夜街巷", character_ids=[character.id])
    )
    event = sessions.add_session_event(
        session.id,
        SessionEventCreate(type="记录", title="开场", content="游戏开始。"),
    )

    context = sessions.get_gm_context(session.id)

    assert context.session.id == session.id
    assert context.characters[0].id == character.id
    assert context.recent_events[0].id == event.id
    assert context.rules["skills"] == "/api/rules/skills"


def test_agent_turn_records_player_event(monkeypatch, storage_dir):
    patch_storage(storage_dir)
    character = characters.create_character(
        CharacterCreate(name="边缘行者", role="独狼", max_hp=40)
    )
    session = sessions.create_session(
        SessionCreate(name="单人局", scene="雨夜街巷", character_ids=[character.id])
    )

    monkeypatch.setattr(
        sessions,
        "run_gm_agent",
        lambda **kwargs: {
            "model": "test-model",
            "usage": {},
            "response": {
                "narration": "GM 看着你走进雨里。",
                "recommended_api_calls": [],
            },
        },
    )

    result = sessions.run_agent_turn(
        session.id,
        sessions.AgentTurnRequest(player_message="我走进后巷。"),
    )
    updated = sessions.get_session(session.id)

    assert result.player_event is not None
    assert result.player_event.type == "玩家"
    assert updated.events[0].content == "我走进后巷。"
    assert updated.events[1].content == "GM 看着你走进雨里。"
