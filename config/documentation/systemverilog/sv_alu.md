SystemVerilog arithmetic and logic operators, signed arithmetic, and parameterized bit-width patterns. Use these to build ALU-style combinational and sequential logic.

# Arithmetic and Bitwise Operators

- `+`, `-`, `*` — addition, subtraction, multiplication (result width = max(operands); overflow wraps)
- `/`, `%` — division and modulo (avoid for synthesis unless divisor is power-of-two)
- `&`, `|`, `^`, `~`, `~&`, `~|`, `~^` — bitwise AND, OR, XOR, NOT, NAND, NOR, XNOR
- `<<`, `>>` — logical left/right shift (fills with 0)
- `>>>`, `<<<` — arithmetic right shift (sign-extends if signed), arithmetic left shift
- Unary reductions: `&a` (AND all bits), `|a`, `^a`, `~&a`, `~|a`, `~^a`

```
logic [7:0] a, b;
logic [15:0] product = a * b;           // width 16 to hold full result
logic [7:0] sum   = a + b;             // overflow wraps at 256
logic       carry = a > 8'hFF - b;     // unsigned overflow detect
logic [7:0] and_r = a & b;
logic [7:0] xor_r = a ^ b;
```

# Signed Arithmetic

- `$signed(expr)` — interpret bits as signed for this operation
- `$unsigned(expr)` — interpret bits as unsigned
- `signed` keyword on port/wire declarations makes them signed by default
- Comparison: `<`, `>`, `<=`, `>=` behave differently for signed vs unsigned operands

```
logic signed [7:0] sa, sb;
logic signed [7:0] sadd = sa + sb;               // signed addition
logic        [7:0] ua, ub;
logic        [7:0] uadd = $signed(ua) + $signed(ub); // mix signed/unsigned
logic              neg  = sa[7];                       // sign bit
logic signed [7:0] abs_sa = sa[7] ? -sa : sa;         // absolute value
```

# Concatenation and Replication

- `{a, b}` — concatenation; result width = sum of operand widths
- `{N{a}}` — replicate `a` exactly `N` times
- `{1'b0, a[7:1]}` — shift right by 1 with zero fill

```
logic [3:0] lo, hi;
logic [7:0] cat = {hi, lo};           // concatenate
logic [15:0] dup = {2{cat}};          // replicate: {cat, cat}
logic [7:0] sll2 = {a[5:0], 2'b00};  // left shift by 2 via concat
```

# Parameterized Bit Width

- `parameter int WIDTH = 8;` — overridable at instantiation
- `localparam int DW = $clog2(DEPTH);` — derived constant
- Port declarations use `[WIDTH-1:0]` to stay generic

```
module top #(parameter int WIDTH = 8) (
    input  logic             clk,
    input  logic             rst,
    input  logic [WIDTH-1:0] a,
    input  logic [WIDTH-1:0] b,
    input  logic [2:0]       op,
    output logic [WIDTH-1:0] y
);
    always_comb begin
        unique case (op)
            3'd0: y = a + b;
            3'd1: y = a - b;
            3'd2: y = a & b;
            3'd3: y = a | b;
            3'd4: y = a ^ b;
            3'd5: y = ~a;
            3'd6: y = a << b[2:0];
            3'd7: y = a >> b[2:0];
        endcase
    end
endmodule
```

# Carry and Overflow Detection

```
logic [WIDTH-1:0] sum;
logic             carry;
{carry, sum} = {1'b0, a} + {1'b0, b};   // wider add to capture carry

logic signed_overflow = (a[WIDTH-1] == b[WIDTH-1]) && (sum[WIDTH-1] != a[WIDTH-1]);
```

# Conditional Operator

- `cond ? a : b` — ternary mux, synthesizes to a 2:1 MUX

```
logic [7:0] min_val = (a < b) ? a : b;
logic [7:0] max_val = (a >= b) ? a : b;
```

# Style notes

- Use `parameter` for overridable widths; `localparam` for derived constants.
- Prefer `always_comb` for pure combinational ALU logic.
- Use `always_ff @(posedge clk)` for pipelined or registered ALU outputs.
