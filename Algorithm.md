# Algorithm

## Inputs

See [`AlgorithmInputs.md`](AlgorithmInputs.md).

## Problem

Solve the constrained optimization problem defined in [`AlgorithmObjective.md`](AlgorithmObjective.md) subject to the hard constraints in [`AlgorithmConstraints.md`](AlgorithmConstraints.md).

## Output

The algorithm returns **two links** to the single optimal flight identified by the optimization:

1. **Google Flights link** — a deep link that lands the user on the Google Flights result page for that specific flight, so they can book through Google's surface if they choose.
2. **Airline direct link** — a deep link to the **operating airline's own booking page** (e.g., `aa.com`, `delta.com`, `united.com`) for that specific flight, so they can book directly with the airline.

Both links must point to the **same flight** that the optimization selected.
