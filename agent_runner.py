import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
RULE_DOCS_DIR = BASE_DIR / "docs" / "rules"
STRUCTURED_RULES_DIR = BASE_DIR / "rules"

GM_AGENT_SYSTEM_PROMPT = """
你是赛博朋克 TRPG 的 GM agent。你负责叙事、提出选择、维护场景连贯性，并判断何时需要调用后端规则接口。

你不能自行修改核心规则；需要检定、伤害、状态变化或规则查询时，应在 recommended_api_calls 中提出要调用的 API。
你必须严格基于 gm_context 和 player_message 继续当前场景，不要引入与当前场景无关的新任务、NPC、地点或剧情。
如果玩家行动的成败、发现信息、命中、躲避、治疗、破解、潜行或社交影响存在不确定性，你不能直接宣布结果；你应推荐调用相应 API。
如果玩家是在观察埋伏、寻找线索或判断危险，通常推荐调用 /api/sessions/{session_id}/actions/check，skill_name 使用“觉察”，dv 根据局面建议 13、15、17、21 或 24。
如果攻击已经命中并需要结算武器伤害，优先推荐调用 /api/sessions/{session_id}/combat/damage，而不是手动计算 HP 和护甲。
如果玩家正在发动一次完整攻击，且已知攻击技能、DV 和武器伤害，优先推荐调用 /api/sessions/{session_id}/combat/attack。
如果进入或推进战斗，推荐调用战斗回合工具维护先攻、轮数和当前回合。
如果工具结果或叙事明确导致 HP、护甲、状态、物品、金钱或资源变化，你应推荐调用对应状态工具。
如果 gm_notes 中存在隐藏信息，不要直接透露给玩家；只有在推荐检定并成功后，后续叙事才可以揭示。
你必须输出合法 json，不要输出 markdown。

输出 JSON 格式：
{
  "narration": "给玩家看的叙事文本",
  "questions": ["需要玩家回答的问题"],
  "suggested_actions": ["玩家可选行动"],
  "needs_player_input": true,
  "recommended_api_calls": [
    {
      "method": "POST",
      "path": "/api/sessions/{session_id}/actions/check",
      "reason": "为什么需要调用",
      "body": {}
    }
  ],
  "event": {
    "type": "GM回应",
    "title": "简短标题",
    "content": "应写入事件日志的内容",
    "metadata": {}
  },
  "state_summary": null,
  "gm_notes": null
}

可用状态工具：
- POST /api/sessions/{session_id}/combat/damage
- POST /api/sessions/{session_id}/combat/attack
- POST /api/sessions/{session_id}/combat/start
- POST /api/sessions/{session_id}/combat/next-turn
- POST /api/sessions/{session_id}/combat/set-turn
- POST /api/sessions/{session_id}/combat/participants
- POST /api/sessions/{session_id}/combat/end
- POST /api/sessions/{session_id}/characters/{character_id}/damage
- POST /api/sessions/{session_id}/characters/{character_id}/heal
- POST /api/sessions/{session_id}/characters/{character_id}/armor
- POST /api/sessions/{session_id}/characters/{character_id}/conditions
- POST /api/sessions/{session_id}/characters/{character_id}/conditions/remove
- POST /api/sessions/{session_id}/characters/{character_id}/money
- POST /api/sessions/{session_id}/characters/{character_id}/inventory/add
- POST /api/sessions/{session_id}/characters/{character_id}/inventory/remove
- POST /api/sessions/{session_id}/characters/{character_id}/resources

示例：玩家说“我观察街口有没有埋伏”，当前会话有可疑街巷和角色 ID 时，recommended_api_calls 应包含：
{
  "method": "POST",
  "path": "/api/sessions/{session_id}/actions/check",
  "reason": "观察潜在埋伏需要觉察检定。",
  "body": {
    "character_id": "角色 ID",
    "skill_name": "觉察",
    "modifier": 0,
    "dv": 15,
    "intent": "观察街口是否有埋伏"
  }
}
""".strip()

