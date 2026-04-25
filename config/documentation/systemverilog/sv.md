SystemVerilog (IEEE 1800) extends Verilog with features for RTL design, verification, and formal assertions. This is a short feature reference to guide generation of self-contained synthesizable modules and simple verification constructs. Every generated program should define a single top-level `module top` with no external package or include dependencies.

# Data Model

SystemVerilog introduces 2-state and 4-state types in addition to Verilog's `reg`/`wire`:

- `logic` — 4-state (0, 1, x, z) single- or multi-bit signal; replaces most uses of `reg`/`wire` and can be driven procedurally or continuously (but not both).
- `bit` — 2-state (0, 1) scalar or packed vector, useful for testbench counters.
- `byte`, `shortint`, `int`, `longint`, `integer` — signed 2-state or 4-state integer types.
- `real`, `shortreal` — floating point (non-synthesizable).
- `string` — dynamic character string with built-in methods `.len()`, `.substr()`, `.atoi()`.
- Packed and unpacked arrays: `logic [7:0] bus [0:15];`, `int q[$]` (queue), `int d[]` (dynamic), `int a[string]` (associative).
- `struct packed { logic [3:0] op; logic [7:0] data; }` and `union packed` for bit-level layouts.
- `typedef enum logic [1:0] { IDLE, RUN, DONE } state_t;` for named enumerations.

# General

Module, port, and instantiation syntax:

```
module top(input logic clk, input logic rst_n, output logic [7:0] out);
  parameter int WIDTH = 8;
  logic [WIDTH-1:0] counter;
  sub #(.W(WIDTH)) u_sub (.clk(clk), .rst_n(rst_n), .q(counter));
  assign out = counter;
endmodule
```

- ANSI-style port lists with direction+type+name in the header are preferred.
- `parameter` and `localparam` for compile-time constants; overriding via `#(.NAME(value))` at instantiation.
- `interface` bundles signals and `modport` defines access direction from each side.
- `package`/`import` scope shared types and parameters (avoid if you need a self-contained single file).
- `generate`/`endgenerate` with `for` or `if` creates structural replication at elaboration.
- `function` (combinational, no time) and `task` (may advance time) encapsulate reusable logic.

# Control Flow

Procedural blocks:

- `always_comb` — combinational, inferred sensitivity, tool checks for latches.
- `always_ff @(posedge clk or negedge rst_n)` — sequential, flip-flop inferred.
- `always_latch` — intentional latch.
- `initial` / `final` — one-shot blocks (simulation only; non-synthesizable).

Statements: `if`/`else if`/`else`, `case`/`casex`/`casez`/`case inside`, `unique`/`priority` case qualifiers, `for`, `foreach`, `while`, `do-while`, `break`, `continue`, `return`. `fork`/`join`, `join_any`, `join_none` for parallel simulation threads.

Example:

```
always_ff @(posedge clk or negedge rst_n) begin
  if (!rst_n)      counter <= '0;
  else if (enable) counter <= counter + 1'b1;
end
```

# Preprocess

Verilog preprocessor directives carry over:

- \`define, \`undef, \`ifdef, \`ifndef, \`elsif, \`else, \`endif
- \`include "file.svh"
- \`timescale 1ns/1ps
- \`__FILE__, \`__LINE__

Macros may be multi-line with trailing backslash and can take arguments: \`define MAX(a,b) ((a) > (b) ? (a) : (b)).

# Timing

- Event control: `@(posedge clk)`, `@(negedge rst_n)`, `@(signal)`, `@*` (sensitivity list).
- Delays: `#10;`, `#(PERIOD/2);` in testbench only.
- `wait(cond);` blocks until a condition is true.
- Clocking blocks (`clocking cb @(posedge clk); ... endclocking`) group sampling and driving timing for verification.
- Reset strategies: synchronous (`if (!rst_n) q <= 0;` inside posedge block) or asynchronous (second sensitivity term `or negedge rst_n`).

# SVA Property

SystemVerilog Assertions for verification and formal properties:

- Immediate: `assert (a == b) else $error("mismatch");` inside procedural code.
- Concurrent: named properties built from sequences over time.

```
property req_gnt;
  @(posedge clk) disable iff (!rst_n) req |-> ##[1:3] gnt;
endproperty
a_req_gnt: assert property (req_gnt);
c_req_gnt: cover  property (req_gnt);
```

Sequence operators: `##N` (cycle delay), `##[a:b]` (range), `|->` (overlapping implication), `|=>` (non-overlapping), `throughout`, `within`, `intersect`, `[*N]` (repetition), `[=N]`, `[->N]`. `disable iff` suppresses evaluation during reset. `assert`, `assume`, `cover`, `restrict` select the verification semantic.

# Style notes for this fuzzer

- Always name the top module `top`.
- Prefer `logic` over `reg`/`wire`; use `always_ff`/`always_comb`/`always_latch` rather than the untyped `always`.
- Keep everything in one file; do not `import` external packages or `include` external files.
- `initial $display(...)` is acceptable for trivial exercises but is not synthesizable.
