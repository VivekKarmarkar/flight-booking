# Tomorrow

No open items as of session 2026-05-17 (evening). Both prior agenda items resolved within-session.

## Resolved this session

### One-way stochasticity probe (was #23)

Probed whether `search_flights` with a single fixed `departure_date` exhibits the same non-determinism as `search_dates` (the round-trip noise source).

**Setup**: 7 parallel agents, pinned params (CID → JFK,LGA,EWR, range 2026-05-17 to 2026-05-31, depart 10-23, ≤1 stop, ≤7h, <$400). Each agent ran `/find-flight` end-to-end (15 search_flights calls × 7 agents = 105 MCP calls total).

**Result**: 7 of 7 agents picked the **identical** flight:
- Tue May 19, UA4170+UA2166, CID → ORD → EWR
- $379, 5h 31min, 1 stop
- Dep 12:34, Arr 18:05

Raw flight counts per agent: 2045–2051 (spread of 6 across ~2050). Feasible counts after hard constraints: exactly 60 for all 7. P* = $371 for all 7. Band [$371, $391] held 55 itineraries for all 7.

**Conclusion**: `search_flights` (single-date drill-in) is empirically deterministic. The noise we documented yesterday lives specifically in `search_dates` (range sweep). The hypothesis was correct.

**Implication for the skill stack**:
- `/find-flight` (one-way) does NOT need a statistical wrapper. Single calls are reliable.
- `/find-flight-rt-optimized-statistical`'s variance reduction is precisely targeted — it aggregates `search_dates` outputs (noisy), not `search_flights` drill-ins (stable).
- The architecture we built is correct on this dimension.

### Tool-usage audit (was #24)

Confirmed earlier in this session that the skills are MCP-tool-agnostic. Every flight-data retrieval goes through `search_flights` or `search_dates`. Three justified bypasses: LLM airport resolution (instead of `find_airports`), client-side price/duration filters (MCP has no such params), leg-split heuristic (MCP serializer flattens round-trip legs).

## Carry-over context

- Skills folder: `~/.claude/skills/find-flight-{,-rt,-rt-optimized,-rt-optimized-statistical}/`
- Spec files: `Algorithm.md`, `AlgorithmInputs.md`, `AlgorithmConstraints.md`, `AlgorithmObjective.md`, plus `MOTIVATION.md` in the statistical skill
- Empirical evidence gathered:
  - Round-trip determinism probe (5 agents, 07:08 UTC): 5/5 divergent answers, spreads $164–$347 per duration
  - Round-trip statistical run (7 agents, 07:36 UTC): converged on $327 UA n=8 with 3-of-7 consensus
  - **One-way determinism probe (7 agents, 19:43 UTC, this session)**: 7/7 identical answers, $379 UA Tue May 19
- Underlying library: `punitarani/fli`, MCP server bound globally as `google-flights` in `~/.claude.json`
- Reverse-engineering technique recap: fli hits Google's internal `FlightsFrontendUi` RPC via `curl_cffi` Chrome TLS impersonation; payload is URL-encoded JSON (not protobuf, despite many descriptions)
- Tool-noise map (now empirically grounded):
  - `search_flights` (single-date): deterministic ✓
  - `search_dates` (range sweep): stochastic ✗ — needs N-sample aggregation for reliable use
  - `find_airports`: unused (LLM resolution is better)