GM_AGENT_TOOL_RESULT_PROMPT = """
你是赛博朋克 TRPG 的 GM agent。后端已经执行了你推荐的工具调用。

你现在必须根据 tool_results 继续叙事，描述检定成功或失败带来的直接后果。
不要再次推荐已经执行过的相同工具调用，除非新的叙事确实引出了新的不确定行动。
如果检定成功，可以揭示 gm_notes 中与该检定相关的信息；如果失败，不要直接泄露隐藏信息，但可以描述压力、误判、风险或局势恶化。
你必须输出合法 json，不要输出 markdown。

输出 JSON 格式：
{
  "narration": "给玩家看的后续叙事文本",
  "questions": ["需要玩家回答的问题"],
  "suggested_actions": ["玩家可选行动"],
  "needs_player_input": true,
  "recommended_api_calls": [],
  "event": {
    "type": "GM结算",
    "title": "简短标题",
    "content": "应写入事件日志的内容",
    "metadata": {}
  },
  "state_summary": null,
  "gm_notes": null
}
""".strip()

RULEBOOK_SYSTEM_PROMPT = """
以下是本游戏的完整规则上下文。你必须优先依据这些规则进行判断。

这些内容是稳定前缀，顺序和格式应保持稳定，以便 DeepSeek 上下文缓存命中。
你可以理解和引用规则，但不要直接执行需要后端状态变更的规则流程；需要掷骰、伤害、治疗、状态变化或事件落盘时，必须推荐调用 API。
""".strip()


class AgentConfigurationError(RuntimeError):
    pass


class AgentRequestError(RuntimeError):
    pass


@lru_cache
def build_rulebook_context() -> str:
    sections: list[str] = []

    sections.append("# 人类可读规则文档")
    for path in sorted(RULE_DOCS_DIR.glob("*.md"), key=lambda item: item.name):
        sections.append(f"\n## {path.name}\n")
        sections.append(path.read_text(encoding="utf-8-sig").strip())

    sections.append("\n# 结构化规则数据")
    for path in sorted(STRUCTURED_RULES_DIR.glob("*.json"), key=lambda item: item.name):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        sections.append(f"\n## {path.name}\n")
        sections.append(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))

    return "\n".join(sections).strip()


def load_env_file(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_agent_config() -> dict[str, str]:
    load_env_file()
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise AgentConfigurationError("未设置 DEEPSEEK_API_KEY，请先在 .env 中填入 DeepSeek API Key。")

    return {
        "api_key": api_key,
        "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro"),
        "thinking": os.environ.get("DEEPSEEK_THINKING", "enabled"),
        "reasoning_effort": os.environ.get("DEEPSEEK_REASONING_EFFORT", "high"),
        "timeout_seconds": os.environ.get("DEEPSEEK_TIMEOUT_SECONDS", "60"),
        "include_rulebook": os.environ.get("DEEPSEEK_INCLUDE_RULEBOOK", "true"),
    }


def suggest_api_calls(
    *,
    session_id: str,
    gm_context: dict[str, Any],
    player_message: str,
) -> list[dict[str, Any]]:
    message = player_message.casefold()
    characters = gm_context.get("characters", [])
    if not characters:
        return []

    character_id = characters[0].get("id")
    if not character_id:
        return []

    checks = [
        (["观察", "查看", "寻找", "搜索", "埋伏", "线索", "危险"], "觉察", 15, "观察当前区域是否存在危险或隐藏线索"),
        (["开枪", "射击", "手枪"], "手枪", 15, "进行远程射击"),
        (["潜行", "偷偷", "隐蔽", "绕开"], "潜行", 15, "尝试隐蔽行动"),
        (["说服", "劝", "谈判"], "说服", 15, "尝试通过交流影响目标"),
    ]
    for keywords, skill_name, dv, intent in checks:
        if any(keyword in message for keyword in keywords):
            return [
                {
                    "method": "POST",
                    "path": f"/api/sessions/{session_id}/actions/check",
                    "reason": f"玩家行动存在不确定结果，需要进行{skill_name}检定。",
                    "body": {
                        "character_id": character_id,
                        "skill_name": skill_name,
                        "modifier": 0,
                        "dv": dv,
                        "intent": intent,
                    },
                }
            ]

    return []


