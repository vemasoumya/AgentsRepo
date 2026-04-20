# Copyright (c) Microsoft. All rights reserved.

import asyncio
import sys

import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Message,
    Part,
    Role,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)
from a2a.utils import get_message_text
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential
from fastapi import FastAPI
from tool_cab import book_cab, cancel_cab


class CabAgent:
    """Cab booking agent usable locally and as an A2A server."""

    def __init__(self, client: FoundryChatClient):
        self.agent = client.as_agent(
            name="CabBookingAgent",
            instructions="""
            You are a helpful cab booking agent. Use the provided tools to book and cancel cabs.
            Always be friendly and provide clear, helpful information.
            When booking cabs, make sure to get all necessary details like pickup location, dropoff location, pickup date, and pickup time.
            
            IMPORTANT: The book_cab tool requires user approval before executing. When you attempt to book a cab:
            1. Present all the booking details clearly to the user
            2. The system will ask for their approval before proceeding
            3. Only after approval will the booking be executed
            
            Cab cancellations do not require approval and will execute immediately.
            """,
            tools=[book_cab, cancel_cab],
        )

    def as_tool(self, **kwargs):
        return self.agent.as_tool(**kwargs)

    def create_session(self):
        return self.agent.create_session()

    async def run(self, message, **kwargs):
        return await self.agent.run(message, **kwargs)
    
    async def run_stream(self, message, **kwargs):
        """Stream the agent response in chunks."""
        # Check if the underlying agent supports streaming
        if hasattr(self.agent, 'run_stream'):
            # Use native streaming if available
            async for chunk in self.agent.run_stream(message, **kwargs):
                yield chunk
        else:
            # Fallback: simulate streaming by chunking the complete response
            # if the uderlying agent does not support streaming, we will get the complete response 
            # at once and then split it into chunks to simulate streaming
            print("Server: Agent doesn't support streaming, simulating with chunks")
            response = await self.agent.run(message, **kwargs)
            response_text = str(response)
            print(f"Server: Got complete response, length: {len(response_text)}")
            print(f"Server: Response preview: {response_text[:100]}...")
            
            # Split response into chunks (simulate streaming)
            chunk_size = 50  # Adjust chunk size as needed
            total_chunks = (len(response_text) + chunk_size - 1) // chunk_size
            print(f"Server: Will send {total_chunks} chunks")
            
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i + chunk_size]
                chunk_num = i // chunk_size + 1
                print(f"Server: Yielding chunk {chunk_num}/{total_chunks}: '{chunk[:20]}...'")
                yield chunk
                # Add small delay to simulate real streaming
                import asyncio
                await asyncio.sleep(0.1)


