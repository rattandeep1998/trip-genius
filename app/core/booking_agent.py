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

extract_parameters_model = "gpt-3.5-turbo"
run_itinerary_model = "gpt-3.5-turbo"
convert_to_human_results_model = "gpt-3.5-turbo"

# Global counter for LLM calls
llm_calls_count = 0

class AmadeusFlightBookingTool(BaseTool):
    """Tool to retrieve and book flight offers from Amadeus API with dynamic traveler details."""
    
    name: str = "amadeus_flight_booking"
    description: str = "Books flight offers from the Amadeus API with dynamic traveler information."
    
    @staticmethod
    def extract_param_llm_call(param: str, input_value: str, verbose: bool = True) -> str:
        global llm_calls_count
        system_prompt = f"""
        You are an expert at extracting structured parameters for a flight booking API function.

        Extract the value of the parameter '{param}' from the give user input.

        Extraction Guidelines:
        1. Carefully analyze the user query to extract values for each parameter
        2. Match parameters exactly as specified in the function specification
        3. Use exact IATA codes for locations if possible. If city names are given, use the main airport code
        4. Use YYYY-MM-DD format for dates. If the year is not given, assume current year for the date.
        5. If travel plan preference is not detected or not provided, return the value as tourism

        Output Instructions:
        - Return a valid string with extracted parameter value
        - Ensure type compatibility
        - If unsure about a parameter, return empty string
        """

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input_value}")
        ])

        llm = ChatOpenAI(model=extract_parameters_model, temperature=0)        
        chain = prompt | llm
        
        llm_calls_count += 1
        response = chain.invoke({
            "input_value": input_value
        })

        if verbose:
            print(f"Extracted Parameter '{param}': {response.content}")

        return response.content

    @classmethod
    def extract_parameters_with_llm(
        cls, 
        query: str,
        function_spec: Dict[str, Any],
        interactive_mode: bool = True,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        global llm_calls_count
        parameters_details = "\n\t".join([
            f"- {param}: {cls._get_parameter_description(param)} "
            f"(Type: {details.get('type', 'unknown')}, "
            f"Required: {'Yes' if param in function_spec['parameters'].get('required', []) else 'No'})"
            for param, details in function_spec['parameters']['properties'].items()
        ])

        system_prompt = f"""
        You are an expert at extracting structured parameters for a flight booking API function. Extract the values of the parameters from the given user query and strictly do not make up any information.

        API Function Specification Details:
        Name: {function_spec.get('name', 'Unknown')}
        Description: {function_spec.get('description', 'No description')}

        Parameters:
        {parameters_details}

        Extraction Guidelines:
        1. Carefully analyze the user query to extract values for each parameter
        2. Match parameters exactly as specified in the function specification
        3. Do not make up any information and default to null if unsure
        4. Use exact IATA codes for locations if possible. If city names are given, use the main airport code
        5. Use YYYY-MM-DD format for dates
        6. If origin location is not provided, then default originLocationCode to null
        7. If destination location is not provided, then default destinationLocationCode to null
        8. If departure date is not provided, then default departureDate to null
        9. If return date is not provided, then default returnDate to null
        10. If number of adults is not provided, then default adults to 1
        11. If max number of flight offers is not provided, then default max to 5
        12. Currency code is the currency of the source location user is travelling

        Output Instructions:
        - Return a valid JSON object with extracted parameters
        - Only include parameters you can confidently extract
        - Ensure type compatibility
        - If unsure about a parameter, do not include it
        """

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{query}")
        ])

        llm = ChatOpenAI(model=extract_parameters_model, temperature=0)
        chain = prompt | llm
        
        llm_calls_count += 1
        response = chain.invoke({
            "query": query
        })
        
        try:
            extracted_params = json.loads(response.content)

        except json.JSONDecodeError:
            extracted_params = {
                "adults": 1,
                "max": 5
            }
        
        if not interactive_mode:
            return extracted_params
        
        # Remove extracted parameters whose value is null
        extracted_params = {k: v for k, v in extracted_params.items() if v is not None}

        print(f"Extracted Parameters: {json.dumps(extracted_params, indent=2)}")

        required_params = function_spec['parameters'].get('required', [])

        for param in required_params:
            while param not in extracted_params:
                input_value = input(f"Please provide a value for '{param}' - {cls._get_parameter_description(param)}: ").strip()
                extracted_params[param] = cls.extract_param_llm_call(param, input_value, verbose)
                #print(f"'{param}' is a required parameter. Please provide a value.")

        return extracted_params
    
    @staticmethod
    def _get_parameter_description(param: str) -> str:
        descriptions = {
            'originLocationCode': 'City/airport IATA code from which the traveler will depart (e.g., JFK for New York)',
            'destinationLocationCode': 'City/airport IATA code to which the traveler is going (e.g., DEL for Delhi)',
            'departureDate': 'Date of departure in ISO 8601 YYYY-MM-DD format (e.g., 2024-12-30)',
            'returnDate': 'Date of return in ISO 8601 YYYY-MM-DD format (e.g., 2025-01-05)',
            'adults': 'Number of adult travelers (age 12 or older)',
            'max': 'Maximum number of flight offers to return (must be >= 1, default 250)',
            'travelPlanPreference': 'Preference for itinerary (Take from user input, leave empty if not specified explicitly)',
            'country':'Country code of the destination location(e.g., US for New York). Donot leave empty',
            'city':'Full city name of the destination city(e.g., New York City for New York or NYC).  Donot leave empty',
            'currencyCode':'Country currency of the source location(originLocationCode e.g., USD for New York). Donot leave empty',
        }
        return descriptions.get(param, 'No description available')
    
    def parse_extracted_details(self, traveler_details: Dict[str, Any], verbose: bool = True) -> Dict[str, Any]:
        global llm_calls_count
        system_prompt = """
        You are an expert at extracting structured traveler details.
        Parse and convert the traveler details values to the required format.

        Extract the following details about a traveler:
        1. Full Name (First and Last Name)
        2. Date of Birth
        3. Gender
        4. Email Address
        5. Phone Number
        
        Output Format (JSON):
        {{
            dateOfBirth: YYYY-MM-DD,
            name: {{
                firstName: FIRST_NAME,
                lastName: LAST_NAME
            }},
            gender: MALE/FEMALE,
            contact: {{
                emailAddress: valid_email@example.com,
                phones: [
                    {{
                        deviceType: MOBILE,
                        countryCallingCode: COUNTRY_CODE,
                        number: PHONE_NUMBER
                    }}
                ]
            }}
        }}
        
        Guidelines:
        - Use uppercase for names
        - Validate email format
        - Format phone number without country code. Remove + or 00 from the country code
        - Convert M/F to MALE/FEMALE for gender
        - If country code is missing, default country code is 1
        - If any detail is missing, leave it as is in the input
        - Do not make up information
        - The output should be in same format as input json
        """
        
        llm = ChatOpenAI(model=extract_parameters_model, temperature=0)        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{traveler_input}")
        ])
        
        chain = prompt | llm
        traveler_details_str = json.dumps(traveler_details)

        try:
            llm_calls_count += 1

            parsed_traveller_details = chain.invoke({"traveler_input": traveler_details_str})
            parsed_traveller_details = json.loads(parsed_traveller_details.content)

            if verbose:
                print(f"Parsed Traveler Details: {json.dumps(parsed_traveller_details, indent=2)}")

            return parsed_traveller_details
        except Exception as e:
            if verbose:
                print(f"Error parsing traveler details: {e}")
            return traveler_details

    def extract_traveler_details(self, traveler_input: str = None, interactive_mode: bool = True, verbose: bool = True):
        global llm_calls_count

        system_prompt = """
        You are an expert at extracting structured traveler details from natural language input.
        
        Extract the following details about a traveler:
        1. Full Name (First and Last Name)
        2. Date of Birth
        3. Gender
        4. Email Address
        5. Phone Number
        
        Output Format (JSON):
        {{
            dateOfBirth: YYYY-MM-DD,
            name: {{
                firstName: FIRST_NAME,
                lastName: LAST_NAME
            }},
            gender: MALE/FEMALE,
            contact: {{
                emailAddress: valid_email@example.com,
                phones: [
                    {{
                        deviceType: MOBILE,
                        countryCallingCode: COUNTRY_CODE,
                        number: PHONE_NUMBER
                    }}
                ]
            }}
        }}
        
        Guidelines:
        - Do not make up any information and default to null if unsure
        - Use uppercase for names
        - Validate email format
        - Format phone number with country code if present
        - Try to infer gender of the traveller from the input if not provided
        - If any other detail is missing, return null for that field
        """
        
        llm = ChatOpenAI(model=extract_parameters_model, temperature=0)        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{traveler_input}")
        ])
        
        chain = prompt | llm
        
        extracted_details = {}
        if traveler_input:
            try:
                if verbose:
                    print(f"Traveller Details Input: {traveler_input}")
                
                llm_calls_count += 1
                response = chain.invoke({"traveler_input": traveler_input})
                extracted_details = json.loads(response.content)
            except Exception as e:
                extracted_details = {}
                print(f"Error extracting traveler details: {e}")
        
        if verbose:
            print(f"Extracted Traveler Details: {json.dumps(extracted_details, indent=2)}")

        # If not is iterative mode and function is run on the entire dataset, then return the extracted parameters without asking for human input
        if not interactive_mode:
            return extracted_details
        
        # Interactive validation and completion
        def validate_input(prompt_text, validator=None):
            while True:
                user_input = input(prompt_text).strip()
                if validator is None or validator(user_input):
                    return user_input
        
        # Validate and complete full name
        if not extracted_details.get('name') or not all(extracted_details['name'].values()):
            full_name = validate_input("Enter full name (First Last): ")
            name_parts = full_name.split()
            extracted_details['name'] = {
                "firstName": name_parts[0].upper(),
                "lastName": ' '.join(name_parts[1:]).upper()
            }
        
        # Validate date of birth
        if not extracted_details.get('dateOfBirth'):
            dob = validate_input("Enter date of birth: ")
            # The DOB will be parsed by the LLM call
            extracted_details['dateOfBirth'] = dob

            # while True:
            #     dob = validate_input("Enter date of birth (YYYY-MM-DD): ")
            #     try:
            #         datetime.strptime(dob, "%Y-%m-%d")
            #         extracted_details['dateOfBirth'] = dob
            #         break
            #     except ValueError:
            #         print("Invalid date format. Use YYYY-MM-DD.")
        
        # Validate gender
        if not extracted_details.get('gender'):
            gender = validate_input("Enter gender: ")
            extracted_details['gender'] = gender

            # gender = validate_input(
            #     "Enter gender (Male/Female): ", 
            #     lambda g: g.upper() in ['MALE', 'FEMALE']
            # ).upper()
            # extracted_details['gender'] = gender
        
        # Validate email
        if not extracted_details.get('contact') or not extracted_details['contact'].get('emailAddress'):
            email = validate_input(
                "Enter email address: ", 
                lambda e: '@' in e and '.' in e
            )

            if not extracted_details.get('contact'):
                extracted_details['contact'] = {}

            extracted_details['contact']['emailAddress'] = email
        
        # Validate phone number
        if not extracted_details['contact'].get('phones') or not extracted_details['contact']['phones'][0].get('number') or not extracted_details['contact']['phones'][0].get('countryCallingCode'):
            phone = validate_input("Enter phone number (with country code): ")
            
            if len(phone) > 10:
                country_code = ''.join(filter(str.isdigit, phone[:-10]))
            else:
                country_code = '1'  # Default country code
            
            number = ''.join(filter(str.isdigit, phone[-10:]))
            
            extracted_details['contact']['phones'] = [{
                "deviceType": "MOBILE",
                "countryCallingCode": country_code,
                "number": number
            }]
        
        if verbose:
            print(f"Traveler details before parsing: {json.dumps(extracted_details, indent=2)}")
        
        extracted_details = self.parse_extracted_details(extracted_details, verbose)

        return extracted_details
    
    def _run(
        self, 
        originLocationCode: str, 
        destinationLocationCode: str, 
        departureDate: str,
        returnDate: str,
        travelPlanPreference: str,
        country:str,
        city:str,
        currencyCode:str,
        travelers_details: List[Dict[str, Any]] = [],
        adults: int = 1,
        max: int = 5,
        verbose: bool = True,
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
            'currencyCode':currencyCode,
        }
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

    def _run_hotel_booking(
        self,
        originLocationCode: str,
        destinationLocationCode: str,
        departureDate: str,
        returnDate: str,
        adults: int,
        travelPlanPreference: str,
        country:str,
        city:str,
        currencyCode:str,
        travelers_details: List[Dict[str, Any]],
        max: int = 5,
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
            'currency':currencyCode
        }

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

    def _run_itinerary(
        self,
        originLocationCode: str,
        destinationLocationCode: str,
        departureDate: str,
        returnDate: str,
        adults: int,
        travelPlanPreference: str,
        country:str,
        city:str,
        currencyCode:str,
        travelers_details: List[Dict[str, Any]],
        max: int = 5,
        verbose: bool = True,
        ) -> Dict[str, Any]:
        global llm_calls_count

        """
        Execute the API call to retrieve and provide itinerary.
        """

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
            token_response = requests.post(token_url, data=token_data)
            token_response.raise_for_status()
            access_token = token_response.json()['access_token']

            # Prepare API call
            headers = {
                'Authorization': f'Bearer {access_token}'
            }

            get_coords_url = "https://test.api.amadeus.com/v1/reference-data/locations/cities"
            params = {
                'countryCode': country,
                'keyword':city,
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
        # except requests.RequestException as e:
        #   print(f"error: {str(e)}, _itinerary_api_calls: {itinerary_api_calls}, _itinerary_api_success: {itinerary_api_success}")
            
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
            

            # Initialize the LLM
            llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

            # Create the prompt template
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

def convert_to_human_readable_result(flight_booking_result: Dict[str, Any], hotel_booking_result: Dict[str, Any], itinerary_result: str, verbose: bool = True):
    global llm_calls_count

    system_prompt = """
    You are an expert at converting structured booking results into human-readable format.
    You have the results from flight and hotel bookings.
    Your task is to extract only the relevant details and output them in a concise format in a single sentence.
    """
        
    llm = ChatOpenAI(model=convert_to_human_results_model, temperature=0)        
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{flight_booking_result} {hotel_booking_result}")
    ])
        
    chain = prompt | llm
    
    try:
        # Invoke LLM
        llm_calls_count += 1

        response = chain.invoke({
            "flight_booking_result": json.dumps(flight_booking_result),
            "hotel_booking_result": json.dumps(hotel_booking_result),
        })
        complete_summary = response.content + " \nTravel Plan:\n" + itinerary_result
        
        if verbose:
            print(f"Human Readable Result: {complete_summary}")
        
    except Exception as e:
        if verbose:
            print(f"Error converting to human-readable result: {e}")


