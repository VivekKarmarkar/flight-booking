#!/usr/bin/env python3
"""Skill-replica round-trip optimizer for JFK -> ORD.

Mirrors the /find-flight-rt-optimized algorithm (outer-tier duration sweep,
$50 band for n_best, inner-tier $20 band picked by shortest total flying time)
but uses direct fli library calls in the round_trip_search_function.py style
(SearchFlights().search() on specific outbound/return pairs) — NOT the MCP.

Pinned example: JFK -> ORD, outbound 2026-06-01..2026-06-07, stay 7..14.
"""
import sys
import time
from datetime import date, timedelta
from urllib.parse import quote_plus

from fli.models import (
    Airport,
    FlightSearchFilters,
    FlightSegment,
    PassengerInfo,
    TripType,
)
from fli.search import SearchFlights


def search_pair_data(origin, destination, outbound_date, return_date):
    """Identical FlightSegment + FlightSearchFilters + SearchFlights pattern to
    round_trip_search_function.round_trip_search, but returns the results list
    rather than printing.
    """
    flight_segments = [
        FlightSegment(
            departure_airport=[[origin, 0]],
            arrival_airport=[[destination, 0]],
            travel_date=outbound_date,
        ),
        FlightSegment(
            departure_airport=[[destination, 0]],
            arrival_airport=[[origin, 0]],
            travel_date=return_date,
        ),
    ]
    filters = FlightSearchFilters(
        trip_type=TripType.ROUND_TRIP,
        passenger_info=PassengerInfo(adults=1),
        flight_segments=flight_segments,
    )
    return SearchFlights().search(filters) or []


# ============================ pinned inputs ============================
ORIGIN = Airport.JFK
DESTINATION = Airport.ORD
OUTBOUND_START = date(2026, 6, 1)
OUTBOUND_END = date(2026, 6, 7)
MIN_STAY = 7
MAX_STAY = 14

# skill's hard constraints (applied client-side, since the function we mirror
# does not pass them into FlightSearchFilters)
DEPART_LO, DEPART_HI = 10, 23
MAX_STOPS_PER_DIR = 1
MAX_LEG_MIN = 7 * 60  # 7h elapsed per direction, measured in TRUE flight minutes

PRICE_OUTER_BAND = 50
PRICE_INNER_BAND = 20


def feasible(out, ret):
    """Skill-equivalent constraints. Uses leg.duration (real flight minutes),
    NOT naive datetime subtraction — avoids the transcon clock-vs-elapsed bug.
    """
    if out.stops > MAX_STOPS_PER_DIR or ret.stops > MAX_STOPS_PER_DIR:
        return False
    if out.duration > MAX_LEG_MIN or ret.duration > MAX_LEG_MIN:
        return False
    for first_leg in (out.legs[0], ret.legs[0]):
        h = first_leg.departure_datetime.hour
        if not (DEPART_LO <= h <= DEPART_HI):
            return False
    return True


# ============================ duration sweep ============================
n_days = (OUTBOUND_END - OUTBOUND_START).days + 1
durations = list(range(MIN_STAY, MAX_STAY + 1))
total_pairs = n_days * len(durations)

print(f"Sweeping {ORIGIN.name}->{DESTINATION.name}: outbound "
      f"{OUTBOUND_START}..{OUTBOUND_END}, stay {MIN_STAY}..{MAX_STAY} "
      f"({total_pairs} pair queries)",
      file=sys.stderr, flush=True)

by_d = {d: [] for d in durations}  # d -> list of (out_date, ret_date, feasible_tuples)
pair_i = 0
t0 = time.time()
for d in durations:
    for offset in range(n_days):
        pair_i += 1
        out_date = OUTBOUND_START + timedelta(days=offset)
        ret_date = out_date + timedelta(days=d)
        out_iso = out_date.strftime("%Y-%m-%d")
        ret_iso = ret_date.strftime("%Y-%m-%d")
        try:
            results = search_pair_data(ORIGIN, DESTINATION, out_iso, ret_iso)
        except Exception as exc:
            print(f"[{pair_i:>3}/{total_pairs}] d={d:2d} {out_iso} ERROR: {exc}",
                  file=sys.stderr, flush=True)
            continue
        feas = [(o, r) for o, r in results if feasible(o, r)]
        if feas:
            by_d[d].append((out_date, ret_date, feas))
        cheap = min((o.price for o, r in feas), default=None)
        cheap_str = f"${cheap:.0f}" if cheap is not None else "  -  "
        elapsed = time.time() - t0
        print(f"[{pair_i:>3}/{total_pairs}] d={d:2d} {out_iso}->{ret_iso}  "
              f"raw={len(results):>3} feas={len(feas):>2} cheap={cheap_str}  "
              f"({elapsed:.1f}s)",
              file=sys.stderr, flush=True)

