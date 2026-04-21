"""A2A client that discovers and sends messages to both HR agents."""
#https://a2a-protocol.org/latest/tutorials/python/6-interact-with-server/#the-helloworld-test-client
import asyncio
import uuid

import httpx
from a2a.client import A2ACardResolver
from a2a.client.client_factory import ClientFactory, ClientConfig
from a2a.types import Message, Role, TextPart, MessageSendConfiguration

AGENT_URLS = {
    "Cab_Agent": "http://localhost:9100"  
}


async def discover_agent(httpx_client: httpx.AsyncClient, url: str):
    """Resolve an agent's AgentCard from its well-known URL."""
    resolver = A2ACardResolver(httpx_client, base_url=url)
    card = await resolver.get_agent_card()
    print(f"  Discovered: {card.name}")
    for skill in card.skills:
        print(f"    Skill: {skill.name} — {skill.description}")
    return card


def extract_agent_response(event):
    """Extract agent response text from A2A task event.

    The factory client yields (Task, context) tuples.
    """
    task = event[0] if isinstance(event, tuple) else event
    
    # Check if this is a direct Message event (cab agent sends these)
    # right now , final response from cab_agent is not sent as TaskStatusUpdateEvent event but its sent as Message event
    # and only the Message event will have parts
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


async def send_message(client, text: str, context_id : str) -> str:
    """Send a message and return the agent's response text."""
    message_id_gen = str(uuid.uuid4())
    print(f"Sending message with ID: {message_id_gen}")
    msg = Message(
        role=Role.user,
        message_id=message_id_gen,
        context_id = context_id,
        parts=[TextPart(text=text)],
    )
    agent_text = None
    # async for event in client.send_message(msg):
    #     print(f"Received event: {event}")
    #     t = extract_agent_response(event)
    #     if t:
    #         print(f"  Extract text: {t}")
    #         agent_text = t
    # return agent_text or "(no response)"
    
    async for event in client.send_message(msg):
        print(f"Received event in non stream")
        t = extract_agent_response(event)
        if t:                
            print(t, end="", flush=True)


async def main():
    async with httpx.AsyncClient(timeout=120.0) as httpx_client:
        # --- Discovery ---
        print("=== Agent Discovery ===\n")
        cards = {}
        for name, url in AGENT_URLS.items():
            cards[name] = await discover_agent(httpx_client, url)
        print(cards)
        config = ClientConfig(httpx_client=httpx_client, streaming=False)
        factory = ClientFactory(config)

        #--- Non-streaming messages ---
        print("\n=== Non-Streaming Messages ===\n")

        client = factory.create(cards["Cab_Agent"])
        response = await send_message(
            client,
            "Book a cab in Hyderabad from MS office to Gachibowli at 6 PM tomorrow",
            "1234"
        )
        print(f"[CabBooking1] {response}\n")
        # response = await send_message(
        #     client,
        #     "Confirm the booking",
        #     "1234"
        # )
        
        # print(f"[CabBooking2] {response}\n")
        # response = await send_message(
        #     client,
        #     "Whats the booking id of my Cab booking",
        #     "1234"
        # )        
        # print(f"[CabBooking3] {response}\n")

       
       

        
        


if __name__ == "__main__":
    asyncio.run(main())