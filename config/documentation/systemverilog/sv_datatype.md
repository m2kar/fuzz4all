SystemVerilog type system: packed structs, unions, typedef, enum with custom encoding, packed 2D arrays, and parameterized types. Use these to create modules that exercise the SV type system beyond plain `logic` vectors.

# Packed Struct

```
typedef struct packed {
    logic [3:0] opcode;
    logic       flag;
    logic [2:0] addr;
    logic [7:0] data;
} packet_t;

packet_t pkt;
assign pkt.opcode = 4'hA;
assign pkt.data   = 8'hFF;
logic [15:0] raw  = pkt;  // packed struct is directly assignable to a bit vector
```

- All fields must be packed (fixed-width `logic`/`bit` types)
- A packed struct is a single vector; can be used in port lists and assignments as a whole
- Total width = sum of field widths

# Packed Union

```
typedef union packed {
    logic [15:0] word;
    packet_t     fields;
} word_or_packet_t;

word_or_packet_t u;
assign u.fields.opcode = 4'h3;
assign u.fields.data   = 8'h42;
logic [15:0] w = u.word;  // read same bits as a flat vector
```

- Both views share the same bits
- Writing one member and reading another is a bit-level reinterpretation

# Typedef

```
typedef logic [7:0] byte_t;
typedef logic [15:0] halfword_t;
typedef enum logic [1:0] { MUL, ADD, SUB, NOP } op_t;

byte_t     a, b;
halfword_t result;
op_t       opcode;
```

- `typedef` creates named aliases for any type
- Use for documentation clarity and to reduce repetition

# Parameterized Struct

```
typedef struct packed {
    logic [PW-1:0] addr;
    logic [DW-1:0] data;
} #(.PW(8), .DW(32)) xfer_t;  // NOT valid SV syntax

// Instead, use parameterized module and define struct inside:
module top #(parameter int AW=4, DW=8) (
    input  logic             clk,
    input  logic             rst,
    output logic [AW+DW-1:0] out
);
    typedef struct packed {
        logic [AW-1:0] addr;
        logic [DW-1:0] data;
    } entry_t;
    entry_t e;
    // ...
endmodule
```

Structs in parameterized modules can reference module-level parameters.

# Enum with Custom Encoding

```
typedef enum logic [2:0] {
    IDLE    = 3'b000,
    READ    = 3'b001,
    WRITE   = 3'b010,
    WAIT    = 3'b100,
    ERROR   = 3'b111
} cmd_t;

cmd_t cmd;
always_ff @(posedge clk) begin
    if (rst) cmd <= IDLE;
    else     cmd <= cmd_next;
end
```

- Enum values can be explicitly assigned to any valid constant
- Gaps in encoding are allowed (e.g., 3'b011 and 3'b101 are unused above)
- `cmd_t` is a proper type: can be used in ports, comparisons, case labels

# 2D Packed Array

```
logic [3:0][7:0] matrix;  // 4 bytes packed into 32 bits
// matrix[0] = lowest byte, matrix[3] = highest byte

assign matrix[0] = 8'hAA;
assign matrix[1] = 8'hBB;
assign matrix[2] = 8'hCC;
assign matrix[3] = 8'hDD;
logic [31:0] flat = matrix;  // = 32'hDDCCBBAA
```

- Leftmost dimension is the "outer" (most-significant) dimension
- Packed 2D arrays can be assigned to flat vectors of the same total width

# Unpacked Array with Procedural Iteration

```
logic [7:0] mem [0:15];

always_ff @(posedge clk) begin
    if (rst) begin
        for (int i = 0; i < 16; i++) mem[i] <= 8'd0;
    end else begin
        mem[addr] <= wr_data;
    end
end
```

- Unpacked arrays cannot be in port lists (use packed or pass element-by-element)
- `for (int i = ...)` is a SystemVerilog feature — `int i` declared inline

# `$clog2` for Derived Widths

```
parameter int DEPTH = 64;
localparam int AW   = $clog2(DEPTH);  // AW = 6
logic [AW-1:0] addr;
```

- `$clog2(N)` returns the number of bits needed to address N entries
- Use `localparam` for derived constants that should not be overridden

# Style notes

- Define types with `typedef` at module scope; avoid anonymous struct/union in ports.
- Prefer packed types for synthesizable design; unpacked for memories and arrays.
- Use `enum` with named values instead of raw constants for readability.
