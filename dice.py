from random import SystemRandom


_rng = SystemRandom()


def roll_d10() -> int:
    return _rng.randint(1, 10)


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
