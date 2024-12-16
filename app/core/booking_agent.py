import dotenv
dotenv.load_dotenv()

import os
import json
from typing import Dict, Any, List
import requests
from langchain.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.utils.function_calling import convert_to_openai_function
from app.core.helpers import extract_parameters_with_llm, extract_traveler_details, convert_to_human_readable_result, extract_missing_booking_parameters

extract_parameters_model = "gpt-3.5-turbo"
# TODO - Where is this model used ?
run_itinerary_model = "gpt-3.5-turbo"
convert_to_human_results_model = "gpt-3.5-turbo"

# Global counter for LLM calls
llm_calls_count = 0

class FlightBookingTool(BaseTool):
    """Tool to retrieve and book flight offers from Amadeus API with dynamic traveler details."""
    
    name: str = "amadeus_flight_booking"
    description: str = "Books flight offers from the Amadeus API with dynamic traveler information."

    def _run(
        self, 
        originLocationCode: str, 
        destinationLocationCode: str, 
        departureDate: str,
        returnDate: str,
        travelers_details: List[Dict[str, Any]] = [],
        travelPlanPreference: str = "",
        destinationCountry:str = "",
        destinationCity: str = "",
        originCurrencyCode: str = "",
        adults: int = 1,
        max: int = 5,
        verbose: bool = True,
        interactive_mode: bool = True,
    ) -> Dict[str, Any]:
        flight_api_calls = 0
        flight_api_success = 0

        client_id = os.getenv('AMADEUS_CLIENT_ID')
        client_secret = os.getenv('AMADEUS_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            return {"error": "Missing credentials for Amadeus API."}
        
        # Token call
        token_url = 'https://test.api.amadeus.com/v1/security/oauth2/token'
        token_data = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret
        }
        flight_api_calls += 1
        try:
            token_response = requests.post(token_url, data=token_data)
            token_response.raise_for_status()
            access_token = token_response.json()['access_token']
            flight_api_success += 1
        except requests.RequestException as e:
            return {"error": str(e), "_flight_api_calls": flight_api_calls, "_flight_api_success": flight_api_success}

        # Flight offers
        api_url = 'https://test.api.amadeus.com/v2/shopping/flight-offers'
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        params = {
            'originLocationCode': originLocationCode,
            'destinationLocationCode': destinationLocationCode,
            'departureDate': departureDate,
            'returnDate': returnDate,
            'adults': adults,
            'max': max,
        }

        if originCurrencyCode:
            params['currencyCode'] = originCurrencyCode
            
        flight_api_calls += 1
        try:
            response = requests.get(api_url, headers=headers, params=params)
            response.raise_for_status()
            results = response.json()
            flight_api_success += 1
        except requests.RequestException as e:
            return {"error": str(e), "_flight_api_calls": flight_api_calls, "_flight_api_success": flight_api_success}

        if "data" not in results or len(results["data"]) == 0:
            if verbose:
                print("No flight offers found.")
            return {"error": "No flight offers found.", "_flight_api_calls": flight_api_calls, "_flight_api_success": flight_api_success}


        flightData = results["data"]

        if interactive_mode:
            mappings = results["dictionaries"]["carriers"]
            flight_details = []
            for i, flight in enumerate(flightData):
                flight_detail = {
                    "departure": flight["itineraries"][0]["segments"][0]["departure"]["iataCode"]+" at: "+flight["itineraries"][0]["segments"][0]["departure"]["at"],
                    "arrival": flight["itineraries"][0]["segments"][-1]["arrival"]["iataCode"]+" at: "+flight["itineraries"][0]["segments"][-1]["arrival"]["at"],
                    "return departure": flight["itineraries"][1]["segments"][0]["departure"]["iataCode"]+" at: "+flight["itineraries"][1]["segments"][0]["departure"]["at"],
                    "return arrival": flight["itineraries"][1]["segments"][-1]["arrival"]["iataCode"]+" at: "+flight["itineraries"][1]["segments"][-1]["arrival"]["at"],
                    "airlines": mappings[flight["itineraries"][0]["segments"][0]["carrierCode"]],
                    "return airlines": mappings[flight["itineraries"][1]["segments"][0]["carrierCode"]],
                    "price": flight["price"]["grandTotal"],
                    "currency": flight["price"]["currency"],
                    }
                flight_details.append(flight_detail)
                print(f"Flight {i + 1}: {flight_detail}")
                yield {"type": "message", "text": f"Flight {i + 1}: {flight_detail}"}

            preferred_flight_input = "Enter the number of your preferred flight to book(by default, it is the first cheapest flight): "
            preferred_flight = yield {"type": "prompt", "text": preferred_flight_input}
            # preferred_flight = input(preferred_flight_input)

            if not preferred_flight or not preferred_flight.isdigit() or int(preferred_flight) < 1 or int(preferred_flight) > len(flight_details):
                preferred_flight = 1
            else:
                preferred_flight = int(preferred_flight)
        else:
            preferred_flight = 1

        flightOfferData = flightData[preferred_flight - 1]

        # Pricing
        pricing_url = "https://test.api.amadeus.com/v1/shopping/flight-offers/pricing"
        payload = {
            "data": {
                "type": "flight-offers-pricing",
                "flightOffers": [
                    flightOfferData
                ]
            }
        }
        flight_api_calls += 1
        try:
            pricing_response = requests.post(pricing_url, headers=headers, json=payload)
            pricing_response.raise_for_status()
            pricing_data = pricing_response.json()
            flight_api_success += 1
        except requests.RequestException as e:
            return {"error": str(e), "_flight_api_calls": flight_api_calls, "_flight_api_success": flight_api_success}

        if "data" not in pricing_data or "flightOffers" not in pricing_data["data"] or len(pricing_data["data"]["flightOffers"]) == 0:
            if verbose:
                print("No priced flight offers found.")
            return {"error": "No priced flight offers found.", "_flight_api_calls": flight_api_calls, "_flight_api_success": flight_api_success}
        
        flightOfferPriceData = pricing_data["data"]["flightOffers"]

        # Flight order
        orders_url = "https://test.api.amadeus.com/v1/booking/flight-orders"
        payload = {
            "data": {
                "type": "flight-order",
                "flightOffers": flightOfferPriceData,
                "travelers": travelers_details
            }
        }

        if verbose:
            print("Flight Order Payload:")
            print(json.dumps(payload, indent=2))

        flight_api_calls += 1
        try:
            order_response = requests.post(orders_url, headers=headers, json=payload)
            order_response.raise_for_status()
            order_data = order_response.json()
            flight_api_success += 1
        except requests.RequestException as e:
            error_details = {
                "error": str(e),
                "status_code": getattr(e.response, "status_code", None),
                "reason": getattr(e.response, "reason", None),
                "text": getattr(e.response, "text", None),
                "_flight_api_calls": flight_api_calls,
                "_flight_api_success": flight_api_success,
            }
            if verbose:
                print(f"Error booking flight: {error_details}")
            return error_details
        
        # Add api call info to result
        order_data["_flight_api_calls"] = flight_api_calls
        order_data["_flight_api_success"] = flight_api_success
        return order_data

