module round_robin_arbiter #(
  parameter int REQUESTERS = 4
) (
  input  logic                  clk,
  input  logic                  rst,
  input  logic [REQUESTERS-1:0] request,
  output logic [REQUESTERS-1:0] grant
);
  localparam int INDEX_WIDTH = (REQUESTERS <= 2) ? 1 : $clog2(REQUESTERS);
  logic [INDEX_WIDTH-1:0] priority_index;
  logic [INDEX_WIDTH-1:0] next_priority_index;
  logic [REQUESTERS-1:0] next_grant;
  integer offset;
  integer index;
  logic found;

  always_comb begin
    next_grant = '0;
    next_priority_index = priority_index;
    found = 1'b0;
    for (offset = 0; offset < REQUESTERS; offset = offset + 1) begin
      index = priority_index + offset;
      if (index >= REQUESTERS)
        index = index - REQUESTERS;
      if (!found && request[index]) begin
        next_grant[index] = 1'b1;
        next_priority_index = (index == REQUESTERS - 1) ? '0 : index + 1;
        found = 1'b1;
      end
    end
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      priority_index <= '0;
      grant <= '0;
    end else begin
      priority_index <= next_priority_index;
      grant <= next_grant;
    end
  end
endmodule
