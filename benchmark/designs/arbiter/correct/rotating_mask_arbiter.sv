module round_robin_arbiter #(
  parameter int REQUESTERS = 4
) (
  input  logic                  clk,
  input  logic                  rst,
  input  logic [REQUESTERS-1:0] request,
  output logic [REQUESTERS-1:0] grant
);
  logic [REQUESTERS-1:0] rotation_mask;
  logic [REQUESTERS-1:0] next_mask;
  logic [REQUESTERS-1:0] next_grant;
  logic [REQUESTERS-1:0] eligible;
  integer index;
  integer selected;
  logic found;

  always_comb begin
    eligible = ((request & rotation_mask) != '0) ? request & rotation_mask : request;
    next_grant = '0;
    next_mask = rotation_mask;
    selected = 0;
    found = 1'b0;
    for (index = 0; index < REQUESTERS; index = index + 1) begin
      if (!found && eligible[index]) begin
        next_grant[index] = 1'b1;
        selected = index;
        found = 1'b1;
      end
    end
    if (found) begin
      next_mask = '0;
      for (index = 0; index < REQUESTERS; index = index + 1)
        if (index > selected)
          next_mask[index] = 1'b1;
      if (selected == REQUESTERS - 1)
        next_mask = '1;
    end
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      rotation_mask <= '1;
      grant <= '0;
    end else begin
      rotation_mask <= next_mask;
      grant <= next_grant;
    end
  end
endmodule
