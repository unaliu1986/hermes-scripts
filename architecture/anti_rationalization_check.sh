#!/bin/bash
# anti_rationalization_check.sh — 交付门禁：机器可读状态检查
# 每天两次，检查 Agent 是否在自欺欺人。
# 无违规 → 静默退出。有违规 → 输出报告。

DATA_DIR=/root/ebay_data
HEALTH_DIR=$DATA_DIR/health
NOW=$(date +%s)
VIOLATIONS=0
REPORT=""

# ─── Gate 1: 竞品数据新鲜度 ──────────────────────────
DB_FILE=$DATA_DIR/competitor_db.json
if [ -f "$DB_FILE" ]; then
    DB_AGE=$(( NOW - $(stat --format='%Y' "$DB_FILE") ))
    DB_HOURS=$(( DB_AGE / 3600 ))
    if [ "$DB_AGE" -gt 86400 ]; then
        REPORT="${REPORT}
🔴 Gate 1 数据过期: 竞品数据 $DB_HOURS 小时未更新（阈值 24h）"
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
fi

# ─── Gate 2: 万邦 API 错误率 ─────────────────────────
WANBANG=$DATA_DIR/lix/.wanbang_count
if [ -f "$WANBANG" ]; then
    WB=$(cat "$WANBANG")
    # 格式: YYYYMMDD|count|last:keyword|items:N
    # 或者: YYYYMMDD|count|exhausted:ERR_CODE
    if echo "$WB" | grep -q 'exhausted'; then
        REPORT="${REPORT}
🔴 Gate 2 API 配额耗尽: 万邦 API 今日已耗尽 → 禁止标记 NO_SUPPLY"
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
fi

# ─── Gate 3: 健康文件新鲜度 ──────────────────────────
STATUS=$HEALTH_DIR/status.json
if [ -f "$STATUS" ]; then
    TS=$(python3 -c "import json; print(json.load(open('$STATUS')).get('ts',''))" 2>/dev/null)
    if [ -n "$TS" ]; then
        TS_EPOCH=$(date -d "$TS" +%s 2>/dev/null || echo 0)
        STATUS_AGE=$(( NOW - TS_EPOCH ))
        STATUS_HOURS=$(( STATUS_AGE / 3600 ))
        if [ "$STATUS_AGE" -gt 7200 ]; then  # 2h
            REPORT="${REPORT}
🔴 Gate 3 健康过期: status.json $STATUS_HOURS 小时未更新（阈值 2h）"
            VIOLATIONS=$((VIOLATIONS + 1))
        fi
    fi
fi

# ─── Gate 4: Browse API 配额（按凭证分别检查）─────────
BROWSE_QUOTA=$HEALTH_DIR/browse_api_quota.json
if [ -f "$BROWSE_QUOTA" ]; then
    BROWSE_ALERT=$(python3 -c "
import json
d=json.load(open('$BROWSE_QUOTA'))
counts=d.get('counts',{})
max_used=0; max_cred=''
for cred,c in counts.items():
    if c > max_used:
        max_used=c; max_cred=cred
ratio = max_used / 5000.0
if ratio >= 0.95:
    print(f'CRITICAL:{max_cred}:{max_used}')
elif ratio >= 0.90:
    print(f'WARN:{max_cred}:{max_used}')
" 2>/dev/null)
    if echo "$BROWSE_ALERT" | grep -q 'CRITICAL'; then
        CRED=$(echo "$BROWSE_ALERT" | cut -d: -f2)
        USED=$(echo "$BROWSE_ALERT" | cut -d: -f3)
        REPORT="${REPORT}
🔴 Gate 4 Browse 配额告警: $CRED 已用 $USED/5000 (≥95%)"
        VIOLATIONS=$((VIOLATIONS + 1))
    elif echo "$BROWSE_ALERT" | grep -q 'WARN'; then
        CRED=$(echo "$BROWSE_ALERT" | cut -d: -f2)
        USED=$(echo "$BROWSE_ALERT" | cut -d: -f3)
        REPORT="${REPORT}
🟡 Gate 4 Browse 配额预警: $CRED 已用 $USED/5000 (≥90%)"
    fi
fi

# ─── Gate 5: self_heal 死信队列积压 ───────────────────
DLQ=$DATA_DIR/dead_letters
if [ -d "$DLQ" ]; then
    DLQ_COUNT=$(find "$DLQ" -name "dlq_*.json" -mmin -1440 2>/dev/null | wc -l)
    if [ "$DLQ_COUNT" -gt 5 ]; then
        REPORT="${REPORT}
🔴 Gate 5 死信积压: 24h 内 $DLQ_COUNT 条死信（阈值 5）"
        VIOLATIONS=$((VIOLATIONS + 1))
    elif [ "$DLQ_COUNT" -gt 0 ]; then
        REPORT="${REPORT}
🟡 Gate 5 死信队列: 24h 内 $DLQ_COUNT 条死信"
    fi
fi

# ─── Gate 6: 目录权限违规 ─────────────────────────────
VIOLATION_LOG=$HEALTH_DIR/dir_violations.jsonl
if [ -f "$VIOLATION_LOG" ]; then
    VIO_COUNT=$(python3 -c "
import json
cutoff=$(date -d '24 hours ago' +%s 2>/dev/null || echo 0)
count=0
with open('$VIOLATION_LOG') as f:
    for line in f:
        try:
            r=json.loads(line.strip())
            ts=r.get('ts','')
            # rough check
            count+=1
        except: pass
print(count)" 2>/dev/null)
    if [ -n "$VIO_COUNT" ] && [ "$VIO_COUNT" -gt 0 ]; then
        REPORT="${REPORT}
🟡 Gate 6 目录越权: 24h 内 $VIO_COUNT 条违规写入"
    fi
fi

# ─── 输出 ─────────────────────────────────────────────
if [ "$VIOLATIONS" -gt 0 ]; then
    echo "## 🛡️ 防合理化闸门报告 — $(date '+%Y-%m-%d %H:%M')"
    echo ""
    echo "发现 $VIOLATIONS 项违规："
    echo "$REPORT"
    echo ""
    echo "---"
    echo "📋 快照:"
    echo "- 竞品数据: ${DB_HOURS:-?}h 前"
    echo "- 万邦调用: $(cat "$WANBANG" 2>/dev/null | cut -d'|' -f2 | head -1) 次"
    echo "- Browse 配额: ${TOTAL_BROWSE:-?}/5000"
fi