def initiate_bookings(query: str, interactive_mode: bool = True, verbose: bool = True, use_real_api: bool = True) -> Dict[str, Any]:
    flight_tool = AmadeusFlightBookingTool()
    flight_tool_openai = convert_to_openai_function(flight_tool)

    if verbose:
        print(f"Flight Tool OpenAI: {json.dumps(flight_tool_openai, indent=2)}")

    flight_params = AmadeusFlightBookingTool.extract_parameters_with_llm(
        query, 
        flight_tool_openai,
        interactive_mode,
        verbose
    )

    if verbose: 
        print(f"Flight Parameters: {json.dumps(flight_params, indent=2)}")
    
    travelers_details = []
    
    traveler_details = flight_tool.extract_traveler_details(query, interactive_mode, verbose)
    traveler_details['id'] = '1'
    travelers_details.append(traveler_details)

    # Run this code only to prompt for additional travelers. Do not run this code when running on the entire dataset
    if interactive_mode:
        while True:
            add_more = input("Do you want to add another traveler? (yes/no): ").lower()
            if add_more != 'yes':
                break
            
            additional_traveler = input("Enter additional traveler details: ")
            additional_traveler_details = flight_tool.extract_traveler_details(additional_traveler, interactive_mode, verbose)
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
        'travelers_details': travelers_details,
        'travelPlanPreference': flight_params.get('travelPlanPreference', ''),
        'country':  flight_params.get('country', ''),
        'city':  flight_params.get('city', ''),
        'currencyCode':  flight_params.get('currencyCode', '')
    }
    
    if verbose:
        print("\nFlight Booking Parameters:")
        print(json.dumps(booking_params, indent=2))
    
    # Do not hit the real API when testing only the extracted parameters
    if not use_real_api:
        return {
            "booking_params": booking_params,
            "total_api_calls": 0,
            "successful_api_calls": 0,
            "llm_calls": llm_calls_count
        }
    
    flight_booking_result = flight_tool._run(**booking_params, verbose=verbose)
    hotel_booking_result = flight_tool._run_hotel_booking(**booking_params)
    itinerary_result = flight_tool._run_itinerary(**booking_params, verbose=verbose)

    # Display booking details
    if verbose:
        print("\nBooking Details:")
        print(json.dumps(flight_booking_result, indent=2))

        print("\nHotel Booking Details:")
        print(json.dumps(hotel_booking_result, indent=2))
        
        print("\Itinerary:")
        print(json.dumps(itinerary_result, indent=2))

    convert_to_human_readable_result(flight_booking_result, hotel_booking_result, itinerary_result, verbose)

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
