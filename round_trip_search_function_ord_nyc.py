#!/usr/bin/env python3
"""Round trip flight search — ORD to NYC (JFK/LGA/EWR) demo.

Sibling of round_trip_search_function_jfklax.py. Tests whether a
multi-destination round-trip query (ORD as origin, JFK+LGA+EWR as joint
destination set) is byte-deterministic across parallel runs.

Same outbound/return dates as the JFK/LAX sibling:
  outbound = 2026-06-17 (today+30 on 2026-05-18)
  return   = 2026-06-24 (today+37 on 2026-05-18)
"""

from fli.models import (
    Airport,
    FlightSearchFilters,
    FlightSegment,
    PassengerInfo,
    TripType,
)
from fli.search import SearchFlights


def round_trip_search_multi(origins, destinations, outbound_date, return_date, adults=1):
    """Run a round-trip search with multi-airport origin and/or destination sets.

    Args:
        origins: list of [Airport, int] pairs (e.g., [[Airport.ORD, 0]])
        destinations: list of [Airport, int] pairs (e.g., [[Airport.JFK, 0], [Airport.LGA, 0]])
        outbound_date: "YYYY-MM-DD" string
        return_date: "YYYY-MM-DD" string
        adults: number of adult passengers (default 1)
    """
    flight_segments = [
        FlightSegment(
            departure_airport=origins,
            arrival_airport=destinations,
            travel_date=outbound_date,
        ),
        FlightSegment(
            departure_airport=destinations,
            arrival_airport=origins,
            travel_date=return_date,
        ),
    ]

    filters = FlightSearchFilters(
        trip_type=TripType.ROUND_TRIP,
        passenger_info=PassengerInfo(adults=adults),
        flight_segments=flight_segments,
    )

    search = SearchFlights()
    results = search.search(filters)

    for outbound, return_flight in results:
        print("\nOutbound Flight:")
        for leg in outbound.legs:
            print(f"Flight: {leg.airline.value} {leg.flight_number}")
            print(f"Departure: {leg.departure_datetime}")
            print(f"Arrival: {leg.arrival_datetime}")

        print("\nReturn Flight:")
        for leg in return_flight.legs:
            print(f"Flight: {leg.airline.value} {leg.flight_number}")
            print(f"Departure: {leg.departure_datetime}")
            print(f"Arrival: {leg.arrival_datetime}")

        print(f"\nTotal Price: ${outbound.price}")


if __name__ == "__main__":
    # Demo: ORD -> JFK/LGA/EWR, same dates as the JFK/LAX sibling.
    outbound_date = "2026-06-17"
    return_date = "2026-06-24"

    round_trip_search_multi(
        origins=[[Airport.ORD, 0]],
        destinations=[[Airport.JFK, 0], [Airport.LGA, 0], [Airport.EWR, 0]],
        outbound_date=outbound_date,
        return_date=return_date,
    )
