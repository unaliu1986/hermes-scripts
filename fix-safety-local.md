# 本地 Hermes 接入修复安全协议

从 VPS 经验迁移：Agent 自愈必须先写快照、有备份兜底、连续失败熔断。

## 一步接入

```bash
# 1. 拉取
cd ~/hermes-scripts && git pull

# 2. 安装 SKILL（如果你用 Hermes Agent）
cp fix-safety-protocol.md ~/.hermes/skills/devops/fix-safety-protocol/SKILL.md

# 3. 创建备份目录
mkdir -p ~/hermes-data/rollback_snapshots

# 4. 定制 pre_heal_backup.sh — 把你的关键文件路径替换进去
# 编辑 backup 脚本里的 FILES 数组

# 5. 给需要自愈的 cron 绑定 fix-safety-protocol
# hermes cron update <job_id> --skills agent-discipline-core,fix-safety-protocol
```

## 本地适配清单

| VPS 路径 | 本地替换为 |
|---|---|
| `/root/ebay_data/` | `~/hermes-data/` 或你的数据目录 |
| `competitor_db.json` | 你的核心数据文件 |
| `browse_api_quota.json` | 你的 API 配额文件 |
| overseer_agent.py | 本地如有总管脚本，填入路径；没有则跳过 |
| write_guard.py | 从 `architecture/write_guard.py` 复制使用 |

## 本地 Hermes 场景举例

| 可能修错的事 | 本地防护 |
|---|---|
| 图片管线脚本改错参数 | fix_plan 快照 + 备份上一次正确的参数 |
| ComfyUI API 调用崩了盲目重试 | overseer 熔断：连续失败 3 次停手 |
| bridge 同步方向搞反覆盖数据 | 同步前自动备份目标文件 |
| 删了不该删的缓存 | 删之前写快照记录路径（手动恢复） |

## 防修错四层（本地版）

```
Agent 要动手修 →
  第1层: fix-safety-protocol → 不在已知模式/不可逆 → 停手
  第2层: 自动备份(每N分钟) → 修错了从 rollback_snapshots/ 恢复
  第3层: 熔断(连续失败→停手) → Python硬编码或cron逻辑
  第4层: write_guard → 写错目录→拦截
```
