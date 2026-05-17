# Algorithm Objective

Given the bounds defined in [`AlgorithmConstraints.md`](AlgorithmConstraints.md), solve the following constrained optimization problem.

## Optimization Procedure

1. **Restrict the search space** to all flights satisfying the hard constraints.
2. **Find the cheapest flight** `P*` in that restricted space.
3. **Construct the $20 band**: all flights whose price lies in `[P*, P* + $20]`.
4. **Within that band**, select the flight with the **shortest flying time** (minimum total elapsed duration).

## Return

The single flight that minimizes flying time within the $20 cheapest-band — under the hard constraints.
