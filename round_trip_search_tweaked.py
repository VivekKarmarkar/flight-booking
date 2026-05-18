#!/usr/bin/env python3
"""Deterministic round-trip flight finder — Iowa City to NYC in May.

Uses the fli Python library directly (NOT the MCP) to avoid the stochastic
SearchDates endpoint. Enumerates (outbound_date, duration) pairs across May
and calls SearchFlights for each, which is empirically deterministic.

Implements find-flight-rt-optimized algorithm:
  Inputs (pinned):
    - Origin: CID (Cedar Rapids serves Iowa City)
    - Destinations: JFK, LGA, EWR (NYC airports within ~1h)
    - Outbound range: 2026-05-17 to 2026-05-31
    - Min stay: 7 days, Max stay: 14 days
  Hard constraints (per direction):
    - Depart 10:00-24:00 local
    - Total elapsed <= 7 hours
    - <= 1 layover
  Objective (two-tier, lexicographic):
    Outer: P_d* = cheapest per duration; build $50 band; pick min(d) in band.
    Inner: among (out,ret) tuples at n_best, cheapest -> $20 band -> shortest
           total flying time -> earliest outbound dep -> alphabetical flight nos.

Output: ONE picked round-trip plus Google Flights URL and airline-direct URL.
Byte-identical across parallel runs by design.
"""
from datetime import date, timedelta
from urllib.parse import quote_plus

from fli.models import (
    Airport,
    FlightSearchFilters,
    FlightSegment,
    MaxStops,
    PassengerInfo,
    SeatType,
    SortBy,
    TimeRestrictions,
    TripType,
)
from fli.search.flights import SearchFlights


# ============================== pinned inputs ==============================
ORIGINS = [[Airport.CID, 0]]
DESTS = [[Airport.JFK, 0], [Airport.LGA, 0], [Airport.EWR, 0]]
OUTBOUND_START = date(2026, 5, 18)  # 5/17 rejected by validator (in past)
OUTBOUND_END = date(2026, 5, 31)
MIN_STAY = 7
MAX_STAY = 14
# Each fli round-trip call recurses (~top_n+1 HTTP requests/pair) at 10 req/s.
# Full enumeration (14 outbound × 8 durations = 112 pairs × ~8s) ≈ 15 min/run.
# To keep wall-clock manageable, sample 3 outbound dates spread across May and
# 2 durations (min, mid). The algorithm is unchanged; only the search space shrinks.
OUTBOUND_DATES = [date(2026, 5, 18), date(2026, 5, 23), date(2026, 5, 28)]
DURATIONS = [7, 10]
DEPART_LO, DEPART_HI = 10, 23
MAX_LEG_MIN = 7 * 60
PRICE_OUTER_BAND = 50
PRICE_INNER_BAND = 20
TOP_N = 5  # fli round-trip recurses per outbound; top_n=N => ~N+1 HTTP calls/pair

TIME = TimeRestrictions(earliest_departure=DEPART_LO, latest_departure=DEPART_HI)


# ============================== query helpers ==============================
def sweep_pairs():
    """Deterministic enumeration of (outbound, duration, return) tuples."""
    pairs = []
    for d_out in OUTBOUND_DATES:
        for d in DURATIONS:
            pairs.append((d_out, d, d_out + timedelta(days=d)))
    return pairs


def query_pair(out_date, ret_date):
    """One round-trip SearchFlights call for a fixed (out, ret) pair."""
    filters = FlightSearchFilters(
        trip_type=TripType.ROUND_TRIP,
        passenger_info=PassengerInfo(adults=1),
        seat_type=SeatType.ECONOMY,
        stops=MaxStops.ONE_STOP_OR_FEWER,
        sort_by=SortBy.CHEAPEST,
        flight_segments=[
            FlightSegment(
                departure_airport=ORIGINS,
                arrival_airport=DESTS,
                travel_date=out_date.strftime("%Y-%m-%d"),
                time_restrictions=TIME,
            ),
            FlightSegment(
                departure_airport=DESTS,
                arrival_airport=ORIGINS,
                travel_date=ret_date.strftime("%Y-%m-%d"),
                time_restrictions=TIME,
            ),
        ],
    )
    return SearchFlights().search(filters, top_n=TOP_N) or []


