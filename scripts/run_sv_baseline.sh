#!/usr/bin/env bash
# Run all SystemVerilog baseline legs sequentially.
# Tools covered: iverilog, verilator, circt, yosys, cxxrtl.
set -u
cd /edazz/playground/fuzz4all
source .venv/bin/activate
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy

TOOLS=("${@:-iverilog verilator circt yosys cxxrtl}")
# allow passing a space-separated list via argv; default = all five
if [ $# -eq 0 ]; then TOOLS=(iverilog verilator circt yosys cxxrtl); else TOOLS=("$@"); fi

declare -A RC

for tool in "${TOOLS[@]}"; do
    cfg="config/full_run/sv_${tool}_qwen.yaml"
    out="outputs/full_run/sv_${tool}_qwen"
    echo "=== $(date -Is) :: ${tool} ==="
    python Fuzz4All/fuzz.py \
        --config "$cfg" \
        main_with_config \
        --folder "$out" \
        --batch_size 4 \
        --model_name openai/qwen3-coder-30b-a3b \
        --target "$tool"
    RC[$tool]=$?
    echo "=== $(date -Is) :: ${tool} done rc=${RC[$tool]} ==="
done

echo -n "=== $(date -Is) :: ALL DONE"
for tool in "${TOOLS[@]}"; do echo -n " ${tool}=${RC[$tool]}"; done
echo " ==="
