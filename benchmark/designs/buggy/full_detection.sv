module fifo #(
  parameter int DATA_WIDTH = 8,
  parameter int DEPTH = 4,
  localparam int PTR_WIDTH = (DEPTH <= 1) ? 1 : $clog2(DEPTH),
  localparam int COUNT_WIDTH = (DEPTH <= 1) ? 1 : $clog2(DEPTH + 1)
) (
  input logic clk, rst, wr_en, rd_en,
  input logic [DATA_WIDTH-1:0] din,
  output logic [DATA_WIDTH-1:0] dout,
  output logic full, empty,
  output logic [COUNT_WIDTH-1:0] count
);
  logic [DATA_WIDTH-1:0] mem [0:DEPTH-1];
  logic [PTR_WIDTH-1:0] wr_ptr, rd_ptr;
  wire write_accepted = wr_en && !full;
  wire read_accepted = rd_en && !empty;

  assign full = count == DEPTH - 1;
  assign empty = count == 0;

  function automatic logic [PTR_WIDTH-1:0] advance(input logic [PTR_WIDTH-1:0] pointer);
    advance = (pointer == DEPTH - 1) ? '0 : pointer + 1'b1;
  endfunction

  always_ff @(posedge clk) begin
    if (rst) begin
      wr_ptr <= '0;
      rd_ptr <= '0;
      count <= '0;
      dout <= '0;
    end else begin
      if (write_accepted) begin
        mem[wr_ptr] <= din;
        wr_ptr <= advance(wr_ptr);
      end
      if (read_accepted) begin
        dout <= mem[rd_ptr];
        rd_ptr <= advance(rd_ptr);
      end
      case ({write_accepted, read_accepted})
        2'b10: count <= count + 1'b1;
        2'b01: count <= count - 1'b1;
        default: count <= count;
      endcase
    end
  end
endmodule

