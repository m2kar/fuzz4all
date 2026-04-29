SystemVerilog finite state machine patterns: typed enums, case variants, Moore/Mealy styles, encoding schemes. Use these to generate state machines with non-trivial state transitions and output logic.

# Enum Definition

```
typedef enum logic [2:0] {
    IDLE  = 3'd0,
    START = 3'd1,
    RUN   = 3'd2,
    DONE  = 3'd3,
    ERR   = 3'd4
} state_t;
```

- `typedef enum logic [N:0] { ... } name_t;` — named enum with explicit width
- Enum labels are constants of the enum type; no need for numeric values unless custom encoding
- One-hot: assign values like `3'd1, 3'd2, 3'd4, 3'd8` (power of 2)

# Case Variants

- `case` — standard case statement (treats x/z as literal matches)
- `casez` — treats `z`/`?` as don't-care: `3'b1??:` matches `3'b100`, `3'b111`, etc.
- `casex` — treats both `x` and `z` as don't-care (use sparingly)
- `unique case` — compiler checks that cases are mutually exclusive and complete
- `priority case` — first match wins; implies a priority encoder

```
unique case (state)
    IDLE:   next = start ? START : IDLE;
    START:  next = RUN;
    RUN:    next = done  ? DONE  : (err ? ERR : RUN);
    DONE:   next = IDLE;
    ERR:    next = clear ? IDLE : ERR;
endcase
```

# Two-Always Pattern (Moore)

State register in `always_ff`, next-state + output in `always_comb`:

```
state_t state, next;

always_ff @(posedge clk) begin
    if (rst) state <= IDLE;
    else     state <= next;
end

always_comb begin
    next = state; // default: hold
    unique case (state)
        IDLE:   next = go ? RUN : IDLE;
        RUN:    next = fin ? DONE : RUN;
        DONE:   next = IDLE;
    endcase
end
```

# Mealy Output (Output Depends on Input)

In Mealy machines, outputs are computed in `always_comb` based on both state and inputs:

```
always_comb begin
    y = 8'd0;
    unique case (state)
        IDLE: y = go ? 8'hAA : 8'h00;
        RUN:  y = data;
        DONE: y = 8'hFF;
    endcase
end
```

# One-Hot Encoding

Assign one-hot values explicitly in the enum:

```
typedef enum logic [3:0] {
    S0 = 4'b0001,
    S1 = 4'b0010,
    S2 = 4'b0100,
    S3 = 4'b1000
} oh_state_t;
```

One-hot case tends to synthesize to fewer gates; each flip-flop drives one decode term.

# Registered Output (Three-Always Pattern)

Separate output register from state transition:

```
always_ff @(posedge clk) begin
    if (rst) begin
        state <= IDLE;
        y     <= 8'd0;
    end else begin
        state <= next;
        y     <= y_next;
    end
end
```

# Counter-Based State Transition

Use a counter to control how long a state is held:

```
logic [3:0] cnt;
always_ff @(posedge clk) begin
    if (rst)        cnt <= 4'd0;
    else if (state != next) cnt <= 4'd0;
    else            cnt <= cnt + 1'b1;
end

// in always_comb: next = (state == RUN && cnt == TIMEOUT) ? DONE : ...
```

# Style notes

- Always use `typedef enum` — never raw integer states.
- Always include `default` in `case` to avoid latch inference.
- Prefer `unique case` for state decoding to catch overlapping conditions.
- Reset state to `IDLE` (or equivalent initial state) synchronously inside `always_ff`.
