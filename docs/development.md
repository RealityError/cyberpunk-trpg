# 开发说明

所有命令都从项目根目录运行。

```powershell
python -m uvicorn main:app --reload
```

打开 API 文档：

```text
http://127.0.0.1:8000/docs
```

运行测试：

```powershell
python -m pytest
```

通用检定示例：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/rolls/check `
  -ContentType "application/json" `
  -Body '{"label":"手枪射击","stat":8,"skill":6,"modifier":0,"dv":15}'
```

创建角色：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/characters `
  -ContentType "application/json" `
  -Body '{"name":"边缘行者","role":"独狼","stats":{"REF":8,"DEX":7},"skills":{"手枪":6,"闪避":5},"max_hp":40,"armor_sp":11,"weapons":[{"name":"重型手枪","damage":"3d6"}]}'
```

使用角色进行检定：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/characters/{id}/roll `
  -ContentType "application/json" `
  -Body '{"skill_name":"手枪","modifier":0,"dv":15}'
```

查看规则数据：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/rules
Invoke-RestMethod http://127.0.0.1:8000/api/rules/skills
```

创建会话：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/sessions `
  -ContentType "application/json" `
  -Body '{"name":"第一局","scene":"雨夜的夜之城街巷。","character_ids":[],"gm_notes":"","state_summary":"游戏刚开始。"}'
```

读取 GM 上下文：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/sessions/{id}/gm-context
```

执行会话内行动检定：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/sessions/{id}/actions/check `
  -ContentType "application/json" `
  -Body '{"character_id":"角色 ID","skill_name":"手枪","modifier":0,"dv":15,"intent":"向巷口的帮派枪手开火"}'
```

调用 GM agent：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/sessions/{id}/agent/turn `
  -ContentType "application/json" `
  -Body '{"player_message":"我观察街口有没有埋伏。"}'
```

调整会话内角色状态：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/sessions/{id}/characters/{character_id}/damage `
  -ContentType "application/json" `
  -Body '{"amount":8,"ignore_armor":false,"ablate_armor":true,"source":"手枪命中"}'
```

结算战斗伤害：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/sessions/{id}/combat/damage `
  -ContentType "application/json" `
  -Body '{"target_character_id":"角色 ID","damage":"3d6","source":"重型手枪命中"}'
```

执行攻击并在命中后自动结算伤害：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/sessions/{id}/combat/attack `
  -ContentType "application/json" `
  -Body '{"attacker_character_id":"攻击者 ID","target_character_id":"目标 ID","skill_name":"手枪","dv":15,"damage":"3d6","source":"重型手枪射击","intent":"向目标开火"}'
```

开始并推进战斗：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/sessions/{id}/combat/start `
  -ContentType "application/json" `
  -Body '{"participants":[{"character_id":"角色 ID"}]}'

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/sessions/{id}/combat/next-turn
```
