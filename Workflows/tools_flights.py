# Below are Agent Framework compatible tools for the Flight Booking Agent. These tools can be used to search for flights, book flights,
#  get flight booking details, and cancel flight bookings.

def search_flights(origin: str, destination: str, departure_date: str, return_date: str = None) -> str:
    """
    Searches for available flights between the specified origin and destination.
    
    Args:
        origin (str): The departure city or airport code
        destination (str): The arrival city or airport code
        departure_date (str): Departure date (format: YYYY-MM-DD)
        return_date (str, optional): Return date for round-trip flights (format: YYYY-MM-DD)
    
    Returns:
        str: A formatted string containing available flight options
    """
    # Mock data - in a real implementation, this would connect to a flight booking API
    flights = [
        {
            "flight_id": "F123",
            "airline": "Airways A",
            "price": 300,
            "departure_time": f"{departure_date}T08:00:00",
            "arrival_time": f"{departure_date}T12:00:00",
            "origin": origin,
            "destination": destination
        },
        {
            "flight_id": "F456",
            "airline": "Airways B",
            "price": 250,
            "departure_time": f"{departure_date}T10:00:00",
            "arrival_time": f"{departure_date}T14:00:00",
            "origin": origin,
            "destination": destination
        },
        {
            "flight_id": "F789",
            "airline": "Airways C",
            "price": 350,
            "departure_time": f"{departure_date}T12:00:00",
            "arrival_time": f"{departure_date}T16:00:00",
            "origin": origin,
            "destination": destination
        }
    ]
    
    result = f"Found {len(flights)} flights from {origin} to {destination} on {departure_date}"
    if return_date:
        result += f" with return on {return_date}"
    result += ":\n\n"
    
    for flight in flights:
        result += f"• {flight['airline']} (ID: {flight['flight_id']})\n"
        result += f"  - Price: ${flight['price']}\n"
        result += f"  - Departure Time: {flight['departure_time']}\n"
        result += f"  - Arrival Time: {flight['arrival_time']}\n\n"
    
    return result


def book_flight(flight_id: str, origin: str, destination: str, departure_date: str, return_date: str = None,
                 passenger_name: str = "Passenger") -> str:
    """
    Books a flight.
    
    Args:
        flight_id (str): The unique identifier of the flight to book
        origin (str): The departure city or airport code
        destination (str): The arrival city or airport code
        departure_date (str): Departure date (format: YYYY-MM-DD)
        return_date (str, optional): Return date for round-trip flights (format: YYYY-MM-DD)
        passenger_name (str): Name of the passenger making the booking
    
    Returns:
        str: A confirmation message with booking details
    """
    # Mock booking confirmation - in a real implementation, this would connect to a flight booking API
    booking_reference = f"BR{flight_id[-3:]}{passenger_name[:2].upper()}"
    
    result = f"Flight {flight_id} from {origin} to {destination} on {departure_date} has been booked for {passenger_name}."
    if return_date:
        result += f" Return flight on {return_date} is also included."
    result += f" Your booking reference is {booking_reference}."
    
    return result


def get_flight_details(booking_reference: str) -> str:
    """
    Retrieves details of a flight booking.
    
    Args:
        booking_reference (str): The unique booking reference number
    
    Returns:
        str: A formatted string containing the flight booking details
    """
    # Mock booking details - in a real implementation, this would connect to a flight booking API
    details = {
        "booking_reference": booking_reference,
        "flight_id": "F123",
        "airline": "Airways A",
        "origin": "City A",
        "destination": "City B",
        "departure_date": "2024-10-01",
        "return_date": "2024-10-10",
        "passenger_name": "Passenger"
    }
    
    result = f"Booking Reference: {details['booking_reference']}\n"
    result += f"Flight ID: {details['flight_id']}\n"
    result += f"Airline: {details['airline']}\n"
    result += f"Origin: {details['origin']}\n"
    result += f"Destination: {details['destination']}\n"
    result += f"Departure Date: {details['departure_date']}\n"
    if details['return_date']:
        result += f"Return Date: {details['return_date']}\n"
    result += f"Passenger Name: {details['passenger_name']}\n"
    
    return result


def cancel_flight_booking(booking_reference: str) -> str:
    """
    Cancels a flight booking.
    
    Args:
        booking_reference (str): The unique booking reference number
    
    Returns:
        str: A confirmation message indicating the booking has been cancelled
    """
    # Mock cancellation - in a real implementation, this would connect to a flight booking API
    result = f"Booking with reference {booking_reference} has been cancelled successfully."
    
    return result
