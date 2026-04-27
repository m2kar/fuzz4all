Please create a short, self-contained SystemVerilog (IEEE 1800-2012) module that the EDAzz pipeline (verible-verilog-syntax + iverilog -g2012 + verilator --sv) can elaborate without errors. Output only the module code wrapped in a ```systemverilog block.

Hard requirements (the EDAzz static checker rejects modules that violate any of these):

1. The top-level module must be named `top` and must be the only entry module in the file (helper modules are allowed but must be defined as plain `module ... endmodule` blocks in the same file).
2. The `top` module must declare ANSI-style ports including, at a minimum, `input logic clk` and `input logic rst`. Both `clk` and `rst` are required even if the design is purely combinational — leave them unconnected if unused.
3. The `top` module must declare at least one `output` port. Modules with zero outputs are rejected.
4. Use `always_ff @(posedge clk)` for sequential logic and `always_comb` for combinational logic. Do NOT use bare `always @(...)` blocks or asynchronous reset sensitivity lists. If reset is needed, use a synchronous `if (rst) ... else ...` inside `always_ff @(posedge clk)`.
5. Each signal must have a single driver. Do NOT mix `assign` with procedural writes to the same signal, and do not drive the same signal from multiple procedural blocks.
6. Use `logic` for procedurally assigned signals; do not write to `wire`/net declarations from procedural blocks.
7. Do NOT use delays or time constructs (`#...`, `timeunit`, `timeprecision`, `fork`/`join`, `wait`).
8. Do NOT instantiate undefined modules, UDPs, or vendor primitives such as `IOBUF`, `NAND`, `NOT` unless you also define them as plain modules in the same file.
9. `always_comb` blocks must be feed-forward: do not read and write the same state variable in the same combinational block.
10. Avoid `interface`, `clocking`, `assert property`, `cover property`, concurrent assertions, `import`, `` `include ``, classes, dynamic arrays/queues, constraints, and DPI calls.
11. Do NOT introduce simulation self-termination or runtime-abort constructs: no `$fatal`, `$finish`, `$stop`, `$error`, `$warning`, `$info`, no immediate `assert(...)`/`assume(...)`/`cover(...)`. Express intended behavior through normal data/control flow only.
12. Keep the design under ~40 lines when possible. Prefer synthesizable code.

Permitted features include: `logic` signals, `parameter`/`localparam`, packed structs, enums (`typedef enum logic [N:0] { ... } t;`), `case`/`if`, arithmetic and bitwise ops, `assign`, and `generate`/`for` blocks.

Example output:

```systemverilog
module top(
    input  logic       clk,
    input  logic       rst,
    input  logic [3:0] a,
    input  logic [3:0] b,
    output logic [4:0] sum
);
    logic [4:0] acc;
    always_ff @(posedge clk) begin
        if (rst) acc <= '0;
        else     acc <= a + b;
    end
    assign sum = acc;
endmodule
```

Now generate a new SystemVerilog module that follows every requirement above. Output only the module code wrapped in a ```systemverilog code block.
