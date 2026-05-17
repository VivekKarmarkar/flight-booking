# Tomorrow

Agenda items captured at end of session 2026-05-17. Both stem from open questions surfaced by the empirical determinism probe.

## 1. Stochasticity analysis for one-way flights

**Question:** Does the determinism issue we found in `search_dates` (round-trip duration sweep) also affect `search_flights` calls for one-way queries?

**Why it matters:** `/find-flight` (one-way) uses `search_flights` directly with a fixed `departure_date`. We have not measured its variance — the determinism probe we ran was on round-trip + `search_dates`. If `search_flights` for a specific date is reliable, `/find-flight` needs no statistical wrapper. If it's stochastic, we need a `/find-flight-statistical` sibling.

**Method:**
- Pin parameters (e.g., `CID → JFK,LGA,EWR`, `departure_date=2026-06-15`, `departure_window=10-23`, `max_stops=ONE_STOP`).
- Dispatch N=7 parallel agents, each calls `search_flights` once with those exact params.
- Each agent reports its cheapest itinerary (price, flights, total_min) + the full feasible pool size.
- Compare across agents. Identical → reliable. Divergent → noisy.

**Hypothesis:** Drilling into a single date is less noisy than sweeping multiple durations. Reasoning: Google's cache hierarchy probably stores per-date fare buckets densely, while "cheapest in a range" requires sampling/exploration that exposes shard variability. Unverified.

## 2. Audit tool usage in fli MCP — pin noise sources

**Question:** Which of fli's MCP tools (`search_flights`, `search_dates`, `find_airports`) does each of our 4 skills actually use? Where have we built alternatives that we could compare against the native tool?

**Current understanding:**
| Tool | `/find-flight` | `/find-flight-rt` | `/find-flight-rt-optimized` | `/find-flight-rt-optimized-statistical` |
|---|---|---|---|---|
| `search_flights` | ✓ | ✓ (with return_date) | ✓ (drill-in only) | ✓ (× N) |
| `search_dates` | ✗ | ✗ | ✓ (sweep) | ✓ (sweep × N) |
| `find_airports` | ✗ | ✗ | ✗ | ✗ |

We resolve airports via LLM training-data knowledge + the 1-hour-radius rule. We do not use `find_airports` at all.

**Investigation:**
- Compare `find_airports` vs LLM resolution on test cases: Iowa City, Cedar Rapids, NYC, "Bay Area", Rutgers University. Do they return the same airport set? Where do they disagree?
- Run N-parallel probes per tool to characterize each tool's noise profile independently. We've done this for `search_dates` (high noise). We've not done it for `search_flights` (item 1 above) or `find_airports`.
- Produce a noise-source map: which tool is the actual culprit, where is the algorithm robust, where do we need variance reduction.

**Expected outcome:** `search_dates` is the noisy one; `search_flights` is *probably* stable; `find_airports` may have its own surprises. Once we know this, we can:
- Drop the statistical wrapper for the inner drill-in (since `search_flights` is stable).
- Apply the statistical wrapper *only* to the duration sweep step (since `search_dates` is noisy).
- Decide whether to ever use `find_airports` (probably no, since LLM resolution is deterministic).

## Carry-over context

- Skills folder: `~/.claude/skills/find-flight-{,-rt,-rt-optimized,-rt-optimized-statistical}/`
- Spec files: `Algorithm.md`, `AlgorithmInputs.md`, `AlgorithmConstraints.md`, `AlgorithmObjective.md`, plus `MOTIVATION.md` in the statistical skill
- Empirical evidence already gathered: 5-agent determinism probe at 07:08 UTC + 7-agent statistical run at 07:36 UTC (results in this session's transcripts)
- Underlying library: `punitarani/fli`, MCP server bound globally as `google-flights` in `~/.claude.json`
- Reverse-engineering technique recap: fli hits Google's internal `FlightsFrontendUi` RPC via `curl_cffi` Chrome TLS impersonation; payload is URL-encoded JSON (not protobuf, despite many descriptions)
