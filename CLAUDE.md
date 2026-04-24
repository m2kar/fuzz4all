# CLAUDE.md

Project-specific notes for Claude Code when working in this repo.

## Reproduction summary

Fuzz4All (ASE '24, arXiv 2308.04748) originally ships with two LLM backends:
StarCoder (HuggingFace) and Ollama. This fork adds a third: an **OpenAI
chat-completions backend** so we can plug in any OpenAI-compatible gateway
(LiteLLM / vLLM / local proxy).

Key changes vs upstream:
- `Fuzz4All/model.py` — new `OpenAIChatModel` class and `openai/` prefix
  dispatch in `make_model`. Uses `chat.completions`, extracts the first
  fenced code block via `Fuzz4All.util.util.simple_parse`, parallelizes
  the batch with a thread pool.
- `Fuzz4All/target/target.py` — forwards `config_dict["llm"]` (so
  `base_url` / `api_key` reach the new model).
- `config/full_run/cpp_23_qwen.yaml` — ready-made C++23 short-validation
  config pointing at a local gateway.

Reports: `REPRODUCTION_PLAN.md`, `REPRODUCTION_REPORT.md`.

## Environment

Use an isolated Python 3.10 venv (torch/transformers must import even for the
OpenAI path since `target.py` imports them at top level):

```bash
uv venv --python 3.10 .venv
source .venv/bin/activate
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install -r requirements.txt
uv pip install -e .
uv pip install "httpx[socks]"    # only if a SOCKS proxy is configured
```

Targets need their own toolchain installed locally (skip what you do not run):
`g++` for C++, `gcc` for C, `javac` for Java, `go`, `cvc5` for SMT2,
`qiskit` (already in requirements.txt) for Qiskit.

## Running the C++ short validation

Current config: `config/full_run/cpp_23_qwen.yaml`
- 15 minutes, `batch_size=4`, `otf=true`, hand-written prompt
  (`config/documentation/cpp/cpp_23_shortened.md`).
- LLM: `openai/qwen3-coder-30b-a3b` via `http://localhost:4000/v1`.

```bash
source .venv/bin/activate
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
python Fuzz4All/fuzz.py \
    --config config/full_run/cpp_23_qwen.yaml \
    main_with_config \
    --folder outputs/full_run/cpp_qwen \
    --batch_size 4 \
    --model_name openai/qwen3-coder-30b-a3b \
    --target g++
```

CLI flags override YAML (`--folder`, `--batch_size`, `--model_name`,
`--target`), so keep them consistent with the config you intend to run.

Outputs:
```
outputs/full_run/cpp_qwen/
├── N.fuzz              # one file per generated sample
├── log.txt             # INFO-level run log
├── log_generation.txt  # LLM prompts and generated text (VERBOSE)
├── log_validation.txt  # per-sample g++ output (VERBOSE)
└── prompts/best_prompt.txt
```

Expect hundreds of samples in 15 minutes; validation pass/fail depends on
the local toolchain's C++23 support (GCC 13 is incomplete — see
`REPRODUCTION_REPORT.md` §5).

## Switching the LLM backend

Set in the YAML's `llm:` block:
```yaml
model_name: openai/<model-id>        # e.g. openai/qwen3-coder-30b-a3b
base_url:  http://localhost:4000/v1
api_key:   ""                         # leave empty for a no-auth gateway
```
The prefix selects the backend: `openai/` → `OpenAIChatModel`,
`ollama/` → Ollama, anything else → StarCoder (HuggingFace).

## Smoke-testing the backend without a full run

```python
from Fuzz4All.model import make_model
m = make_model(eos=[], model_name='openai/qwen3-coder-30b-a3b',
               device='cpu', max_length=512,
               llm_cfg={'base_url': 'http://localhost:4000/v1', 'api_key': ''})
print(m.generate('Write a one-line C++ hello world inside a code block.',
                 batch_size=1, temperature=0.7, max_length=200)[0])
```

## Extending to other targets

Duplicate `cpp_23_qwen.yaml`, change `target.language` (`c` / `java` / `go` /
`smt2` / `qiskit`), point `path_documentation` / `path_hand_written_prompt`
at the matching files under `config/documentation/`, and pass the matching
compiler/runtime via `--target` (e.g. `--target gcc`, `--target javac`,
`--target cvc5`).

## Out of scope for the current repro

- Full RQ1 (24h × 5 runs × 6 targets).
- Autoprompting (§3.2) — currently disabled; `use_hand_written_prompt: true`
  is used instead. To enable, route `Fuzz4All/util/api_request.py` to the
  same OpenAI-compatible gateway.
- Differential oracle across multiple compilers (needed to convert
  "failed to compile" into real bug counts).
