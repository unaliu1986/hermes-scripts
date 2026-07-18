---
name: intent-gate
description: "操作意图闸门 — 任何 Agent 存在理解偏差可能的操作，必须先亮出意图卡获用户确认。DECO 之外的第五层：治「Agent 自作主张」。"
version: 1.0.0
triggers:
  keywords: [terminal, file_write, write_file, patch, submit, add_item, 处理, 批, 跑, 运行, 改, 部署, 发布]
  mode: before_tool
metadata:
  hermes:
    tags: [gate, intent, alignment, P0]
    priority: 0
    manifest_template: ~/.hermes/launch_manifest_template.json
---

# 操作意图闸门 — 启动前硬性确认

## 铁律

> **你不猜，我不做；你点头，我才动。**

Agent 不是用户肚子里的蛔虫。只要用户的话里有任何需要"推测"的细节——用什么脚本、跑在哪个机器、输入文件是哪个、Key 怎么分——必须先把推测结果亮出来。

---

## 什么时候触发

**只要满足以下任一条件，必须先出意图卡：**

| 条件 | 示例 |
|------|------|
| 用户没指定脚本路径 | "跑那批图片" → 你推测用 cj_agnes_batch.py |
| 涉及多实例/多Key/多平台 | "KEY1-KEY4" → 必须逐 Key 列出分配 |
| 涉及写操作（file_write/patch/API 提交） | 任何改数据/改配置/推生产的操作 |
| 用户描述的是"目标"而非"命令" | "把 CJ 管线重新拉起来" |
| Agent 从上下文推断参数 | "上次那个脚本再用同样的参数跑" |

**不需要意图卡的例外：**
- 用户给了完整命令："python3 cj_agnes_batch.py --key-index 0"
- 纯读操作："ls /tmp"、"cat xxx"
- 用户明确说"直接做/不用确认"

---

## 意图卡格式

填充模板 `/root/.hermes/launch_manifest_template.json`，用自然语言输出给用户：

```
══════ 操作意图卡 ══════

📋 你的要求: {user_request}
🧠 我的理解: {agent_understanding_in_plain_language}
⚠️ 不确定的点: {list_ambiguities}

──── 具体动作 ────
{for each action:}
  动作 {N}: {label}
    类型: {script_exec|file_write|api_call|config_change}
    目标/命令: {target}
    参数: {params}
    在哪跑: {platform}
    预期结果: {expected_outcome}
    🔴 搞错的后果: {risk_if_wrong}

──── 风险评估 ────
  可逆吗: {是/否}
  回滚方案: {rollback_plan}
  预计耗时: {estimated_duration}

══════════════════════
请确认以上理解是否正确？
```

---

## 确认流程

1. Agent 生成意图卡 → 输出给用户
2. 用户回复「对/正确/是的/可以/确认」→ 记录 `user_confirmed: true` → 执行
3. 用户回复「不对/K4 是另一个脚本」→ 修正意图卡 → 重新确认
4. 用户 30 秒内不回复 → 不执行，等待

**绝对禁止：没有用户确认就执行。**

---

## CJ/K4 教训复盘

如果当时有这张卡：

```
📋 你的要求: 把 CJ AGNES 管线重新拉起来
🧠 我的理解: 4 个 Key 全都用同一个脚本、同一批数据
⚠️ 不确定的点: K4 是否和 K1-K3 完全一样？

──── 具体动作 ────
  动作 1: KEY1 — cj_agnes_batch.py --key-index 0, WSL
  动作 2: KEY2 — cj_agnes_batch.py --key-index 1, WSL
  动作 3: KEY3 — cj_agnes_batch.py --key-index 2, WSL
  动作 4: KEY4 — cj_agnes_batch.py --key-index 3, WSL  ← 🔴
  🔴 搞错的后果: K4 跑错脚本，浪费数千次 API 配额 + 污染输出
```

你一看：「K4 不是这个脚本」→ 纠正 → 避免事故。

---

## 与其他护栏的关系

```
[意图闸门] → [截断检测] → [危险工具] → [执行] → [副作用采集]
    ↑                                            ↑      ↑      ↑
  intent-gate                              guard-   guard-  side-effect
  (这一层)                                shortcuts dangerous collector
```

**意图闸门是第 0 层** — 在动手之前先对齐。其他四层管的是"执行过程中的安全"，这一层管的是"执行之前你在想什么"。

---

## Pitfalls

1. **不要对用户明确指出的命令套意图卡** — "跑 python3 xxx --key-index 0" 直接跑
2. **意图卡不是用来炫技的** — 控制在 15 行以内，不要写成论文
3. **不确定的点必须列出来** — 哪怕只有一个模糊点，也要标 ⚠️
4. **用户说"直接做" = bypass** — 记录 bypass 原因，不追问
