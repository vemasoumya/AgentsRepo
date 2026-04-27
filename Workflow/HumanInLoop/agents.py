from agent_framework import Message, AgentExecutor, Agent
from tools_flights import search_flights, book_flight, get_flight_details, cancel_flight_booking
from tools_cab import book_cab, cancel_cab
from model_data import FlightResult, CabResult
from agent_framework.foundry import FoundryChatClient


def create_flight_agent(client : FoundryChatClient, history_provider): 

    
    flight_agent = client.as_agent(
        name="FlightBookingAgent",
        instructions="""You are a helpful flight booking agent. Use the provided tools to search for flights, book flights,
     get flight details, and cancel flight bookings.
Always be friendly and provide clear, helpful information. 
When booking flights, make sure to get all necessary details like passenger name, dates, origin, and destination.

Interpret is_flight_booked strictly for the current user turn.
- Set is_flight_booked to true only when this turn completes a new confirmed flight booking.
- Set is_flight_booked to false for flight searches, fare checks, status questions, memory questions, follow-up questions about earlier bookings, and cancellations.
- If the user asks a follow-up such as "what was the source and destination for the flight search I asked you to do on May-2", answer the question in flight_agent_response and set is_flight_booked to false.

IMPORTANT: Always respond with a JSON object containing exactly these fields:
- is_flight_booked: boolean (true if a flight was successfully booked in the current turn, false otherwise)   
- is_flight_cancelled: boolean (true if a flight was cancelled in the current turn, false otherwise)  
- flight_agent_response: string (detailed response about the booking status and flight details)

Example response for a flight booking inquiry that results in a successful booking:
    {"is_flight_booked": true, "is_flight_cancelled": false, 
"flight_agent_response": "Successfully booked flight AA123 from NYC to LAX on 2024-05-15 on name "XYZ"}
Example response for a flight booking inquiry about a successful booking:
    {"is_flight_booked": false, "is_flight_cancelled": false, 
"flight_agent_response": "The flight AA123 from NYC to LAX on 2024-05-15 for passenger XYZ is confirmed. 
            Your booking reference is ABCDEF."}
""",
        tools=[book_flight, search_flights, get_flight_details, cancel_flight_booking],
        context_providers=[history_provider],  
        default_options={"response_format": FlightResult}
    )
    return flight_agent

def create_cab_agent(client : FoundryChatClient, history_provider): 
    
    cab_agent = client.as_agent(   
        name="CabBookingAgent",
        instructions="""You are a helpful cab booking agent. Use the provided tools to book and cancel cabs.
Your input will be response from the flight agent containing flight booking details. 
Extract flight booking information and use those details to book a cab for the user.
When booking cabs, make sure to get all necessary details like:
- pickup location will be arrival airport from flight booking
- pickup date will be arrival date from flight booking  
- pickup time will be 2.5 hours from the flight departure time

IMPORTANT: Always respond with a JSON object containing exactly this field:
- cab_agent_response: string (detailed response about the cab booking status and details)

Example response:
{"cab_agent_response": "Successfully booked cab from LAX airport to downtown, pickup at 7:30 PM"}""",
        context_providers=[history_provider],  
        tools=[book_cab, cancel_cab],
        default_options={"response_format": CabResult}
    )
    return cab_agent
           