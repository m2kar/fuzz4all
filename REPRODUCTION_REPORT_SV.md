# Fuzz4All → SystemVerilog Baseline 实验报告

作为 EDAzz 论文的对标 baseline，在 Fuzz4All 中新增 SystemVerilog target，支持 `iverilog` 与 `verilator` 两个编译器作为 `--target`，并用同一 LLM 配置（`qwen3-coder-30b-a3b` via OpenAI 兼容网关）各跑 15 min 验证管线。

## 1. 结论

- ✅ 端到端管线跑通：qwen3-coder-30b-a3b → Fuzz4All fuzz loop → iverilog/verilator on-the-fly 验证。
- ✅ **iverilog** 15 min 产出 **920** 个样本，**915 SAFE (99.46%)**，5 FAILURE，0 ERROR/timeout。
- ✅ **verilator** 15 min 产出 **1012** 个样本，**1009 SAFE (99.70%)**，3 FAILURE，0 ERROR/timeout。
- ⚠️ 两个编译器均未发现潜在 bug（`ERROR` 归档为 0）。这对 Fuzz4All single-compiler 单纯 compile-check 属预期——工业级的 iverilog/verilator 稳定度足够接纳 60 行以内的基础 RTL；要把 FAILURE 转成 bug，需要差分（EDAzz 的本职工作）。
- 本次实验过程中**踩到并修复了两个 prompt 设计坑**（`input_hint` 重复声明 / 初始 hw prompt 过激鼓励 SVA），见 §5 归因。

## 2. 环境

| 项 | 值 |
|----|----|
| OS | Linux 6.8.0-94-generic (Ubuntu 24.04) |
| Python | 3.10.20 (uv venv) |
| iverilog | 13.0 (stable) |
| verilator | 5.046 (2026-02-28) |
| LLM 网关 | `http://localhost:4000/v1`, model `qwen3-coder-30b-a3b` |

## 3. 新增 / 修改

| 文件 | 作用 |
|------|------|
| `Fuzz4All/target/SV/SV.py` (new) | `SVTarget(Target)` —— iverilog/verilator 分发的 compile-only target |
| `Fuzz4All/target/SV/__init__.py` (new) | package marker |
| `Fuzz4All/make_target.py` (edit) | 在两个工厂函数注册 `language: systemverilog` |
| `config/documentation/systemverilog/sv.md` (new, 75 行) | SV 特性概览（Data Model / General / Control Flow / Preprocess / Timing / SVA），按现有 cpp_23.md 规模 |
| `config/documentation/systemverilog/sv_shortened.md` (new, 1 段) | 手写 prompt；v3 版约束只生成基础可综合 RTL |
| `config/full_run/sv_iverilog_qwen.yaml` (new) | 15 min 短验证配置 |
| `config/full_run/sv_verilator_qwen.yaml` (new) | 同上，输出目录不同 |
| `scripts/run_sv_baseline.sh` (new) | tmux 里顺序跑两腿 |

`SVTarget` 关键实现：

- `write_back_file(code)` → `/tmp/tempN.sv`
- `clean` / `clean_code`：复用 `comment_remover(code, "cpp")`（SV 与 C++ 注释同形）
- `validate_individual(filename)`：按 `self.target_name` 分发
  ```
  iverilog:  iverilog -g2012 -o /tmp/outN.vvp <file>
  verilator: verilator --lint-only --sv -Wno-fatal --top-module top <file>
  ```
  用 `--lint-only` 而不是 `--cc --exe --build`，避开对 C++ harness 和 `obj_dir` 的依赖，语义上就是"能否 elaborate 通过"，和 Fuzz4All 其它 target 的 compile-check 对齐。
- 返回码映射：`rc==0 → SAFE`，`rc<0`（信号被杀，如 SIGSEGV/SIGABRT）`→ ERROR`（真 bug），`rc>0 → FAILURE`，TimeoutExpired `→ TIMED_OUT`（顺带 `ps|awk|xargs kill` 清子树，照搬 C.py）。

**相对 EDAzz 的精简**：不移植 `run.cpp` / `run.vpi` / `stimulus.json` / `runtime_fingerprint.json` / Makefile；这些是差分测试链路的件，single-compiler baseline 用不上。