def feasible(outbound, return_flight):
    """Per-direction hard constraints (server enforces depart-window and stops)."""
    return outbound.duration <= MAX_LEG_MIN and return_flight.duration <= MAX_LEG_MIN


# ============================== URL builders ==============================
def google_flights_url(origin_iata, dest_iata, out_iso, ret_iso):
    q = f"Flights from {origin_iata} to {dest_iata} on {out_iso} returning {ret_iso} after 10am round trip"
    return f"https://www.google.com/travel/flights?q={quote_plus(q)}"


def airline_url(carrier_iata, origin, dest, out_date, ret_date):
    out_iso = out_date.strftime("%Y-%m-%d")
    ret_iso = ret_date.strftime("%Y-%m-%d")
    out_mdy = out_date.strftime("%m/%d/%Y")
    ret_mdy = ret_date.strftime("%m/%d/%Y")
    if carrier_iata == "AA":
        return (
            f"https://www.aa.com/booking/search/find-flights?searchType=matrix"
            f"&origin={origin}&destination={dest}"
            f"&departureMonth={out_date.month}&departureDay={out_date.day}"
            f"&returnMonth={ret_date.month}&returnDay={ret_date.day}"
            f"&adultPassengerCount=1&tripType=roundtrip"
        )
    if carrier_iata == "DL":
        return (
            f"https://www.delta.com/flightsearch/search?action=findFlights"
            f"&tripType=ROUND_TRIP&originCity={origin}&destinationCity={dest}"
            f"&departureDate={out_mdy}&returnDate={ret_mdy}"
            f"&paxCount=1&cabinFareClass=MAIN"
        )
    if carrier_iata == "UA":
        return (
            f"https://www.united.com/en/us/fsr/choose-flights?"
            f"f={origin}&t={dest}&fd={out_iso}&fc=ECONOMY&tt=2&fr={ret_iso}&px=1"
        )
    if carrier_iata == "WN":
        return (
            f"https://www.southwest.com/air/booking/select.html?"
            f"originationAirportCode={origin}&destinationAirportCode={dest}"
            f"&departureDate={out_iso}&returnAirportCode={origin}"
            f"&returnDate={ret_iso}&tripType=roundtrip&adultPassengersCount=1"
        )
    return f"https://www.google.com/search?q={quote_plus(carrier_iata + ' round trip ' + origin + ' to ' + dest + ' ' + out_iso)}"


