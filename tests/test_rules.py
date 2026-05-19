from rules_loader import resolve_character_stat, resolve_stat_for_skill


def test_skill_resolves_canonical_stat_and_alias_value():
    stat_rule = resolve_stat_for_skill("手枪")

    assert stat_rule is not None
    assert stat_rule["name"] == "反应"

    stat_name, stat_value = resolve_character_stat({"REF": 8}, stat_rule["name"])
    assert stat_name == "反应"
    assert stat_value == 8
