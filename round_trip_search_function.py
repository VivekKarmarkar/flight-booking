#!/usr/bin/env python3
"""Round trip flight search — function form.

Same as round_trip_search.py but the hardcoded origin/destination/dates are
turned into function parameters. Demo at the bottom runs a CID -> LGA round
trip departing 1 June and returning 15 June.
"""

from fli.models import (
    Airport,
    FlightSearchFilters,
    FlightSegment,
    PassengerInfo,
    TripType,
)
from fli.search import SearchFlights


def round_trip_search(origin, destination, outbound_date, return_date, adults=1):
    """Run a round-trip search and print every (outbound, return) tuple found.

    Args:
        origin: an Airport enum member (e.g. Airport.CID)
        destination: an Airport enum member (e.g. Airport.LGA)
        outbound_date: outbound travel date as a "YYYY-MM-DD" string
        return_date: return travel date as a "YYYY-MM-DD" string
        adults: number of adult passengers (default 1)
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
    # Demo: CID (Cedar Rapids — serves Iowa City) to LGA (NYC), 1 Jun -> 15 Jun
    round_trip_search(
        origin=Airport.CID,
        destination=Airport.LGA,
        outbound_date="2026-06-01",
        return_date="2026-06-15",
    )