class CabAgentExecutor(AgentExecutor):
    """Bridges CabAgent into the A2A server protocol."""

    def __init__(self, cab_agent: CabAgent):
        self.cab_agent = cab_agent        
        self._sessions: dict[str, object] = {}

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = get_message_text(context.message)
        context_id = context.context_id

        # Reuse or create a session per context_id
        if context_id not in self._sessions:
            self._sessions[context_id] = self.cab_agent.create_session()
        session = self._sessions[context_id]
        # Correct way to detect streaming: check if blocking=False in configuration
        # blocking = True mean non streaming
        is_streaming_client = not getattr(context._params.configuration, 'blocking', True)
        print(f"Server: blocking = {getattr(context._params.configuration, 'blocking', True)}")
        print(f"Server: is_streaming_client = {is_streaming_client}")
        
        # stream: The client opens an HTTPS connection to the A2A server and keeps it open to receive a 
        # stream of events. The DefaultRequestHandler will enqueue events to the event queue as the agent processes the request, 
        # and these events will be sent to the client in real time over the open connection.
        # send: The client sends a POST request to the A2A server and waits for a single response. 
        # In this case, the DefaultRequestHandler will wait until the agent has finished processing the request 
        # and then send a single response back to the client with the final result.

        #The event queue is used to send updates back to the A2A server about the status of the task execution.
        #This is a in memory queue that the executor uses to communicate with the A2A server. 
        # The executor enqueues events to this queue to inform the server about the progress and results of the task execution.
        # When the A2A server receives a request for this agent, it will call this execute method.  

        # The task is created even before we start processing the request by the DefaultRequestHandler, 
        #This sits between the A2A server and the agent execution and is responsible for handling incoming requests,
        #  managing task state, and sending events back to the server.
        

        #This tells the caller that the agent has started processing the request and is working on it. 
        # The final=False indicates that this is an intermediate update and not the final result.
        # This event says that I started this task now and changes the the state from "not_started" to "working". 
        
        print("Server: Sending working event")
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                taskId=context.task_id,
                contextId=context_id,
                status=TaskStatus(state=TaskState.working),
                final=False,
            )
        )

        try:
            if is_streaming_client:
                print("Server: Taking streaming path")
                # Stream response chunks
                chunk_count = 0
                async for chunk in self.cab_agent.run_stream(user_text, session=session):
                    if chunk:  # Only send non-empty chunks
                        chunk_count += 1
                        print(f"Server: Received chunk {chunk_count}, sending to client: '{chunk[:30]}...'")
                        await event_queue.enqueue_event(
                            Message(
                                role=Role.agent,
                                parts=[Part(root=TextPart(text=chunk))],
                                messageId=context.task_id,
                            )
                        )
                        print(f"Server: Chunk {chunk_count} sent successfully")
                print(f"Server: Streaming complete, sent {chunk_count} chunks total")
            else:
                print("Server: Taking non-streaming path")
                # Send complete response at once after processing
                response = await self.cab_agent.run(user_text, session=session)
                response_text = str(response)
                print("Server: Sending message event")
                await event_queue.enqueue_event(
                    Message(
                        role=Role.agent,
                        parts=[Part(root=TextPart(text=response_text))],
                        messageId=context.task_id,
                    )
                )
            # For streaming, don't send completion event - stream end is implicit
            if not is_streaming_client:
                #This signals the task is finished and closes the event stream.
                print("Server: Sending completed event")
                await event_queue.enqueue_event(
                    TaskStatusUpdateEvent(
                        taskId=context.task_id,
                        contextId=context_id,
                        status=TaskStatus(state=TaskState.completed),
                        final=True,
                    )
                )
        except Exception as e:
            print(f"Server: Exception occurred: {e}")
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    taskId=context.task_id,
                    contextId=context_id,
                    status=TaskStatus(
                        state=TaskState.failed,
                        message=Message(
                            role=Role.agent,
                            parts=[Part(root=TextPart(text=str(e)))],
                            messageId=context.task_id,
                        ),
                    ),
                    final=True,
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                taskId=context.task_id,
                contextId=context.context_id,
                status=TaskStatus(state=TaskState.canceled),
                final=True,
            )
        )


def build_a2a_app(cab_agent: CabAgent, host: str = "0.0.0.0", port: int = 9100) -> FastAPI:
    """Build a FastAPI app that serves this agent over A2A."""
    agent_card = AgentCard(
        name="CabBookingAgent",
        description="Agent that books and cancels cabs in a city.",
        url=f"http://localhost:{port}/",
        version="1.0.0",
        capabilities=AgentCapabilities(),
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
        skills=[
            AgentSkill(
                id="book_cab",
                name="Book Cab",
                description="Book a cab from one location to another.",
                tags=["cab", "booking", "transportation"],
            ),
            AgentSkill(
                id="cancel_cab",
                name="Cancel Cab",
                description="Cancel a previously booked cab.",
                tags=["cab", "cancel", "transportation"],
            ),
        ],
    )

    executor = CabAgentExecutor(cab_agent)
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )

    a2a_app = A2AFastAPIApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    app = FastAPI(title="Cab Booking A2A Agent")
    a2a_app.add_routes_to_app(app)
    return app


async def run_local() -> None:
    """Run the agent locally in an interactive console loop."""
    client = FoundryChatClient(
        project_endpoint="https://vema-ai-foundry2.services.ai.azure.com/api/projects/secondproject",
        model="model-router",
        credential=AzureCliCredential(),
    )

    cab = CabAgent(client)
    session = cab.create_session()
    while True:
        user_message = input("User: ")
        if user_message.lower() in ["exit", "quit"]:
            print("Exiting chat.")
            break

        response = await cab.run(user_message, session=session)
        print(f"Agent: {response}\n")


def run_a2a_server(host: str = "0.0.0.0", port: int = 9100) -> None:
    """Run the agent as an A2A server."""
    client = FoundryChatClient(
        project_endpoint="https://vema-ai-foundry2.services.ai.azure.com/api/projects/secondproject",
        model="model-router",
        credential=AzureCliCredential(),
    )

    cab = CabAgent(client)
    app = build_a2a_app(cab, host=host, port=port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    if "--a2a" in sys.argv:
        run_a2a_server()
    else:
        asyncio.run(run_local())