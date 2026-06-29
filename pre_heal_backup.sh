#!/bin/bash
# pre_heal_backup.sh — 自愈动手前的自动快照
# 绑在总管 cron 前 2 分钟跑，备份关键文件

SNAPSHOT_DIR=/root/ebay_data/rollback_snapshots
mkdir -p "$SNAPSHOT_DIR"
TS=$(date +%Y%m%d_%H%M)

# 关键文件列表
FILES=(
    /root/ebay_data/competitor_db.json
    /root/ebay_data/health/status.json
    /root/ebay_data/health/browse_api_quota.json
    /root/ebay_data/lix/.wanbang_count
    /root/ebay_data/lix/.taobao_standalone_checkpoint.json
    /root/ebay_data/lix/.pull_checkpoint_LIX.json
    /root/ebay_data/price_query_checkpoint.json
)

for f in "${FILES[@]}"; do
    if [ -f "$f" ]; then
        cp "$f" "$SNAPSHOT_DIR/$(basename $f).$TS"
    fi
done

# 保留最近 50 个快照，删旧的
ls -t "$SNAPSHOT_DIR"/* 2>/dev/null | tail -n +51 | xargs rm -f 2>/dev/null

# 静默 — 不输出任何东西