class HotelBookingTool(BaseTool):
    """Tool to retrieve and book hotel offers from Amadeus API."""
    
    name: str = "hotel_booking"
    description: str = "Books hotel offers from the Amadeus API."

    def _run(
        self,
        originLocationCode: str,
        destinationLocationCode: str,
        departureDate: str,
        returnDate: str,
        adults: int,
        travelers_details: List[Dict[str, Any]]=[],
        travelPlanPreference: str = "",
        destinationCountry:str = "",
        destinationCity: str = "",
        originCurrencyCode: str = "",
        max: int = 5,
        interactive_mode: bool = True,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        hotel_api_calls = 0
        hotel_api_success = 0

        client_id = os.getenv('AMADEUS_CLIENT_ID')
        client_secret = os.getenv('AMADEUS_CLIENT_SECRET')

        if not client_id or not client_secret:
            return {"error": "Missing credentials for Amadeus API."}

        # Token
        token_url = 'https://test.api.amadeus.com/v1/security/oauth2/token'
        token_data = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret
        }

        hotel_api_calls += 1
        try:
            token_response = requests.post(token_url, data=token_data)
            token_response.raise_for_status()
            access_token = token_response.json()['access_token']
            hotel_api_success += 1
        except requests.RequestException as e:
            return {"error": str(e), "_hotel_api_calls": hotel_api_calls, "_hotel_api_success": hotel_api_success}

        # Hotels by city
        api_url = 'https://test.api.amadeus.com/v1/reference-data/locations/hotels/by-city'
        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        params = {
            'cityCode': destinationLocationCode
        }

        hotel_api_calls += 1
        try:
            response = requests.get(api_url, headers=headers, params=params)
            response.raise_for_status()
            results = response.json()
            hotel_api_success += 1
        except requests.RequestException as e:
            return {"error": str(e), "_hotel_api_calls": hotel_api_calls, "_hotel_api_success": hotel_api_success}

        if "data" not in results or len(results["data"]) == 0:
            print("No hotels found.")
            return {"error": "No hotels found.", "_hotel_api_calls": hotel_api_calls, "_hotel_api_success": hotel_api_success}

        hotelIdsData = [hotel["hotelId"] for hotel in results["data"][:30]]
        hotelIds = ",".join(hotelIdsData)

        pricing_url = "https://test.api.amadeus.com/v3/shopping/hotel-offers"
        params = {
            'hotelIds': hotelIds,
            'adults':len(travelers_details),
            'checkInDate':departureDate,
            'checkOutDate': returnDate,
            'paymentPolicy':'NONE',
            'bestRateOnly':True,
            'includeClosed':False,
        }
        if originCurrencyCode:
            params['currency'] = originCurrencyCode

        hotel_api_calls += 1
        try:
            pricing_response = requests.get(pricing_url, headers=headers, params=params)
            pricing_response.raise_for_status()
            pricing_data = pricing_response.json()
            hotel_api_success += 1
        except requests.RequestException as e:
            return {"error": str(e), "_hotel_api_calls": hotel_api_calls, "_hotel_api_success": hotel_api_success}

        if "data" not in pricing_data  or len(pricing_data["data"]) == 0 or "hotel" not in pricing_data["data"][0]:
            print("No priced hotel offers found.")
            return {"error": "No priced hotel offers found.", "_hotel_api_calls": hotel_api_calls, "_hotel_api_success": hotel_api_success}
 
        hotels = pricing_data["data"]
        hotelOfferPriceData = sorted(hotels, key=lambda h: float(h["offers"][0]["price"]["total"]))[:5]
        
        if interactive_mode:
            for idx, hotel in enumerate(hotelOfferPriceData, start=1):
                offer = hotel["offers"][0]
                print(
                    f"Hotel {idx}. {hotel['hotel']['name']} - {offer['price']['total']} {offer['price']['currency']} "
                    f"(Check-in: {offer['checkInDate']}, Check-out: {offer['checkOutDate']})"
                )

                yield {"type": "message", "text": f"Hotel {idx}. {hotel['hotel']['name']} - {offer['price']['total']} {offer['price']['currency']} (Check-in: {offer['checkInDate']}, Check-out: {offer['checkOutDate']})"}

            preferred_hotel_input = "Enter the number of your preferred hotel to book(by default, it is the first cheapest hotel): "
            preferred_hotel = yield {"type": "prompt", "text": preferred_hotel_input}
            # preferred_hotel = input(preferred_hotel_input)

            if not preferred_hotel or not preferred_hotel.isdigit() or int(preferred_hotel) < 1 or int(preferred_hotel) > len(hotelOfferPriceData):
                preferred_hotel = 1
            else:
                preferred_hotel = int(preferred_hotel)
        else:
            preferred_hotel = 1

        hotelOfferPriceId = hotelOfferPriceData[preferred_hotel-1]["offers"][0]["id"]

        def guest_reference(traveler):
            return {
                "tid": int(traveler["id"]),
                "title":  "MR" if traveler["gender"] == "MALE" else "MS",
                "firstName": traveler["name"]["firstName"],
                "lastName": traveler["name"]["lastName"],
                "phone": traveler["contact"]["phones"][0]["number"],
                "email": traveler["contact"]["emailAddress"]
            }

        guestDetails = [guest_reference(traveler) for traveler in travelers_details]

        orders_url = "https://test.api.amadeus.com/v2/booking/hotel-orders"
        payload = {
            "data": {
                "type": "hotel-order",
                "roomAssociations":[{
                    "guestReferences": [
                        {
                            "guestReference": str(len(guestDetails))
                        }
                        ],
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

        if verbose:
            print("Hotel Order Payload:")
            print(json.dumps(payload, indent=2))

        hotel_api_calls += 1
        try:
            order_response = requests.post(orders_url, headers=headers, json=payload)
            order_response.raise_for_status()
            order_data = order_response.json()
            hotel_api_success += 1
        except requests.RequestException as e:
            error_details = {
                "error": str(e),
                "status_code": getattr(e.response, "status_code", None),
                "reason": getattr(e.response, "reason", None),
                "text": getattr(e.response, "text", None),
                "_hotel_api_calls": hotel_api_calls,
                "_hotel_api_success": hotel_api_success,
            }
            if verbose:
                print(f"Error booking hotel: {error_details}")
            return error_details

        order_data["_hotel_api_calls"] = hotel_api_calls
        order_data["_hotel_api_success"] = hotel_api_success
        return order_data

class ItinerarySuggestionTool(BaseTool):
    """Tool to provide itinerary suggestions based on destination and travel preferences."""
    
    name: str = "itinerary_suggestion"
    description: str = "Generates optimized travel itineraries."
    
    def _run(
        self,
        originLocationCode: str,
        destinationLocationCode: str,
        departureDate: str,
        returnDate: str,
        adults: int,
        travelers_details: List[Dict[str, Any]]= [],
        travelPlanPreference: str = "",
        destinationCountry:str = "",
        destinationCity: str = "",
        originCurrencyCode: str = "",
        max: int = 5,
        verbose: bool = True,
        interactive_mode: bool = True,
        ) -> Dict[str, Any]:
        global llm_calls_count

        """
        Execute the API call to retrieve and provide itinerary.
        """
        if interactive_mode and not travelPlanPreference:
            itinerary_preference_message = "Provide any preference in itinerary: "
            travelPlanPreference = yield {"type": "prompt", "text": itinerary_preference_message}
            # travelPlanPreference = input(itinerary_preference_message)
            
        if not travelPlanPreference:
            travelPlanPreference = "tourism"

        travelPlanPreference = travelPlanPreference.strip()

        itinerary_api_calls = 0
        itinerary_api_success = 0

        client_id = os.getenv('AMADEUS_CLIENT_ID')
        client_secret = os.getenv('AMADEUS_CLIENT_SECRET')

        if not client_id or not client_secret:
            raise ValueError("Amadeus API credentials not found. Set AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET.")

        # First, get an access token
        token_url = 'https://test.api.amadeus.com/v1/security/oauth2/token'
        token_data = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret
        }

        try:
            # Get access token
            data = ""
            if destinationCity and destinationCountry:
                token_response = requests.post(token_url, data=token_data)
                token_response.raise_for_status()
                access_token = token_response.json()['access_token']

                # Prepare API call
                headers = {
                    'Authorization': f'Bearer {access_token}'
                }

                get_coords_url = "https://test.api.amadeus.com/v1/reference-data/locations/cities"
                params = {
                    'countryCode': destinationCountry,
                    'keyword':destinationCity,
                    'max':1
                }
                itinerary_api_calls+=1
                try:
                    get_coords_response = requests.get(get_coords_url, headers=headers, params=params)
                    get_coords_response.raise_for_status()
                    get_coords_response_data = get_coords_response.json()
                    itinerary_api_success += 1
                    if "data" not in get_coords_response_data  or len(get_coords_response_data["data"]) == 0 or "geoCode" not in get_coords_response_data["data"][0]:
                        data = ""
                    else:
                        activities_url = "https://test.api.amadeus.com/v1/shopping/activities"
                        itinerary_api_calls+=1
                        try:
                            activities_response = requests.get(activities_url, headers=headers, params= get_coords_response_data["data"][0]["geoCode"])
                            activities_response.raise_for_status()
                            activities_data = activities_response.json()
                            itinerary_api_success += 1
                            if "data" not in activities_data  or len(activities_data["data"]) == 0:
                                data = ""
                            else:
                                activities_data = activities_data['data'][:50]
                                for activity in activities_data:
                                     if 'description' in activity:
                                         del activity['description']
                                data = json.dumps(activities_data)
                                data = data.replace('{', '{{')
                                data = data.replace('}', '}}')
                        except requests.RequestException as e:
                            print(f"error: {str(e)}, _itinerary_api_calls: {itinerary_api_calls}, _itinerary_api_success: {itinerary_api_success}")
                except requests.RequestException as e:
                    print(f"error: {str(e)}, _itinerary_api_calls: {itinerary_api_calls}, _itinerary_api_success: {itinerary_api_success}")

            system_prompt = f"""
            You are an expert at planning trips in the most optimized way with best suggestions for the given city.

            Here are few suggestions retrieved from the web {data}

            Guidelines:
            - Give priority to the information provided and combine your knowledge, if nothing provided use your knowledge alone to plan
            - Need a day to day plan
            - Suggest top restaurants
            - Tourist places
            - Activities
            - Optimized travel plan

            Return the the entire itinerary as a paragraph as a string with detailed 
            day wise plan incorporating all the guidelines.
            """

            query = f"Plan an optimized trip itinerary for {adults} adults in {destinationLocationCode} starting from {departureDate} to {returnDate} prioritizing user preference: {travelPlanPreference} in the plan."
            
            llm = ChatOpenAI(model=run_itinerary_model, temperature=0)

            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                 ("human", "{query}")
            ])
            
            chain = prompt | llm
            response = chain.invoke({
                "query": query
            })

            itinerary = {}
            itinerary['travel_plan'] = response.content
            itinerary["_itinerary_api_calls"] = itinerary_api_calls
            itinerary["_itinerary_api_success"] = itinerary_api_success
            print(itinerary)
            return itinerary
        except Exception as e:
            error_details = {
                "error": str(e),
                "status_code": getattr(e.response, "status_code", None),
                "reason": getattr(e.response, "reason", None),
                "text": getattr(e.response, "text", None),
                "_itinerary_api_calls": itinerary_api_calls,
                "_itinerary_api_success": itinerary_api_success,
            }
            if verbose:
                print(f"Error booking hotel: {error_details}")
            return error_details

def detect_intent(query: str) -> str:
    """
    Detect the user's intent from the query: 'book flights', 'book hotels', 'get itinerary', or 'book a trip.'
    """

    system_prompt = f"""
    You are a travel assistant. Your task is to classify the user's query into one of the following intents:

    - "book flights": If the user specifically mentions booking or reserving flights, purchasing plane tickets, or arranging air travel.
    - "book hotels": If the user specifically mentions booking hotels, reserving accommodations, or finding a place to stay.
    - "get itinerary or travel plan": If the user asks for a travel itinerary, a detailed plan, a schedule, or recommendations for their trip.
    - "book a trip": If the user requests a full trip booking that includes multiple components like flights, hotels, and activities.

    Guidelines:
    - Return "book flights" for queries related solely to flight bookings.
    - Return "book hotels" for queries related solely to hotel bookings.
    - Return "get itinerary or travel plan" for queries focused on creating or retrieving travel plans.
    - Otherwise, return "book a trip" for general or multi-component trip bookings.

    Output the intent as a single string.

    """
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{query}")
        ])

    chain = prompt | llm
    response = chain.invoke({"query": query})
    return response.content


