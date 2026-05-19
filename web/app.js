const state = {
  sessions: [],
  characters: [],
  activeSessionId: null,
  activeSession: null,
  busy: false,
};

const elements = {
  refreshButton: document.querySelector("#refreshButton"),
  demoButton: document.querySelector("#demoButton"),
  sessionSelect: document.querySelector("#sessionSelect"),
  sceneText: document.querySelector("#sceneText"),
  combatBox: document.querySelector("#combatBox"),
  characterGrid: document.querySelector("#characterGrid"),
  rollList: document.querySelector("#rollList"),
  messageList: document.querySelector("#messageList"),
  chatForm: document.querySelector("#chatForm"),
  playerMessage: document.querySelector("#playerMessage"),
  sendButton: document.querySelector("#sendButton"),
  agentStatus: document.querySelector("#agentStatus"),
  toast: document.querySelector("#toast"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const data = await response.json();
      detail = data.detail || JSON.stringify(data);
    } catch {
      detail = await response.text();
    }
    throw new Error(detail);
  }

  return response.status === 204 ? null : response.json();
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.remove("hidden");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    elements.toast.classList.add("hidden");
  }, 3600);
}

function setBusy(isBusy, label = "处理中") {
  state.busy = isBusy;
  elements.sendButton.disabled = isBusy;
  elements.demoButton.disabled = isBusy;
  elements.refreshButton.disabled = isBusy;
  elements.agentStatus.textContent = isBusy ? label : "就绪";
  elements.agentStatus.classList.toggle("busy", isBusy);
}

function escapeText(value) {
  const div = document.createElement("div");
  div.textContent = value == null ? "" : String(value);
  return div.innerHTML;
}

function formatTime(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleTimeString("zh-CN", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
  });
}

function characterById(id) {
  return state.characters.find((character) => character.id === id);
}

function activeCharacters() {
  if (!state.activeSession) {
    return [];
  }
  return state.activeSession.character_ids
    .map((id) => characterById(id))
    .filter(Boolean);
}

function renderSessions() {
  elements.sessionSelect.innerHTML = "";
  if (!state.sessions.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "暂无存档";
    elements.sessionSelect.append(option);
    return;
  }

  for (const session of state.sessions) {
    const option = document.createElement("option");
    option.value = session.id;
    option.textContent = session.name;
    elements.sessionSelect.append(option);
  }

  elements.sessionSelect.value = state.activeSessionId || state.sessions[0].id;
}

function renderScene() {
  if (!state.activeSession) {
    elements.sceneText.textContent = "暂无存档。点击“新游戏”开始一个单人演示局。";
    elements.sceneText.classList.add("muted");
    return;
  }

  elements.sceneText.textContent = state.activeSession.scene || state.activeSession.state_summary || "场景尚未展开。";
  elements.sceneText.classList.toggle("muted", !state.activeSession.scene && !state.activeSession.state_summary);
}

function renderCharacters() {
  const characters = activeCharacters();
  elements.characterGrid.innerHTML = "";
  elements.characterGrid.classList.toggle("empty", characters.length === 0);

  if (!characters.length) {
    elements.characterGrid.textContent = "暂无角色。";
    return;
  }

  for (const character of characters) {
    const hpPercent = Math.max(0, Math.min(100, Math.round((character.current_hp / character.max_hp) * 100)));
    const hpClass = hpPercent <= 30 ? "danger" : hpPercent <= 55 ? "warning" : "";
    const weapons = (character.weapons || [])
      .map((item) => `${item.name}${item.damage ? ` ${item.damage}` : ""}`)
      .join("、");
    const inventory = (character.inventory || [])
      .map((item) => `${item.name} x${item.quantity}`)
      .join("、");
    const conditions = (character.conditions || []).map((item) => item.name).join("、");

    const card = document.createElement("article");
    card.className = "character-card";
    card.innerHTML = `
      <div class="character-heading">
        <div>
          <h3>${escapeText(character.name)}</h3>
          <div class="role">${escapeText(character.role || "角色")}</div>
        </div>
        <span class="tag">护甲 SP ${character.armor_sp}</span>
      </div>
      <div class="meter-line">
        <div class="meter"><div class="meter-fill ${hpClass}" style="width: ${hpPercent}%"></div></div>
        <strong>${character.current_hp}/${character.max_hp} HP</strong>
      </div>
      <div class="tag-row">
        <span class="tag">欧元 ${character.eurobucks || 0}</span>
        ${character.luck_current == null ? "" : `<span class="tag">幸运 ${character.luck_current}</span>`}
        ${character.humanity == null ? "" : `<span class="tag">人性 ${character.humanity}</span>`}
      </div>
      <p class="visible-detail">武器：${escapeText(weapons || "无")}</p>
      <p class="visible-detail">物品：${escapeText(inventory || "无")}</p>
      <p class="visible-detail">状态：${escapeText(conditions || "正常")}</p>
    `;
    elements.characterGrid.append(card);
  }
}

