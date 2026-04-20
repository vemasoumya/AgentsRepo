# Copyright (c) Microsoft. All rights reserved.

import asyncio
import httpx
import uuid
from typing import Annotated, Dict

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential
from tools_flights import search_flights, book_flight, get_flight_details, cancel_flight_booking
from a2a.client import A2ACardResolver
from a2a.client.client_factory import ClientFactory, ClientConfig
from a2a.client import A2AClient
from a2a.types import Message, Role, TextPart, SendMessageRequest, SendMessageResponse
from typing import Any


class RemoteAgentConnection:
    """A class to hold the connections to the remote agents."""

    def __init__(self, name: str, agent_card):
        self.name = name
        self._httpx_client = httpx.AsyncClient(timeout=30)
        self.config = ClientConfig(httpx_client=self._httpx_client, streaming=False)
        self.factory = ClientFactory(self.config)       
        self.a2a_agent_client = self.factory.create(agent_card)        
        self.card = agent_card

    def get_agent(self):
        """Get the agent card."""
        return self.card

    async def send_message(self, message_text: str) -> SendMessageResponse:       

        def extract_agent_response(event):
            """Extract agent response text from A2A task event.

            The factory client yields (Task, context) tuples.
            """
            task = event[0] if isinstance(event, tuple) else event
           
            if hasattr(task, "role") and hasattr(task, "parts"):
                # This is a direct Message object
                parts = task.parts
                return "".join(
                    p.root.text for p in parts if hasattr(p.root, "text")
                )
            
            # Check if this is a TaskStatusUpdateEvent with a message    
            if hasattr(task, "status") and task.status and task.status.message:
                parts = task.status.message.parts
                return "".join(
                    p.root.text for p in parts if hasattr(p.root, "text")
                )
            
            return None
        
        msg = Message(
            role=Role.user,
            messageId=str(uuid.uuid4()),
            parts=[TextPart(text=message_text)],
        )
        async for event in self.a2a_agent_client.send_message(msg):        
            t = extract_agent_response(event)
            if t:                
                agent_text = t
        return agent_text or "(no response)"           
           


class FlightBookingAgent:
    """Flight booking agent with integrated A2A agent capabilities."""
    
    def __init__(self, project_endpoint: str, model: str, credential):
        self.project_endpoint = project_endpoint
        self.model = model
        self.credential = credential
        
        # Remote agent connections
        self.remote_agent_connections: dict[str, RemoteAgentConnection] = {}
        
        # Agent components
        self.client = None
        self.agent = None
        self.session = None
    
    async def discover_agents(self, a2a_agent_urls: Dict[str, str]):
        """Discover A2A agents and update remote_agent_connections."""
        print("=== Discovering A2A Agents ===")
        async with httpx.AsyncClient(timeout=120.0) as httpx_client:
            for name, url in a2a_agent_urls.items():
                try:
                    resolver = A2ACardResolver(httpx_client, base_url=url)
                    agent_card = await resolver.get_agent_card()
                    connection = RemoteAgentConnection(name, agent_card)
                    self.remote_agent_connections[name] = connection
                    print(f"  ✓ {name}: {agent_card.name} - {agent_card.description}")
                except Exception as e:
                    print(f"  ✗ Failed to discover {name}: {e}")
        print(f"Successfully discovered {len(self.remote_agent_connections)} A2A agents.\n")
    
    def list_remote_agents(self) -> str:       

        lines = []
        for connection in self.remote_agent_connections.values():
            card = connection.card
            lines.append(f"{card.name}: {card.description}")

        return "[\n  " + ",\n  ".join(lines) + "\n]"
    
    async def send_message(self, agent_name: str, messsage: str):
        # Sends a task to remote agent.

        if agent_name not in self.remote_agent_connections:
            raise ValueError(f'Agent {agent_name} not found')
        
        # Retrieve the remote agent's A2A client using the agent name 
        client = self.remote_agent_connections[agent_name]          
        
        message_id = str(uuid.uuid4())

       # Construct the payload to send to the remote agent
        payload: dict[str, Any] = {
            'message': {
                'role': 'user',
                'parts': [{'kind': 'text', 'text': messsage}],
                'messageId': message_id,
            },
        }                      

        return client.send_message(messsage)

    async def create_agent(self):
        
        # Create Foundry client
        self.client = FoundryChatClient(
            project_endpoint=self.project_endpoint,
            model=self.model,
            credential=self.credential,
        )        
      
        
        # Create agent with flight tools + remote agent tools
        self.agent = self.client.as_agent(        
            name="FlightBookingChatAgent",
            instructions=f"""
            You are a helpful flight booking agent. Use the provided tools to search for flights, book flights, get flight details, and cancel flight bookings.
            Always be friendly and provide clear, helpful information. 
            When booking flights, make sure to get all necessary details like passenger name, dates, origin, and destination.
            
            You also have access to remote A2A agents for additional services like Cab Booking. You can see the list of available remote agents and their capabilities below:   
            {self.list_remote_agents()}
            
            After successfully booking or cancelling flights, proactively offer services from remote agents.
            
            """,
            tools=[book_flight, search_flights, get_flight_details, cancel_flight_booking, self.send_message]
        )
        
        # Create session
        self.session = self.agent.create_session()
        print("Flight Booking Agent initialized successfully!")
    
    async def run(self, message: str):
        """Run a message through the agent with session."""
        if not self.agent or not self.session:
            raise RuntimeError("Agent not initialized. Call create_agent() first.")
        
        return await self.agent.run(message, session=self.session)
    
    


async def main() -> None:
    # Create flight booking agent
    flight_agent = FlightBookingAgent(
        project_endpoint="https://vema-ai-foundry2.services.ai.azure.com/api/projects/secondproject",
        model="model-router",
        credential=AzureCliCredential()
    )
    
    # Discover A2A agents
    await flight_agent.discover_agents({"Cab_Agent": "http://localhost:9100"})
    await flight_agent.create_agent()
    
    # Start conversation loop
    print("FlightBooking Agent with A2A capabilities ready! Type 'exit' or 'quit' to end.\n")
    
    while True:
        user_message = input("User: ")
        if user_message.lower() in ["exit", "quit"]:
            print("Exiting chat.")
            break
        
        try:
            response = await flight_agent.run(user_message)
            
            # Show tool calls for debugging
            for msg in response.messages:
                for content in msg.contents:
                    if content.type == "function_call":
                        print(f"Tool called: {content.name}, args: {content.arguments}")

            print(f"Agent: {response.text}\n")
        except Exception as e:
            print(f"Error: {e}\n")
    
    

if __name__ == "__main__":
    asyncio.run(main())
           


