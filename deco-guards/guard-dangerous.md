---
name: guard-dangerous
description: "DECO HITL 门禁 — 危险操作物理阻断。所有 terminal 调用前，查 dangerous_tools.yaml，匹配则必须用 clarify 确认后放行。"
version: 1.0.0
triggers:
  keywords: [terminal, run, 执行, 提交, 部署, 杀进程, 删除, 发布, 推送]
  mode: before_tool
metadata:
  hermes:
    tags: [guard, deco, hitl, safety, P0]
    config_file: ~/.hermes/dangerous_tools.yaml
---

# 危险工具 HITL 门禁 v1.1

## 核心规则

**所有 terminal 调用，执行前必须过危险工具清单检查。**

这是 DECO beforeTool Hook 的 Hermes 等价实现 —— 物理阻断，不可绕过。

## 门禁流程（v1.1 管道安全版）

```
每次 terminal() 调用前：
  1. 解析命令：如果有管道 | → 拆分为独立子命令列表
     - echo "DROP TABLE" | mysql → ["echo ...", "mysql"]
     - 每个子命令独立检查
  2. 展开 $(...) 和 `...` 命令替换 → 递归检查
  3. 展开 $VAR → 递归检查
  4. 对每个叶子命令：
     a. 先查 whitelist（精确匹配 or 路径通配） → 命中 → 放行
     b. 再查 tools[].pattern → 命中 → 按 level 处理
  5. 所有子命令全部通过 → 放行
  6. 任一子命令被阻断 → 整条命令被阻断

⚠️ 关键变更 v1.1：
  - whitelist 在 pattern 之前匹配（不是之后）
  - 管道命令必须拆分子命令逐个检查
  - 不支持 AST 的环境用启发式：管道符 | 分割 → 拆
```

## 确认话术

根据 YAML 中的 `confirm` 字段和 `options` 字段生成 clarify 调用：

```python
# CRITICAL 示例
clarify(
    question="⚠️ 确认将数据提交到 eBay 生产环境？建议先 dry-run。",
    choices=["推生产", "先 dry-run", "取消"]
)
# 选"推生产" → 执行命令
# 选"先 dry-run" → 修改命令，加上 --dry-run 参数
# 选"取消" → 中止
```

## 用户确认后的处理

| 用户选择 | 行为 |
|---------|------|
| 确认/确认操作/确认推送 | 执行原命令 |
| 先 dry-run | 插入 `--dry-run` 参数后执行 |
| 改为测试/改为 PR | 提示修改方案，不执行 |
| 取消 | 中止，返回 "操作已取消" |

## require_reason

如果 YAML 中 `require_reason: true`，确认后记录操作理由：
```
时间: {timestamp} | 命令: {command} | 理由: {user_reason}
```

## Pitfalls

1. **不要对 cron job / no_agent 脚本套门禁** — 确定性脚本不需要 HITL
2. **whitelist 优先** — `/tmp/` 下的常见清理操作安全
3. **管道命令可能漏检** — `echo "DROP TABLE" | mysql` 当前版本不处理
4. **用户说"直接做" = bypass** — 不要反问第二次
