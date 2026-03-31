import os
import asyncio
from pathlib import Path

# Add references
from agent_framework import tool, Agent
from agent_framework.azure import AzureOpenAIResponsesClient
from azure.identity import AzureCliCredential
from pydantic import Field
from typing import Annotated
from tools import book_hotel, search_hotels, get_hotel_details, cancel_hotel_booking

from dotenv import load_dotenv

load_dotenv()


class HotelAgent:
    def __init__(self):
        self.credential = AzureCliCredential()
        self.agent = Agent(
            client=AzureOpenAIResponsesClient(
                credential=self.credential,
                deployment_name="gpt-5.1",
                project_endpoint=os.getenv("FOUNDRY_PROJECT_ENDPOINT")
            ),
            store=False,
            default_options={"truncation": "auto"},
            instructions="""You are an AI assistant for hotel booking.
                        At the user's request, you can search for hotels, get hotel details, book a hotel, or cancel a hotel booking.
                        Use the appropriate tool function for each task and provide the user with the necessary information.""",
            tools=[book_hotel, search_hotels, get_hotel_details, cancel_hotel_booking],
        )

    async def __aenter__(self):
        await self.agent.__aenter__()
        return self

    async def __aexit__(self, *args):
        await self.agent.__aexit__(*args)

    def create_session(self, session_id: str = None):
        return self.agent.create_session(session_id=session_id)

    async def chat(self, user_input: str, session=None) -> str:
        for attempt in range(3):
            try:
                response = await self.agent.run([user_input], session=session)
                return str(response)
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    wait = (attempt + 1) * 10
                    print(f"Rate limited. Retrying in {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    raise

    async def run_chat_loop(self):
        print("Hotel Booking Assistant (type 'end' or 'quit' to exit)\n")
        while True:
            user_input = input("You: ").strip()
            if user_input.lower() in ("end", "quit"):
                print("Goodbye!")
                break
            if not user_input:
                continue
            try:
                response = await self.chat(user_input)
                print(f"\nAgent: {response}\n")
            except Exception as e:
                print(f"Error: {e}\n")


async def main():
    # instatiate : creates instance of class HotelAgent
    # __aenter__ executes
    # whatever __aenter__ returns is assigned to hotel_agent variable
    # after run_chat_loop completes __aexit__ is executed for cleanup
    async with HotelAgent() as hotel_agent:
        await hotel_agent.run_chat_loop()



if __name__ == "__main__":
    asyncio.run(main())
