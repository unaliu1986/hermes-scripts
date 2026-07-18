# 🛡️ DECO 护栏三层 — 每次操作自动触发

> 借鉴腾讯 DECO Agent 引擎的 Hook 体系。Prompt 管不住的问题，框架层代码兜底。

## 第一层：写侧截断检测（guard-shortcuts）

**所有 file_write / write_file / patch 操作前，扫描截断标记。**

命中以下任一模式 → 拒绝写入 → 重新生成：
- `...` `…`（省略号）
- `# 其他字段...` `-- remaining...` `/* same */`（注释跳段）
- `TODO` `FIXME` + `implement/实现/填`（占位符）
- 行号跳跃（>200行文件，相邻行差 >30）

## 第二层：危险工具 HITL（guard-dangerous）

**所有 terminal 调用前，查 `/root/.hermes/dangerous_tools.yaml`。**

| 级别 | 行为 |
|------|------|
| CRITICAL | 物理阻断 → `clarify(choices=[...])` 确认 |
| HIGH | 确认 + 可选理由 |
| MEDIUM | 警告继续 |
| whitelist | 直接放行 |

## 第三层：副作用采集（side-effect-collector）

**每次写/跑操作后，必过三阶段闸门：**

```
写代码 → [阶段一: 写完验证] → 跑脚本 → [阶段二: 跑中监控] → 跑完 → [阶段三: 跑完验证]
```

- **阶段一**（6 项）：文件存在、行数、语法、截断、输入路径、输出目录 — 全部 PASS 才启动
- **阶段二**（6 项）：进程存活、日志进度、错误率、配额、心跳、磁盘 — 5 个告警阈值
- **阶段三**（7 项）：退出码、stderr、输出文件、断点、行数对比、空行、配额

> **铁律：写完不改 = 没写完。跑完不验 = 没跑完。不再需要用户提醒。**

## 配置

- 危险工具清单：`/root/.hermes/dangerous_tools.yaml`
- 副作用状态：`/root/.hermes/side_effects.json`
- Skill 目录：`skills/devops/guard-shortcuts/` `guard-dangerous/` `side-effect-collector/`
```
