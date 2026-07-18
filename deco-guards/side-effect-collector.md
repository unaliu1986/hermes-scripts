---
name: side-effect-collector
description: "DECO afterTool 副作用采集 + Attachment 注入。所有写操作/脚本执行后，强制采集副作用并写入 state，下轮自动注入。治「跑完不验证」。"
version: 1.0.0
triggers:
  keywords: [terminal, file_write, write_file, patch, submit, add_item, revise, 运行, 执行, 部署]
  mode: after_tool
metadata:
  hermes:
    tags: [deco, afterTool, attachment, safety, P1]
    state_file: ~/.hermes/side_effects.json
    auto_load: true
---

# 副作用采集 + Attachment 注入

## 铁律

> **写完不改 = 没写完。跑完不验 = 没跑完。**

这是 DECO afterTool → Attachment 闭环的 Hermes 实现。Agent 不需要"记得验证"——框架主动 push。

---

## 一、状态文件

`/root/.hermes/side_effects.json` — 持久化的待验证清单。

格式：
```json
{
  "pending_checks": [
    {
      "id": "check_001",
      "type": "file_write|terminal|patch|cronjob",
      "target": "文件路径或命令",
      "checks_done": ["已验证项"],
      "checks_pending": ["待验证项"],
      "created_at": "ISO时间"
    }
  ]
}
```

---

## 二、验证三阶段

**每个涉及「改代码 + 跑脚本」的任务，必过三个闸门。缺一不可。**

```
写代码 → [阶段一: 写完验证] → 跑脚本 → [阶段二: 跑中监控] → 跑完 → [阶段三: 跑完验证]
```

---

## 阶段一：写完验证（写文件后 / 启动前）

**目的**：确认脚本本身没问题，才允许启动。

### A. file_write / write_file / patch 后

| # | 检查 | 命令 |
|---|------|------|
| 1 | 文件存在且非空 | `ls -la {path}` |
| 2 | 行数合理 | `wc -l {path}`（对比预期） |
| 3 | 语法通过 | `python3 -m py_compile {path}` |
| 4 | 截断检测 | 跑 guard-shortcuts 规则（无省略号/跳段） |
| 5 | 输入路径存在 | `ls {脚本依赖的输入文件}` |
| 6 | 输出目录可写 | `touch {output_dir}/.test && rm {output_dir}/.test` |

**通过标准**：6/6 全部 PASS → 才允许进入「启动脚本」。

### B. 启动前额外检查（terminal 执行前）

| # | 检查 | 说明 |
|---|------|------|
| 1 | 无同名进程冲突 | `pgrep -f {script_name}` |
| 2 | 断点文件存在 | 如果续跑模式，检查 checkpoint JSON |
| 3 | API 配额够用 | `cat /root/ebay_data/health/trading_daily_counter.json` |
| 4 | 磁盘空间充足 | `df -h {输出目录挂载点}` |

**如果断点不存在但跑续跑模式 → 阻断，先确认用户意图。**

---

## 阶段二：事件驱动监控（替代主动轮询）

**目的**：脚本跑起来后，确认它真的在跑。不依赖定时器——LLM 是请求-响应模型。

**事件驱动策略（v1.1 替代主动轮询）：**

### A. 每次用户消息/Agent 回复前

在回复用户之前，检查是否有正在运行的长任务：

| # | 检查 | 命令 |
|---|------|------|
| 1 | 上次启动的进程还活着吗 | `pgrep -f {script_name}` |
| 2 | 心跳文件上次更新是什么时候 | `stat -c %Y {heartbeat_file}` 对比当前时间 |
| 3 | 超过 10 分钟没更新 → 在回复中报告 | 「⚠️ 长任务可能已停止」 |

**不需要定时轮询** — 每次轮到 Agent 回复时自动检查一次即可。

### B. 长任务心跳契约

