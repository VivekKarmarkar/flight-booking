# Reflections — Walls Hit and Current Status

Captured at end of session 2026-05-18 (evening). Honest record of what we've learned, what we haven't, and where things actually stand.

## The walls, roughly in the order we hit them

### 1. No first-party consumer flight-search API at non-enterprise cost

Duffel, Sabre, Amadeus, Travelport — all enterprise-gated. Test credentials don't grant live booking. Skyscanner/Kayak/Google Flights don't publish a public API at all. The only "open" path for an individual building automation is unofficial wrappers around scrape-style endpoints.

That's how we ended up on `fli` (Punit Arani's library), which reverse-engineers Google's internal `FlightsFrontendUi` RPC by impersonating Chrome's TLS fingerprint via `curl_cffi`. It works, but every layer of "this isn't an API, this is a wire-protocol hack" adds fragility: Google can change anything quietly and our stack can break.

### 2. The MCP wrapper doesn't cover the library

We have `google-flights` registered as an MCP server, which exposes `search_flights` / `search_dates` / `find_airports`. But the underlying `fli` library exposes more — `MaxStops` granularity, `TimeRestrictions` on each segment, `SearchDates` filters, top_n tuning, currency parsing, encoded-payload introspection. The MCP also serializes round-trip results in a way that flattens leg tuples; the library returns proper `(outbound, return)` pairs.

When skills are written against the MCP and then a richer behavior is needed, we either bypass the MCP (write Python that calls fli directly) or accept that the skill is doing less than the library could.

### 3. `search_dates` is empirically non-deterministic — and not just for niche routes

The original MOTIVATION for `/find-flight-rt-optimized-statistical` was a 5-agent probe on CID↔NYC (multi-hop required) where every agent picked a different "optimal" flight because `search_dates` returned different cheapest-fares-per-duration. We documented that yesterday.

Today's runs on JFK↔ORD (nonstop-dominated dense double-hub route) showed `search_dates` is *also* noisy there: 7 parallel agents, $118 spread at d=7, n_best votes split 5/1/1 between durations 7, 8, 9. The variance isn't a multi-hop-only phenomenon. The endpoint is structurally non-deterministic.

`search_flights` (the per-pair drill-in endpoint), in contrast, was byte-identical across 10 parallel JFK↔LAX runs at the library level, 5/5 byte-identical across function-form ORD↔NYC runs, and 5/5 for the parameterized JFK↔LAX. But CID↔LGA at the library level produced 4 distinct outputs out of 5 — so even `search_flights` determinism is route-shape-dependent (dense nonstops: stable; multi-hop niches: not).

### 4. The skill's algorithm is built around `search_dates`' sparse shape

`/find-flight-rt-optimized`'s outer tier is "one `search_dates` call per duration." That's natural when the data source pre-aggregates "cheapest pair per (duration, date-range)." It's 8 calls total for our typical sweep.

The naive port of that algorithm onto `search_flights` (which gives byte-determinism) requires querying every (outbound, return) cell of the cross-product — 7 outbound × 8 durations = 56 calls — because `search_flights` is per-pair. With the library's default top_n=5 recursion each call costs ~6 HTTP sub-calls, so 56×6 = 336 HTTP calls per run. ~17 minutes per run sequentially.

The right reframing (which I missed in this session despite being walked there explicitly multiple times) is: the same logic on a denser dataset needs a smarter algorithm. Brute-force enumeration over a discrete grid is exactly the situation where global-minimum search techniques (branch-and-bound, Bayesian optimization, sampling with pruning) outperform exhaustive evaluation. The algorithm itself needs to be rebuilt for the dense data shape, not just parallelized over the naive baseline. Open work.

### 5. The inherited `solve_rt_opt.py` has a transcontinental bug

The hard-constraint "≤ 7h per direction" is evaluated by naive datetime subtraction on the raw `departure_datetime`/`arrival_datetime` fields, which have no timezone info. For eastbound LAX→JFK that subtraction shows ~8h15m even though actual flight time is ~5h15m, because the 3-hour TZ offset is included in the clock difference. Every eastbound transcon return fails the cap. The bug is invisible on CID↔NYC (TZ delta ~1h) where the skill was originally tested.

5 of 7 subagents in today's JFK↔LAX statistical run hit this bug and reported "no feasible." The two that returned answers either silently used `leg.duration` (the true flight-minutes field that fli already populates) or simply got lucky.

Per the cardinal "don't modify working code" rule, we built the skill replica's `feasible()` check to use `leg.duration` directly, sidestepping the bug.

### 6. Google's IP-level rate-limiting will fire after a few hundred calls

We've burned through enough of today's quota that even single runs of the fast library-direct script 429 out. The throttle's release window for an aggressive day looks like hours, not minutes. Practical implication: heavy parallel experimentation is brittle. Need to throttle locally or budget calls deliberately.

## Current status (what works, what doesn't)

| Component | Status |
|---|---|
| `/find-flight` (one-way) | Works. 7-agent probe today: 7/7 identical answer. Single calls are reliable. |
| `/find-flight-rt` | Should work for nonstop-dense routes; not re-validated today. |
| `/find-flight-rt-optimized` | Works but its outer-tier is structurally non-deterministic. Single run = sample from a distribution, not "the answer." Transcon bug in inner solver. |
| `/find-flight-rt-optimized-statistical` | Built correctly to absorb `search_dates` variance via N=7 sampling + median aggregation. Confirmed today on JFK↔LAX (4/7 consensus) and JFK↔ORD (5/7 consensus). Inherits the transcon solver bug from the parent skill. |
| Direct library replicas (skill_replica*.py) | Two versions: slow `SearchFlights`-only (deterministic, ~17 min/run) and fast `SearchDates`+`SearchFlights` hybrid (~30-60 sec/run, but uses the non-deterministic endpoint). Neither yet validated for parallel-run determinism because of today's rate-limit lockout. |

## Open questions

- **Can the SearchFlights-only algorithm be rewritten with smart global-minimum search (Bayesian / branch-and-bound / sampling) to match SearchDates speed without losing determinism?** This is the genuine algorithmic question the session surfaced but didn't answer. I missed it for a long time, hung on parallelism as the lazy answer, and the user had to redirect repeatedly.
- **Is the transcon solver bug a hard wall for the existing skill, or can a sibling skill with a corrected `feasible()` (using `leg.duration` instead of naive datetime subtraction) be built without touching the working CID↔NYC version?** The cardinal rule says don't touch working code; this argues for a sibling.
- **What's the true variance profile of `search_flights` across route classes?** Empirical pattern so far: dense nonstop routes byte-identical; multi-hop required routes non-deterministic. Where's the boundary? Single-stop routes through major hubs (CID↔NYC via ORD)? Mid-density transcon (JFK↔SEA)?
- **Is there any first-party / non-Google data source we should be evaluating?** The current stack is entirely Google-Flights-via-Chrome-impersonation. Carrier ITA Matrix, Travelport's UAPI, even Skyscanner B2B — anything that's not scrape-style would lower the architectural risk.

## Meta-reflection on this session

I burned more of the user's patience than I should have, particularly on the algorithm-optimization conversation, by repeatedly mapping abstract framework questions (algorithm A, datasets D1/D2) back onto my already-committed concrete frame instead of letting the abstraction relocate me. That's the local-minimum behavior the user named explicitly. Fresh sessions help; the real fix is being faster to admit "I don't see it yet, keep leading" rather than filling silence with another variant of the same wrong answer. Recording it here so future sessions can see the failure mode in writing.
