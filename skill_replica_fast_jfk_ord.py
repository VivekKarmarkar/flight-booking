#!/usr/bin/env python3
"""Fast skill-replica round-trip optimizer for JFK -> ORD.

Mirrors /find-flight-rt-optimized using fli library DIRECTLY:
- Outer tier: SearchDates per duration (cheapest (outbound, return) pair in date range)
- $50 outer band -> n_best
- Inner tier: SearchFlights at n_best, $20 band, shortest total flying time

~9 calls per run (8 SearchDates + 1 SearchFlights), matching the MCP skill's call count.
"""
import sys
from datetime import date, timedelta
from urllib.parse import quote_plus

from fli.models import (
    Airport,
    DateSearchFilters,
    FlightSearchFilters,
    FlightSegment,
    MaxStops,
    PassengerInfo,
    SeatType,
    TimeRestrictions,
    TripType,
)
from fli.search import SearchDates, SearchFlights


# pinned inputs
ORIGIN = Airport.JFK
DESTINATION = Airport.ORD
OUTBOUND_START = date(2026, 6, 1)
OUTBOUND_END = date(2026, 6, 7)
MIN_STAY = 7
MAX_STAY = 14
DEPART_LO, DEPART_HI = 10, 23
MAX_STOPS = MaxStops.ONE_STOP_OR_FEWER
MAX_LEG_MIN = 7 * 60
PRICE_OUTER_BAND = 50
PRICE_INNER_BAND = 20

TIME_RESTR = TimeRestrictions(earliest_departure=DEPART_LO, latest_departure=DEPART_HI)


def _segments(out_iso, ret_iso):
    return [
        FlightSegment(
            departure_airport=[[ORIGIN, 0]],
            arrival_airport=[[DESTINATION, 0]],
            travel_date=out_iso,
            time_restrictions=TIME_RESTR,
        ),
        FlightSegment(
            departure_airport=[[DESTINATION, 0]],
            arrival_airport=[[ORIGIN, 0]],
            travel_date=ret_iso,
            time_restrictions=TIME_RESTR,
        ),
    ]


def outer_sweep_for_duration(d):
    out_iso = OUTBOUND_START.strftime("%Y-%m-%d")
    ret_iso = (OUTBOUND_START + timedelta(days=d)).strftime("%Y-%m-%d")
    filters = DateSearchFilters(
        trip_type=TripType.ROUND_TRIP,
        passenger_info=PassengerInfo(adults=1),
        flight_segments=_segments(out_iso, ret_iso),
        from_date=OUTBOUND_START.strftime("%Y-%m-%d"),
        to_date=OUTBOUND_END.strftime("%Y-%m-%d"),
        duration=d,
        stops=MAX_STOPS,
        seat_type=SeatType.ECONOMY,
    )
    return SearchDates().search(filters) or []


def inner_search_pair(outbound_d, return_d):
    out_iso = outbound_d.strftime("%Y-%m-%d")
    ret_iso = return_d.strftime("%Y-%m-%d")
    filters = FlightSearchFilters(
        trip_type=TripType.ROUND_TRIP,
        passenger_info=PassengerInfo(adults=1),
        flight_segments=_segments(out_iso, ret_iso),
        stops=MAX_STOPS,
        seat_type=SeatType.ECONOMY,
    )
    return SearchFlights().search(filters) or []


def feasible(out, ret):
    """≤7h elapsed per direction (true flight minutes)."""
    return out.duration <= MAX_LEG_MIN and ret.duration <= MAX_LEG_MIN


# ============================ outer tier ============================
per_d = {}
for d in range(MIN_STAY, MAX_STAY + 1):
    results = outer_sweep_for_duration(d)
    if not results:
        continue
    cheapest = min(results, key=lambda dp: dp.price)
    out_dt, ret_dt = cheapest.date
    per_d[d] = (out_dt.date(), ret_dt.date(), cheapest.price)

if not per_d:
    print("No results.")
    sys.exit(1)

P_star = min(t[2] for t in per_d.values())
band = sorted(d for d, t in per_d.items() if t[2] <= P_star + PRICE_OUTER_BAND)
n_best = band[0]
out_nb, ret_nb, _ = per_d[n_best]

# ============================ inner tier ============================
inner_results = inner_search_pair(out_nb, ret_nb)
feas = [(o, r) for o, r in inner_results if feasible(o, r)]
if not feas:
    print(f"No feasible itinerary at n_best={n_best} ({out_nb} -> {ret_nb}).")
    sys.exit(1)

P_inner = min(o.price for o, r in feas)
inner_band = [(o, r) for o, r in feas if o.price <= P_inner + PRICE_INNER_BAND]


def pick_key(t):
    o, r = t
    return (
        o.duration + r.duration,
        o.legs[0].departure_datetime,
        "+".join(leg.flight_number for leg in o.legs + r.legs),
    )


inner_band.sort(key=pick_key)
picked_out, picked_ret = inner_band[0]

# ============================ present ============================
print("=" * 60)
print(f"PICKED ROUND-TRIP — ${picked_out.price:.2f} — {n_best}-day stay")
print(f"Outbound: {out_nb}")
for leg in picked_out.legs:
    print(f"  {leg.airline.name} {leg.flight_number}  "
          f"{leg.departure_airport.name}->{leg.arrival_airport.name}  "
          f"{leg.departure_datetime.strftime('%H:%M')}->{leg.arrival_datetime.strftime('%H:%M')}  "
          f"({leg.duration} min, {leg.airline.value})")
print(f"  Outbound total: {picked_out.duration} min, {picked_out.stops} stop(s)")
print(f"Return: {ret_nb}")
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
print(f"Inner: P_inner = ${P_inner:.2f}; band held {len(inner_band)} itineraries.")

out_iso = out_nb.strftime("%Y-%m-%d")
ret_iso = ret_nb.strftime("%Y-%m-%d")
gf_q = (f"Flights from {ORIGIN.name} to {DESTINATION.name} on {out_iso} "
        f"returning {ret_iso} after 10am round trip")
print(f"\nGoogle Flights: https://www.google.com/travel/flights?q={quote_plus(gf_q)}")
print("=" * 60)
