from pydantic import BaseModel
from dataclasses import dataclass


class FlightResult(BaseModel):
    """Represents the result of a flight booking operation."""
    # is_flight_booked drives the routing decision taken by edge conditions
    is_flight_booked: bool
    # is_flight_cancelled drives the routing decision taken by edge conditions
    is_flight_cancelled: bool
    # Human readable rationale from the agent
    flight_agent_response: str    

class CabResult(BaseModel):
    """Represents the result of a cab booking operation."""    
    cab_agent_response: str  

@dataclass
class HumanInputRequest:
    """Request sent to the human for feedback on the agent's guess."""

    human_prompt: str

