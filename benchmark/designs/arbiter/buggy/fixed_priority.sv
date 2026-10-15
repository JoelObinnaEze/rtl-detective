module round_robin_arbiter #(
  parameter int REQUESTERS = 4
) (
  input  logic                  clk,
  input  logic                  rst,
  input  logic [REQUESTERS-1:0] request,
  output logic [REQUESTERS-1:0] grant
);
  logic [REQUESTERS-1:0] next_grant;
  integer index;
  logic found;

  always_comb begin
    next_grant = '0;
    found = 1'b0;
    for (index = 0; index < REQUESTERS; index = index + 1) begin
      if (!found && request[index]) begin
        next_grant[index] = 1'b1;
        found = 1'b1;
      end
    end
  end

  always_ff @(posedge clk) begin
    if (rst)
      grant <= '0;
    else
      grant <= next_grant;
  end
endmodule
