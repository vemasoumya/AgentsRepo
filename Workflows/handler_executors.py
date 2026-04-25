from agent_framework import AgentExecutorRequest, AgentExecutorResponse, Executor, Message, WorkflowContext, executor, handler, response_handler
from model_data import FlightResult, CabResult, HumanInputRequest
from typing_extensions import Never


class HumanDropLocationExecutor(Executor):
    def __init__(self) -> None:
        super().__init__(id="store_flight_get_drop_location")

    @handler
    async def store_flight_get_drop_location(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        """Store flight result in state and request the cab drop location."""
        flight_result = FlightResult.model_validate_json(response.agent_response.text)
        ctx.set_state("flight_agent_result", flight_result.flight_agent_response)

        prompt = f"{flight_result.flight_agent_response}\n\nTo proceed with cab booking, provide the cab drop-off location:"
        await ctx.request_info(
            request_data=HumanInputRequest(human_prompt=prompt),
            response_type=str,
        )

    @response_handler
    async def on_human_feedback_call_cab_agent(
        self,
        original_request: HumanInputRequest,
        feedback: str,
        ctx: WorkflowContext[AgentExecutorRequest],
    ) -> None:
        drop_location = f"Consider the drop location as {feedback.strip()}"
        flight_result = ctx.get_state("flight_agent_result")

        request = AgentExecutorRequest(
            messages=[Message(role="assistant", contents=[flight_result, drop_location])],
            should_respond=True,
        )
        await ctx.send_message(request)


@executor(id="handle_final_result_flight")
async def handle_final_result_flight(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
   
    flight_result = FlightResult.model_validate_json(response.agent_response.text)
    await ctx.yield_output(f"*********Flight booking result************:\n{flight_result.flight_agent_response}")


@executor(id="handle_combined_flight_cab_result")
async def handle_combined_flight_cab_result(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
    """Handle cab result and include previously stored flight result from state."""
    # Parse cab result
    cab_result = CabResult.model_validate_json(response.agent_response.text)
    
    # Retrieve stored flight result from state
    flight_result = ctx.get_state("flight_agent_result")
    
    # Combine both results in output
    combined_output = f"""*********COMPLETE BOOKING RESULTS************:

FLIGHT BOOKING:
{flight_result}

CAB BOOKING:
{cab_result.cab_agent_response}

*****************************************"""
    
    await ctx.yield_output(combined_output)



