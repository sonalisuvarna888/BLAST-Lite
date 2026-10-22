# Battery Degradation Proxy in the Dispatch Objective

## Purpose

This analysis compares annual community-microgrid battery scheduling
with and without a linear battery-throughput penalty in the CVXPY
objective.

## Cases

- Battery only
- Demand response plus battery

## Degradation coefficients

- 0
- 0.005
- 0.015
- 0.030 dollars per kWh-throughput

The primary comparison is between 0 and 0.015.

## Degradation proxy

`c_deg * 0.5 * sum(charge + discharge)`

This proxy affects CVXPY dispatch. It is not equivalent to BLAST-Lite
degradation. BLAST-Lite independently evaluates each resulting annual
SOC trajectory using the same second-life state.

## Primary annual findings

At c_deg = 0.015 compared with c_deg = 0:

### Battery only

- bill increase: approximately 0.39%;
- throughput reduction: approximately 27.78%;
- q improvement: approximately 0.0111;
- remaining-capacity improvement: approximately 0.582 kWh.

### Demand response plus battery

- bill increase: approximately 0.29%;
- throughput reduction: approximately 28.84%;
- q improvement: approximately 0.0147;
- remaining-capacity improvement: approximately 0.774 kWh.

## Sensitivity finding

The best remaining capacity did not occur at the largest coefficient.

- Battery only: best at c_deg = 0.005
- DR plus battery: best at c_deg = 0.015

The response is non-monotonic because the linear proxy changes
throughput, mean SOC, timing, and DOD together.

## Validation

All eight annual runs completed successfully with:

- 8,760 hours per run;
- 365 successful daily optimizations;
- finite q and resistance outputs;
- negligible energy-balance residuals;
- SOC within bounds; and
- final annual SOC returned to target.

## Limitations

- Coefficients are scenario values, not calibrated replacement costs.
- Community inputs remain synthetic.
- The throughput proxy is not equivalent to BLAST-Lite aging.
- BLAST-Lite is a cell-level model.
- q is not a complete SOH or safety metric.

## Next milestone

Replace the synthetic household load layer with the real Harvard
Dataverse household dataset.
