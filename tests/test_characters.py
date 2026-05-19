import characters
from models import CharacterCreate, CharacterRollRequest

from tests.conftest import patch_storage


def test_character_roll_can_infer_stat_from_skill(storage_dir):
    patch_storage(storage_dir)
    character = characters.create_character(
        CharacterCreate(
            name="边缘行者",
            role="独狼",
            stats={"REF": 8},
            skills={"手枪": 6},
            max_hp=40,
        )
    )

    result = characters.roll_character_check(
        character.id,
        CharacterRollRequest(skill_name="手枪", dv=1),
    )

    assert result.stat_name == "反应"
    assert result.skill_name == "手枪"
    assert result.stat == 8
    assert result.skill == 6
