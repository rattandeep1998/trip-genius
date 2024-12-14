import os
import json
from typing import Dict, Any, List
import requests
from dotenv import load_dotenv

from langchain.tools import BaseTool
from langchain.agents import initialize_agent, AgentType
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.utils.function_calling import convert_to_openai_function

load_dotenv()

# Global configuration
EXTRACT_PARAMETERS_MODEL = "gpt-3.5-turbo"
RUN_ITINERARY_MODEL = "gpt-3.5-turbo"
CONVERT_TO_HUMAN_RESULTS_MODEL = "gpt-3.5-turbo"

class AmadeusBaseAPI:
    """Base class for Amadeus API interactions"""
    
    @staticmethod
    def _get_access_token():
        client_id = os.getenv('AMADEUS_CLIENT_ID')
        client_secret = os.getenv('AMADEUS_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            raise ValueError("Missing Amadeus API credentials")
        
        token_url = 'https://test.api.amadeus.com/v1/security/oauth2/token'
        token_data = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret
        }
        
        response = requests.post(token_url, data=token_data)
        response.raise_for_status()
        return response.json()['access_token']

class FlightBookingTool(BaseTool):
    name: str = "flight_booking"
    description: str = "Books flight offers from the Amadeus API with dynamic traveler information."

    def _run(
        self, 
        originLocationCode: str, 
        destinationLocationCode: str, 
        departureDate: str,
        returnDate: str,
        travelers_details: List[Dict[str, Any]] = [],
        adults: int = 1,
        max: int = 5,
    ) -> Dict[str, Any]:
        try:
            access_token = AmadeusBaseAPI._get_access_token()
            
            # Flight offers search
            api_url = 'https://test.api.amadeus.com/v2/shopping/flight-offers'
            headers = {'Authorization': f'Bearer {access_token}'}
            params = {
                'originLocationCode': originLocationCode,
                'destinationLocationCode': destinationLocationCode,
                'departureDate': departureDate,
                'returnDate': returnDate,
                'adults': adults,
                'max': max
            }
            
            response = requests.get(api_url, headers=headers, params=params)
            response.raise_for_status()
            results = response.json()
            
            if "data" not in results or len(results["data"]) == 0:
                return {"error": "No flight offers found."}
            
            flightOfferData = results["data"][0]
            
            # Pricing
            pricing_url = "https://test.api.amadeus.com/v1/shopping/flight-offers/pricing"
            payload = {
                "data": {
                    "type": "flight-offers-pricing",
                    "flightOffers": [flightOfferData]
                }
            }
            
            pricing_response = requests.post(pricing_url, headers=headers, json=payload)
            pricing_response.raise_for_status()
            pricing_data = pricing_response.json()
            
            if "data" not in pricing_data or "flightOffers" not in pricing_data["data"]:
                return {"error": "No priced flight offers found."}
            
            flightOfferPriceData = pricing_data["data"]["flightOffers"][0]
            
            # Flight order
            orders_url = "https://test.api.amadeus.com/v1/booking/flight-orders"
            payload = {
                "data": {
                    "type": "flight-order",
                    "flightOffers": [flightOfferPriceData],
                    "travelers": travelers_details
                }
            }
            
            order_response = requests.post(orders_url, headers=headers, json=payload)
            order_response.raise_for_status()
            order_data = order_response.json()
            
            return order_data
        
        except Exception as e:
            return {"error": str(e)}

class HotelBookingTool(BaseTool):
    name: str = "hotel_booking"
    description: str = "Books hotel offers from the Amadeus API with dynamic traveler information."

    def _run(
        self,
        originLocationCode: str,
        destinationLocationCode: str,
        departureDate: str,
        returnDate: str,
        travelers_details: List[Dict[str, Any]],
        adults: int = 1,
        max: int = 5,
    ) -> Dict[str, Any]:
        try:
            access_token = AmadeusBaseAPI._get_access_token()
            
            # Hotels by city
            api_url = 'https://test.api.amadeus.com/v1/reference-data/locations/hotels/by-city'
            headers = {'Authorization': f'Bearer {access_token}'}
            
            params = {'cityCode': destinationLocationCode}
            response = requests.get(api_url, headers=headers, params=params)
            response.raise_for_status()
            results = response.json()
            
            if "data" not in results or len(results["data"]) == 0:
                return {"error": "No hotels found."}
            
            hotelIdsData = [hotel["hotelId"] for hotel in results["data"][:30]]
            hotelIds = ",".join(hotelIdsData)
            
            # Hotel offers pricing
            pricing_url = "https://test.api.amadeus.com/v3/shopping/hotel-offers"
            params = {
                'hotelIds': hotelIds,
                'adults': len(travelers_details),
                'checkInDate': departureDate,
                'checkOutDate': returnDate,
                'roomQuantity': 1,
                'paymentPolicy': 'NONE',
                'bestRateOnly': True
            }
            
            pricing_response = requests.get(pricing_url, headers=headers, params=params)
            pricing_response.raise_for_status()
            pricing_data = pricing_response.json()
            
            if "data" not in pricing_data or len(pricing_data["data"]) == 0:
                return {"error": "No priced hotel offers found."}
            
            hotelOfferPriceData = pricing_data["data"][0]
            hotelOfferPriceId = hotelOfferPriceData["offers"][0]["id"]
            
            # Guest references
            def guest_reference(traveler):
                return {
                    "tid": int(traveler.get("id", 1)),
                    "title": "MR" if traveler.get("gender") == "MALE" else "MS",
                    "firstName": traveler.get("name", {}).get("firstName", ""),
                    "lastName": traveler.get("name", {}).get("lastName", ""),
                    "phone": traveler.get("contact", {}).get("phones", [{}])[0].get("number", ""),
                    "email": traveler.get("contact", {}).get("emailAddress", "")
                }
            
            guestDetails = [guest_reference(traveler) for traveler in travelers_details]
            
            # Hotel order
            orders_url = "https://test.api.amadeus.com/v2/booking/hotel-orders"
            payload = {
                "data": {
                    "type": "hotel-order",
                    "roomAssociations": [{
                        "guestReferences": [{"guestReference": str(len(guestDetails))}],
                        "hotelOfferId": hotelOfferPriceId
                    }],
                    "travelAgent": {
                        "contact": {
                            "email": "bob.smith@email.com"
                        }
                    },
                    "guests": guestDetails,
                    "payment": {
                        "method": "CREDIT_CARD",
                        "paymentCard": {
                            "paymentCardInfo": {
                                "vendorCode": "VI",
                                "cardNumber": "4151289722471370",
                                "expiryDate": "2026-08",
                                "holderName": "BOB SMITH"
                            }
                        }
                    }
                }
            }
            
            order_response = requests.post(orders_url, headers=headers, json=payload)
            order_response.raise_for_status()
            order_data = order_response.json()
            
            return order_data
        
        except Exception as e:
            return {"error": str(e)}

