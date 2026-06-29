#!/usr/bin/env python3
"""
router_check.py — 数据路由合规检查
检查: ①路由表指向的文件是否存在 ②脚本是否绕过了路由用 glob
输出: 有违规→报告，无违规→静默
用法: python3 router_check.py [--verbose]
"""

import json, os, re, sys
from datetime import datetime
from pathlib import Path

ROUTER_FILE = '/root/ebay_data/health/data_router.json'
SCRIPT_DIR = '/root/ebay_data/lix'

# ─── 脚本 → 任务映射 ────────────────────────────────────
# 哪些脚本应该用路由表取文件，而不是 glob
TASK_SCRIPTS = {
    'scan_competitors': 'scan_competitors.py',
    'reverse_price': 'reverse_price.py',
    'incremental_filter_today': 'incremental_filter.py',
}

# ─── 检查函数 ───────────────────────────────────────────

def load_router():
    if not os.path.exists(ROUTER_FILE):
        return {}
    with open(ROUTER_FILE) as f:
        return json.load(f)


def check_router_entries(router, verbose=False):
    """检查路由表指向的文件是否存在"""
    issues = []
    inputs = router.get('inputs', {})

    for task, paths in inputs.items():
        if isinstance(paths, dict):
            for store, path in paths.items():
                if not os.path.exists(path):
                    issues.append({
                        'type': 'router_stale',
                        'task': task,
                        'store': store,
                        'path': path,
                        'msg': f'{task}[{store}] 路由指向不存在的文件: {path}'
                    })
        elif isinstance(paths, str) and paths and os.path.exists(paths):
            if not os.path.exists(paths):
                issues.append({
                    'type': 'router_stale',
                    'task': task,
                    'path': paths,
                    'msg': f'{task} 路由指向不存在的文件: {paths}'
                })

    if verbose and not issues:
        print('✓ 所有路由条目指向的文件存在')
    return issues


def check_glob_abuse(router, verbose=False):
    """检查脚本是否用 glob 而路由器有明确路径"""
    issues = []
    inputs = router.get('inputs', {})

    for task, script_name in TASK_SCRIPTS.items():
        script_path = os.path.join(SCRIPT_DIR, script_name)
        if not os.path.exists(script_path):
            continue

        # 读脚本看有没有用 glob
        with open(script_path) as f:
            content = f.read()

        has_glob = bool(re.search(r'glob\.glob|sorted\(.*glob', content))
        uses_router = 'data_router' in content or 'get_input' in content

        # 只在路由表有明确路径时才报警
        task_inputs = inputs.get(task, {})
        has_router_path = False
        if isinstance(task_inputs, dict) and task_inputs:
            has_router_path = any(
                isinstance(v, str) and v and os.path.exists(v)
                for v in task_inputs.values()
            )
        elif isinstance(task_inputs, str) and task_inputs:
            has_router_path = os.path.exists(task_inputs)

        if has_glob and not uses_router and has_router_path:
            issues.append({
                'type': 'glob_bypass',
                'task': task,
                'script': script_name,
                'msg': f'{script_name} 用 glob 找文件但路由表有明确路径，应改用 data_router.get_input()'
            })
        elif verbose:
            status = '✓' if uses_router else ('◌' if not has_glob else '✗ 用glob但路由无路径')
            print(f'  {status} {script_name}: glob={has_glob} router={uses_router}')

    return issues


def check_router_freshness(router, verbose=False):
    """检查路由表是否过期"""
    issues = []
    meta = router.get('_meta', {})
    updated = meta.get('updated', '')
    if not updated:
        issues.append({
            'type': 'router_stale',
            'msg': '路由表无更新时间'
        })
    if verbose:
        print(f'  路由表更新: {updated}')
    return issues


# ─── 主逻辑 ──────────────────────────────────────────────

def main():
    verbose = '--verbose' in sys.argv
    router = load_router()

    if not router:
        print("⚠️ 路由表不存在或为空")
        return

    all_issues = []
    all_issues += check_router_entries(router, verbose)
    all_issues += check_glob_abuse(router, verbose)
    all_issues += check_router_freshness(router, verbose)

    if not all_issues:
        if verbose:
            print('✅ 数据路由合规，无问题')
        return

    # 有违规，输出报告
    print(f"## 📡 数据路由合规报告 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"发现 {len(all_issues)} 个问题：\n")

    by_type = {}
    for i in all_issues:
        t = i['type']
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(i)

    for t, items in by_type.items():
        label = {'router_stale': '🔴 路由过期', 'glob_bypass': '🟡 绕过路由'}.get(t, t)
        print(f"### {label} ({len(items)} 条)")
        for i in items:
            print(f"- {i['msg']}")
        print()

    # 汇总
    print("---")
    print(f"路由表有 {len(router.get('inputs', {}))} 个任务条目")
    print(f"glob_bypass: {len(by_type.get('glob_bypass', []))} 个脚本应改用路由")
    print(f"router_stale: {len(by_type.get('router_stale', []))} 条路由过期")


if __name__ == '__main__':
    main()
