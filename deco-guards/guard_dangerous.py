#!/usr/bin/env python3
"""DECO 第二层: 危险工具 HITL 门禁 — pre_tool_call Hook v1.2
terminal 命令执行前查 dangerous_tools.yaml。
whitelist 使用 fnmatch (glob)，tools 使用 regex。
"""
import json, sys, re, os, fnmatch, shlex
from pathlib import Path

CONFIG_FILE = Path(os.path.expanduser("~/.hermes/dangerous_tools.yaml"))

def load_config():
    try:
        import yaml
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f)
    except Exception:
        return None

def check_terminal(command: str, config: dict) -> dict:
    if not config or not command:
        return {"action": "pass"}

    # Step 0: 递归展开管道（使用 shlex 安全解析）
    def expand_pipes(cmd):
        try:
            tokens = shlex.split(cmd)
        except ValueError:
            tokens = cmd.split()
        parts = []
        current_part = []
        for token in tokens:
            if token == '|':
                if current_part:
                    parts.append(' '.join(current_part))
                    current_part = []
            else:
                current_part.append(token)
        if current_part:
            parts.append(' '.join(current_part))

        expanded = []
        for part in parts:
            if '|' in part:
                expanded.extend(expand_pipes(part))
            else:
                expanded.append(part)
        return expanded if expanded else [cmd]

    sub_commands = expand_pipes(command)

    # Step 1: whitelist 优先（支持 glob fnmatch + regex）
    # 规则：regex 优先于 glob（regex 可防路径穿越，glob 不可以）
    whitelist = config.get("whitelist", [])
    for wl in whitelist:
        regex_pattern = wl.get("regex", "")
        if regex_pattern and re.search(regex_pattern, command):
            return {"action": "pass", "whitelist_match": regex_pattern}
        glob_pattern = wl.get("glob", "")
        if glob_pattern and not regex_pattern and fnmatch.fnmatch(command, glob_pattern):
            return {"action": "pass", "whitelist_match": glob_pattern}

    # Step 1.5: 危险组合检测（curl|bash, wget|sh 等）
    DANGEROUS_COMBOS = [
        ("curl", "bash"), ("wget", "sh"),
        ("curl", "python3"), ("wget", "python3"),
    ]
    tool_names = set()
    for sub_cmd in sub_commands:
        tool_names.update(sub_cmd.split())
    for combo in DANGEROUS_COMBOS:
        if all(t in tool_names for t in combo):
            return {
                "action": "block",
                "message": f"⛔ 检测到危险管道组合: {' | '.join(combo)} — 禁止执行",
                "level": "CRITICAL",
                "hook": "guard-dangerous"
            }

    # Step 2: tools regex 匹配
    tools = config.get("tools", [])
    for sub_cmd in sub_commands:
        for tool in tools:
            pattern = tool.get("pattern", "")
            if re.search(pattern, sub_cmd, re.IGNORECASE):
                level = tool.get("level", "MEDIUM")
                if level in ("CRITICAL", "HIGH"):
                    return {
                        "action": "block",
                        "message": tool.get("confirm", f"⚠️ 危险操作: {tool.get('description')}"),
                        "level": level,
                        "matched": pattern,
                        "sub_command": sub_cmd[:80],
                        "hook": "guard-dangerous"
                    }
                else:
                    return {
                        "action": "warn",
                        "message": tool.get("confirm", ""),
                        "level": level
                    }

    return {"action": "pass"}

def main():
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        print(json.dumps({"action": "block", "message": "Invalid JSON input"}))
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    if tool_name != "terminal":
        sys.exit(0)

    args = payload.get("tool_input", {})
    command = args.get("command", "")

    if not command:
        sys.exit(0)

    config = load_config()
    if not config:
        sys.exit(0)

    result = check_terminal(command, config)

    if result.get("action") in ("block", "warn"):
        print(json.dumps(result))
        sys.exit(0)

    sys.exit(0)

if __name__ == "__main__":
    main()