启动长任务时，脚本必须满足：
1. 输出心跳文件：每处理 N 条写 `{progress: N, total: M, timestamp: ISO}`
2. 心跳文件路径固定：`/tmp/{script_name}_heartbeat.json`
3. Agent 启动前检查 ± 回复前检查 = 两次覆盖

### C. 告警阈值（事件触发，非定时）

| 信号 | 触发条件 | 动作 |
|------|---------|------|
| 进程消失 | `pgrep` 无结果 | 🔴 回复中立刻告警 |
| 心跳超时 | `now - mtime > 600s` | 🟡 回复中提示 |
| 错误率 > 10% | 心跳 JSON 中有 error_count 对 | 🟡 报告，询问 |
| 配额 < 500 | counter JSON 检查 | 🟡 建议减速 |

### D. 不需要检查的

- 前台终端命令（10秒内执行完的）→ 跳过阶段二
- 读操作（ls/cat/grep）→ 跳过

---

## 阶段三：跑完验证（脚本结束后）

**目的**：确认输出正确、完整、可用。

### C. terminal 跑脚本 — 跑完后

| # | 检查 | 命令 |
|---|------|------|
| 1 | 退出码 = 0 | 看 `exit_code` |
| 2 | stderr 无致命错误 | grep `ERROR|Traceback|FAIL` |
| 3 | 输出文件存在且非空 | `ls -la {output_path} && wc -l {output_path}` |
| 4 | 断点标记完成 | `cat {checkpoint_path}` 看是否 `all_done: true` |
| 5 | 输出行数 vs 预期 | 对比输入行数，偏差 > 10% 报警 |
| 6 | 输出无空行/重复 | `head -5` + `tail -5` 肉眼扫 |
| 7 | API 配额余量 | 对比跑前后的 counter |

**特别关注**：
- **eBay API 脚本** → 额外查 `trading_daily_counter.json` 三凭证各剩多少
- **Agnes 管线** → 查日志最后一行进度 + OSS 文件数（采样） + OK/FAIL/SKIP 汇总
- **GAP 筛选** → 查输出 CSV 列名 + 行数 + 有无 `NO_MODEL` 占比
- **图片管线** → 查 OSS 上传成功率 + 本地文件数 vs 预期

### D. API 调用 — 调完后

| # | 检查 | 命令 |
|---|------|------|
| 1 | HTTP 状态码 200 | 看响应 `status_code` |
| 2 | 配额余额 | `cat {counter_path}` |
| 3 | 响应 JSON 有效 | `python3 -m json.tool` |

### E. cronjob 操作 — 改完后

| # | 检查 | 命令 |
|---|------|------|
| 1 | 状态已生效 | `cronjob(action='list')` 核对目标 job |
| 2 | 上次运行 status | 看 `last_status`（ok/error） |

---

## 三、Attachment 注入机制

**每次会话开始**，自动执行：

```bash
cat /root/.hermes/side_effects.json | python3 -m json.tool
```

如果有 `pending_checks`，逐条执行验证动作，完成后将 `checks_done` 写回。

**如果 pending_checks 为空**，跳过注入——不增加无意义的 token。

---

## 四、记录格式

每完成一项检查，追加到 `checks_done`：

```json
{
  "check": "语法检查",
  "result": "pass|fail",
  "detail": "python3 -m py_compile OK",
  "at": "2026-07-18T12:34:56"
}
```

全部通过后 → `checks_pending` 清空 → 该条从 `pending_checks` 移除。

---

## 五、Pitfalls

1. **不要只跑不报告** — 验证结果必须在回复中展示，不能 silence
2. **语法检查不是运行** — `py_compile` 不执行代码，安全无副作用
3. **验证失败 = 任务未完成** — 继续修，不要跳过
4. **大文件 wc -l 用 rtk** — 超过 10 万行用 `rtk wc -l`
5. **OSS 文件数统计别用 oss2.ObjectIterator 全量扫** — 用 `max_keys=10` 采样即可
