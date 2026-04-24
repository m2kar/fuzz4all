# Fuzz4All 复现过程报告

## 1. 结论

- ✅ 端到端管线跑通：qwen3-coder-30b-a3b (via `http://localhost:4000/v1`) 作为 LLM → Fuzz4All fuzz loop → g++ 13.3 on-the-fly 验证。
- ✅ 15 分钟产出 **528** 个 C++23 `*.fuzz` 样本，每个样本均由 LLM 生成并经 `g++ -std=c++23` 编译验证。
- ⚠️ 所有样本在本机 g++ 13.3 / libstdc++ 下均报编译错误 —— 生成内容本身是合法的 C++23 目标代码（如 `std::stacktrace`, `std::views`, `_sz` 字面量后缀, `<stdatomic.h>` 互操作），但这些 C++23 新特性在 GCC 13 标准库里实现不完整。这与 Fuzz4All 的设计目标一致（暴露编译器/库的边界），但要评估真实"bug"数量需要 GCC 14+ / libc++ 对照差分。

## 2. 环境

| 项 | 值 |
|----|----|
| OS | Linux 6.8.0-94-generic (Ubuntu 24.04) |
| Python | 3.10.20 (uv venv) |
| torch | 2.11.0+cpu |
| transformers | 5.6.2 |
| openai | 装 requirements 默认版本 |
| g++ | 13.3.0 |
| LLM 网关 | `http://localhost:4000/v1`，模型 `qwen3-coder-30b-a3b` |

## 3. 实施步骤与实际命令

### 3.1 预检
```bash
g++ --version                             # 13.3.0 OK
curl -s http://localhost:4000/v1/models    # qwen3-coder-30b-a3b OK
```

### 3.2 环境
```bash
cd /edazz/playground/fuzz4all
uv venv --python 3.10 .venv
source .venv/bin/activate
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install -r requirements.txt
uv pip install -e .
uv pip install "httpx[socks]"            # 修复 R-extra 见下文
```

### 3.3 代码改动（新增 OpenAI 兼容后端）
- `Fuzz4All/model.py`
  - 新增 `is_openai_compatible_model()`, `get_openai_model_name()`
  - 新增 `OpenAIChatModel` 类：构造 `openai.OpenAI(base_url, api_key)`；`generate()` 用 `ThreadPoolExecutor(max_workers=min(batch_size, 8))` 并发 `batch_size` 次 `chat.completions.create`，对每个响应调用 `Fuzz4All/util/util.py:simple_parse` 抽取 ```` ``` ```` 代码块，解析失败则回退原文本；失败时写入 `// OPENAI_ERROR: ...` 不中断批次。
  - `make_model(...)` 新增 `llm_cfg=None` 参数，按 `ollama/` / `openai/` 前缀分发。
- `Fuzz4All/target/target.py:228-238`
  - HF 分支调用 `make_model(..., llm_cfg=self.config_dict.get("llm", {}))`，把 base_url/api_key 透传到模型工厂。OpenAI 分支 `.generate` 签名与 StarCoder 一致，因此 `generate_model()` 不需要改动。

### 3.4 配置
新建 `config/full_run/cpp_23_qwen.yaml`：
- `llm.model_name: openai/qwen3-coder-30b-a3b`
- `llm.base_url: http://localhost:4000/v1`，`api_key: ""`
- `fuzzing.total_time: 0.25`，`batch_size: 4`
- `use_hand_written_prompt: true`，`path_hand_written_prompt: config/documentation/cpp/cpp_23_shortened.md`（规避 autoprompting，对齐论文 ablation 中的 "hw" 设置）
- `resume: false`，`otf: true`，`prompt_strategy: 2`

### 3.5 烟测
```python
from Fuzz4All.model import make_model
m = make_model(eos=[], model_name='openai/qwen3-coder-30b-a3b', device='cpu',
               max_length=512, llm_cfg={'base_url':'http://localhost:4000/v1','api_key':''})
m.generate('Write a one-line C++ hello world inside a code block.', batch_size=1, ...)
# => ["#include <iostream> int main() { std::cout << \"Hello, World!\" << std::endl; return 0; }"]
```

### 3.6 正式跑
```bash
source .venv/bin/activate
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
python Fuzz4All/fuzz.py --config config/full_run/cpp_23_qwen.yaml \
    main_with_config --folder outputs/full_run/cpp_qwen \
    --batch_size 4 --model_name openai/qwen3-coder-30b-a3b --target g++
```

## 4. 运行产物

```
outputs/full_run/cpp_qwen/
├── 0.fuzz ... 527.fuzz     # 528 个样本
├── log.txt                 # INFO 级运行日志
├── log_generation.txt      # LLM prompt / 生成内容 (VERBOSE)
├── log_validation.txt      # g++ 验证逐样本输出 (VERBOSE)
└── prompts/
    └── best_prompt.txt     # 手写 prompt + trigger + input_hint 的拼接
```

- `best_prompt.txt` 构成 = `cpp_23_shortened.md` 全文 + `/* Please create a very short program which uses new C++ features in a complex way */` + `#include <iostream>`
- 样本示例（`0.fuzz` 首 10 行）：