class ItineraryPlanningTool(BaseTool):
    name: str = "itinerary_planning"
    description: str = "Creates an optimized travel itinerary for a given destination."

    def _run(
        self,
        originLocationCode: str,
        destinationLocationCode: str,
        departureDate: str,
        returnDate: str,
        adults: int = 1,
        travelers_details: List[Dict[str, Any]] = [],
    ) -> Dict[str, Any]:
        system_prompt = """
        You are an expert at planning trips in the most optimized way for the given city.

        Guidelines:
        - Suggest top restaurants
        - Tourist places
        - Activities
        - Optimized travel plan

        Return a valid JSON of the entire itinerary with a field optimized_travel_plan.
        """

        query = f"Plan an optimized trip itinerary for {adults} adults in {destinationLocationCode} starting from {departureDate} to {returnDate}."

        llm = ChatOpenAI(model=RUN_ITINERARY_MODEL, temperature=0)
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", query)
        ])
        chain = prompt | llm

        try:
            response = chain.invoke({"query": query})
            itinerary = json.loads(response.content)
            return itinerary
        except Exception as e:
            return {"error": f"Error extracting itinerary: {e}"}

class ParameterExtractionTool(BaseTool):
    name: str = "parameter_extraction"
    description: str = "Extracts travel booking parameters from natural language input."

    @classmethod
    def extract_parameters(
        cls, 
        query: str,
        function_spec: Dict[str, Any],
        interactive_mode: bool = False,
    ) -> Dict[str, Any]:
        system_prompt = """
        You are an expert at extracting structured parameters for a travel booking function.

        Extract the values of parameters from the given user query and strictly do not make up any information.

        Guidelines:
        1. Carefully analyze the user query to extract values for each parameter
        2. Do not make up any information and default to null if unsure
        3. Use exact IATA codes for locations if possible
        4. Use YYYY-MM-DD format for dates
        5. If parameters are missing, return defaults or null
        """

        llm = ChatOpenAI(model=EXTRACT_PARAMETERS_MODEL, temperature=0)
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{query}")
        ])
        
        chain = prompt | llm
        
        response = chain.invoke({"query": query})
        
        try:
            extracted_params = json.loads(response.content)
        except json.JSONDecodeError:
            extracted_params = {}
        
        return extracted_params

def extract_traveler_details(query: str, interactive_mode: bool = False):
    """Simplified traveler details extraction"""
    llm = ChatOpenAI(model=EXTRACT_PARAMETERS_MODEL, temperature=0)
    
    system_prompt = """
    Extract traveler details from the input:
    - Full Name (First and Last Name)
    - Date of Birth
    - Gender
    - Email Address
    - Phone Number

    Return as a JSON with structured fields.
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{query}")
    ])
    
    chain = prompt | llm
    
    try:
        response = chain.invoke({"query": query})
        traveler_details = json.loads(response.content)
        return traveler_details
    except Exception as e:
        print(f"Error extracting traveler details: {e}")
        return {}

def create_travel_booking_agent():
    """Create a LangChain agent for travel bookings"""
    llm = ChatOpenAI(temperature=0)
    
    # Initialize tools
    flight_tool = FlightBookingTool()
    hotel_tool = HotelBookingTool()
    itinerary_tool = ItineraryPlanningTool()
    
    # Convert tools to OpenAI functions
    tools = [
        convert_to_openai_function(flight_tool),
        convert_to_openai_function(hotel_tool),
        convert_to_openai_function(itinerary_tool)
    ]
    
    # Initialize agent
    agent = initialize_agent(
        tools, 
        llm, 
        agent=AgentType.OPENAI_FUNCTIONS,
        verbose=True
    )
    
    return agent

def process_travel_booking(query: str, interactive_mode: bool = False):
    """Main function to process travel bookings"""
    # Extract traveler details
    traveler_details = extract_traveler_details(query, interactive_mode)
    
    # Create agent
    agent = create_travel_booking_agent()
    
    # Process query
    try:
        response = agent.run(query)
        return {
            "result": response,
            "traveler_details": traveler_details
        }
    except Exception as e:
        return {
            "error": str(e),
            "traveler_details": traveler_details
        }

# Example usage
if __name__ == "__main__":
    # Example query
    query = "I want to book a flight from New York to London for 2 adults in July"
    result = process_travel_booking(query, interactive_mode=True)
    print(json.dumps(result, indent=2))