from langchain import hub
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage

@tool
def FlightBooking(source: str, destination: str, departure_date: str, return_date: str) -> str:
    """Book a flight from specified source to the specified destination with given departure and return dates."""
    return f"Flight booked from {source} to {destination} from {departure_date} to {return_date}."

@tool
def HotelBooking(destination: str, check_in_date: str, check_out_date: str) -> str:
    """Book a hotel at the specified destination with given check-in and check-out dates."""
    return f"Hotel booked in {destination} from {check_in_date} to {check_out_date}."

@tool
def ItinerarySuggestion(destination: str) -> str:
    """Suggest a travel itinerary for the specified destination."""
    return f"Suggested itinerary for {destination}: Day 1 - Sightseeing, Day 2 - Local Food Tour, Day 3 - Relax at the Beach."

# Initialize the Language Model
llm = ChatOpenAI(model="gpt-3.5-turbo")

# Pull the existing prompt
prompt = hub.pull("hwchase17/openai-tools-agent")

system_message = SystemMessage(
    content="""
You are an intelligent travel assistant. Follow these rules when handling user requests:
1. **For trip planning or booking a trip**: Book a flight, a hotel, and suggest an itinerary.
2. **For flight booking requests**: Book only the flight.
3. **For hotel booking requests**: Book only the hotel.
4. **For itinerary suggestions**: Suggest only an itinerary.

Always respond clearly and concisely, specifying the actions taken.
"""
)

# Combine the system message with the original prompt
updated_prompt = prompt + system_message

# Display the updated prompt (for verification)
# print(updated_prompt)

# List of tools for the agent
tools = [FlightBooking, HotelBooking, ItinerarySuggestion]

# Create the agent
agent = create_tool_calling_agent(llm, tools, updated_prompt)

# Create the agent executor
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# Sample Queries

# Book a flight
agent_executor.invoke({"input": "Provide a travel plan from New Delhi to New York, departing on December 20, 2024, and returning on January 5, 2025. It's for one adult, born on March 7, 1998. My name is RD Singh, and my contact email is jnnj@gmail.com. My phone number is +1 9144471153."})

# # Book a hotel
# agent_executor.invoke({"input": "Book a hotel in New York from January 5 to January 10."})

# # Suggest an itinerary
# agent_executor.invoke({"input": "Suggest an itinerary for Tokyo."})

# # Book a complete trip (flight, hotel, and itinerary)
# agent_executor.invoke({"input": "Book a complete trip to Bali from March 15 to March 25, including flights, hotel, and itinerary."})