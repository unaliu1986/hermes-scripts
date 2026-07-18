---
name: fail-asymmetric
description: "DECO 失败语义非对称 — 读失败降级继续，写失败硬阻断抛异常。治错误传播和静默失败。"
version: 1.0.0
triggers:
  keywords: [error, fail, 失败, 报错, exception, traceback, 超时, 404, 429, 503]
  mode: after_tool
metadata:
  hermes:
    tags: [deco, fail, asymmetric, safety, P2]
---

# 失败语义非对称

## 核心原则

> **读失败 = 信号，写失败 = 炸弹。对读和对写，不能用同一套错误处理。**

这是 DECO 的核心设计原则 —— 区分"可恢复"和"不可恢复"的失败。

---

## 读操作失败 → 降级继续

读操作失败不代表数据丢了，只是暂时不可用。给 LLM 完整信息让它自行处理。

| 失败类型 | 处理 | 示例 |
|---------|------|------|
| `file_read` 404 | 返回「文件不存在」，继续 | `read_file('/tmp/nonexist')` → 告知，不崩 |
| `web_search` 超时 | 返回「搜索超时，请重试或用其他关键词」 | 不阻塞后续操作 |
| `web_extract` 403 | 返回「页面不可访问」，建议浏览器 | |
| API 429 (限流) | 返回 quota 信息 + 等待时间 | 不重试，让 LLM 决定 |
| API 5xx (服务端) | 重试 1 次 → 仍失败则返回错误 | 最多 2 次 |
| `terminal` 非零退出 | 返回 exit_code + stderr，继续 | 不阻断，LLM 判断是否致命 |

**降级策略**：
```python
# 读失败不抛异常，返回结构化信息
{
  "status": "degraded",
  "error_type": "not_found|timeout|rate_limited|server_error",
  "message": "具体原因",
  "suggestion": "建议操作",
  "can_continue": true
}
```

---

## 写操作失败 → 硬阻断 + 幂等保护（v1.1）

写操作失败意味着数据可能已损坏、部分写入或完全丢失。**不允许静默继续。**

| 失败类型 | 处理 | 阻断方式 |
|---------|------|---------|
| `file_write` EIO | 立即阻断，不继续 | 抛异常，停止任务链 |
| `write_file` 磁盘满 | 即刻阻断 + 报告剩余空间 | 抛异常 |
| `patch` 匹配失败 | 阻断 + 显示上下文 | 提示用户检查 diff |
| API POST/PUT（非幂等） | 重试前先查 idempotency key → 已成功则返回旧结果 | 不重复提交 |
| API POST/PUT（幂等） | 重试最多 2 次 | 幂等操作可安全重试 |
| API 429（写操作） | 不重试，直接报 quota 耗尽 | 和读的 429 处理不同 |
| `terminal` 写脚本失败但退出码 0 | **检查 stderr + stdout 尾行** → 有 ERROR 则阻断 | 双重检查 |

### 幂等保护（v1.1 新增）

对不可逆的写操作（eBay AddItem、git push、DELETE 等），重试前必须：
1. 本地记录 `X-Idempotency-Key: {hash(user_intent + target + timestamp)}`
2. 重试前检查本地状态文件 `/tmp/hermes_idempotency.json`：
   - 如果 same key + status=success → 直接返回上次结果，不重试
   - 如果 same key + status=failed → 可以重试（上次确实失败了）
   - 如果 key 不存在 → 新建记录，执行操作
3. 写操作成功后立即写入 status=success

### 幂等判断速查

| 操作 | 幂等？ | 可重试？ |
|------|--------|---------|
| `file_write`（同路径覆盖） | ✅ 是 | 可重试 |
| `git push`（无新 commit） | ✅ 是 | 安全 |
| `git push`（有新 commit） | ❌ 否 | 先查远端 SHA |
| eBay AddItem | ❌ 否 | 重试前查 inventory |
| eBay ReviseItem | ✅ 是 | 同一 ItemID 可复写 |
| `rm -rf` | ✅ 是 | 已删则报错无害 |
| `pip install` | ✅ 是 | 已装则跳过 |

**阻断策略**：
```python
# 写失败 → 硬阻断
{
  "status": "blocked",
  "error_type": "io_error|disk_full|patch_failed|api_failed|silent_error",
  "message": "具体原因",
  "can_continue": false,
  "require_user_decision": true,  # 等用户决定下一步
}
```

---

## 非对称对比

| 维度 | 读失败 | 写失败 |
|------|--------|--------|
| **默认行为** | 降级继续 | 硬阻断 |
| **重试次数** | 0-1 次 | 2-3 次 |
| **429 处理** | 返回 quota 信息 | 立刻停止 |
| **退出码非零** | 信息提示 | 检查 stderr，有致命则阻断 |
| **用户确认** | 不需要 | 需要（数据安全） |
| **状态传播** | 不传播 | 阻断后续所有依赖操作 |

---

## 常见场景速查

| 场景 | 类型 | 行为 |
|------|------|------|
| `ls` 目录不存在 | 读 | 返回错误信息，LLM 换路径 |
| `python3 script.py` 报错 | 写（脚本执行） | 返回错误，分析原因，修 |
| `curl` eBay API 返回 429 | 读 | 返回 quota 信息，不重试 |
| `curl` eBay AddItem 返回 429 | 写 | 立刻阻断，报告配额耗尽 |
| `git push` 失败 | 写 | 阻断，检查原因 |
| `pip install` 失败 | 写 | 阻断，检查依赖 |
| `patch` 找不到 old_string | 写 | 阻断 + 显示文件当前内容 |
| `read_file` 无权限 | 读 | 降级，提示用 sudo |

---

## Pitfalls（v1.1）

1. **不要把 exit_code=0 等同于成功** — 有些脚本失败但 exit 0（静默失败），必须同时查 `stderr` + `stdout 尾行`
2. **检查 stdout 尾 20 行** — Python 脚本的 `print(e)` / logging 可能在 stdout，不是 stderr
3. **写操作的 429 不能和读的一视同仁** — 读 429 可以等，写 429 立即停
4. **降级 ≠ 忽略** — 读失败的信息必须展示给用户，不能 silence
5. **依赖链阻断** — 如果一个写操作被阻断，后续依赖它的一律跳过
6. **幂等保护是硬要求** — 非幂等写操作（eBay AddItem、git push 主分支）重试前必须查状态