def initiate_bookings(query: str, interactive_mode: bool = True, verbose: bool = True, use_real_api: bool = True):
    global llm_calls_count
    flight_booking_tool = FlightBookingTool()
    hotel_booking_tool = HotelBookingTool()
    itinerary_tool = ItinerarySuggestionTool()

    flight_tool_openai = convert_to_openai_function(flight_booking_tool)

    if verbose:
        print(f"Flight Tool OpenAI: {json.dumps(flight_tool_openai, indent=2)}")

    flight_params, param_extract_llm_calls_count = yield from extract_parameters_with_llm(query, flight_tool_openai, extract_parameters_model, interactive_mode, verbose)
    llm_calls_count += param_extract_llm_calls_count

    travelers_details = []

    llm_calls_count += 1
    user_intent = detect_intent(query)

    if verbose:
        print(f"User Intent: {user_intent}")

    if 'itinerary' not in user_intent and 'plan' not in user_intent:
        travelers_details, traveler_extract_llm_calls = yield from extract_traveler_details(extract_parameters_model, query, interactive_mode, verbose)
        llm_calls_count += traveler_extract_llm_calls
        id = 1
        for traveler_details in travelers_details:
            traveler_details['id'] = str(id)
            id +=1

        # Run this code only to prompt for additional travelers. Do not run this code when running on the entire dataset
        if interactive_mode:
            while True:
                add_more_message = "Do you want to add another traveler? (yes/no): "
                add_more = yield {"type": "prompt", "text": add_more_message}
                # add_more = input(add_more_message)

                print(f"Add More: {add_more}")
                
                if not add_more or add_more.lower() != 'yes':
                    break
                
                additional_traveler_input_message = "Enter additional traveler details: "
                additional_traveler = yield {"type": "prompt", "text": additional_traveler_input_message}
                # additional_traveler = input(additional_traveler_input_message)
                
                additional_traveler_details, traveler_extract_llm_calls = yield from extract_traveler_details(extract_parameters_model, additional_traveler, interactive_mode, verbose)
                llm_calls_count += traveler_extract_llm_calls
                for traveler_details in additional_traveler_details:
                    traveler_details['id'] = str(id)
                    id+=1
                    travelers_details.append(traveler_details)
    
    # Combine parameters for booking
    booking_params = {
        'originLocationCode': flight_params.get('originLocationCode', ''),
        'destinationLocationCode': flight_params.get('destinationLocationCode', ''),
        'departureDate': flight_params.get('departureDate', ''),
        'returnDate': flight_params.get('returnDate', ''),
        'adults': len(travelers_details),
        'max': flight_params.get('max', 5),
        'travelPlanPreference': flight_params.get('travelPlanPreference', ''),
        'destinationCountry':  flight_params.get('destinationCountry', ''),
        'destinationCity':  flight_params.get('destinationCity', ''),
        'originCurrencyCode':  flight_params.get('originCurrencyCode', ''),
        'travelers_details': travelers_details,
    }

    if verbose:
        print("\nBooking Parameters Before Extracting Missing Values:")
        print(json.dumps(booking_params, indent=2))

    booking_params, llm_calls_made = extract_missing_booking_parameters(
        booking_params=booking_params,
        extract_parameters_model=extract_parameters_model,
        verbose=verbose,
    )

    llm_calls_count += llm_calls_made

    # HARDCODED BOOKING PARAM FOR TESTING
    # booking_params = {
    #     "originLocationCode": "DEL",
    #     "destinationLocationCode": "JFK",
    #     "departureDate": "2024-12-20",
    #     "returnDate": "2025-01-05",
    #     "adults": 1,
    #     "max": 5,
    #     "travelPlanPreference": "",
    #     "destinationCountry": "US",
    #     "destinationCity": "New York",
    #     "originCurrencyCode": "INR",
    #     "travelers_details": [
    #     {
    #         "dateOfBirth": "1998-03-07",
    #         "name": {
    #         "firstName": "RD",
    #         "lastName": "SINGH"
    #         },
    #         "gender": "MALE",
    #         "contact": {
    #         "emailAddress": "jnnj@gmail.com",
    #         "phones": [
    #             {
    #             "deviceType": "MOBILE",
    #             "countryCallingCode": 1,
    #             "number": "9144471153"
    #             }
    #         ]
    #         },
    #         "id": "1"
    #     }
    #     ]
    # }

    if verbose:
        print("\nBooking Parameters:")
        print(json.dumps(booking_params, indent=2))
    
    # Do not hit the real API when testing only the extracted parameters
    if not use_real_api:
        return {
            "booking_params": booking_params,
            "total_api_calls": 0,
            "successful_api_calls": 0,
            "llm_calls": llm_calls_count
        }
    
    flight_booking_result, hotel_booking_result, itinerary_result = {}, {}, {}
    if 'flight' in user_intent:
       flight_booking_result = yield from flight_booking_tool._run(**booking_params, verbose=verbose, interactive_mode=interactive_mode)
    elif 'hotel' in user_intent:
        hotel_booking_result = yield from hotel_booking_tool._run(**booking_params, verbose=verbose, interactive_mode=interactive_mode)
    elif 'itinerary' in user_intent or 'plan' in user_intent:
        itinerary_result = yield from itinerary_tool._run(**booking_params, verbose=verbose, interactive_mode=interactive_mode)

    else:
        flight_booking_result = yield from flight_booking_tool._run(**booking_params, verbose=verbose, interactive_mode=interactive_mode)
        hotel_booking_result = yield from hotel_booking_tool._run(**booking_params, verbose=verbose, interactive_mode=interactive_mode)
        itinerary_result = yield from itinerary_tool._run(**booking_params, verbose=verbose, interactive_mode=interactive_mode)

    # Display booking details
    if verbose:
        print("\nBooking Details:")
        print(flight_booking_result)

        print(json.dumps(flight_booking_result, indent=2))

        print("\nHotel Booking Details:")
        print(json.dumps(hotel_booking_result, indent=2))
        
        print("\nItinerary:")
        print(json.dumps(itinerary_result, indent=2))

    llm_calls_count += 1

    complete_summary = convert_to_human_readable_result(flight_booking_result, hotel_booking_result, itinerary_result, convert_to_human_results_model, verbose)

    flight_api_calls = flight_booking_result.get("_flight_api_calls", 0)
    flight_api_success = flight_booking_result.get("_flight_api_success", 0)

    hotel_api_calls = hotel_booking_result.get("_hotel_api_calls", 0)
    hotel_api_success = hotel_booking_result.get("_hotel_api_success", 0)

    itinerary_api_calls = itinerary_result.get("_itinerary_api_calls", 0)
    itinerary_api_success = itinerary_result.get("_itinerary_api_success", 0)

    return {
        "booking_params": booking_params,
        "flight_booking_result": flight_booking_result,
        "hotel_booking_result": hotel_booking_result,
        "itinerary_result": itinerary_result,
        "flight_api_calls": flight_api_calls,
        "flight_api_success": flight_api_success,
        "hotel_api_calls": hotel_api_calls,
        "hotel_api_success": hotel_api_success,
        "itinerary_api_calls": itinerary_api_calls,
        "itinerary_api_success": itinerary_api_success,
        "llm_calls": llm_calls_count,
        "complete_summary": complete_summary,
        "intent": user_intent
    }
