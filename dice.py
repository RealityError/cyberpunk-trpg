from random import SystemRandom
import re


_rng = SystemRandom()


def roll_d10() -> int:
    return _rng.randint(1, 10)


def roll_die(sides: int) -> int:
    return _rng.randint(1, sides)


def roll_dice(expression: str) -> dict:
    match = re.fullmatch(r"\s*(\d+)d(\d+)(?:\s*([+-])\s*(\d+))?\s*", expression)
    if match is None:
        raise ValueError(f"不支持的伤害骰表达式：{expression}")

    count = int(match.group(1))
    sides = int(match.group(2))
    sign = match.group(3)
    modifier_value = int(match.group(4) or 0)
    modifier = -modifier_value if sign == "-" else modifier_value
    if count < 1 or count > 30 or sides < 2 or sides > 100:
        raise ValueError(f"伤害骰表达式超出范围：{expression}")

    rolls = [roll_die(sides) for _ in range(count)]
    total = sum(rolls) + modifier
    return {
        "expression": expression,
        "rolls": rolls,
        "modifier": modifier,
        "total": total,
    }


def roll_cyberpunk_check(stat: int, skill: int, modifier: int = 0) -> dict:
    base_roll = roll_d10()
    extra_roll = None
    critical = None

    if base_roll == 10:
        extra_roll = roll_d10()
        critical = "success"
        dice_total = base_roll + extra_roll
    elif base_roll == 1:
        extra_roll = roll_d10()
        critical = "failure"
        dice_total = base_roll - extra_roll
    else:
        dice_total = base_roll

    total = dice_total + stat + skill + modifier

    return {
        "base_roll": base_roll,
        "extra_roll": extra_roll,
        "critical": critical,
        "stat": stat,
        "skill": skill,
        "modifier": modifier,
        "total": total,
    }
