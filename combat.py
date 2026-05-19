from typing import Any

from dice import roll_dice


CRITICAL_INJURIES = {
    2: "断臂",
    3: "断手",
    4: "肺塌陷",
    5: "肋骨断裂",
    6: "手臂骨折",
    7: "异物嵌入",
    8: "断腿",
    9: "肌肉撕裂",
    10: "脊柱损伤",
    11: "断指",
    12: "腿部重创",
}


def calculate_attack_damage(
    *,
    damage: str,
    armor_sp: int,
    ignore_armor: bool = False,
    half_armor: bool = False,
    ablate_armor: bool = True,
    minimum_hp: int = 0,
    current_hp: int,
) -> dict[str, Any]:
    damage_roll = roll_dice(damage)
    six_count = sum(1 for value in damage_roll["rolls"] if value == 6)
    critical_injury = None
    critical_bonus_damage = 0
    if six_count >= 2:
        critical_roll = roll_dice("2d6")
        critical_injury = {
            "roll": critical_roll,
            "name": CRITICAL_INJURIES.get(critical_roll["total"], "未知重伤"),
        }
        critical_bonus_damage = 5

    effective_armor = 0
    if not ignore_armor:
        effective_armor = armor_sp
        if half_armor:
            effective_armor = armor_sp // 2

    damage_after_armor = max(damage_roll["total"] - effective_armor, 0)
    hp_damage = damage_after_armor + critical_bonus_damage
    new_hp = max(minimum_hp, current_hp - hp_damage)
    armor_ablation = 1 if ablate_armor and damage_after_armor > 0 and armor_sp > 0 and not ignore_armor else 0
    new_armor_sp = max(0, armor_sp - armor_ablation)

    return {
        "damage_roll": damage_roll,
        "six_count": six_count,
        "critical_injury": critical_injury,
        "critical_bonus_damage": critical_bonus_damage,
        "effective_armor": effective_armor,
        "damage_after_armor": damage_after_armor,
        "hp_damage": hp_damage,
        "new_hp": new_hp,
        "armor_ablation": armor_ablation,
        "new_armor_sp": new_armor_sp,
    }