function eventTone(event) {
  const text = `${event.type || ""}${event.title || ""}`;
  if (event.type === "玩家") {
    return "player";
  }
  if (text.includes("检定") || text.includes("伤害") || text.includes("战斗") || text.includes("状态")) {
    return "system";
  }
  return "gm";
}

function renderMessages() {
  const events = state.activeSession?.events || [];
  elements.messageList.innerHTML = "";

  if (!state.activeSession) {
    appendMessage("system", "系统", "点击“新游戏”后就可以直接用对话推进单人游戏。");
    return;
  }

  if (!events.length) {
    appendMessage("system", "系统", "存档已载入。输入你的行动，GM 会根据规则推进场景。");
    return;
  }

  for (const event of events.slice(-40)) {
    const tone = eventTone(event);
    const title = tone === "player" ? "你" : tone === "gm" ? event.title || "GM" : event.title || event.type || "系统";
    appendMessage(tone, title, event.content || "", "", false);
  }
  elements.messageList.scrollTop = elements.messageList.scrollHeight;
}

function appendMessage(role, title, content, extraClass = "", scroll = true) {
  const message = document.createElement("article");
  message.className = `message ${role} ${extraClass}`.trim();
  message.innerHTML = `
    ${title ? `<div class="message-title">${escapeText(title)}</div>` : ""}
    <div>${escapeText(content)}</div>
  `;
  elements.messageList.append(message);
  if (scroll) {
    elements.messageList.scrollTop = elements.messageList.scrollHeight;
  }
}

function collectRecentRolls() {
  const events = state.activeSession?.events || [];
  const rolls = [];

  for (const event of events) {
    if (event.metadata?.roll) {
      rolls.push({
        kind: "roll",
        time: event.created_at,
        title: event.title || "检定",
        content: event.content,
        roll: event.metadata.roll,
      });
    }
    if (event.metadata?.damage) {
      rolls.push({
        kind: "damage",
        time: event.created_at,
        title: event.title || "伤害",
        content: event.content,
        damage: event.metadata.damage,
      });
    }
  }

  return rolls.slice(-6).reverse();
}

function renderRolls() {
  const rolls = collectRecentRolls();
  elements.rollList.innerHTML = "";
  elements.rollList.classList.toggle("empty", rolls.length === 0);

  if (!rolls.length) {
    elements.rollList.textContent = "暂无判定。";
    return;
  }

  for (const item of rolls) {
    const div = document.createElement("article");
    div.className = `roll-item ${item.kind === "damage" ? "damage" : ""}`;
    if (item.roll) {
      const result = item.roll.success == null ? "无目标难度" : item.roll.success ? "成功" : "失败";
      div.innerHTML = `
        <div class="roll-meta">${escapeText(formatTime(item.time))} · ${escapeText(item.title)}</div>
        <strong>${escapeText(item.roll.character_name || "")}</strong>
        <div>${escapeText(item.roll.stat_name || "")}+${escapeText(item.roll.skill_name || "")}：d10=${item.roll.base_roll}，总值 ${item.roll.total}，${result}</div>
      `;
    } else {
      div.innerHTML = `
        <div class="roll-meta">${escapeText(formatTime(item.time))} · ${escapeText(item.title)}</div>
        <div>伤害 ${item.damage.damage_roll?.total ?? "-"}，实际 HP 伤害 ${item.damage.hp_damage ?? "-"}</div>
      `;
    }
    elements.rollList.append(div);
  }
}

function renderCombat() {
  const combat = state.activeSession?.combat_state;
  if (!combat || !combat.active || !combat.participants?.length) {
    elements.combatBox.classList.add("muted");
    elements.combatBox.textContent = "未进入战斗。";
    return;
  }

  const current = combat.participants[combat.current_turn_index];
  elements.combatBox.classList.remove("muted");
  elements.combatBox.innerHTML = `
    <strong>第 ${combat.round} 轮</strong>
    <p class="visible-detail">当前行动：${escapeText(current?.name || "未知")}</p>
    <div class="tag-row">
      ${combat.participants.map((item) => `<span class="tag">${escapeText(item.name)} ${item.initiative}</span>`).join("")}
    </div>
  `;
}

function renderAll() {
  renderSessions();
  renderScene();
  renderCharacters();
  renderMessages();
  renderRolls();
  renderCombat();
}

