# Algorithm Inputs

## 1. Departure Destination

A place name (city, town, region) provided by the user. The destination is **not** required to have its own airport.

**Resolution rule:** From training-data knowledge of US/worldwide airports and their IATA codes, identify every commercial airport that **serves** the departure destination. An airport serves the destination iff it lies within an approximately **one-hour-or-less travel radius** of the destination's center. Multiple serving airports are allowed.

**Examples (non-exhaustive):**
- *Iowa City* → CID (Cedar Rapids, ~25 mi, ~30 min). Des Moines (DSM, ~2 h) and Chicago (ORD, ~3+ h) do **not** serve Iowa City.
- *New York City* → JFK, LGA, EWR.

## 2. Arrival Destination

Same as input 1, applied to the arrival side. Same one-hour-radius rule. Multiple serving airports allowed.

## 3. Date Range

A temporal window for the flight. Three forms are supported:

- **Lower bound only**: `date ≥ D_lo` (open upper bound)
- **Upper bound only**: `date < D_hi` (open lower bound)
- **Both bounds**: `D_lo ≤ date ≤ D_hi`

## 4. Additional Context (optional)

Free-form supplementary information the user wants the algorithm to be aware of. May be empty.
