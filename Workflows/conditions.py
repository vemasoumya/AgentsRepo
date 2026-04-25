from agent_framework import (
    AgentExecutor,
    AgentExecutorRequest,
    AgentExecutorResponse,
    Message,
    WorkflowBuilder,
    WorkflowContext,    
    Case,
    Default,
)
from typing import Any, Literal
from model_data import FlightResult


def check_for_flight_booked(expected_result: bool):
    """Create a condition callable that routes based on FlightResult.is_flight_booked."""

    # The returned function will be used as an edge predicate.
    # It receives whatever the upstream executor produced.
    def condition(message: Any) -> bool:
        # Defensive guard. If a non AgentExecutorResponse appears, let the edge pass to avoid dead ends.
        if not isinstance(message, AgentExecutorResponse):
            return True
        try:            
            flight_booking = FlightResult.model_validate_json(message.agent_response.text)            
            return flight_booking.is_flight_booked == expected_result
        except Exception:            
            return False

    return condition