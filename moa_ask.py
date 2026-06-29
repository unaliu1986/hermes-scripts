#!/usr/bin/env python3
"""Manual MoA: parallel reference models → aggregator
Usage: python3 moa_ask.py "question" ["model1,model2"] [--final-only]

Models configured below. Add new ones by extending MODELS dict.
Reads API keys from ~/.hermes/.env
"""
import sys, json, concurrent.futures, urllib.request, os, argparse

# ── Model Registry ──
MODELS = {
    "deepseek-chat": {
        "url": "https://api.deepseek.com/v1/chat/completions",
        "key_env": "DEEPSEEK_API_KEY",
    },
    "agnes-2.0-flash": {
        "url": "https://apihub.agnes-ai.com/v1/chat/completions",
        "key_env": "AGNES_API_KEY",
    },
    "deepseek-v4-pro": {
        "url": "https://api.deepseek.com/v1/chat/completions",
        "key_env": "DEEPSEEK_API_KEY",
    },
}

DEFAULT_REFERENCES = ["deepseek-chat", "agnes-2.0-flash"]
AGGREGATOR = "deepseek-v4-pro"

# ── Load keys ──
def load_env():
    env = {}
    env_path = os.path.expanduser("~/.hermes/.env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        env[parts[0]] = parts[1]
    return env

ENV = load_env()

# ── API call ──
def call_api(model_name, prompt, max_tokens=300):
    cfg = MODELS[model_name]
    key = ENV.get(cfg["key_env"], "")
    if not key:
        raise ValueError(f"Missing env var: {cfg['key_env']}")
    
    data = json.dumps({
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }).encode()
    
    req = urllib.request.Request(
        cfg["url"],
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        }
    )
    r = urllib.request.urlopen(req, timeout=60)
    return json.loads(r.read())['choices'][0]['message']['content']

# ── Main ──
def moa_ask(question, references=None, final_only=False):
    refs = references or DEFAULT_REFERENCES
    
    if not final_only:
        print("=" * 50)
        print(f"MoA: {len(refs)} 个参考模型并行分析")
        print("=" * 50)
    
    # Step 1: Parallel reference calls
    results = {}
    with concurrent.futures.ThreadPoolExecutor() as ex:
        futures = {ex.submit(call_api, m, question): m for m in refs}
        for f in concurrent.futures.as_completed(futures):
            model = futures[f]
            try:
                results[model] = f.result()
                if not final_only:
                    print(f"\n[{model}] 分析：")
                    print("-" * 40)
                    print(results[model])
            except Exception as e:
                results[model] = f"[ERROR: {e}]"
                if not final_only:
                    print(f"\n[{model}] ❌ 失败: {e}")
    
    # Step 2: Aggregator
    if not final_only:
        print(f"\n{'=' * 50}")
        print(f"Aggregator ({AGGREGATOR}) 综合输出：")
        print("-" * 40)
    
    ref_text = "\n\n".join(f"【{m}】\n{results[m]}" for m in results)
    agg_prompt = f"""综合以下多个模型的分析，给出最终答案。不要简单复述，要取其精华、补其不足。

【问题】{question}

{ref_text}

请输出综合答案："""
    
    final = call_api(AGGREGATOR, agg_prompt, max_tokens=500)
    print(final)
    
    if not final_only:
        print(f"\n{'=' * 50}")
        print("MoA 完成")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manual MoA: multi-model analysis")
    parser.add_argument("question", help="The question to ask")
    parser.add_argument("models", nargs="?", default=",".join(DEFAULT_REFERENCES),
                        help=f"Comma-separated reference models (default: {','.join(DEFAULT_REFERENCES)})")
    parser.add_argument("--final-only", action="store_true", help="Only show final output")
    args = parser.parse_args()
    
    moa_ask(args.question, args.models.split(","), args.final_only)
