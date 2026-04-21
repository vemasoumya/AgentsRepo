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
    Artifact,
    Message,
    Part,
    Role,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    TextPart
    
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
        # Use MAF native streaming - pass stream=True to get real chunks
        async for chunk in self.agent.run(message, **kwargs):
            if chunk.text:  # Only yield chunks with actual text content
                yield chunk.text
       


class CabAgentExecutor(AgentExecutor):
    """Bridges CabAgent into the A2A server protocol."""

    def __init__(self, cab_agent: CabAgent):
        self.cab_agent = cab_agent        
        self._sessions: dict[str, object] = {}

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = get_message_text(context.message)
        context_id = context.context_id
        print(f"Server: Received request with context_id={context_id}, user_text='{user_text}'")

        # Reuse or create a session per context_id
        if context_id not in self._sessions:
            self._sessions[context_id] = self.cab_agent.create_session()
        session = self._sessions[context_id]
        
        # Debug: Inspect full configuration
        print(f"Server: Full context._params: {context._params}")
        print(f"Server: Configuration object: {context._params.configuration}")
        print(f"Server: Configuration dict: {vars(context._params.configuration)}")        
       
        is_streaming_client = True
        print(f"Server: is_streaming_client = {is_streaming_client}")        
        
        
        
        print("Server: Sending working event")
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.working),
                final=False,
            )
        )

        try:
            if is_streaming_client:
                print("Server: Taking streaming path")
                # Stream response chunks
                chunk_count = 0
                async for chunk in self.cab_agent.run_stream(user_text, session=session, stream = True):
                    if chunk:  # Only send non-empty chunks
                        chunk_count += 1
                        # Extract text from AgentResponseUpdate object                        
                        chunk_text = str(chunk) if hasattr(chunk, '__str__') else repr(chunk)
                        print(f"Server: Received chunk {chunk_count}, sending to client: '{chunk_text}...'")
                        await event_queue.enqueue_event(
                            TaskArtifactUpdateEvent(
                                task_id=context.task_id,
                                context_id=context.context_id,
                                # Create proper Artifact object with all required fields
                                artifact=Artifact(
                                    artifactId=f"chunk-{chunk_count}",
                                    parts=[Part(root=TextPart(text=chunk_text))],
                                    content=chunk_text, 
                                    content_type="text/plain"
                                ), 
                                last_chunk=False
                            )
                        )                        
                print(f"Server: Streaming complete, sent {chunk_count} chunks total")
            else:
                print("Server: Taking non-streaming path")
                # Send complete response at once after processing
                response = await self.cab_agent.run(user_text, session=session, stream = False)
                response_text = str(response)               
                print("Server: Sending message event 1")
                await event_queue.enqueue_event(
                    Message(
                        role=Role.agent,
                        parts=[Part(root=TextPart(text=response_text))],
                        message_id=context.task_id,
                    )
                ) 
                    
           
            # Only send completion event for non-streaming clients
            # For streaming, completion is implicit when stream ends
            if not is_streaming_client:
                print("Server: Sending completed event")
                await event_queue.enqueue_event(
                    TaskStatusUpdateEvent(
                        task_id=context.task_id,
                        context_id=context_id,
                        status=TaskStatus(state=TaskState.completed),
                        final=True,
                    )
                )
            else:
                await event_queue.enqueue_event(
                    TaskArtifactUpdateEvent(
                        task_id=context.task_id,
                        context_id=context.context_id,
                        artifact=Artifact(
                            artifactId="streaming-complete",
                            parts=[Part(root=TextPart(text=""))],
                            content="", 
                            content_type="text/plain"
                        ), # Proper Artifact object to signal completion
                        last_chunk=True # Tells the UI "I am done streaming this part"                       
                    )
                )
        except Exception as e:
            print(f"Server: Exception occurred: {e}")
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=context.task_id,
                    context_id=context_id,
                    status=TaskStatus(
                        state=TaskState.failed,
                        message=Message(
                            role=Role.agent,
                            parts=[Part(root=TextPart(text=str(e)))],
                            message_id=context.task_id,
                        ),
                    ),
                    final=True,
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
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
        capabilities=AgentCapabilities(
            streaming=True, extended_agent_card=True
        ),
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