# ============================ outer tier: P_d* per d ============================
per_d = {}
for d, entries in by_d.items():
    if not entries:
        continue
    all_tuples = [(od, rd, o, r) for (od, rd, feas) in entries for (o, r) in feas]
    cheapest_price = min(o.price for (_, _, o, _) in all_tuples)
    # representative (out_date, ret_date) at the cheapest price for that d
    for (od, rd, o, r) in all_tuples:
        if o.price == cheapest_price:
            per_d[d] = (od, rd, cheapest_price)
            break

if not per_d:
    print("\nNo feasible round-trip at any duration.")
    sys.exit(1)

P_star = min(t[2] for t in per_d.values())
band = sorted(d for d, t in per_d.items() if t[2] <= P_star + PRICE_OUTER_BAND)
n_best = band[0]

# ============================ inner tier: pick at n_best ============================
all_at_nb = []
for (od, rd, feas) in by_d[n_best]:
    for (o, r) in feas:
        all_at_nb.append((od, rd, o, r))

P_inner = min(t[2].price for t in all_at_nb)
inner_band = [t for t in all_at_nb if t[2].price <= P_inner + PRICE_INNER_BAND]


def pick_key(t):
    od, rd, o, r = t
    return (
        o.duration + r.duration,
        o.legs[0].departure_datetime,
        "+".join(leg.flight_number for leg in o.legs + r.legs),
    )


inner_band.sort(key=pick_key)
picked_od, picked_rd, picked_out, picked_ret = inner_band[0]

# ============================ present ============================
primary_carrier = picked_out.legs[0].airline.name

print()
print("=" * 60)
print(f"PICKED ROUND-TRIP — ${picked_out.price:.2f} — {n_best}-day stay")
print(f"Outbound: {picked_od}")
for leg in picked_out.legs:
    print(f"  {leg.airline.name} {leg.flight_number}  "
          f"{leg.departure_airport.name}->{leg.arrival_airport.name}  "
          f"{leg.departure_datetime.strftime('%H:%M')}->{leg.arrival_datetime.strftime('%H:%M')}  "
          f"({leg.duration} min, {leg.airline.value})")
print(f"  Outbound total: {picked_out.duration} min, {picked_out.stops} stop(s)")
print(f"Return: {picked_rd}")
for leg in picked_ret.legs:
    print(f"  {leg.airline.name} {leg.flight_number}  "
          f"{leg.departure_airport.name}->{leg.arrival_airport.name}  "
          f"{leg.departure_datetime.strftime('%H:%M')}->{leg.arrival_datetime.strftime('%H:%M')}  "
          f"({leg.duration} min, {leg.airline.value})")
print(f"  Return total: {picked_ret.duration} min, {picked_ret.stops} stop(s)")
print(f"Total flying time: {picked_out.duration + picked_ret.duration} min")
print()

print("Duration sweep (this run):")
for d in sorted(per_d):
    od, rd, p = per_d[d]
    marker = (
        "  <-- n_best" if d == n_best
        else ("  <-- in $50 band" if p <= P_star + PRICE_OUTER_BAND else "")
    )
    print(f"  d={d:2d}: ${p:.2f}  ({od} -> {rd}){marker}")
print(f"P* = ${P_star:.2f}; band = {band}; n_best = {n_best}")
print(f"Inner: P_inner = ${P_inner:.2f}; band held {len(inner_band)} itineraries; "
      "shortest-total-flying-time pick.")

# booking links
out_iso = picked_od.strftime("%Y-%m-%d")
ret_iso = picked_rd.strftime("%Y-%m-%d")
gf_q = (f"Flights from {ORIGIN.name} to {DESTINATION.name} on {out_iso} "
        f"returning {ret_iso} after 10am round trip")
gf_url = f"https://www.google.com/travel/flights?q={quote_plus(gf_q)}"
print(f"\nGoogle Flights: {gf_url}")

if primary_carrier == "AA":
    aa_url = (f"https://www.aa.com/booking/search/find-flights?searchType=matrix"
              f"&origin={ORIGIN.name}&destination={DESTINATION.name}"
              f"&departureMonth={picked_od.month}&departureDay={picked_od.day}"
              f"&returnMonth={picked_rd.month}&returnDay={picked_rd.day}"
              f"&adultPassengerCount=1&tripType=roundtrip")
    print(f"AA round-trip: {aa_url}")
print("=" * 60)