async function loadData(preferredSessionId = state.activeSessionId) {
  const [sessions, characters] = await Promise.all([
    api("/api/sessions"),
    api("/api/characters"),
  ]);
  state.sessions = sessions;
  state.characters = characters;
  state.activeSessionId = preferredSessionId;
  if (!state.sessions.some((session) => session.id === state.activeSessionId)) {
    state.activeSessionId = state.sessions[0]?.id || null;
  }
  state.activeSession = state.sessions.find((session) => session.id === state.activeSessionId) || null;
  renderAll();
}

async function loadActiveSession(sessionId) {
  if (!sessionId) {
    state.activeSessionId = null;
    state.activeSession = null;
    renderAll();
    return;
  }

  const [session, characters] = await Promise.all([
    api(`/api/sessions/${sessionId}`),
    api("/api/characters"),
  ]);
  state.activeSessionId = sessionId;
  state.activeSession = session;
  state.characters = characters;
  const index = state.sessions.findIndex((item) => item.id === sessionId);
  if (index >= 0) {
    state.sessions[index] = session;
  }
  renderAll();
}

async function addEvent(sessionId, event) {
  return api(`/api/sessions/${sessionId}/events`, {
    method: "POST",
    body: JSON.stringify(event),
  });
}

async function createDemoSession() {
  setBusy(true, "创建中");
  try {
    const character = await api("/api/characters", {
      method: "POST",
      body: JSON.stringify({
        name: `边缘行者-${new Date().toLocaleTimeString("zh-CN", { hour12: false })}`,
        role: "独狼",
        stats: {
          INT: 6,
          REF: 8,
          DEX: 7,
          TECH: 5,
          COOL: 7,
          WILL: 6,
          LUCK: 5,
          MOVE: 6,
          BODY: 6,
          EMP: 5,
        },
        skills: {
          手枪: 6,
          闪避: 5,
          觉察: 4,
          潜行: 4,
          说服: 3,
        },
        max_hp: 40,
        current_hp: 40,
        armor_sp: 11,
        weapons: [{ name: "重型手枪", damage: "3d6", notes: "可靠但声音很大" }],
        inventory: [
          { name: "急救包", quantity: 1, notes: "" },
          { name: "一次性手机", quantity: 2, notes: "" },
        ],
        eurobucks: 250,
        humanity: 50,
        luck_current: 5,
        notes: "前端演示角色。",
      }),
    });

    const session = await api("/api/sessions", {
      method: "POST",
      body: JSON.stringify({
        name: `演示回放 ${new Date().toLocaleTimeString("zh-CN", { hour12: false })}`,
        scene: "后巷深处的蓝色招牌只剩一半还亮着。目标躲进装卸区，雨水顺着消防梯往下流。一个保镖倒在货箱旁，另一个还在黑暗里移动。",
        character_ids: [character.id],
        gm_notes: "这是用于查看玩家端效果的前端演示回放。",
        state_summary: "玩家已潜入后巷，发现目标和一名保镖，当前处于短暂交火后的压制状态。",
      }),
    });

    await addEvent(session.id, {
      type: "GM回应",
      title: "开场",
      content: "雨水敲在你的夹克肩头。后巷入口只有一盏忽明忽暗的灯，垃圾箱后面传来短促的金属碰撞声。匿名消息还停在你的视网膜投影上：别让他离开。",
      character_ids: [character.id],
      metadata: {},
    });

    await addEvent(session.id, {
      type: "玩家",
      title: "玩家行动",
      content: "我压低身子靠近垃圾箱，先观察后巷里有没有埋伏。",
      character_ids: [character.id],
      metadata: {},
    });

    await api(`/api/sessions/${session.id}/actions/check`, {
      method: "POST",
      body: JSON.stringify({
        character_id: character.id,
        skill_name: "觉察",
        dv: 13,
        intent: "观察后巷入口和垃圾箱附近是否有埋伏。",
        title: "观察后巷",
      }),
    });

    await addEvent(session.id, {
      type: "GM回应",
      title: "发现动静",
      content: "你看见垃圾箱后的积水泛起一圈波纹。不是雨点，是有人刚刚挪动了脚。目标在装卸门旁低声骂了一句，另一个影子抬起了枪口。",
      character_ids: [character.id],
      metadata: {},
    });

    await addEvent(session.id, {
      type: "玩家",
      title: "玩家行动",
      content: "我抢先开火，瞄准那个抬枪的影子。",
      character_ids: [character.id],
      metadata: {},
    });

    await api(`/api/sessions/${session.id}/actions/check`, {
      method: "POST",
      body: JSON.stringify({
        character_id: character.id,
        skill_name: "手枪",
        dv: 15,
        intent: "在雨夜后巷中抢先射击武装保镖。",
        title: "手枪射击",
      }),
    });

    await api(`/api/sessions/${session.id}/characters/${character.id}/damage`, {
      method: "POST",
      body: JSON.stringify({
        amount: 14,
        source: "流弹擦伤",
        notes: "保镖反击时子弹擦过护甲边缘。",
      }),
    });

    await api(`/api/sessions/${session.id}/characters/${character.id}/conditions`, {
      method: "POST",
      body: JSON.stringify({
        condition: {
          name: "被压制",
          description: "敌方火力迫使你暂时贴住掩体。",
          source: "后巷交火",
          modifiers: {},
        },
      }),
    });

    await addEvent(session.id, {
      type: "GM回应",
      title: "短暂压制",
      content: "你的第一枪打碎了保镖身后的警示灯，火花在雨里炸开。他的回击擦过你的护甲，冲击力把你压回垃圾箱后。目标趁乱钻进装卸门，门还没完全合上。",
      character_ids: [character.id],
      metadata: {},
    });

    await api(`/api/sessions/${session.id}/combat/start`, {
      method: "POST",
      body: JSON.stringify({
        participants: [
          { character_id: character.id, initiative: 17, name: character.name, notes: "玩家" },
        ],
        round: 2,
        current_turn_index: 0,
        notes: "演示：只展示玩家可见的当前回合。",
      }),
    });

    await loadData(session.id);
  } catch (error) {
    showToast(`创建失败：${error.message}`);
    appendMessage("system", "创建失败", error.message, "error");
  } finally {
    setBusy(false);
  }
}

