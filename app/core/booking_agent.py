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
from helpers import extract_parameters_with_llm, extract_traveler_details, convert_to_human_readable_result, extract_missing_booking_parameters

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
            params['originCurrencyCode'] = originCurrencyCode
            
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
        
            preferred_flight = input("Enter the number of your preferred flight to book(by default, it is the first cheapest flight): ")
            if not preferred_flight.isdigit() or int(preferred_flight) < 1 or int(preferred_flight) > len(flight_details):
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
        
        flightOfferPriceData = pricing_data["data"]["flightOffers"][0]

        # Flight order
        orders_url = "https://test.api.amadeus.com/v1/booking/flight-orders"
        payload = {
            "data": {
                "type": "flight-order",
                "flightOffers": [
                    flightOfferPriceData
                ],
                "travelers": travelers_details
            }
        }
        flight_api_calls += 1
        try:
            order_response = requests.post(orders_url, headers=headers, json=payload)
            order_response.raise_for_status()
            order_data = order_response.json()
            flight_api_success += 1
        except requests.RequestException as e:
            return {"error": str(e), "_flight_api_calls": flight_api_calls, "_flight_api_success": flight_api_success}

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
        travelers_details: List[Dict[str, Any]],
        travelPlanPreference: str = "",
        destinationCountry:str = "",
        destinationCity: str = "",
        originCurrencyCode: str = "",
        max: int = 5,
        interactive_mode: bool = True,
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
        
            preferred_hotel = input("Enter the number of your preferred hotel to book(by default, it is the first cheapest hotel): ")
            if not preferred_hotel.isdigit() or int(preferred_hotel) < 1 or int(preferred_hotel) > len(hotelOfferPriceData):
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

        hotel_api_calls += 1
        try:
            order_response = requests.post(orders_url, headers=headers, json=payload)
            order_response.raise_for_status()
            order_data = order_response.json()
            hotel_api_success += 1
        except requests.RequestException as e:
            return {"error": str(e), "_hotel_api_calls": hotel_api_calls, "_hotel_api_success": hotel_api_success}

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
        travelers_details: List[Dict[str, Any]],
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
            travelPlanPreference = input("Provide any preference in itinerary: ").strip()

        if not travelPlanPreference:
            travelPlanPreference = "tourism"

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
                                data = json.dumps(activities_data['data'][:50])
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

            Return the valid JSON of the entire itinerary as a paragraph as a field optimized_travel_plan with detailed 
            day wise plan incorporating all the guidelines.
            """

            query = f"Plan an optimized trip itinerary for {adults} adults in {destinationLocationCode} starting from {departureDate} to {returnDate} prioritizing user preference: {travelPlanPreference} in the plan."
            
            llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                 ("human", "{query}")
            ])
            
            chain = prompt | llm
            response = chain.invoke({
                "query": query
            })

            itinerary = response.content

            return itinerary
        except Exception as e:
            print(f"Error extracting itinerary: {e}")
        return ""

def initiate_bookings(query: str, interactive_mode: bool = True, verbose: bool = True, use_real_api: bool = True):
    global llm_calls_count
    flight_booking_tool = FlightBookingTool()
    hotel_booking_tool = HotelBookingTool()
    itinerary_tool = ItinerarySuggestionTool()

    flight_tool_openai = convert_to_openai_function(flight_booking_tool)

    if verbose:
        print(f"Flight Tool OpenAI: {json.dumps(flight_tool_openai, indent=2)}")

    flight_params, param_extract_llm_calls_count = extract_parameters_with_llm(query, flight_tool_openai, extract_parameters_model, interactive_mode, verbose)
    llm_calls_count += param_extract_llm_calls_count

    travelers_details = []
    
    traveler_details, traveler_extract_llm_calls = extract_traveler_details(extract_parameters_model, query, interactive_mode, verbose)
    llm_calls_count += traveler_extract_llm_calls
    traveler_details['id'] = '1'
    travelers_details.append(traveler_details)

    # Run this code only to prompt for additional travelers. Do not run this code when running on the entire dataset
    if interactive_mode:
        while True:
            add_more = input("Do you want to add another traveler? (yes/no): ").lower()
            if add_more != 'yes':
                break
            
            additional_traveler = input("Enter additional traveler details: ")
            additional_traveler_details, traveler_extract_llm_calls = extract_traveler_details(extract_parameters_model, additional_traveler, interactive_mode, verbose)
            llm_calls_count += traveler_extract_llm_calls
            additional_traveler_details['id'] = str(len(travelers_details) + 1)
            travelers_details.append(additional_traveler_details)

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
        extract_parameters_model=extract_parameters_model
    )

    llm_calls_count += llm_calls_made

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
    
    flight_booking_result = flight_booking_tool._run(**booking_params, verbose=verbose, interactive_mode=interactive_mode)
    hotel_booking_result = hotel_booking_tool._run(**booking_params, interactive_mode=interactive_mode)
    itinerary_result = itinerary_tool._run(**booking_params, verbose=verbose, interactive_mode=interactive_mode)

    # Display booking details
    if verbose:
        print("\nBooking Details:")
        print(json.dumps(flight_booking_result, indent=2))

        print("\nHotel Booking Details:")
        print(json.dumps(hotel_booking_result, indent=2))
        
        print("\nItinerary:")
        print(json.dumps(itinerary_result, indent=2))

    llm_calls_count += 1
    convert_to_human_readable_result(flight_booking_result, hotel_booking_result, itinerary_result, convert_to_human_results_model, verbose)

    flight_api_calls = flight_booking_result.get("_flight_api_calls", 0)
    flight_api_success = flight_booking_result.get("_flight_api_success", 0)

    hotel_api_calls = hotel_booking_result.get("_hotel_api_calls", 0)
    hotel_api_success = hotel_booking_result.get("_hotel_api_success", 0)

    return {
        "booking_params": booking_params,
        "flight_booking_result": flight_booking_result,
        "hotel_booking_result": hotel_booking_result,
        "itinerary_result": itinerary_result,
        "flight_api_calls": flight_api_calls,
        "flight_api_success": flight_api_success,
        "hotel_api_calls": hotel_api_calls,
        "hotel_api_success": hotel_api_success,
        "llm_calls": llm_calls_count
    }