SystemVerilog counter patterns: binary up/down, LFSR, Gray code, ring counter, Johnson counter, saturating, and parameterized modulus. Use these to generate counters with non-trivial sequencing behavior.

# Binary Up/Down Counter

```
logic [WIDTH-1:0] cnt;
always_ff @(posedge clk) begin
    if (rst)      cnt <= '0;
    else if (en) begin
        if (up_down) cnt <= cnt + 1'b1;
        else         cnt <= cnt - 1'b1;
    end
end
```

- `'0` fills all bits with 0 regardless of width
- `up_down` selects direction; `en` gates counting

# Load and Modulus

```
logic [WIDTH-1:0] cnt;
always_ff @(posedge clk) begin
    if (rst)      cnt <= '0;
    else if (load) cnt <= data;
    else if (cnt == MODULO - 1) cnt <= '0;
    else             cnt <= cnt + 1'b1;
end
```

- `parameter int MODULO = 16;` — overridable wrap point
- `load` has priority over counting

# LFSR (Linear Feedback Shift Register)

XOR-based maximal-length pseudo-random sequence. Taps for common widths:

- 4-bit: bits [3, 2]
- 8-bit: bits [7, 5, 4, 3]
- 16-bit: bits [15, 14, 12, 3]

```
logic [7:0] lfsr;
always_ff @(posedge clk) begin
    if (rst) lfsr <= 8'hAC;  // any non-zero seed
    else     lfsr <= {lfsr[6:0], lfsr[7] ^ lfsr[5] ^ lfsr[4] ^ lfsr[3]};
end
```

- Feedback = XOR of tap positions; shifted into LSB (or MSB for Galois form)
- Seed must be non-zero or the LFSR locks at all-zeros

# Galois LFSR (Alternative Form)

XOR is applied in-place at each tap:

```
logic [7:0] glfsr;
always_ff @(posedge clk) begin
    if (rst) glfsr <= 8'h01;
    else begin
        glfsr <= glfsr >> 1;
        if (glfsr[0]) glfsr[7]   <= ~glfsr[7];
        if (glfsr[0]) glfsr[5]   <= ~glfsr[5];
        if (glfsr[0]) glfsr[4]   <= ~glfsr[4];
        if (glfsr[0]) glfsr[3]   <= ~glfsr[3];
    end
end
```

# Gray Code Counter

Binary-to-Gray: `gray = bin ^ (bin >> 1)`. Gray-to-binary requires iterative XOR:

```
logic [WIDTH-1:0] bin_cnt, gray_out;
always_ff @(posedge clk) begin
    if (rst) bin_cnt <= '0;
    else     bin_cnt <= bin_cnt + 1'b1;
end
assign gray_out = bin_cnt ^ (bin_cnt >> 1);
```

Gray code changes only one bit per cycle — useful for cross-clock-domain pointers.

# Ring Counter (One-Hot Shift)

Single bit circulates through the register:

```
logic [N-1:0] ring;
always_ff @(posedge clk) begin
    if (rst) ring <= {{(N-1){1'b0}}, 1'b1};  // one-hot init
    else     ring <= {ring[N-2:0], ring[N-1]}; // rotate left
end
```

Only one flip-flop toggles per cycle. Decoding a state is just reading one bit.

# Johnson Counter (Twisted Ring)

Like ring counter but the feedback bit is inverted:

```
logic [N-1:0] johnson;
always_ff @(posedge clk) begin
    if (rst)    johnson <= '0;
    else        johnson <= {~johnson[0], johnson[N-1:1]};
end
```

Sequence length = 2N (twice the register width). Each step changes one bit.

# Saturating Counter

Clamp at boundaries instead of wrapping:

```
always_ff @(posedge clk) begin
    if (rst)      cnt <= '0;
    else if (inc && cnt < MAX_VAL) cnt <= cnt + 1'b1;
    else if (dec && cnt > 0)       cnt <= cnt - 1'b1;
end
```

# Parameterized Counter Module

```
module top #(parameter int WIDTH = 8, int MODULO = 256) (
    input  logic             clk,
    input  logic             rst,
    input  logic             en,
    output logic [WIDTH-1:0] cnt
);
    always_ff @(posedge clk) begin
        if (rst)             cnt <= '0;
        else if (en && cnt == MODULO - 1) cnt <= '0;
        else if (en)         cnt <= cnt + 1'b1;
    end
endmodule
```

# Style notes

- Use `parameter` for width and modulus so the counter can be reused at different scales.
- LFSR seed must be non-zero; document which tap polynomial is used.
- Prefer `'0` and `'1` fill constants over hardcoded widths.