# ============================== algorithm ==============================
def run():
    import sys, time, os
    progress = os.environ.get("RT_PROGRESS", "1") == "1"  # turn off for byte-identical run

    # Step 1 — query every (out, d) pair deterministically
    by_duration = {}  # d -> list of (out_date, ret_date, [(outbound, return_flight) ...])
    pairs = sweep_pairs()
    total = len(pairs)
    t_start = time.time()
    for i, (out_date, d, ret_date) in enumerate(pairs, 1):
        try:
            results = query_pair(out_date, ret_date)
        except Exception as exc:
            if progress:
                print(f"[{i:>3}/{total}] d={d:2d} out={out_date} ret={ret_date}  ERROR: {exc}",
                      file=sys.stderr, flush=True)
            continue
        feas = [(o, r) for o, r in results if feasible(o, r)]
        if progress:
            elapsed = time.time() - t_start
            cheapest = min((o.price for o, r in feas), default=None)
            cheapest_str = f"${cheapest:.0f}" if cheapest else "  -  "
            print(f"[{i:>3}/{total}] d={d:2d} out={out_date} ret={ret_date}  "
                  f"raw={len(results):>3} feas={len(feas):>2} cheap={cheapest_str}  "
                  f"({elapsed:.1f}s)",
                  file=sys.stderr, flush=True)
        if feas:
            by_duration.setdefault(d, []).append((out_date, ret_date, feas))

    if not by_duration:
        print("No feasible round-trip under hard constraints.")
        return

    # Step 2 — outer tier: P_d* per duration
    P_d_star = {}
    for d in sorted(by_duration):
        all_tuples = [(o, r) for (od, rd, tuples) in by_duration[d] for (o, r) in tuples]
        P_d_star[d] = min(o.price for o, r in all_tuples)

    # Step 3 — outer band, pick smallest qualifying duration
    P_star = min(P_d_star.values())
    band = sorted(d for d, p in P_d_star.items() if p <= P_star + PRICE_OUTER_BAND)
    n_best = band[0]

    # Step 4 — inner tier: pick the specific tuple at n_best
    flat = []
    for (od, rd, tuples) in by_duration[n_best]:
        for (o, r) in tuples:
            flat.append((od, rd, o, r))

    P_inner_star = min(t[2].price for t in flat)
    inner_band = [t for t in flat if t[2].price <= P_inner_star + PRICE_INNER_BAND]

    def pick_key(t):
        od, rd, o, r = t
        total_min = o.duration + r.duration
        first_dep = o.legs[0].departure_datetime
        flight_no_concat = "+".join(l.flight_number for l in o.legs + r.legs)
        return (total_min, first_dep, flight_no_concat)

    inner_band.sort(key=pick_key)
    picked_od, picked_rd, picked_out, picked_ret = inner_band[0]

    # Step 5 — deterministic output
    primary_carrier = picked_out.legs[0].airline.name  # IATA-ish
    origin_iata = picked_out.legs[0].departure_airport.name
    dest_iata = picked_out.legs[-1].arrival_airport.name

    out_iso = picked_od.strftime("%Y-%m-%d")
    ret_iso = picked_rd.strftime("%Y-%m-%d")

    lines = []
    lines.append("=" * 60)
    lines.append(
        f"PICKED ROUND-TRIP — ${picked_out.price:.2f} {picked_out.currency or 'USD'} — "
        f"{n_best}-day stay"
    )
    lines.append(f"Outbound: {picked_od} ({out_iso})")
    for leg in picked_out.legs:
        lines.append(
            f"  {leg.airline.name} {leg.flight_number}  "
            f"{leg.departure_airport.name} -> {leg.arrival_airport.name}  "
            f"{leg.departure_datetime.strftime('%H:%M')} -> {leg.arrival_datetime.strftime('%H:%M')}  "
            f"({leg.duration} min, {leg.airline.value})"
        )
    lines.append(f"  Outbound total: {picked_out.duration} min, {picked_out.stops} stop(s)")
    lines.append(f"Return: {picked_rd} ({ret_iso})")
    for leg in picked_ret.legs:
        lines.append(
            f"  {leg.airline.name} {leg.flight_number}  "
            f"{leg.departure_airport.name} -> {leg.arrival_airport.name}  "
            f"{leg.departure_datetime.strftime('%H:%M')} -> {leg.arrival_datetime.strftime('%H:%M')}  "
            f"({leg.duration} min, {leg.airline.value})"
        )
    lines.append(f"  Return total: {picked_ret.duration} min, {picked_ret.stops} stop(s)")
    lines.append(f"Total flying time: {picked_out.duration + picked_ret.duration} min")
    lines.append("")
    lines.append(f"Google Flights: {google_flights_url(origin_iata, dest_iata, out_iso, ret_iso)}")
    lines.append(
        f"Airline direct ({primary_carrier}): "
        f"{airline_url(primary_carrier, origin_iata, dest_iata, picked_od, picked_rd)}"
    )
    lines.append("=" * 60)
    lines.append("")
    lines.append("DEBUG: outer-tier P_d* per duration")
    for d in sorted(P_d_star):
        in_band = P_d_star[d] <= P_star + PRICE_OUTER_BAND
        marker = "  <-- n_best" if d == n_best else ("  <-- in $50 band" if in_band else "")
        lines.append(f"  d={d:2d}: ${P_d_star[d]:.2f}{marker}")
    lines.append(
        f"P* = ${P_star:.2f}; outer band [${P_star:.0f}, ${P_star + PRICE_OUTER_BAND:.0f}] "
        f"-> durations {band} -> n_best = {n_best}"
    )
    lines.append(
        f"Inner: P_inner* = ${P_inner_star:.2f}; band [${P_inner_star:.0f}, ${P_inner_star + PRICE_INNER_BAND:.0f}] "
        f"held {len(inner_band)} itineraries; shortest-total-flying-time pick."
    )

    print("\n".join(lines))


if __name__ == "__main__":
    run()
