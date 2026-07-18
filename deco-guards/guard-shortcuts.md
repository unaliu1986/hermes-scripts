---
name: guard-shortcuts
description: "DECO 写侧截断检测 — 所有 file_write/patch/write_file 操作前必检截断标记。模拟 DECO 的 beforeTool(写) Hook。"
version: 1.0.0
triggers:
  keywords: [file_write, write_file, patch, 写文件, 保存脚本, 生成代码]
  mode: before_tool
metadata:
  hermes:
    tags: [guard, deco, safety, P0]
    always_load: false
---

# 写侧截断检测 Guard

## 核心规则

**所有 file_write / write_file / patch 操作，写入前必须逐条过截断检测。**

这是 DECO 写侧 onload 的 Hermes 等价实现 —— 不是靠 Agent"记住"，而是靠 Skill 强制执行。

## 截断标记清单（v1.1 — 去误报版）

扫描即将写入的 `content` 或 `new_string`。**只检查注释行，不检查代码行。**

```python
TRUNCATION_PATTERNS = [
    # ═ 注释型截断（高置信度） ═
    # 匹配: # 其他字段... | -- remaining fields... | // 同上 | <!-- 略 -->
    (r'(#|--|//|<!--)\s*(其他|其余|remaining|rest|same as above|同上|略|省略)',
     '注释型跳段 — CRITICAL'),
    (r'/\*\s*(same|同上|略|省略).*\*/',
     '块注释截断 — CRITICAL'),
    
    # ═ 占位符截断 ═
    (r'(TODO|FIXME|HACK)\s*[：:]\s*(implement|实现|填写|补全|完成)',
     'TODO占位 — CRITICAL'),
    (r'pass\s*#\s*(implement|实现|填写|补全|完成)',
     'pass占位 — CRITICAL'),
    
    # ═ 省略号（仅注释行） ═
    # 代码行的 ... 是合法 Python/JS/Go 语法，不检查
    (r'^[^a-zA-Z0-9]*(#|--|//).*\.{3,}',
     '注释中省略号 — WARN'),
    (r'^[^a-zA-Z0-9]*(#|--|//).*…',
     '注释中中文省略号 — WARN'),
]
```

## 不检查（v1.1 排除清单）

| 排除项 | 原因 |
|--------|------|
| 代码行的 `...` | Python Ellipsis/JS spread/Go variadic 是完全合法的 |
| Markdown 分隔符 `---` `===` | 不是截断标记 |
| diff 的 `@@` 行 | patch 格式标签 |
| SQL 中的 `...` | PostgreSQL variadic 语法 |
| 字符串内的 `...` | `"loading..."` 是 UI 文本，不是截断 |
| ~~行数断层检测~~ | v1.1 移除 — AI 生成的代码无显式行号，无法检测 |

## 执行流程（v1.1）

```
每次 file_write / write_file / patch 之前：
  1. 将 content 按行拆分
  2. 过滤：只保留注释行（以 # -- // 开头的行 + /* */ 块）
  3. 在注释行中扫描 TRUNCATION_PATTERNS
  4. CRITICAL 匹配 → 拒绝写入 → 提示位置 → 重新生成
  5. WARN 匹配 → 提示「疑似截断」→ 询问用户是否继续
  6. 未命中 → 放行
```

## 拒绝时的标准回复

```
⛔ 截断检测拦截: 第 {line} 行注释「{pattern_type}: {matched_text}」

DECO 护栏层物理阻断 — 不允许跳过任何字段。
请完整生成后再写入。

上下文:
  {context_before}
→ {matched_line}
  {context_after}
```

## Pitfalls（v1.1）

1. **只查注释行** — 代码行的 `...` 是合法语法，绝不拦截
2. **diff/patch `@@` 行不查** — 格式标签
3. **文件 > 5000 行跳过详细检查** — token 开销太大
4. **字符串内的截断标记不查** — `"loading..."` 是 UI 文本
5. **Python `pass` 不拦截** — 只在 `pass # implement` 模式拦截
