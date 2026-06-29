---
name: fix-safety-protocol
description: "修复安全四步协议——Agent动手修之前必须写快照→验证→回滚/升级。防止修错。触发：自愈、修复、诊断后动手、overseer。"
version: 1.0.0
triggers:
  - 修复
  - 自愈
  - 诊断
  - 修
  - fix
  - heal
  - overseer
  - 自动修复
---

# 修复安全协议（Fix Safety Protocol）

**铁律：没写快照不准动手。验证失败必须回滚。**

## 四步协议

### Step 0：判定能不能自动修

| 可以自动修 | 禁止自动修（必须你确认） |
|---|---|
| 进程重启 | 删除数据 |
| 切凭证 | 覆盖生产文件 |
| 刷新 Token | 修改数据库结构 |
| 修改配置文件（有备份） | 不可逆操作 |
| 清理临时文件 | 你之前说"先不动"的事 |
| 6 种已知提交失败模式 | 没见过的新错误模式 |

**判断方法**：对照 known_patterns（heal_submit_fails.py 的 PATTERNS + overseer N1-N4）

- 在已知模式里 → Step 1
- 不在 → 汇报给你，等你决策，**不动手**

### Step 1：写修复快照（Fix Plan）

**动手之前**，写一个文件到 `/root/ebay_data/health/fix_plans/{round_id}.json`：

```json
{
  "round_id": "20260629_1730_N3",
  "diagnosis": "配额耗尽 → 进程卡在重试循环",
  "matched_pattern": "submit_fails.py:quota_exhausted",
  "what_i_will_do": "写 reset_creds → 等进程自己切凭证",
  "what_can_go_wrong": "reset_creds 没被读取 → 进程继续重试 → 浪费额度",
  "rollback_plan": "删除 reset_creds，手动 pkill 进程",
  "reversible": true
}
```

**快照文件是给自己保底的。10 分钟后回来看，修错了按 rollback_plan 回滚。**

### Step 2：修复 + 验证

1. 执行修复动作
2. 等一个周期（至少 2 分钟）
3. 用**第二个独立命令**验证修复效果（不能用同一个检查）
   - 例：修了进程重启 → 不能只看 pid 存在 → 要检查日志有新输出
   - 例：修了 Token → 不能只看刷新成功 → 要实际调用一次 API 确认 200

**验证失败 ≠ 没事。验证失败 = 立即执行 Step 3 回滚。**

### Step 3：回滚或升级

| 情况 | 动作 |
|---|---|
| 可逆 + 验证失败 | 立即按 rollback_plan 回滚 → 汇报你"修了但失败，已回滚" |
| 可逆 + 验证通过 | 汇报你"✅ 已自动修复: <根因→动作→验证>" |
| 不可逆 + 验证失败 | 立即汇报你"🚨 修复失败且不可回滚: <详情>" |
| 同一问题 2 次修复失败 | 停止自动修 → 汇报你"已两次修失败，需要你决策" |

---

## 和现有系统的关系

| 现有 | 本协议补充什么 |
|---|---|
| overseer N1-N4 | 在 N3（fix）之前插入快照，N3 之后强制验证 |
| heal_submit_fails.py | 已知模式可自动修，但修完必须验证 |
| agent-discipline 规则4 | 补上"修之前写快照"这一步 |
| anti-rationalization-gate | 修复后验证 = 交付前的机器可读检查 |
| pre_heal_backup.sh (每25分钟) | 关键文件自动快照到 rollback_snapshots/，修错了可恢复 |

## 防修错四层防线（经验固化）

```
Agent 要动手修 →
  第1层: 本协议 (SKILL) — 不在已知模式/不可逆/没写 fix_plan → 停手
  第2层: pre_heal_backup.sh (每25分钟) — 关键文件已有快照，修错可恢复
  第3层: overseer 红灯 (Python 硬编码) — 连续失败 → 熔断
  第4层: write_guard — 写错目录 → 记录违规
```

**经验来源**：2026-06-29 发现 VPS 自愈可能修错，仅靠 SKILL 文本不够。补了三道代码层硬防线：自动备份、overseer 熔断、write_guard 目录拦截。

---

## 快照目录

```
/root/ebay_data/health/fix_plans/
├── 20260629_1730_N3.json   ← 总管第3步修复快照
├── 20260629_1745_diag.json  ← AI诊断修复快照
└── ...
```

**每次修之前写一个。修完验证通过后保留（审计用），验证失败后追加 `_FAILED` 后缀。**

---

## 检查清单（Agent 自检）

修之前问自己：
- [ ] 这个问题在 known_patterns 里吗？（不在 → 停手）
- [ ] 是可逆操作吗？（不可逆 → 停手）
- [ ] 写了 fix_plans/{round_id}.json 吗？（没写 → 停手）
- [ ] 有独立的验证命令吗？（没有 → 停手）
- [ ] 同一问题是不是第 2 次修了？（是 → 停手）
