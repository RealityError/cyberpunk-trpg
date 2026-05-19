from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from models import (
    CharacterConditionRequest,
    CharacterCreate,
    CharacterDamageRequest,
    CombatParticipantInput,
    CombatStartRequest,
    Condition,
    InventoryItem,
    SessionCheckActionRequest,
    SessionCreate,
    SessionEventCreate,
    Weapon,
)
import characters
import sessions


def add_event(session_id: str, event_type: str, title: str, content: str, character_id: str) -> None:
    sessions.add_session_event(
        session_id,
        SessionEventCreate(
            type=event_type,
            title=title,
            content=content,
            character_ids=[character_id],
        ),
    )


def main() -> None:
    character = characters.create_character(
        CharacterCreate(
            name="演示角色-边缘行者",
            role="独狼",
            stats={
                "INT": 6,
                "REF": 8,
                "DEX": 7,
                "TECH": 5,
                "COOL": 7,
                "WILL": 6,
                "LUCK": 5,
                "MOVE": 6,
                "BODY": 6,
                "EMP": 5,
            },
            skills={
                "手枪": 6,
                "闪避": 5,
                "觉察": 4,
                "潜行": 4,
                "说服": 3,
            },
            max_hp=40,
            current_hp=40,
            armor_sp=11,
            weapons=[Weapon(name="重型手枪", damage="3d6", notes="可靠但声音很大")],
            inventory=[
                InventoryItem(name="急救包", quantity=1),
                InventoryItem(name="一次性手机", quantity=2),
            ],
            eurobucks=250,
            humanity=50,
            luck_current=5,
            notes="用于查看玩家端效果的演示角色。",
        )
    )
    session = sessions.create_session(
        SessionCreate(
            name="演示回放：雨夜后巷",
            scene="后巷深处的蓝色招牌只剩一半还亮着。目标躲进装卸区，雨水顺着消防梯往下流。一个保镖倒在货箱旁，另一个还在黑暗里移动。",
            character_ids=[character.id],
            gm_notes="这是用于查看玩家端效果的预置演示回放。",
            state_summary="玩家已潜入后巷，发现目标和一名保镖，当前处于短暂交火后的压制状态。",
        )
    )

    add_event(
        session.id,
        "GM回应",
        "开场",
        "雨水敲在你的夹克肩头。后巷入口只有一盏忽明忽暗的灯，垃圾箱后面传来短促的金属碰撞声。匿名消息还停在你的视网膜投影上：别让他离开。",
        character.id,
    )
    add_event(
        session.id,
        "玩家",
        "玩家行动",
        "我压低身子靠近垃圾箱，先观察后巷里有没有埋伏。",
        character.id,
    )
    sessions.run_check_action(
        session.id,
        SessionCheckActionRequest(
            character_id=character.id,
            skill_name="觉察",
            dv=13,
            intent="观察后巷入口和垃圾箱附近是否有埋伏。",
            title="观察后巷",
        ),
    )
    add_event(
        session.id,
        "GM回应",
        "发现动静",
        "你看见垃圾箱后的积水泛起一圈波纹。不是雨点，是有人刚刚挪动了脚。目标在装卸门旁低声骂了一句，另一个影子抬起了枪口。",
        character.id,
    )
    add_event(
        session.id,
        "玩家",
        "玩家行动",
        "我抢先开火，瞄准那个抬枪的影子。",
        character.id,
    )
    sessions.run_check_action(
        session.id,
        SessionCheckActionRequest(
            character_id=character.id,
            skill_name="手枪",
            dv=15,
            intent="在雨夜后巷中抢先射击武装保镖。",
            title="手枪射击",
        ),
    )
    sessions.damage_session_character(
        session.id,
        character.id,
        CharacterDamageRequest(
            amount=14,
            source="流弹擦伤",
            notes="保镖反击时子弹擦过护甲边缘。",
        ),
    )
    sessions.add_session_character_condition(
        session.id,
        character.id,
        CharacterConditionRequest(
            condition=Condition(
                name="被压制",
                description="敌方火力迫使你暂时贴住掩体。",
                source="后巷交火",
            ),
        ),
    )
    add_event(
        session.id,
        "GM回应",
        "短暂压制",
        "你的第一枪打碎了保镖身后的警示灯，火花在雨里炸开。他的回击擦过你的护甲，冲击力把你压回垃圾箱后。目标趁乱钻进装卸门，门还没完全合上。",
        character.id,
    )
    sessions.start_session_combat(
        session.id,
        CombatStartRequest(
            participants=[
                CombatParticipantInput(
                    character_id=character.id,
                    initiative=17,
                    name=character.name,
                    notes="玩家",
                )
            ],
            round=2,
            current_turn_index=0,
            notes="演示：只展示玩家可见的当前回合。",
        ),
    )

    print(session.id)


if __name__ == "__main__":
    main()
