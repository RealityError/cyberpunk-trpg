# GM Agent 使用说明

GM agent 的职责是叙事、提问、组织信息和推进场景；规则执行和状态落盘应交给 FastAPI 接口完成。

## 权威上下文

每次行动前，GM agent 应优先读取：

```text
GET /api/sessions/{session_id}/gm-context
```

该接口会返回：

- 当前会话状态
- 当前场景说明
- 参与角色快照
- 最近事件日志
- 缺失的角色 ID
- 可用规则接口
- GM 操作提示

## 事件日志

重要信息必须写入事件日志，包括：

- 场景变化
- 玩家声明的行动意图
- 检定结果
- NPC 反应
- 战斗中的关键状态变化
- GM 对后续场景的备注

写入事件：

```text
POST /api/sessions/{session_id}/events
```

示例：

```json
{
  "type": "检定",
  "title": "手枪射击",
  "content": "边缘行者向巷口的帮派枪手射击，检定成功。",
  "character_ids": ["角色 ID"],
  "metadata": {
    "skill_name": "手枪",
    "dv": 15,
    "success": true
  }
}
```

## 规则调用原则

GM agent 不应自行发明或修改核心规则。

需要规则时优先读取：

```text
GET /api/rules
GET /api/rules/stats
GET /api/rules/skills
GET /api/rules/difficulty-values
GET /api/rules/ranged-dv
GET /api/rules/cover
GET /api/rules/combat-actions
```

需要角色检定时优先调用：

```text
POST /api/characters/{character_id}/roll
```

只传技能名即可：

```json
{
  "skill_name": "手枪",
  "modifier": 0,
  "dv": 15
}
```

系统会根据规则数据自动匹配属性。

会话内玩家行动应优先调用：

```text
POST /api/sessions/{session_id}/actions/check
```

该接口会执行检定并自动写入事件日志。

## DeepSeek 配置

本地 `.env` 保存 DeepSeek 配置：

```text
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_THINKING=enabled
DEEPSEEK_REASONING_EFFORT=high
DEEPSEEK_INCLUDE_RULEBOOK=true
```

当前 DeepSeek 官方 API 应优先使用 `deepseek-v4-pro` 或 `deepseek-v4-flash`。旧模型名 `deepseek-chat` 和 `deepseek-reasoner` 会在 2026-07-24 停用。

调用 GM agent：

```text
POST /api/sessions/{session_id}/agent/turn
```

GM agent 会读取会话上下文，并返回结构化 JSON。默认会把 GM 回应写入事件日志。

`agent/turn` 默认会自动执行白名单中的工具调用。目前允许：

```text
POST /api/sessions/{session_id}/actions/check
POST /api/sessions/{session_id}/combat/damage
POST /api/sessions/{session_id}/combat/attack
POST /api/sessions/{session_id}/combat/start
POST /api/sessions/{session_id}/combat/next-turn
POST /api/sessions/{session_id}/combat/set-turn
POST /api/sessions/{session_id}/combat/participants
POST /api/sessions/{session_id}/combat/end
POST /api/sessions/{session_id}/characters/{character_id}/damage
POST /api/sessions/{session_id}/characters/{character_id}/heal
POST /api/sessions/{session_id}/characters/{character_id}/armor
POST /api/sessions/{session_id}/characters/{character_id}/conditions
POST /api/sessions/{session_id}/characters/{character_id}/conditions/remove
POST /api/sessions/{session_id}/characters/{character_id}/money
POST /api/sessions/{session_id}/characters/{character_id}/inventory/add
POST /api/sessions/{session_id}/characters/{character_id}/inventory/remove
POST /api/sessions/{session_id}/characters/{character_id}/resources
```

接口响应中的 `tool_results` 会记录每个推荐调用是否执行、执行结果或错误原因。

默认还会启用二阶段结算：工具执行后，系统会把 `tool_results` 再交给 GM agent，让它生成检定成功或失败后的叙事。响应字段包括：

- `followup_response`
- `followup_event`
- `followup_usage`

如果只想看 agent 建议、不自动执行工具，可在请求体中传：

```json
{
  "player_message": "我观察街口有没有埋伏。",
  "execute_tools": false
}
```

如果只想自动执行工具，但不让 GM agent 进行第二次结算，可传：

```json
{
  "player_message": "我观察街口有没有埋伏。",
  "resolve_tools_with_agent": false
}
```

## 规则包上下文

GM agent 请求默认会携带完整规则包，来源包括：

- `docs/rules/*.md`
- `rules/*.json`

规则包会作为动态会话上下文之前的稳定 system message 注入。这样 DeepSeek 可以在长上下文中直接参考完整规则，同时更容易命中上下文缓存。

规则包只用于理解和判断；真正需要掷骰、伤害、治疗、状态变化或事件落盘时，GM agent 仍应推荐调用 API。

如果需要临时关闭完整规则包，可在 `.env` 中设置：

```text
DEEPSEEK_INCLUDE_RULEBOOK=false
```

## 状态维护原则

`state_summary` 用于保存当前局面的简短摘要，适合放入 GM agent 的短上下文。

`gm_notes` 用于保存主持人不可直接暴露给玩家的信息，例如伏笔、NPC 真实动机和隐藏威胁。

`scene` 用于保存玩家可感知的当前场景。
