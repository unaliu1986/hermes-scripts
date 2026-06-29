---
name: moa-manual
description: "手动 MoA（Mixture of Agents）：并行调多个模型做参考分析，由 DeepSeek v4-pro 聚合综合。用于需要多视角交叉验证的场景（竞品判断、定价决策、风险分析等）。Hermes 原生 MoA 未上线前的过渡方案。"
version: 1.0.0
triggers:
  - MoA
  - 多模型分析
  - 第三方视角
  - 多角度交叉验证
  - 多个模型一起判断
---

# 手动 MoA（Mixture of Agents）

## 原理

```
用户问题
  ├─→ DeepSeek-chat 并行分析 ──┐
  ├─→ Agnes-2.0-Flash 并行分析 ─┤
  └─→ (可选更多模型)            │
                                 ▼
                    Aggregator: DeepSeek v4-pro
                    综合所有观点 → 最终答案
```

## 适用场景

| 场景 | 示例 |
|---|---|
| 竞品判断 | "这个淘宝 SKU 和 eBay 产品匹不匹配？" |
| 定价决策 | "这个品类该定 15% 还是 20% 利润率？" |
| 风险分析 | "这个 Amazon 类目有没有品牌侵权风险？" |
| 标题优化 | "这个标题改法会不会降低搜索曝光？" |
| 代码审查 | "这个修复方案有没有潜在副作用？" |

## 不要用的场景

- 确定性计算（定价公式、运费计算）→ 不需要"观点"
- 简单查询（查参数、翻译）→ 单模型够快
- 高频率批量任务 → 每次多调几个模型太慢

## 使用方法

脚本位置：`/root/scripts/moa_ask.py`

```bash
# 基础用法
python3 /root/scripts/moa_ask.py "你的问题"

# 指定参考模型（逗号分隔）
python3 /root/scripts/moa_ask.py "你的问题" "deepseek-chat,agnes-2.0-flash"

# 仅输出最终结果（不显示中间分析）
python3 /root/scripts/moa_ask.py "你的问题" --final-only
```

## 扩展模型

在脚本的 `MODELS` 字典里加新模型：

```python
MODELS = {
    "deepseek-chat": {
        "url": "https://api.deepseek.com/v1/chat/completions",
        "key_env": "DEEPSEEK_API_KEY",
    },
    "agnes-2.0-flash": {
        "url": "https://apihub.agnes-ai.com/v1/chat/completions",
        "key_env": "AGNES_API_KEY",
    },
    # 未来加新模型在这里
}
```

## 与 Hermes 原生 MoA 的关系

Hermes v0.17.0 暂无原生 MoA。等官方上线后：
- 原生 MoA 用于整个 Agent 会话（工具调用、多轮对话）
- 手动 MoA 保留用于单次多视角判断（轻量、解耦）
