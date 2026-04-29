SystemVerilog multiplexer, decoder, encoder, and barrel shifter patterns using `case`, ternary chains, `generate for`, and `casez`. Use these to build routing and selection logic.

# Case-Based N:1 MUX

```
logic [WIDTH-1:0] mux_out;
always_comb begin
    unique case (sel)
        2'd0: mux_out = a;
        2'd1: mux_out = b;
        2'd2: mux_out = c;
        2'd3: mux_out = d;
    endcase
end
```

- `unique case` — compiler verifies mutually exclusive select values
- Always include `default` or cover all select values to avoid latches

# Ternary Assign Chain (Small MUX)

```
logic [7:0] y;
assign y = sel[1] ? (sel[0] ? d : c)
                  : (sel[0] ? b : a);
```

Synthesizes to a tree of 2:1 MUXes. Readable for up to 4:1; use `case` beyond that.

# Generate-For Replicated MUX

```
genvar i;
generate
    for (i = 0; i < NUM_CH; i++) begin : ch_mux
        always_comb begin
            case (sel[i])
                1'b0: dout[i] = src0[i];
                1'b1: dout[i] = src1[i];
            endcase
        end
    end
endgenerate
```

- `generate for` with `genvar` creates N independent MUX instances at elaboration
- Each instance is named `ch_mux[0]....`, `ch_mux[1]....` for hierarchy

# 1-of-N Decoder

Binary input → one-hot output:

```
logic [3:0] onehot;
always_comb begin
    onehot = 4'd0;
    onehot[sel] = 1'b1;
end
```

Or equivalently with shift:

```
assign onehot = 4'b0001 << sel;
```

# Priority Encoder

Use `casez` with don't-care (`?`) wildcards for priority encoding:

```
logic [1:0] prio;
logic       valid;
always_comb begin
    prio  = 2'd0;
    valid = 1'b0;
    casez (req)
        4'b1???: begin prio = 2'd3; valid = 1'b1; end
        4'b01??: begin prio = 2'd2; valid = 1'b1; end
        4'b001?: begin prio = 2'd1; valid = 1'b1; end
        4'b0001: begin prio = 2'd0; valid = 1'b1; end
    endcase
end
```

- `casez` treats `z` and `?` as don't-care
- First match wins → priority order is MSB-first

# One-Hot to Binary Encoder

```
logic [1:0] bin;
always_comb begin
    bin = 2'd0;
    case (onehot)
        4'b0001: bin = 2'd0;
        4'b0010: bin = 2'd1;
        4'b0100: bin = 2'd2;
        4'b1000: bin = 2'd3;
        default: bin = 2'd0;
    endcase
end
```

Compact OR-based alternative for power-of-two sizes:

```
assign bin = {(onehot[3] | onehot[2]), (onehot[3] | onehot[1])};
```

# Barrel Shifter

Shift by variable amount using `generate for` to create log2(N) stages:

```
logic [WIDTH-1:0] stage [0:STAGES];
assign stage[0] = data_in;
genvar s;
generate
    for (s = 0; s < STAGES; s++) begin : shStage
        always_comb begin
            if (shamt[s])
                stage[s+1] = (dir == 0) ? (stage[s] << (1 << s))
                                        : (stage[s] >> (1 << s));
            else
                stage[s+1] = stage[s];
        end
    end
endgenerate
assign data_out = stage[STAGES];
```

- STAGES = $clog2(WIDTH)
- Each stage shifts by 2^s if the corresponding shamt bit is set

# Demultiplexer (1-to-N)

Route input to one of N outputs:

```
always_comb begin
    dout = '{default: '0};
    dout[sel] = din;
end
```

`'{default: '0}` sets all elements to 0 before assigning one.

# Style notes

- Prefer `always_comb` for all combinational MUX/decoder/encoder logic.
- Use `unique case` when select values are known to be one-hot or mutually exclusive.
- `generate for` is the idiomatic way to replicate logic across bit slices or channels.