## 4. 实际命令与产出

```bash
source .venv/bin/activate
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
tmux new-session -d -s fuzz4all-sv \
    "bash scripts/run_sv_baseline.sh 2>&1 | tee outputs/full_run/sv_baseline_run.log"
```

`scripts/run_sv_baseline.sh` 顺序执行：

```bash
python Fuzz4All/fuzz.py --config config/full_run/sv_iverilog_qwen.yaml main_with_config \
  --folder outputs/full_run/sv_iverilog_qwen --batch_size 4 \
  --model_name openai/qwen3-coder-30b-a3b --target iverilog
# 然后同样用 sv_verilator_qwen.yaml + --target verilator
```

时间线（v3，最终一次）：

| 阶段 | 起 | 止 | 耗时 |
|------|----|----|------|
| iverilog leg | 21:05:43 | 21:20:49 | 15m06s |
| verilator leg | 21:20:49 | 21:35:53 | 15m04s |

产出结构：

```
outputs/full_run/
├── sv_iverilog_qwen/          5.8 MB
│   ├── 0.fuzz … 919.fuzz       # 920 份 .sv 体样本, 平均 ~52 行/份
│   ├── log.txt                 # INFO
│   ├── log_generation.txt      # 每次 prompt + LLM 生成
│   ├── log_validation.txt      # 每份样本的 iverilog 输出
│   └── prompts/best_prompt.txt
├── sv_verilator_qwen/         8.3 MB, 1012 份样本, 平均 ~50 行/份
└── sv_baseline_run.log        # 两腿 stdout/stderr
```

## 5. 实验计量

| 指标 | iverilog | verilator |
|------|---------:|----------:|
| 总样本数 | 920 | 1012 |
| 有效时间 (s) | 906 | 904 |
| 吞吐 (样本/min) | 60.9 | 67.2 |
| SAFE | 915 | 1009 |
| SAFE 率 | **99.46%** | **99.70%** |
| FAILURE | 5 | 3 |
| ERROR (潜在 bug) | 0 | 0 |
| TIMED_OUT | 0 | 0 |
| 磁盘占用 | 5.8 MB | 8.3 MB |

两个工具的 SAFE 率差异主要来自 iverilog 对几个 SV-2012 语法的未完成实现，例如：

- `outputs/.../3.fuzz:22: sorry: Unpacked structs not supported.`（iverilog 只完整支持 packed struct）
- 个别 LLM 样本在极长行里出现 `` ` `` 非法字符 → verilator 报 `syntax error, unexpected invalid token`（两者均 3 例）。

这几例 FAILURE 不是编译器 bug，而是 LLM 生成的 ill-formed code（Fuzz4All 语义里计入 `LLM_WEAKNESS`/`FAILURE` 分支，不是 `ERROR`）。

## 6. Prompt 调优过程（两次返工）

v1 → v2 → v3，每一轮 15 min + 15 min。

| 版本 | SAFE 率 (iv / vl) | 症结 | 修复 |
|------|------------------:|------|------|
| v1 | 0% / 0% | `input_hint: "module top;"` 被每次 prepend，但 LLM 自己也输出 `module top ...` → 同一文件两个 `module` 头 | `input_hint: ""` |
| v2 | 0% / —* | 初版 `sv_shortened.md` 明确鼓励 `assert property` / `interface` / SVA，LLM 生成 ~110 行含并发断言的模块；iverilog 13 的 SVA 支持不完整 + interface-in-module 两者都拒 | 重写 hw prompt：**禁止** `interface` / `assert property` / `cover property` / `clocking` / `fork-join` / `import` / `` `include `` / 类 / 动态数组；要求 ≤ 40 行 |
| v3 | 99.46% / 99.70% | — | — |

(*) v2 verilator leg 在分析 iverilog 失败模式时已被手动终止，未跑完。v1/v2 产出存档于 `outputs/full_run/sv_{iverilog,verilator}_qwen.v{1,2}_*`，供对照。

v3 hw prompt 的关键指令（`config/documentation/systemverilog/sv_shortened.md`）：