def _deduplicate_api_calls(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for call in calls:
        key = json.dumps(
            {
                "method": call.get("method"),
                "path": call.get("path"),
                "body": call.get("body"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(call)
    return result


def run_gm_agent(
    *,
    session_id: str,
    gm_context: dict[str, Any],
    player_message: str,
) -> dict[str, Any]:
    config = get_agent_config()
    timeout_seconds = int(config["timeout_seconds"])
    suggested_api_calls = suggest_api_calls(
        session_id=session_id,
        gm_context=gm_context,
        player_message=player_message,
    )
    messages = [{"role": "system", "content": GM_AGENT_SYSTEM_PROMPT}]
    if config["include_rulebook"].casefold() in {"1", "true", "yes", "on"}:
        messages.append(
            {
                "role": "system",
                "content": f"{RULEBOOK_SYSTEM_PROMPT}\n\n{build_rulebook_context()}",
            }
        )

    messages.append(
        {
            "role": "user",
            "content": json.dumps(
                {
                    "要求": "请根据当前上下文推进一小步游戏，并输出 json。",
                    "session_id": session_id,
                    "player_message": player_message,
                    "gm_context": gm_context,
                    "system_suggested_api_calls": suggested_api_calls,
                    "要求补充": "如果 system_suggested_api_calls 非空，recommended_api_calls 必须包含这些调用，不得删除。",
                },
                ensure_ascii=False,
            ),
        }
    )

    payload = {
        "model": config["model"],
        "messages": messages,
        "response_format": {"type": "json_object"},
        "thinking": {"type": config["thinking"]},
        "reasoning_effort": config["reasoning_effort"],
        "stream": False,
        "max_tokens": 1600,
    }
    request = Request(
        f"{config['base_url']}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AgentRequestError(f"DeepSeek 请求失败：HTTP {exc.code}，{detail}") from exc
    except URLError as exc:
        raise AgentRequestError(f"DeepSeek 请求失败：{exc.reason}") from exc
    except TimeoutError as exc:
        raise AgentRequestError("DeepSeek 请求超时。") from exc

    try:
        content = raw["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AgentRequestError("DeepSeek 响应格式不符合预期。") from exc

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AgentRequestError("GM agent 未返回合法 JSON。") from exc

    if suggested_api_calls:
        existing = parsed.get("recommended_api_calls")
        if not isinstance(existing, list):
            existing = []
        existing.extend(
            call
            for call in suggested_api_calls
            if call not in existing
        )
        parsed["recommended_api_calls"] = _deduplicate_api_calls(existing)

    return {
        "model": config["model"],
        "usage": raw.get("usage", {}),
        "response": parsed,
    }


def run_gm_agent_with_tool_results(
    *,
    session_id: str,
    gm_context: dict[str, Any],
    player_message: str,
    first_response: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> dict[str, Any]:
    config = get_agent_config()
    timeout_seconds = int(config["timeout_seconds"])
    messages = [{"role": "system", "content": GM_AGENT_TOOL_RESULT_PROMPT}]
    if config["include_rulebook"].casefold() in {"1", "true", "yes", "on"}:
        messages.append(
            {
                "role": "system",
                "content": f"{RULEBOOK_SYSTEM_PROMPT}\n\n{build_rulebook_context()}",
            }
        )

    messages.append(
        {
            "role": "user",
            "content": json.dumps(
                {
                    "要求": "请根据工具执行结果继续叙事，并输出 json。",
                    "session_id": session_id,
                    "player_message": player_message,
                    "gm_context": gm_context,
                    "first_response": first_response,
                    "tool_results": tool_results,
                },
                ensure_ascii=False,
            ),
        }
    )
    payload = {
        "model": config["model"],
        "messages": messages,
        "response_format": {"type": "json_object"},
        "thinking": {"type": config["thinking"]},
        "reasoning_effort": config["reasoning_effort"],
        "stream": False,
        "max_tokens": 1600,
    }
    request = Request(
        f"{config['base_url']}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AgentRequestError(f"DeepSeek 请求失败：HTTP {exc.code}，{detail}") from exc
    except URLError as exc:
        raise AgentRequestError(f"DeepSeek 请求失败：{exc.reason}") from exc
    except TimeoutError as exc:
        raise AgentRequestError("DeepSeek 请求超时。") from exc

    try:
        content = raw["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AgentRequestError("DeepSeek 响应格式不符合预期。") from exc

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AgentRequestError("GM agent 未返回合法 JSON。") from exc

    return {
        "model": config["model"],
        "usage": raw.get("usage", {}),
        "response": parsed,
    }