function renderToolMessages(toolResults) {
  for (const item of toolResults || []) {
    if (!item.executed) {
      appendMessage("system", "规则执行失败", item.error || JSON.stringify(item.call), "error");
      continue;
    }

    const result = item.result || {};
    if (result.roll) {
      const roll = result.roll;
      const outcome = roll.success == null ? "无目标难度" : roll.success ? "成功" : "失败";
      appendMessage("system", "掷骰", `${roll.character_name}：${roll.stat_name}+${roll.skill_name}，d10=${roll.base_roll}，总值 ${roll.total}，${outcome}`);
    } else if (result.damage) {
      const damage = result.damage;
      appendMessage("system", "伤害", `总伤害 ${damage.damage_roll?.total ?? "-"}，实际 HP 伤害 ${damage.hp_damage ?? "-"}。`);
    } else if (result.character) {
      appendMessage("system", "状态", `${result.character.name}：HP ${result.character.current_hp}/${result.character.max_hp}，SP ${result.character.armor_sp}`);
    }
  }
}

async function sendAgentTurn(event) {
  event.preventDefault();
  const message = elements.playerMessage.value.trim();
  if (!message || !state.activeSessionId) {
    showToast("请先开始或选择一个存档。");
    return;
  }

  appendMessage("player", "你", message);
  elements.playerMessage.value = "";
  setBusy(true, "GM 思考中");

  try {
    const result = await api(`/api/sessions/${state.activeSessionId}/agent/turn`, {
      method: "POST",
      body: JSON.stringify({
        player_message: message,
        write_event: true,
        update_session_state: true,
        execute_tools: true,
        resolve_tools_with_agent: true,
      }),
    });

    const firstNarration = result.response?.narration;
    const followupNarration = result.followup_response?.narration;
    if (firstNarration) {
      appendMessage("gm", "GM", firstNarration);
    }
    renderToolMessages(result.tool_results);
    if (followupNarration && followupNarration !== firstNarration) {
      appendMessage("gm", "GM", followupNarration);
    }
    if (!firstNarration && !followupNarration) {
      appendMessage("gm", "GM", "GM 返回了响应，但没有可展示的叙事文本。");
    }
    await loadActiveSession(state.activeSessionId);
  } catch (error) {
    appendMessage("system", "请求失败", error.message, "error");
  } finally {
    setBusy(false);
  }
}

elements.refreshButton.addEventListener("click", () => {
  loadData().catch((error) => showToast(`刷新失败：${error.message}`));
});

elements.demoButton.addEventListener("click", createDemoSession);

elements.sessionSelect.addEventListener("change", (event) => {
  loadActiveSession(event.target.value).catch((error) => showToast(`加载失败：${error.message}`));
});

elements.chatForm.addEventListener("submit", sendAgentTurn);

loadData().catch((error) => {
  showToast(`初始化失败：${error.message}`);
  appendMessage("system", "初始化失败", error.message, "error");
});