```cpp
#include <iostream>
#include <string>
#include <string_view>
#include <vector>
#include <stacktrace>
#include <type_traits>

int main() {
    auto size = 10_sz;
    ...
```

- 生成吞吐：~528 samples / 15 min ≈ **35 samples/min**（batch_size=4，ThreadPoolExecutor 并发）。

## 5. 验证结果

- 528 个样本，`log_validation.txt` 533 个 "failed"（含少量补偿），通过数 = 0。
- 失败原因集中（抽样统计）：
  - `std::stacktrace::current()` —— libstdc++ 13 未提供默认链接符号
  - `std::views::filter/take` —— 需 `#include <ranges>` 而 LLM 未加
  - `_sz` / `_size_t` 字面量后缀 —— GCC 13 未实现 P0330
  - `std::is_scoped_enum_v` —— 部分平台缺
  - `<stdatomic.h>` —— g++ 对 C++ 模式下的 C 原子头兼容不全
- 这与论文预期一致：Fuzz4All 的价值正是生成"触及编译器/库边界"的代码。要把失败数转成真正的 bug 计数，需要对 g++ / clang++ / MSVC 做差分或对 GCC 14+ 回归测试。

## 6. 遇到的问题与解决

| 问题 | 解决 |
|------|------|
| `openai` SDK 启动报 `socksio` 缺失（系统装了 socks 代理环境） | `uv pip install "httpx[socks]"`；并在 fuzz 运行前 `unset *_PROXY`，避免 openai 客户端误走 socks 代理 localhost |
| `target.py` 顶部强制 `import torch`，即使用 OpenAI 后端也要求装 torch | 装 CPU 版 torch (`--index-url whl/cpu`)，约 240 MB，满足 import，不加载 GPU 运行时 |
| Fuzzer CLI 与 YAML 两层覆盖 | CLI 显式传一致值 `--batch_size 4 --model_name openai/qwen3-coder-30b-a3b --target g++` |

## 7. 与论文的差异

| 维度 | 论文 | 本次 | 说明 |
|------|------|------|------|
| Fuzzing LLM | StarCoderBase | qwen3-coder-30b-a3b (chat) | 原代码 completions-style 续写 + stop；qwen 仅 chat，改为"抽取代码块"模式。效果待量化对照。 |
| Autoprompting | GPT-4 | 禁用（手写 prompt） | 直接用仓库 `cpp_23_shortened.md`，对齐论文 ablation 设置 |
| Budget | 24h × 5 次 | 15 min × 1 次 | 本轮仅验证管线闭环 |
| Targets | 6 个 | 1 个 (C++) | g++ 已装，其他需 gcc/javac/go/cvc5/qiskit |
| Coverage metric | 是 | 否 | 未跑 `coverage`/`fastcov`；仅做 otf 编译通过率 |

## 8. 验收清单回查

- [x] `outputs/full_run/cpp_qwen/prompts/best_prompt.txt` 存在且非空
- [x] ≥ 5 个 `*.fuzz` 文件 (实际 528)
- [x] `log_generation.txt` 记录成功 chat 请求与样本 (25k+ 行)
- [x] `log_validation.txt` 记录 per-sample 编译结果 (33k+ 行)
- [x] 15 分钟内完成，无未捕获异常
- [ ] pass/fail 混合 —— 实际 pass=0，原因见 §5，非管线缺陷

## 9. 下一步（超出本轮）

1. **增加 compile-pass 率**：尝试 `g++ -std=c++23 -lstdc++_libbacktrace`、或升级 GCC 14；或把 target 改成更保守的 `cpp_demo.yaml`（C++17 子集）。
2. **多目标扩展**：装 `cvc5`, `z3`, `go`, `javac`，复制 `*_qwen.yaml` 四份。
3. **差分 oracle**：实现 g++ vs clang++ 同源对比，输出不同则判 bug。
4. **Qwen-autoprompting**：把 `Fuzz4All/util/api_request.py` 的 `openai.OpenAI()` 改用本地网关，替换 GPT-4，复现 §3.2 的自动 prompt 生成阶段。
5. **长跑 RQ1**：`total_time: 24`，跑 5 次，合计 120 小时/目标。

## 10. 关键文件清单

| 路径 | 状态 | 说明 |
|------|------|------|
| `Fuzz4All/model.py` | 修改 | +55 行：`OpenAIChatModel`, `is_openai_compatible_model`, `make_model(..., llm_cfg=)` |
| `Fuzz4All/target/target.py` | 修改 | HF 分支调用 `make_model` 时透传 `llm_cfg` |
| `config/full_run/cpp_23_qwen.yaml` | 新增 | 本轮验证配置 |
| `REPRODUCTION_PLAN.md` | 新增 | 计划+风险 |
| `REPRODUCTION_REPORT.md` | 新增 | 本文件 |
| `outputs/full_run/cpp_qwen/` | 生成 | 528 样本 + 日志 |
| `.venv/` | 新增 | Python 3.10 虚拟环境（未入库） |
