# Agent 三层治理架构

从代码约束 → 架构隔离 → 多 Agent 长线稳定性，自底向上的完整治理体系。

## 架构总览

```
┌─────────────────────────────────────────────────────┐
│  第三层：多 Agent 长线稳定性                          │
│  自愈总管 + cron 调度 + 心跳 + 配额熔断 + EVOLVE     │
├─────────────────────────────────────────────────────┤
│  第二层：架构约束                                    │
│  目录权限隔离 + 交付门禁 + 数据路由 + 文件邮箱       │
├─────────────────────────────────────────────────────┤
│  第一层：SKILL 代码约束                               │
│  agent-discipline + code-review-gate + anti-ratio   │
└─────────────────────────────────────────────────────┘
```

**核心理念**：不信任 Agent 的判断，只信任机器可读的证据。

## 第一层：代码怎么写

| 约束 | 管什么 | 实现 |
|---|---|---|
| agent-discipline | Agent 行为：声明假设、范围自律、自愈优先诊断 | SKILL.md |
| code-review-gate | 代码质量：flush缺失、API超时、falsy陷阱 | grep + cron |
| anti-rationalization | 防自欺：pytest绿≠通过、API_FAIL≠NO_SUPPLY | 确定性检查 |
| Ponytail | 精简：不需要就别做 | Memory 注入 |

**本地 Hermes 适配**：
- agent-discipline-core 直接复用（零平台依赖）
- 创建 agent-discipline-local 适配层，填入本地工具名、路径

## 第二层：架构怎么搭

### 2.1 目录权限隔离

**原理**：每个 Agent 只能写自己目录，工具层拦截（先 warn 后 enforce）。

**文件**：`write_guard.py`（本目录，可直接复制使用）

**本地 Hermes 适配**：
1. 创建 `dir_owners.json`，填入本地 Agent 的目录归属
2. 给关键脚本加 `from write_guard import guard_open`
3. 用 warn 模式观察一周
4. 确认无误后切 enforce

### 2.2 交付门禁

**原理**：Agent 说"通过了"不算，必须读文件验证。

**文件**：`anti_rationalization_check.sh`（框架，需填本地检查项）

**本地 Hermes 适配检查项**：
- [ ] 图片产出文件新鲜度（>Xh 未产出 → 过期）
- [ ] bridge 双向同步心跳（>Xmin 无心跳 → 断连）
- [ ] ComfyUI / 仙宫云 API 配额（剩余 <X → 告警）
- [ ] Agnes API 配额
- [ ] 本地死信队列积压

### 2.3 数据路由

**原理**：脚本不准用 glob 猜文件，必须读路由表取精确路径。

**文件**：`router_check.py`（框架，需填本地任务映射）

**本地 Hermes 适配**：
- 建 `data_router.json`：定义每个任务的确切输入输出文件
- 填 `TASK_SCRIPTS` 映射：脚本名 → 路由任务名
- 检查器自动发现 glob 绕过

### 2.4 文件邮箱（未来）

每个 Agent 有自己的 `mailboxes/agent_name.json`，通过读写 JSON 传递任务。
当前用共享状态（health 文件），串行接力场景出现后再切。

## 第三层：跑起来怎么稳

| 约束 | 管什么 |
|---|---|
| cron + 心跳 | 30min 心跳，挂了报警 |
| 自愈总管 | 诊断→匹配→修复→验证→杀进程 |
| 配额熔断 | 90%预警 + 100%熔断 |
| EVOLVE | 踩坑3次 → 固化到代码 |
| MoA 多模型 | 关键决策交叉验证 |

**本地 Hermes 适配**：
- 心跳监控：用 overseer_agent.py 框架，填入本地进程名
- 配额熔断：接入本地 API（Agnes, ComfyUI 等）
- EVOLVE：本地 SKILL 的 Pitfalls 自动追加

---

## 快速接入

```bash
# 1. 复制本目录到本地
cp -r architecture/ ~/hermes-architecture/

# 2. 先接入 write_guard（零依赖）
cd ~/hermes-architecture
python3 write_guard.py check <your_agent> <test_path>

# 3. 创建本地 dir_owners.json
# 填入你的 Agent 和目录

# 4. 给关键脚本加 guard_open
# 替换 open(path, 'w') → guard_open('my_agent', path, 'w')

# 5. 定制约 2 个 checker，绑 cron
```

## 文件清单

| 文件 | 类型 | 说明 |
|---|---|---|
| `README.md` | 文档 | 本文件 |
| `write_guard.py` | 直接复用 | 目录权限守卫模块 |
| `anti_rationalization_check.sh` | 框架复用 | 交付门禁检查，需填本地检查项 |
| `router_check.py` | 框架复用 | 数据路由合规检查，需填本地任务映射 |
