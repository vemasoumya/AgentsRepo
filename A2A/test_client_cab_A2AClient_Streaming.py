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


def extract_streaming_text(event):
    """Extract text from streaming artifact-update events."""
    # Get the actual event object from tuple if needed
    actual_event = event[1] if isinstance(event, tuple) and len(event) == 2 else event
    
    if not hasattr(actual_event, 'kind') or actual_event.kind != "artifact-update":
        return None

    text = ""
    for part in actual_event.artifact.parts:
        if part.root.kind == "text":
            text += part.root.text

    return text


async def main():
    async with httpx.AsyncClient(timeout=120.0) as httpx_client:
        # --- Discovery ---
        print("=== Agent Discovery ===\n")
        cards = {}
        for name, url in AGENT_URLS.items():
            cards[name] = await discover_agent(httpx_client, url)
        print(cards)
       
       
        # --- Streaming messages ---
        print("=== Streaming Messages ===\n")

        stream_config = ClientConfig(httpx_client=httpx_client, streaming=True)
        stream_factory = ClientFactory(stream_config)

        client_stream = stream_factory.create(cards["Cab_Agent"])
        
        #Explicitly create message with non-blocking configuration for streaming        
        message = Message(
            role=Role.user,
            message_id=str(uuid.uuid4()),
            context_id="streaming-1234",                
            parts=[TextPart(text="Book a cab in Hyderabad from MS office to Gachibowli at 6 PM tomorrow")],
        )
        
        accumulated_text = ""
        async for event in client_stream.send_message(message):
            print("Received Event")
            text = extract_streaming_text(event)
            if text:
                accumulated_text += text
        
        # Display the complete response with preserved newlines
        print("\n=== Complete Agent Response ===")
        print(accumulated_text)
        
     

        
        


if __name__ == "__main__":
    asyncio.run(main())