# Fuzz4All 复现计划与风险评估

> 目标：按论文 *Fuzz4All: Universal Fuzzing with Large Language Models* (ASE '24, arXiv:2308.04748) 复现端到端 fuzzing 流水线。用本地 OpenAI 兼容网关 (`http://localhost:4000/v1`, model=`qwen3-coder-30b-a3b`) 替换原仓库 StarCoder 后端。

## 1. 范围与本轮取舍

| 维度 | 论文默认 | 本轮复现 | 理由 |
|------|---------|---------|------|
| 目标语言 | C、C++、Java、Go、SMT2、Qiskit (6 个) | **仅 C++** | 编译器 g++ 系统自带，最低外部依赖 |
| 时长 | 24h × 5 次 (RQ1) | 15 分钟短验证 | 先验证管线可跑通，再评估扩展 |
| LLM (fuzzing loop) | StarCoder (HF) | `qwen3-coder-30b-a3b` via OpenAI-compatible API | 用户指定本地网关 |
| Autoprompting (§3.2) | GPT-4 | **禁用**，走 `use_hand_written_prompt=true` | 用户要求；仓库内已有 shortened 文档 |
| 调用模式 | `completions`（续写 + stop） | `chat.completions` + 抽代码块 | Qwen3-Coder 无 completions 端点 |

## 2. 关键代码改动清单

1. `Fuzz4All/model.py`
   - 新增 `is_openai_compatible_model()` / `get_openai_model_name()`
   - 新增 `OpenAIChatModel` 类，暴露与 `StarCoder.generate` 一致签名
   - `make_model(...)` 新增 `llm_cfg=None` 参数，按 `openai/` 前缀分发
2. `Fuzz4All/target/target.py`
   - `initialize()` 中 `make_model(...)` 传入 `llm_cfg=llm`
   - openai 后端走 "HuggingFace" 分支（因 `.generate` 接口一致，无需分支改动）
3. `config/full_run/cpp_23_qwen.yaml` 新建
   - `llm.model_name: openai/qwen3-coder-30b-a3b`
   - `llm.base_url: http://localhost:4000/v1`, `api_key: ""`
   - `fuzzing.total_time: 0.25`, `batch_size: 4`
   - `use_hand_written_prompt: true`, `path_hand_written_prompt: config/documentation/cpp/cpp_23_shortened.md`

## 3. 复用已有工具

- `Fuzz4All/util/util.py::simple_parse` —— 从 chat 返回的 markdown 代码块抽代码（Ollama 分支已使用）
- `config/documentation/cpp/cpp_23_shortened.md` —— 论文 ablation 中使用的 C++23 shortened 手写 prompt

## 4. 风险点与缓解

| # | 风险 | 影响 | 缓解 |
|---|------|-----|------|
| R1 | 本地网关 `localhost:4000/v1` 未就绪 / 模型名拼写不符 | 生成阶段 401/404 直接失败 | 运行前 `curl /v1/models` 自检；失败则打印并中止 |
| R2 | Qwen3-Coder chat API 延迟高 —— 批量 `batch_size` 次串行会非常慢 | 15 分钟内生成量极少 | 用 `ThreadPoolExecutor` 并发 `batch_size` 次 |
| R3 | chat 返回可能不是 ```cpp 代码块``` 包裹，而是裸代码或混合文本 | `simple_parse` 返回空 → fuzzer 落回 raw content，验证失败率高 | 保持 fallback：`code if code else content`；必要时补强 parse |
| R4 | `torch` / `transformers` 在 `target.py` 顶部 `import torch` —— 即便走 OpenAI 后端也要求装 torch | 环境臃肿 | 装 CPU 版 torch（`--index-url .../whl/cpu`），不下 GPU wheel |
| R5 | 仓库 pin `coverage==7.2.7` / `pandas==2.0.3` 可能与系统其他包冲突 | pip install 失败 | 强制用独立 venv 隔离 |
| R6 | `qiskit==0.43.1` 是重依赖但本轮 C++ 不需要 | 安装慢/失败拖累整体 | 可尝试跳过 qiskit 安装（只影响 QISKIT target）；若 import 失败再处理 |
| R7 | `simple_parse` 抽取后代码缺少 `#include <iostream>` 等头文件 | `otf: true` 验证全部失败 | `target.py` 已在 prompt 前追加 `input_hint`，且 `generate()` 会把 `begin` 前缀拼回；观察首批结果再调优 |
| R8 | `prompt_strategy=2`（语义等价变异）需要多轮 LLM 调用 | 15 分钟内轮数有限 | 改成 `prompt_strategy: 0`（独立生成）以最大化覆盖率 —— 若时间允许保持 2 |
| R9 | chat 模型 temperature=1.0 可能输出过于发散 | 大量无法编译代码 | 保持 1.0 符合论文；必要时回落 0.7 |
| R10 | `resume: true` 若上轮残留 `best_prompt.txt` 会被沿用 | 修改 prompt 后失效 | 本轮 config 设 `resume: false` |
| R11 | Fuzz4All CLI 基于 Click，参数冲突可能让 CLI 值覆盖 YAML | 与计划的 batch_size 不一致 | 运行时 CLI 显式传一致值 |
| R12 | C++23 新特性 g++ 版本支持度不足 | 大面积 "unknown feature" 失败（非 bug，只是编译器太旧） | 确认 `g++ --version ≥ 13`；否则降级到 c++20 |

## 5. 验收标准（本轮最小集）

- [ ] `outputs/full_run/cpp_qwen/prompts/best_prompt.txt` 存在且非空
- [ ] `outputs/full_run/cpp_qwen/` 下有 ≥ 5 个 `*.fuzz` 文件
- [ ] `log_generation.txt` 记录至少一次成功 chat 请求与样本
- [ ] `log_validation.txt` 混合 pass/fail（证明 on-the-fly 验证闭环）
- [ ] 端到端 15 分钟内完成，无未捕获异常

## 6. 超出本轮范围

- C / Java / Go / SMT2 / Qiskit 目标 —— 各自需 gcc / javac / go / cvc5 / qiskit
- RQ1 完整 24h × 5 × 6 = ~30 机器日
- Autoprompting 阶段用 qwen3-coder 替代 GPT-4 生成 seed prompt
- Coverage / bug 数量等论文数值指标复现
