import os
import asyncio
from pathlib import Path

# Add references
from agent_framework import InMemoryHistoryProvider, tool, Agent, CompactionProvider
from agent_framework._compaction import (
    SelectiveToolCallCompactionStrategy,
    ToolResultCompactionStrategy
)
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential
from pydantic import Field
from typing import Annotated

from dotenv import load_dotenv
from requests import session

from compaction import DebugStrategy
from tools import search_hotels, book_hotel, get_hotel_details, cancel_hotel_booking

load_dotenv()

# Now using Azure Cosmos DB SQL API to store conversation context persistently.
# This provides durable storage for conversation history across sessions.
# The CosmosDBHistoryProvider manages conversation isolation automatically.
# Each session gets a unique ID and conversations are stored as separate documents.
# Benefits: Persistent storage, scalable, managed service, cross-session memory.

# Hotel booking tools
@tool(approval_mode="never_require")
def search_hotels_tool(
    destination: Annotated[str, Field(description="The destination city or area to search for hotels")],
    check_in: Annotated[str, Field(description="Check-in date (format: YYYY-MM-DD)")],
    check_out: Annotated[str, Field(description="Check-out date (format: YYYY-MM-DD)")]
) -> str:
    """Search for available hotels in a destination."""
    return search_hotels(destination, check_in, check_out)

@tool(approval_mode="never_require")
def book_hotel_tool(
    hotel_id: Annotated[str, Field(description="The unique identifier of the hotel to book")],
    destination: Annotated[str, Field(description="The destination city or area")],
    check_in: Annotated[str, Field(description="Check-in date (format: YYYY-MM-DD)")],
    check_out: Annotated[str, Field(description="Check-out date (format: YYYY-MM-DD)")],
    guest_name: Annotated[str, Field(description="Name of the guest making the booking")] = "Guest"
) -> str:
    """Book a hotel room."""
    return book_hotel(hotel_id, destination, check_in, check_out, guest_name)

@tool(approval_mode="never_require")
def get_hotel_details_tool(
    hotel_id: Annotated[str, Field(description="The unique identifier of the hotel")]
) -> str:
    """Get detailed information about a specific hotel."""
    return get_hotel_details(hotel_id)

@tool(approval_mode="never_require")
def cancel_hotel_booking_tool(
    confirmation_number: Annotated[str, Field(description="The booking confirmation number")]
) -> str:
    """Cancel a hotel booking using the confirmation number."""
    return cancel_hotel_booking(confirmation_number)


async def main():
    # Clear the console
    os.system('cls' if os.name=='nt' else 'clear')

    print("🏨 Hotel Booking Assistant")
    print("=" * 50)
    print("I can help you search for hotels, make bookings, get hotel details, and cancel reservations.")
    print("Type 'quit', 'exit', or 'bye' to end the conversation.\n")
    
    # Run the async agent code with multi-turn conversation
    await start_conversation()
    
async def start_conversation():
    """Start a multi-turn conversation with the hotel booking agent."""
    
    # Create a client and initialize an agent with the tool and instructions
    credential = AzureCliCredential()
    
    # Configure Cosmos DB history provider
    cosmos_endpoint = os.getenv("COSMOS_ENDPOINT", "")
    if not cosmos_endpoint:
        raise ValueError("COSMOS_ENDPOINT environment variable is required")
    
   
    histprovider = InMemoryHistoryProvider()
    

    # before = DebugStrategy(
    #     "BEFORE_STRATEGY",
    #     SlidingWindowStrategy(
    #         keep_last_groups=3           
    #     )
    # )

    # after = DebugStrategy(
    #     "AFTER_STRATEGY",
    #     TruncationStrategy(
    #         max_n=500,  # Lowered to trigger sooner
    #         compact_to=300,  # Lowered to trigger sooner  
    #         tokenizer=tokenizer,
    #     )
    # )

    after = DebugStrategy(
         "AFTER_STRATEGY",SelectiveToolCallCompactionStrategy(keep_last_tool_call_groups=1)
    )

    compaction = CompactionProvider(        
        after_strategy=after,
        history_source_id=histprovider.source_id
    )

    try:
        async with (
            Agent(
                client = FoundryChatClient(
                    project_endpoint="https://vemafoundrysea1-resource.services.ai.azure.com/api/projects/vemafoundrysea1",
                    model="gpt-5.1",
                    credential=AzureCliCredential()
                ),            
                context_providers=[histprovider, compaction],  # History first, then compaction
                instructions="""You are a helpful hotel booking assistant. I can help you with:
                            
                            1. Search for hotels in any destination
                            2. Book hotel rooms with confirmation details
                            3. Get detailed information about specific hotels
                            4. Cancel existing hotel bookings
                            
                            Always be friendly and provide clear, helpful information. When booking hotels, 
                            make sure to get all necessary details like guest name, dates, and destination.""",
                tools=[search_hotels_tool, book_hotel_tool, get_hotel_details_tool, cancel_hotel_booking_tool] 

            ) as agent,
        ):
            # Create a fresh new session
            session = agent.create_session()
            print(f"🆔 Started new conversation session: {session.session_id}")
            print("-" * 50)
            
            # Multi-turn conversation loop
            while True:
                try:
                    # Get user input
                    user_input = input("\n💬 You: ").strip()
                    
                    # Check for exit commands
                    if user_input.lower() in ['quit', 'exit', 'bye', 'stop']:
                        print(f"\n👋 Goodbye! Your conversation is saved in Cosmos DB with session ID: {session.session_id}")
                        break
                    
                    if not user_input:
                        print("Please enter a message or type 'quit' to exit.")
                        continue
                    
                    # Prepare message for the hotel booking agent
                    prompt_messages = [user_input]
                    
                    # Get agent response
                    print("\n🤖 Assistant: ", end="", flush=True)
                    response = await agent.run(prompt_messages, session=session)
                    print(f"{response}")
                    
                except KeyboardInterrupt:
                    print(f"\n\n⛔ Conversation interrupted. Session saved: {session.session_id}")
                    break
                except Exception as e:
                    print(f"\n❌ Error in conversation: {e}")
                    print("Continuing conversation...")
                    
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
    



if __name__ == "__main__":
    asyncio.run(main())