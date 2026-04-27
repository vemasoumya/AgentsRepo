from agent_framework.foundry import FoundryChatClient
from agent_framework import Message, AgentExecutor, WorkflowBuilder, FileCheckpointStorage,AgentExecutorRequest, WorkflowEvent
from azure.identity.aio import AzureCliCredential
import os
from collections.abc import AsyncIterable

from dotenv import load_dotenv
from model_data import FlightResult, HumanInputRequest
from agents import create_flight_agent, create_cab_agent

from conditions import check_for_flight_booked
from handler_executors import HumanDropLocationExecutor, handle_final_result_flight, handle_combined_flight_cab_result
import asyncio
from agent_framework.azure import CosmosHistoryProvider


# Load environment variables from parent directory
load_dotenv(dotenv_path="../../.env")
print(os.getenv("FOUNDRY_PROJECT_ENDPOINT"))
def get_workflow(flight_agent_executor, cab_agent_executor):
    human_drop_location_executor = HumanDropLocationExecutor()
    print("Starting workflow execution. You can type messages to interact with the agents. Type 'quit' to exit.")
    workflow = (
        WorkflowBuilder(start_executor=flight_agent_executor)
        # Flight booked path: flight -> store & forward -> cab -> combined result handler
        .add_edge(flight_agent_executor, human_drop_location_executor, condition=check_for_flight_booked(True))
        .add_edge(human_drop_location_executor, cab_agent_executor)
        .add_edge(cab_agent_executor, handle_combined_flight_cab_result)
        # Flight not booked path: flight -> flight result handler
        .add_edge(flight_agent_executor, handle_final_result_flight, condition=check_for_flight_booked(False))        
        .build()
    )
    
    return workflow

async def process_event_stream(stream: AsyncIterable[WorkflowEvent]) -> tuple[dict[str, str] | None, str | None]:
    """Process workflow stream events, handling human-input requests and final outputs."""
    requests: list[tuple[str, HumanInputRequest]] = []
    final_output: str | None = None

    async for event in stream:
        if event.type == "request_info" and isinstance(event.data, HumanInputRequest):
            requests.append((event.request_id, event.data))
        elif event.type == "output" and isinstance(event.data, str):
            final_output = event.data

    # Handle any pending human feedback requests.
    if requests:
        responses: dict[str, str] = {}
        for request_id, request in requests:
            print(f"\n{request.human_prompt}")
            answer = input("Drop Location: ").strip()  # noqa: ASYNC250
            if answer.lower() == "exit":
                print("Exiting...")
                return None, final_output
            responses[request_id] = answer
        return responses, final_output
    return None, final_output

async def main(session_id_flight, session_id_cab) -> None:    
    history_provider = CosmosHistoryProvider(
        endpoint=os.getenv("COSMOS_ENDPOINT"),
        database_name="memorydb",
        container_name="memorycont_hil",
        credential=os.getenv("COSMOS_KEY")
    )

    try:
        async with AzureCliCredential() as credential:
            chat_client = FoundryChatClient(
                project_endpoint=os.getenv("FOUNDRY_PROJECT_ENDPOINT"),
                model="model-router",
                credential=credential,
            )

            agent_flight = create_flight_agent(chat_client, history_provider)
            agent_cab = create_cab_agent(chat_client, history_provider)
            flight_agent_executor = AgentExecutor(agent_flight, session=agent_flight.create_session(session_id=session_id_flight))
            cab_agent_executor = AgentExecutor(agent_cab, session=agent_cab.create_session(session_id=session_id_cab))
            workflow = get_workflow(flight_agent_executor, cab_agent_executor)

            # Multi-turn conversation loop
            while True:
                try:
                    # Get user input
                    user_input = input("\n💬 You: ").strip()

                    # Check for exit commands
                    if user_input.lower() in ['quit', 'exit', 'bye', 'stop', 'end']:
                        print("*****exiting workflow. Goodbye!*****")
                        break

                    if not user_input:
                        print("Please enter a message or type 'quit' to exit.")
                        continue

                    # Execute the workflow. Since the start is an AgentExecutor, pass an AgentExecutorRequest.
                    # The workflow completes when it becomes idle (no more work to do).
                    request = AgentExecutorRequest(messages=[Message(role="user", contents=[user_input])], should_respond=True)
                    stream = await workflow.run(request, stream=True)
                    pending_responses, final_output = await process_event_stream(stream)
                    if final_output is not None:
                        print(f"Workflow output: {final_output}")
                    else:
                        while pending_responses is not None:
                            # Run the workflow until there is no more human feedback to provide,
                            # in which case this workflow completes.
                            stream = await workflow.run(stream=True, responses=pending_responses)
                            pending_responses, final_output = await process_event_stream(stream)
                            if final_output is not None:
                                print(f"Workflow output: {final_output}")
                                break
                    

                except Exception as e:
                    print(f"❌ Failed to initialize agent: {e}")
    finally:
        await history_provider.close()

if __name__ == "__main__":
    asyncio.run(main("session_demo1_flight", "session_demo1_cab"))