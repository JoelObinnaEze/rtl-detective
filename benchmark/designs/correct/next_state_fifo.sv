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
  logic [DATA_WIDTH-1:0] storage [0:DEPTH-1];
  logic [PTR_WIDTH-1:0] write_index, read_index;
  logic take_write, take_read;

  assign full = count == DEPTH;
  assign empty = count == 0;
  assign take_write = wr_en && !full;
  assign take_read = rd_en && !empty;

  always_ff @(posedge clk) begin
    if (rst) begin
      write_index <= '0;
      read_index <= '0;
      count <= '0;
      dout <= '0;
    end else begin
      if (take_write) begin
        storage[write_index] <= din;
        write_index <= (write_index == DEPTH - 1) ? '0 : write_index + 1'b1;
      end
      if (take_read) begin
        dout <= storage[read_index];
        read_index <= (read_index == DEPTH - 1) ? '0 : read_index + 1'b1;
      end
      count <= count + take_write - take_read;
    end
  end
endmodule

