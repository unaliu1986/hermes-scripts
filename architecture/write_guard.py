#!/usr/bin/env python3
"""
write_guard.py — 目录写权限守卫

用法:
    from write_guard import check_write, guard_open, guard_write, AGENT

    # 方式1: 用 guard_open 替代 open (推荐)
    with guard_open('pricing', '/root/ebay_data/pipelines/result.json', 'w') as f:
        json.dump(data, f)

    # 方式2: 手动检查
    if not check_write('pricing', '/root/ebay_data/health/status.json'):
        print("禁止写入 overseer 领土")

模式:
    WARN (默认): 只记录违规日志，不阻止写入
    ENFORCE: 抛出 PermissionError
    通过环境变量 WRITE_GUARD_MODE=enforce 或 set_mode() 切换
"""

import json, os, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
OWNERS_FILE = SCRIPT_DIR / 'dir_owners.json'
VIOLATIONS_FILE = SCRIPT_DIR / 'dir_violations.jsonl'

# 北京时区
TZ = timezone(timedelta(hours=8))

__mode = os.environ.get('WRITE_GUARD_MODE', 'warn')  # 'warn' | 'enforce'


def set_mode(mode: str):
    """切换模式: 'warn' 或 'enforce'"""
    global __mode
    if mode not in ('warn', 'enforce'):
        raise ValueError(f"mode 只能是 'warn' 或 'enforce'，收到: {mode}")
    __mode = mode


def _load_owners():
    """加载目录归属表"""
    if not OWNERS_FILE.exists():
        return {}
    with open(OWNERS_FILE) as f:
        return json.load(f)


def get_agent_dirs(agent_name: str) -> list:
    """返回 agent 有权写入的目录(相对路径前缀)"""
    owners = _load_owners()
    agent = owners.get('agents', {}).get(agent_name, {})
    return agent.get('dirs', [])


def _log_violation(agent: str, path: str, action: str):
    """记录违规日志"""
    try:
        os.makedirs(os.path.dirname(VIOLATIONS_FILE), exist_ok=True)
        record = {
            'ts': datetime.now(TZ).isoformat(),
            'agent': agent,
            'path': path,
            'action': action,
            'mode': __mode,
            'pid': os.getpid(),
        }
        with open(VIOLATIONS_FILE, 'a') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    except Exception:
        pass  # 日志写失败不应该影响主流程


def check_write(agent_name: str, filepath: str | Path) -> bool:
    """
    检查 agent 是否有权写入 filepath。

    返回 True 表示允许写入，False 表示违规。
    """
    path = str(filepath)
    owners = _load_owners()
    agent = owners.get('agents', {}).get(agent_name, {})
    allowed_dirs = agent.get('dirs', [])

    if not allowed_dirs:
        # 未配置的 agent，默认允许（避免误杀）
        return True

    # 提取相对路径（相对于 ebay_data 根）
    ebay_root = str(SCRIPT_DIR.parent)  # /root/ebay_data
    ebay_path = Path(ebay_root)

    # 统一为绝对路径（相对于 ebay_data 根解析）
    abs_path = str((ebay_path / path).resolve())
    if abs_path.startswith(ebay_root):
        rel = abs_path[len(ebay_root):].lstrip('/')
    else:
        # 不在 ebay_data 下，不属于本守卫管辖，放行
        return True

    # 检查是否匹配任意允许目录
    for allowed in allowed_dirs:
        if rel.startswith(allowed.rstrip('/')) or rel == allowed.rstrip('/'):
            return True

    # 检查 shared 目录
    shared_dirs = owners.get('shared', {}).get('dirs', [])
    for shared in shared_dirs:
        if rel.startswith(shared.rstrip('/')):
            return True

    # 违规
    _log_violation(agent_name, path, 'write_blocked')
    return False


def guard_open(agent_name: str, filepath: str | Path, mode: str = 'r',
               encoding: str = 'utf-8', **kwargs):
    """
    open() 的守卫版本。只对写入模式检查权限。

    用法:
        with guard_open('pricing', 'result.json', 'w') as f:
            f.write(data)
    """
    is_write = 'w' in mode or 'a' in mode or '+' in mode

    if is_write and not check_write(agent_name, str(filepath)):
        msg = (f"[write_guard] {agent_name} 无权写入 {filepath}\n"
               f"  允许的目录: {get_agent_dirs(agent_name)}")
        if __mode == 'enforce':
            raise PermissionError(msg)
        else:
            sys.stderr.write(f"⚠️  {msg}\n")

    return open(str(filepath), mode, encoding=encoding, **kwargs)


def guard_write(agent_name: str, filepath: str | Path, content: str):
    """
    写文件的守卫版本。用法:
        guard_write('pricing', 'result.json', json.dumps(data))
    """
    if not check_write(agent_name, str(filepath)):
        msg = (f"[write_guard] {agent_name} 无权写入 {filepath}\n"
               f"  允许的目录: {get_agent_dirs(agent_name)}")
        if __mode == 'enforce':
            raise PermissionError(msg)
        else:
            sys.stderr.write(f"⚠️  {msg}\n")

    os.makedirs(os.path.dirname(str(filepath)), exist_ok=True)
    with open(str(filepath), 'w', encoding='utf-8') as f:
        f.write(content)


def get_violations(since_hours: int = 24) -> list:
    """读取最近 N 小时的违规记录"""
    if not VIOLATIONS_FILE.exists():
        return []
    cutoff = datetime.now(TZ) - timedelta(hours=since_hours)
    violations = []
    with open(VIOLATIONS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                ts = datetime.fromisoformat(record['ts'])
                if ts >= cutoff:
                    violations.append(record)
            except (json.JSONDecodeError, KeyError, ValueError):
                pass
    return violations


def report(since_hours: int = 24) -> str:
    """生成违规报告"""
    violations = get_violations(since_hours)
    if not violations:
        return f"[write_guard] 过去 {since_hours}h 无违规 ✓"

    # 按 agent 分组
    by_agent = {}
    for v in violations:
        agent = v['agent']
        if agent not in by_agent:
            by_agent[agent] = []
        by_agent[agent].append(v)

    lines = [f"[write_guard] 过去 {since_hours}h 发现 {len(violations)} 条违规:"]
    for agent, items in sorted(by_agent.items()):
        lines.append(f"  {agent}: {len(items)} 次")
        for v in items[:5]:  # 最多显示 5 条
            lines.append(f"    - {v['ts']} → {v['path']}")
    return '\n'.join(lines)


# ─── CLI ───────────────────────────────────────────────────
if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'report':
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        print(report(hours))
    elif len(sys.argv) >= 3 and sys.argv[1] == 'check':
        agent, path = sys.argv[2], sys.argv[3]
        ok = check_write(agent, path)
        print(f"{'✓ 允许' if ok else '✗ 违规'} {agent} → {path}")
        sys.exit(0 if ok else 1)
    else:
        print("用法: python3 write_guard.py report [hours]")
        print("      python3 write_guard.py check <agent> <path>")
