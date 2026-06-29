---
name: anti-rationalization-gate
description: "防合理化闸门——Agent不能自欺欺人。pytest 0≠通过/xfailed=FAIL/API_FAIL≠NO_SUPPLY/数据过期必须重扫。借鉴Agent-Skills防合理化表格。触发：交付前、QA报告、定价结果、竞品数据新鲜度检查。"
version: 1.0.0
triggers:
  - 防合理化
  - QA 通过
  - 交付检查
  - pytest 过了
  - 数据没过期吧
---

# 防合理化闸门（Anti-Rationalization Gate）

借鉴 Agent-Skills 的防合理化表格。「Agent 说通过了」不算数，必须机器可判定。

## 核心理念

```
Agent 汇报 "通过了" → 【防合理化 Gate】→ 读文件验证 → 真通过/打回
```

**铁律：Agent 会自欺欺人。文件不会。**

---

## 防合理化速查表

| Agent 可能会说 | 为什么是自欺欺人 | 机器怎么判 |
|---|---|---|
| **"pytest 全绿，通过"** | xfailed/xpassed 也是绿 | `grep -c 'xfailed\|xpassed' test_report` > 0 → FAIL |
| **"NO_SUPPLY，淘宝没货"** | 可能是万邦 API 挂了返回空 | 先查 `/root/ebay_data/lix/.wanbang_count`，error_rate > 10% → API_FAIL |
| **"竞品数据今天的，能用"** | "今天"可能已超 12h | `stat --format='%Y' competitor_db.json` 与当前时间差 > 86400 → STALE |
| **"batch_update 配额耗尽自动停了"** | 可能前 3 条 FAIL 但后面还在浪费调用 | 查日志：连续 3 条 Call usage limit → 禁止重试直到下次 cron |
| **"定价 50% OK 率，可以跑"** | 50% 意味着一半调用在浪费 | OK 率 < 70% → 先诊断根因，不全量 |
| **"提交了 1000 条"** | 可能 800 条 FAIL | 查 daily_log：FAIL > 30% → 中断排查 |
| **"reverse_price 跑完了"** | 可能 API_FAIL 被误标为 NO_SUPPLY | wanbang_counter 中 error > 0 → 逐条检查 API_FAIL vs NO_SUPPLY |
| **"health.json 绿灯"** | 可能 6h 前更新的 | 检查 last_updated，> 1h → 重新采集 |

---

## 闸门检查流程

### Step 1: 确定检查场景

| 场景 | 触发 |
|---|---|
| QA 报告交付 | pytest 结果、覆盖率 |
| 定价结果 | OK 率、API_FAIL vs NO_SUPPLY |
| 竞品新鲜度 | `competitor_db.json` 时间戳 |
| 提交状态 | FAIL 率、配额状态 |
| 数据契约 | health.json 新鲜度 |

### Step 2: 确定性检查（不依赖 LLM）

```
1. pytest gate:
   - 读 qa/test_status.json 或日志
   - grep xfailed/xpassed → 有则 FAIL
   - 覆盖率 < 80% → FAIL

2. API 健康 gate:
   - 读 .wanbang_count
   - error/total > 0.1 → API_FAIL
   - 强制禁止标记 NO_SUPPLY

3. 数据新鲜度 gate:
   - stat competitor_db.json 修改时间
   - > 24h → STALE，禁止定价
   - 检查 last_scan_ts

4. 提交质量 gate:
   - 读 daily_log
   - FAIL/total > 0.3 → 中断
   - 连续 3 条 Call usage limit → 禁止重试

5. 配额熔断 gate:
   - 读 reset_creds 控制文件
   - 存在 → 当前凭证已限流
```

### Step 3: 输出闸门报告

```
## 🛡️ 防合理化闸门报告

| 门 | 状态 | 证据 |
|----|------|------|
| pytest 真通过 | ✅/❌ | xfailed=0, xpassed=0 |
| API 未伪装成 NO_SUPPLY | ✅/❌ | wanbang error_rate=0.02 |
| 数据未过期 | ✅/❌ | 竞品最后更新: 3h 前 |
| 提交质量 | ✅/❌ | FAIL/total=5% |
| 配额安全 | ✅/❌ | 无熔断标记 |

### 判定: PASS / FAIL
FAIL 项: [具体列出]

### 自欺欺人拦截:
- "pytest 全绿" → 🔴 拦截: 3 个 xfailed
- "NO_SUPPLY 2000 条" → 🟡 警告: API error_rate 8%
```

---

## 集成到现有系统

| 挂载点 | 脚本 | 闸门 |
|---|---|---|
| overseer_agent.py N4 检查 | 健康检查 | 新鲜度 gate + 配额 gate |
| heal_submit_fails.py | 提交失败分析 | 提交质量 gate |
| reverse_price.py 跑后 | 定价结果 | API_FAIL gate + OK率 gate |
| batch_update_v4.py 跑前 | 配额检查 | 配额熔断 gate |
| daily cron 交付 | 交付报告 | 全部门 gate |

---

## 与 code-review-gate 的关系

| | code-review-gate | anti-rationalization-gate |
|---|---|---|
| 检查什么 | 代码质量 | Agent 是否自欺欺人 |
| 时机 | 脚本写完后、跑之前 | 数据产出后、交付前 |
| 判定方式 | grep + LLM 语义审查 | 纯确定性检查（读文件） |
| 谁执行 | Agent 自检 | cron/overseer 巡查 |

---

## 经验积累

每次拦截到自欺欺人行为，追加到速查表。
