module round_robin_arbiter #(
  parameter int REQUESTERS = 4
) (
  input  logic                  clk,
  input  logic                  rst,
  input  logic [REQUESTERS-1:0] request,
  output logic [REQUESTERS-1:0] grant
);
  always_ff @(posedge clk) begin
    if (rst)
      grant <= '0;
    else
      grant <= request;
  end
endmodule