> Use basic synthesizable features: `logic`, `parameter`/`localparam`, packed structs, enums, `always_ff`, `always_comb`, simple `case`/`if`, arithmetic/bitwise, `assign`, `generate`/`for`. **Do not** use `interface`, `clocking`, `assert property`, `cover property`, concurrent assertions, `import`, `` `include ``, classes, dynamic arrays/queues, constraints, `fork`/`join`, or DPI. Keep the module under ~40 lines.

之所以要手动收紧：Fuzz4All 的 `use_hand_written_prompt: true` 路径 bypass 了 autoprompting（本 fork 的 `util/api_request.py` 目前未接 OpenAI 网关），LLM 只看到 `sv_shortened.md`，若里面把 SVA/interface 列为卖点，就会照着产出。等后续把 autoprompting 接好，可以回退到 `sv.md` 全量文档 + LLM 自己摘 prompt。

## 7. 样本观察

v3 样本具有较高多样性：FSM、计数器、寄存器组、ALU、ShiftRegister、FIFO、Priority Encoder、LFSR 等经典 RTL 都有覆盖。平均 ~50 行左右，与 hw prompt "≤ 40 lines" 量级吻合（LLM 常略越界到 50-70 行）。

样例 `outputs/full_run/sv_iverilog_qwen/0.fuzz`（节选）：

```systemverilog
module top (
    input  logic clk,
    input  logic rst_n,
    input  logic [7:0] data_in,
    output logic [7:0] data_out
);
    typedef enum logic [1:0] { IDLE, READ, WRITE, DONE } state_e;
    typedef struct packed { logic enable; logic [2:0] mode; logic [1:0] width; } config_s;
    state_e current_state, next_state;
    config_s config_reg, config_next;
    ...
    always_ff @(posedge clk or negedge rst_n) begin ... end
    always_comb begin : next_state_logic
        case (current_state) ... endcase
    end
endmodule
```

这是 Fuzz4All `prompt_strategy=2`（semantically-equivalent mutation）迭代进化的结果：LLM 基于上一个 SAFE 样本产出语义等价变体，所以风格一致、都是单模块 RTL、都能通过两个工具。

## 8. 局限与下一步

- **无 ERROR 不代表无 bug**。Fuzz4All single-compiler 只能发现 crash（SIGSEGV/SIGABRT，这里 0 条）；真正的 miscompile / 行为差异要 EDAzz 的差分链路。baseline 的意义是：给定同样 LLM + 同样 prompt，Fuzz4All 在同样时间窗口能产出多少**可编译**样本。
- **hw prompt 显式屏蔽了 SVA / interface / package / class 等 Fuzz4All 其它 target 不关心的高级特性**，这会低估 EDAzz 覆盖面的广度。如果要做公平对比，需要再做一组"full feature"实验，在 EDAzz 支持的完整 6 类特征下测。
- **Autoprompting 路径未走通**。Fuzz4All 论文 §3.2 的 autoprompting 会让 LLM 从完整 `sv.md` 里自己浓缩 prompt；本 fork 的 `util/api_request.py` 仍是 Hugging Face/OpenAI `completions` 老接口，未改 chat.completions 路径。接上后可以取消 `use_hand_written_prompt: true`。
- **本 baseline 仅 15 min × 2**。论文 RQ1 是 24h × 5 runs；时间延长后样本多样性、SAFE 率变化、`ERROR` 发生概率都值得再测。

## 9. 复现本报告

```bash
# 前置
iverilog -V | head -1     # Icarus Verilog 13.0
verilator --version       # Verilator 5.046+
curl -s http://localhost:4000/v1/models | head -c 80   # gateway alive

cd /edazz/playground/fuzz4all
source .venv/bin/activate
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
tmux new-session -d -s fuzz4all-sv \
    "bash scripts/run_sv_baseline.sh 2>&1 | tee outputs/full_run/sv_baseline_run.log"
tmux attach -t fuzz4all-sv    # 可选：实时看日志
```

30 min 后 `outputs/full_run/sv_{iverilog,verilator}_qwen/` 下即可看到约 900-1000 份样本与 99%+ SAFE 率。
