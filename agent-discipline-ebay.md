---
name: agent-discipline-ebay
description: "agent-discipline-core 的 eBay 项目适配层。填入具体工具名、路径、参数。加载 core 后加载本文件。触发：eBay脚本、定价、上架、采集、自愈。"
version: 1.0.0
triggers:
  - eBay
  - 定价
  - 上架
  - 采集
  - 竞品
  - 自愈
  - 反推
---

# Agent 纪律 — eBay 项目配置

本文件是 `agent-discipline-core` 的平台适配层。先加载 core（5 条通用规则），再加载本文件填入具体参数。

---

## 平台参数

| 变量 | 值 |
|---|---|
| `{PLATFORM}_health_check` | `python3 /root/ebay_data/overseer_agent.py` |
| `{PLATFORM}_notify` | 微信（通过 pipeline_notify.txt → cron 推送） |
| `{PLATFORM}_known_patterns` | `heal_submit_fails.py` 的 6 种模式 + overseer N1-N4 |
| `{PLATFORM}_health_dir` | `/root/ebay_data/health/` |
| `{PLATFORM}_skills_dir` | `~/.hermes/skills/` |
| `{N}` 心跳超时 | 30 分钟 |
| `{N}` 回写阈值 | 同一坑踩 3 次 |

---

## eBay 专用案例

### 规则 1 案例：声明假设

- reverse_price.py：假设万邦 API 可用 → 挂了返回空 → 全标 NO_SUPPLY（本应是 API_FAIL）
- batch_update_v4.py：假设 eBay Token 有效 → 过期 → 4000 条 FAIL

### 规则 3 案例：运行守护

- scan_competitors：Competitor DB 文件每 10 条 flush+fsync，防止崩溃丢数据
- 万邦 API：`.wanbang_count` 追踪调用量，日配额 10K
- eBay API：Browse API 三凭证各 5K/天，18:00 cron 验证

### 规则 4 案例：自愈优先

- API 限流 → 写 `reset_creds` 控制文件，让进程自己切凭证，不杀进程
- 90% 失败走 `known_patterns`（6 种提交失败模式），不用 LLM
- overseer = 检测+匹配+修复+验证，4 步闭环

### 规则 5 案例：经验回写

- 新失败模式 → `heal_submit_fails.py` 追加模式
- 坑踩 3 次 → 从 SKILL 文字固化到代码检查
- tricky bug → 对应 Skill 的 Pitfalls 段

---

## 已有规则速查

| 你想干什么 | 看哪个 |
|---|---|
| 这活能不能不做？ | Ponytail 六阶梯 |
| 代码写完了，质量过关吗？ | code-review-gate（11 道闸门） |
| 跑完了，结果是真的吗？ | anti-rationalization-gate（8 条防自欺） |
| 出 bug 了怎么修？ | 铁律：先确认根因 → 不擅改 → 小样再全量 |
| 新脚本要跑 7x24？ | script-boundary-card（4 维边界卡） |
| 多 Agent 协作？ | 各自只写自己目录，通过健康文件交接 |
| API 诊断？ | 交叉验证：用户说恢复但我测 503 → 先问其他脚本 |
| eBay Token？ | Trading API 300s/3600s 限流，降速 0.8s，连续 3 fail 退出 |
| 淘宝型号搜索？ | DN15 等短型号必须带品类词 |
