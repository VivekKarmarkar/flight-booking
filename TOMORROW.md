# Tomorrow

Agenda items captured at end of session 2026-05-17. Open question surfaced by this session's empirical determinism work.

## Stochasticity analysis for one-way flights

**Question:** Does the determinism issue we found in `search_dates` (round-trip duration sweep) also affect `search_flights` calls for one-way queries?

**Why it matters:** `/find-flight` (one-way) uses `search_flights` directly with a fixed `departure_date`. We have not measured its variance — the determinism probe we ran was on round-trip + `search_dates`. If `search_flights` for a specific date is reliable, `/find-flight` needs no statistical wrapper. If it's stochastic, we need a `/find-flight-statistical` sibling.

**Method:**
- Pin parameters (e.g., `CID → JFK,LGA,EWR`, `departure_date=2026-06-15`, `departure_window=10-23`, `max_stops=ONE_STOP`).
- Dispatch N=7 parallel agents, each calls `search_flights` once with those exact params.
- Each agent reports its cheapest itinerary (price, flights, total_min) + the full feasible pool size.
- Compare across agents. Identical → reliable. Divergent → noisy.

**Hypothesis:** Drilling into a single date is less noisy than sweeping multiple durations. Reasoning: Google's cache hierarchy probably stores per-date fare buckets densely, while "cheapest in a range" requires sampling/exploration that exposes shard variability. Unverified.

## Carry-over context

- Skills folder: `~/.claude/skills/find-flight-{,-rt,-rt-optimized,-rt-optimized-statistical}/`
- Spec files: `Algorithm.md`, `AlgorithmInputs.md`, `AlgorithmConstraints.md`, `AlgorithmObjective.md`, plus `MOTIVATION.md` in the statistical skill
- Empirical evidence already gathered: 5-agent determinism probe at 07:08 UTC + 7-agent statistical run at 07:36 UTC (results in this session's transcripts)
- Underlying library: `punitarani/fli`, MCP server bound globally as `google-flights` in `~/.claude.json`
- Reverse-engineering technique recap: fli hits Google's internal `FlightsFrontendUi` RPC via `curl_cffi` Chrome TLS impersonation; payload is URL-encoded JSON (not protobuf, despite many descriptions)
- Tool-usage audit (resolved this session): the skills are MCP-tool-agnostic — every data retrieval goes through `search_flights` or `search_dates`, native filter params used where MCP supports them, three justified bypasses (LLM airport resolution, client-side price/duration filters, leg-split heuristic for round-trip serialization). See session transcript for citations.
