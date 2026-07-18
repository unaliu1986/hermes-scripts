#!/usr/bin/env python3
"""DECO 第三层: 副作用采集 + 自动验证 — post_tool_call Hook v2
file_write/write_file/patch/terminal 执行后，
自动记录验证项并立即执行验证，结果写入 side_effects.json。
"""
import json, sys, os, subprocess, time
from datetime import datetime
from pathlib import Path

STATE_FILE = Path(os.path.expanduser("~/.hermes/side_effects.json"))

TRACKED_TOOLS = {"file_write", "write_file", "patch", "terminal"}

def execute_and_verify(checks: list) -> list:
    """执行验证命令列表，返回结构化结果"""
    results = []
    for cmd in checks:
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            stdout_preview = (r.stdout or "")[:200]
            stderr_preview = (r.stderr or "")[:200]
            results.append({
                "command": cmd,
                "exit_code": r.returncode,
                "stdout_preview": stdout_preview,
                "stderr_preview": stderr_preview,
                "status": "ok" if r.returncode == 0 else "error"
            })
        except subprocess.TimeoutExpired:
            results.append({
                "command": cmd,
                "exit_code": -1,
                "stdout_preview": "",
                "stderr_preview": "timeout after 15s",
                "status": "error"
            })
        except Exception as e:
            results.append({
                "command": cmd,
                "exit_code": -1,
                "stdout_preview": "",
                "stderr_preview": str(e)[:200],
                "status": "error"
            })
    return results

def main():
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    if tool_name not in TRACKED_TOOLS:
        sys.exit(0)

    args = payload.get("tool_input", {})
    result_str = payload.get("result", "{}")

    try:
        result = json.loads(result_str) if isinstance(result_str, str) else result_str
    except (json.JSONDecodeError, TypeError):
        result = {"raw": str(result_str)[:200]}

    check = {
        "id": f"check_{int(time.time() * 1000)}",
        "type": tool_name,
        "target": args.get("path", "") or args.get("command", "")[:200],
        "status": "pending",
        "checks_pending": [],
        "verified": [],
        "created_at": datetime.now().isoformat()
    }

    if tool_name in ("file_write", "write_file", "patch"):
        target = args.get("path", "")
        if target:
            file_path = Path(target)
            if not file_path.exists():
                check["verified"].append({
                    "command": f"stat {target}",
                    "exit_code": 1,
                    "status": "error",
                    "message": "文件不存在"
                })
            else:
                check["checks_pending"] = [
                    f"ls -la {target}",
                    f"wc -l {target}",
                ]
                if target.endswith(".py"):
                    check["checks_pending"].append(f"python3 -m py_compile {target}")
                elif target.endswith(".json"):
                    check["checks_pending"].append(f"python3 -m json.tool {target} > /dev/null")
                elif target.endswith((".yaml", ".yml")):
                    check["checks_pending"].append(
                        f"python3 -c \"import yaml; yaml.safe_load(open('{target}'))\""
                    )

    elif tool_name == "terminal":
        exit_code = result.get("exit_code", -1)
        command = args.get("command", "")[:200]

        if exit_code != 0:
            check["checks_pending"].append(f"exit_code={exit_code} — 需要检查")

        for keyword in ["python3", ".py", "ebay", "agnes", "gap_screening"]:
            if keyword in command:
                check["checks_pending"].extend(["检查输出文件", "检查 checkpoint"])
                break

    # 执行验证
    if check["checks_pending"]:
        check["verified"] = execute_and_verify(check["checks_pending"])
        errors = [v for v in check["verified"] if v["status"] == "error"]
        if errors:
            check["status"] = "verify_failed"
        else:
            check["status"] = "verified"
    else:
        check["status"] = "no_checks"

    # 写入 state 文件
    try:
        with open(STATE_FILE, "r+") as f:
            try:
                state = json.load(f)
            except json.JSONDecodeError:
                state = {"pending_checks": [], "completed_count": 0, "verified_log": []}
            state.setdefault("verified_log", []).append(check)
            state["pending_checks"] = [c for c in state.get("pending_checks", [])
                                       if c.get("id") != check["id"]]
            state["completed_count"] = state.get("completed_count", 0) + 1
            state["last_updated"] = datetime.now().isoformat()
            f.seek(0)
            f.truncate()
            json.dump(state, f, indent=2, ensure_ascii=False)
    except FileNotFoundError:
        with open(STATE_FILE, "w") as f:
            json.dump({
                "verified_log": [check],
                "completed_count": 1,
                "last_updated": datetime.now().isoformat()
            }, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    error_count = len([v for v in check.get("verified", []) if v["status"] == "error"])
    result_msg = {
        "hook": "side-effect-collector",
        "action": "verified",
        "status": check["status"],
        "checks_run": len(check.get("verified", [])),
        "errors": error_count
    }
    print(json.dumps(result_msg))
    sys.exit(0)

if __name__ == "__main__":
    main()
