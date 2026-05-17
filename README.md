# flight-booking

A formal specification for a flight-finding algorithm that picks **one** flight via constrained optimization, designed to be driven from a Claude Code terminal.

## Overview

The goal of this project is not to build a flight-booking engine — the airline already does that. The goal is to define, precisely, the algorithm an AI assistant should follow when a user says *"find me a flight from X to Y in this date range."* The spec encodes inputs, hard constraints (a feasible region), and a lexicographic objective (cheapest price → tolerance band → shortest flying time). The output is a single flight plus two booking deep links — one to Google Flights, one to the operating airline's own checkout.

The repository is the **spec**. The implementation that consumes it lives in two globally-installed pieces of tooling on the author's machine:

1. A globally-installed [`google-flights`](https://github.com/punitarani/fli) MCP server that exposes `search_flights`, `search_dates`, and `find_airports` to Claude Code.
2. A globally-installed Claude Code skill at `~/.claude/skills/find-flight/` that imports these four spec files verbatim, drives the MCP, runs the optimization, and emits the result.

## The Algorithm at a Glance

| File | Role |
| ---- | ---- |
| [`Algorithm.md`](Algorithm.md) | Top-level entry point; references the other three files and defines the output (two booking links). |
| [`AlgorithmInputs.md`](AlgorithmInputs.md) | Four inputs: departure place, arrival place, date range, optional context. Places resolve to serving airports within ~1 h travel radius. |
| [`AlgorithmConstraints.md`](AlgorithmConstraints.md) | Four hard constraints: depart 10:00–24:00 local, total elapsed ≤ 7 h, price < $400, ≤ 1 layover. |
| [`AlgorithmObjective.md`](AlgorithmObjective.md) | Lexicographic optimization: find the cheapest feasible price `P*`, take the band `[P*, P* + $20]`, then pick the shortest flying time inside that band. |

The split mirrors the classical optimization formulation — inputs define the problem instance, constraints define the feasible region, objective defines the function to minimize. The files can evolve independently: changing one constraint never requires touching the objective, and vice versa.

## Why the Architecture Looks the Way It Does

A long evening of research surfaced an uncomfortable truth: in May 2026, there is no clean autonomous-AI-flight-booking path for a US-based individual. Duffel demands SSN-level KYC; OpenAI walked away from in-ChatGPT flight transactions in March 2026; browser agents stall before payment; Kiwi.com is upsell-heavy with bad refund history.

The pattern that *does* work for individuals is:

- AI does all the search, planning, comparison, and decision work.
- The user clicks one link to the **real airline's own checkout** (AA, Delta, United, Southwest…), where the credit card and the legal transaction live.

That separation is what this spec encodes. The AI part is rich; the booking layer is the airline you'd visit anyway.

## How to Use This (if you've built the same tooling)

```text
/find-flight Iowa City to NYC, first week of June
```

Behind the scenes the skill:
1. Resolves *Iowa City* → CID and *NYC* → {JFK, LGA, EWR} from training-data knowledge of US airports + the 1-hour-radius rule.
2. Calls the `google-flights` MCP `search_flights` tool for each date in the range.
3. Runs `solve.py` (shipped with the skill) which applies the four hard constraints and runs the cheapest → band → shortest-time selection.
4. Emits one flight plus two booking deep links — Google Flights and the operating airline's own pre-filled URL.

## Tech Stack

- **Spec format**: plain Markdown. Designed to be read by both humans and LLMs.
- **MCP backend**: [`punitarani/fli`](https://github.com/punitarani/fli) — reverse-engineered Google Flights internal API. Free, no API key, sees Southwest fares that Duffel/Amadeus miss.
- **Skill runner**: Python 3.9+, stdlib only. The implementation lives in `~/.claude/skills/find-flight/solve.py` (mirror of the spec).

## License

No license file in this repo. The algorithm specification is intentionally open for adaptation — copy, modify, or extend for your own travel preferences.
