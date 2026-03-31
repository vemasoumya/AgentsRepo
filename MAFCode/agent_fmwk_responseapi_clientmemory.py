import os
import asyncio
from pathlib import Path

# Add references
from agent_framework import tool, Agent
from agent_framework.azure import AzureOpenAIResponsesClient
from azure.identity import AzureCliCredential
from pydantic import Field
from typing import Annotated

from dotenv import load_dotenv

load_dotenv()

#if you prefer not to store data on Azure(privacy concerns), you can use the Responses API with client-side memory.
# for this we need to use store=False in the agent configuration, which tells the agent not to store any data on the server side.
# in the current Public Preview of the Python SDK, the AgentSession effectively acts as the thread for most local development 
# scenarios. It uses that internal InMemoryHistoryProvider to manage the message stack automatically.
#Isolation : 
#the InMemoryHistoryProvider keeps conversations isolated. If you created session_a and session_b, 
# they would have completely different histories.


async def main():
    # Clear the console
    os.system('cls' if os.name=='nt' else 'clear')

    # Load the expnses data file
    script_dir = Path(__file__).parent
    file_path = script_dir / 'data.txt'
    with file_path.open('r') as file:
        data = file.read() + "\n"

    # Ask for a prompt
    user_prompt = input(f"Here is the expenses data in your file:\n\n{data}\n\nWhat would you like me to do with it?\n\n")
    
    # Run the async agent code
    await process_expenses_data (user_prompt, data)
    
async def process_expenses_data(prompt, expenses_data):
    
    # Create a client and initialize an agent with the tool and instructions
    credential = AzureCliCredential()
    async with (
        Agent(
            client=AzureOpenAIResponsesClient(
                credential=credential,
                deployment_name="gpt-5.1",
                project_endpoint=os.getenv("FOUNDRY_PROJECT_ENDPOINT")
            ),
            store=False,  # This tells the agent not to store any data on the server side
            instructions="""You are an AI assistant for expense claim submission.
                        At the user's request, create an expense claim and use the plug-in function to send an email to expenses@contoso.com 
                        with the subject 'Expense Claim`and a body that contains itemized expenses with a total.
                        Then confirm to the user that you've done so. Don't ask for any more information from the user,
                        just use the data provided to create the email.""",
            tools=[submit_claim],
        ) as agent,
    ):
    

    # Use the agent to process the expenses data       
        try:

            # 1. Create a session to hold the "Thread" (memory)
            # This automatically enables client-side persistence by default            
            session = agent.create_session()
            # Add the input prompt to a list of messages to be submitted
            prompt_messages = [f"{prompt}: {expenses_data}"]
            # Invoke the agent for the specified thread with the messages
            response = await agent.run(prompt_messages, session=session)
            # Display the response
            print(f"\n# Agent:\n{response}")

            #Second prompt 
            prompt_messages = [f"what was the total expense amount in the claim submitted"]
            # Invoke the agent for the specified thread with the messages
            response = await agent.run(prompt_messages, session=session)
            # Display the response
            print(f"\n# Agent response 2:\n{response}")
        except Exception as e:
            # Something went wrong
            print (e) 



# Create a tool function for the email functionality
@tool(approval_mode="never_require")
def submit_claim(
    to: Annotated[str, Field(description="Who to send the email to")],
    subject: Annotated[str, Field(description="The subject of the email.")],
    body: Annotated[str, Field(description="The text body of the email.")]):
        print("\nTo:", to)
        print("Subject:", subject)
        print(body, "\n")



if __name__ == "__main__":
    asyncio.run(main())
