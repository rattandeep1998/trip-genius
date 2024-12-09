import dotenv
dotenv.load_dotenv()

import os
import json
from typing import Dict, Any, List
import requests
import traceback
from datetime import datetime
from langchain.tools import BaseTool
from langchain_core.utils.function_calling import format_tool_to_openai_function
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

class AmadeusFlightBookingTool(BaseTool):
    """Tool to retrieve and book flight offers from Amadeus API with dynamic traveler details."""
    
    name: str = "amadeus_flight_booking"
    description: str = "Books flight offers from the Amadeus API with dynamic traveler information."
    
    @staticmethod
    def extract_param_llm_call(param: str, input_value: str) -> str:
        system_prompt = f"""
        You are an expert at extracting structured parameters for a flight booking API function.

        Extract the value of the parameter '{param}' from the give user input.

        Extraction Guidelines:
        1. Carefully analyze the user query to extract values for each parameter
        2. Match parameters exactly as specified in the function specification
        3. Use exact IATA codes for locations if possible. If city names are given, use the main airport code
        4. Use YYYY-MM-DD format for dates. If the year is not given, assume current year for the date.

        Output Instructions:
        - Return a valid string with extracted parameter value
        - Ensure type compatibility
        - If unsure about a parameter, return empty string
        """

        # Create the prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input_value}")
        ])

        # Initialize the LLM
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        
        # Create the chain
        chain = prompt | llm
        
        # Generate the response
        response = chain.invoke({
            "input_value": input_value
        })

        print(f"Extracted Parameter '{param}': {response.content}")

        return response.content

    @classmethod
    def extract_parameters_with_llm(
        cls, 
        query: str, 
        function_spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract API parameters using LLM based on function specification.
        """
        # Prepare a detailed description of parameters
        parameters_details = "\n\t".join([
            f"- {param}: {cls._get_parameter_description(param)} "
            f"(Type: {details.get('type', 'unknown')}, "
            f"Required: {'Yes' if param in function_spec['parameters'].get('required', []) else 'No'})"
            for param, details in function_spec['parameters']['properties'].items()
        ])

        # Create the system prompt
        system_prompt = f"""
        You are an expert at extracting structured parameters for a flight booking API function.

        API Function Specification Details:
        Name: {function_spec.get('name', 'Unknown')}
        Description: {function_spec.get('description', 'No description')}

        Parameters:
        {parameters_details}

        Extraction Guidelines:
        1. Carefully analyze the user query to extract values for each parameter
        2. Match parameters exactly as specified in the function specification
        3. Use exact IATA codes for locations if possible. If city names are given, use the main airport code
        4. Use YYYY-MM-DD format for dates
        5. Default to 1 adult traveler if not specified
        6. Identify key flight details: origin, destination, date
        
        Output Instructions:
        - Return a valid JSON object with extracted parameters
        - Only include parameters you can confidently extract
        - Ensure type compatibility
        - If unsure about a parameter, do not include it
        """

        # Create the prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{query}")
        ])

        # Initialize the LLM
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        
        # Create the chain
        chain = prompt | llm
        
        # Generate the response
        response = chain.invoke({
            "query": query
        })
        
        # Extract and parse the parameters
        try:
            # Try to parse the LLM response as JSON
            extracted_params = json.loads(response.content)
            
            # Validate required parameters
            required_params = function_spec['parameters'].get('required', [])

            # print(f"Required Parameters: {required_params}")

            for param in required_params:
                if param not in extracted_params:
                    input_value = input(f"Please provide a value for '{param}': ").strip()
                    if input_value:
                        extracted_params[param] = cls.extract_param_llm_call(param, input_value)
                    else:
                        raise ValueError(f"Missing required parameter: {param} - No value provided.")
                        # raise ValueError(f"Missing required parameter: {param}")
            
            return extracted_params
        
        except json.JSONDecodeError:
            # Fallback to minimal defaults
            return {
                "adults": 1,
                "max": 5
            }
    
    @staticmethod
    def _get_parameter_description(param: str) -> str:
        """
        Provide detailed descriptions for each parameter.
        """
        descriptions = {
            'originLocationCode': 'City/airport IATA code from which the traveler will depart (e.g., JFK for New York)',
            'destinationLocationCode': 'City/airport IATA code to which the traveler is going (e.g., DEL for Delhi)',
            'departureDate': 'Date of departure in ISO 8601 YYYY-MM-DD format (e.g., 2024-12-30)',
            'returnDate': 'Date of return in ISO 8601 YYYY-MM-DD format (e.g., 2025-01-05)',
            'adults': 'Number of adult travelers (age 12 or older)',
            'max': 'Maximum number of flight offers to return (must be >= 1, default 250)'
        }
        return descriptions.get(param, 'No description available')
    
    def parse_extracted_details(self, traveler_details: Dict[str, Any]) -> Dict[str, Any]:
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
        
        # Initialize the LLM
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        
        # Create the prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{traveler_input}")
        ])
        
        # print(f"Prompt Template: {prompt}")

        # Create the chain
        chain = prompt | llm
        
        traveler_details = json.dumps(traveler_details)

        try:            
            parsed_traveller_details = chain.invoke({"traveler_input": traveler_details})
            parsed_traveller_details = json.loads(parsed_traveller_details.content)

            print(f"Parsed Traveler Details: {json.dumps(parsed_traveller_details, indent=2)}")

            return parsed_traveller_details
        except Exception as e:
            print(f"Error parsing traveler details: {e}")
            return traveler_details

    def extract_traveler_details(self, traveler_input: str = None) -> Dict[str, Any]:
        """
        Extract and validate traveler details interactively.
        
        Args:
            traveler_input (str, optional): Initial traveler information from query
        
        Returns:
            Dict[str, Any]: Structured traveler details
        """
        # Prepare a detailed system prompt for traveler details extraction
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
        - Use uppercase for names
        - Validate email format
        - Format phone number with country code
        - If any detail is missing, return null for that field
        - Do not make up information
        """
        
        # Initialize the LLM
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        
        # Create the prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{traveler_input}")
        ])
        
        # print(f"Prompt Template: {prompt}")

        # Create the chain
        chain = prompt | llm
        
        # Extract initial details
        extracted_details = {}
        if traveler_input:
            try:
                print(f"Traveller Details Input: {traveler_input}")
                response = chain.invoke({"traveler_input": traveler_input})
                extracted_details = json.loads(response.content)
            except Exception as e:
                extracted_details = {}
                print(f"Error extracting traveler details: {e}")
        
        print(f"Extracted Traveler Details: {json.dumps(extracted_details, indent=2)}")

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
        if not extracted_details['contact'].get('phones'):
            phone = validate_input("Enter phone number (with country code): ")
            
            # Ensure the country code contains only numbers and is free of any signs
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
        
        print(f"Traveler details before parsing: {json.dumps(extracted_details, indent=2)}")
        extracted_details = self.parse_extracted_details(extracted_details)

        return extracted_details
    
    def _run(
        self, 
        originLocationCode: str, 
        destinationLocationCode: str, 
        departureDate: str,
        returnDate: str,
        card_details: str = "",
        travelers_details: List[Dict[str, Any]] = [],
        adults: int = 1,
        max: int = 5,
    ) -> Dict[str, Any]:
        """
        Execute the API call to retrieve and book flight offers.
        [Previous implementation would be used here]
        """
        """
        Execute the API call to retrieve flight offers.
        """
        # Retrieve API credentials from environment variables
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
                'max': max
            }
            
            # Make the API call
            response = requests.get(api_url, headers=headers, params=params)
            response.raise_for_status()
            
            results = response.json()

            if "data" not in results or len(results["data"]) == 0:
                print("No flight offers found.")
                return {"error": "No flight offers found."}

            flightOfferData = results["data"][0]  # taking the first flight offer

            pricing_url = "https://test.api.amadeus.com/v1/shopping/flight-offers/pricing"

            payload = {
                "data": {
                    "type": "flight-offers-pricing",
                    "flightOffers": [
                        flightOfferData
                    ]
                }
            }

            pricing_response = requests.post(pricing_url, headers=headers, json=payload)
            pricing_response.raise_for_status()
            pricing_data = pricing_response.json()
            print("Flight Offer Pricing Results:")
            print(json.dumps(pricing_data, indent=2))

            if "data" not in pricing_data or "flightOffers" not in pricing_data["data"] or len(pricing_data["data"]["flightOffers"]) == 0:
                print("No priced flight offers found.")
                return {"error": "No priced flight offers found."}
            
            flightOfferPriceData = pricing_data["data"]["flightOffers"][0]

            print(f"Flight Offer Price Data: {json.dumps(flightOfferPriceData, indent=2)}")
            
            orders_url = "https://test.api.amadeus.com/v1/booking/flight-orders"

            # flightOfferPriceData1 = {"type":"flight-offer","id":"1","source":"GDS","instantTicketingRequired":False,"nonHomogeneous":False,"paymentCardRequired":False,"lastTicketingDate":"2024-12-19","itineraries":[{"segments":[{"departure":{"iataCode":"CDG","at":"2024-12-19T10:00:00"},"arrival":{"iataCode":"FRA","at":"2024-12-19T14:30:00"},"carrierCode":"6X","number":"501","aircraft":{"code":"744"},"operating":{"carrierCode":"6X"},"duration":"PT4H30M","id":"5","numberOfStops":0,"co2Emissions":[{"weight":71,"weightUnit":"KG","cabin":"ECONOMY"}]},{"departure":{"iataCode":"FRA","at":"2024-12-19T18:10:00"},"arrival":{"iataCode":"ICN","at":"2024-12-20T11:25:00"},"carrierCode":"6X","number":"9744","aircraft":{"code":"744"},"operating":{"carrierCode":"6X"},"duration":"PT9H15M","id":"6","numberOfStops":0,"co2Emissions":[{"weight":404,"weightUnit":"KG","cabin":"ECONOMY"}]}]}],"price":{"currency":"EUR","total":"270.36","base":"134.00","fees":[{"amount":"0.00","type":"SUPPLIER"},{"amount":"0.00","type":"TICKETING"},{"amount":"0.00","type":"FORM_OF_PAYMENT"}],"grandTotal":"270.36","billingCurrency":"EUR"},"pricingOptions":{"fareType":["PUBLISHED"],"includedCheckedBagsOnly":True},"validatingAirlineCodes":["6X"],"travelerPricings":[{"travelerId":"1","fareOption":"STANDARD","travelerType":"ADULT","price":{"currency":"EUR","total":"135.18","base":"67.00","taxes":[{"amount":"4.51","code":"IZ"},{"amount":"3.00","code":"O4"},{"amount":"13.13","code":"QX"},{"amount":"21.89","code":"FR"},{"amount":"25.65","code":"RA"}],"refundableTaxes":"68.18"},"fareDetailsBySegment":[{"segmentId":"5","cabin":"ECONOMY","fareBasis":"YCNV1","class":"Y","includedCheckedBags":{"quantity":9}},{"segmentId":"6","cabin":"ECONOMY","fareBasis":"YCNV1","class":"Y","includedCheckedBags":{"quantity":9}}]},{"travelerId":"2","fareOption":"STANDARD","travelerType":"ADULT","price":{"currency":"EUR","total":"135.18","base":"67.00","taxes":[{"amount":"4.51","code":"IZ"},{"amount":"3.00","code":"O4"},{"amount":"13.13","code":"QX"},{"amount":"21.89","code":"FR"},{"amount":"25.65","code":"RA"}],"refundableTaxes":"68.18"},"fareDetailsBySegment":[{"segmentId":"5","cabin":"ECONOMY","fareBasis":"YCNV1","class":"Y","includedCheckedBags":{"quantity":9}},{"segmentId":"6","cabin":"ECONOMY","fareBasis":"YCNV1","class":"Y","includedCheckedBags":{"quantity":9}}]}]}
            print(f"Traveler Details: {json.dumps(travelers_details, indent=2)}")

            payload = {
                "data": {
                    "type": "flight-order",
                    "flightOffers": [
                        flightOfferPriceData
                    ],
                    "travelers": 
                        travelers_details
                }
            }
            
            print(f"Flight Order Payload: {json.dumps(payload, indent=2)}")

            order_response = requests.post(orders_url, headers=headers, json=payload)
            order_response.raise_for_status()
            order_data = order_response.json()

            print("Flight Order Results:")
            print(json.dumps(order_data, indent=2))

            return order_data
        
            # Placeholder for actual API call implementation
            return {
                "flight_details": {
                    "origin": originLocationCode,
                    "destination": destinationLocationCode,
                    "date": departureDate
                },
                "travelers": travelers_details
            }
        
        except requests.RequestException as e:
            return {"error": str(e)}

    def _run_hotel_booking(
        self,
        originLocationCode: str,
        destinationLocationCode: str,
        departureDate: str,
        returnDate: str,
        adults: int,
        travelers_details: List[Dict[str, Any]],
        card_details: str,
        max: int = 5,
    ) -> Dict[str, Any]:
        """
        Execute the API call to retrieve and book hotel offers.
        """
        # Retrieve API credentials from environment variables
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
            api_url = 'https://test.api.amadeus.com/v1/reference-data/locations/hotels/by-city'
            headers = {
                'Authorization': f'Bearer {access_token}'
            }

            params = {
                'cityCode': destinationLocationCode
            }

            # Make the API call
            response = requests.get(api_url, headers=headers, params=params)
            response.raise_for_status()

            results = response.json()

            if "data" not in results or len(results["data"]) == 0:
                print("No hotels found.")
                return {"error": "No hotels found."}

            hotelIdsData = [hotel["hotelId"] for hotel in results["data"][:30]] #taking hotel ids



            hotelIds = ",".join(hotelIdsData)

            pricing_url = "https://test.api.amadeus.com/v3/shopping/hotel-offers"

            params = {
                'hotelIds': hotelIds,
                'adults':len(travelers_details),
                'checkInDate':departureDate,
                'checkOutDate': returnDate,
                'roomQuantity':1,
                'paymentPolicy':'NONE',
                'bestRateOnly':True
            }

            pricing_response = requests.get(pricing_url, headers=headers, params=params)

            pricing_response.raise_for_status()
            pricing_data = pricing_response.json()
            #print("Hotel Offer Pricing Results:")
            #print(json.dumps(pricing_data, indent=2))

            if "data" not in pricing_data  or len(pricing_data["data"]) == 0 or "hotel" not in pricing_data["data"][0]:
                print("No priced hotel offers found.")
                return {"error": "No priced hotel offers found."}

            hotelOfferPriceData = pricing_data["data"][0]
            hotelOfferPriceId = hotelOfferPriceData["offers"][0]["id"]

            #print(f"Hotel Offer Price Data: {json.dumps(hotelOfferPriceData, indent=2)}")

            def guest_reference(traveler):
              return {
                  "tid": int(traveler["id"]),
                  "title":  "MR" if traveler["gender"] == "MALE" else "MS",
                  "firstName" : traveler["name"]["firstName"],
                  "lastName" : traveler["name"]["lastName"],
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
                            "paymentCardInfo": card_details
                            }
                        }
                    }
                }

            order_response = requests.post(orders_url, headers=headers, json=payload)

            order_response.raise_for_status()
            order_data = order_response.json()

            return order_data

        except requests.RequestException as e:
            return {"error": str(e)}

        return {}

    def _run_itinerary(
        self,
        originLocationCode: str,
        destinationLocationCode: str,
        departureDate: str,
        returnDate: str,
        adults: int,
        travelers_details: List[Dict[str, Any]],
        card_details: str,
        max: int = 5
        ) -> Dict[str, Any]:
        """
        Execute the API call to retrieve and book hotel offers.
        """

        system_prompt = """
        You are an expert at planning trips in the most optimized way with best suggestions for the  given city.

        Guidelines:
        - Suggest top restaurants
        - Tourist places
        - Activities
        - Optimized travel plan

        return the valid json of the entire itinerary with a field optimized_travel_plan.
        """

        # Create a user query based on the destination and other details
        query = f"Plan an optimized trip itinerary for {adults} adults in {destinationLocationCode} starting from {departureDate} to {returnDate}."

        # Initialize the LLM
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

        # Create the prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", query)
        ])

        # Extract itinerary
        try:
            chain = prompt | llm
            response = chain.invoke({"query": query})

            itinerary = json.loads(response.content)
            #print(f"Extracted itinerary: {json.dumps(itinerary, indent=2)}")
            return itinerary
        except Exception as e:
            print(f"Error extracting itinerary: {e}")
            return {}




def extract_card_details_from_query(query: str) -> Dict[str, str]:
    """
    Extract credit card details from the query using an LLM.

    Args:
        query (str): The user-provided natural language query.

    Returns:
        Dict[str, str]: Extracted card details.
    """
    system_prompt = """
    You are an expert at extracting structured credit card details from natural language input.

    Extract the following details about a credit card:
    1. Card Vendor Code (e.g., VI for Visa, MC for MasterCard)
    2. Card Number
    3. Expiry Date in YYYY-MM format
    4. Card Holder's Full Name

    Output Format (JSON):
    {{
        "vendorCode": "VI/MC/AMEX",
        "cardNumber": "CARD_NUMBER",
        "expiryDate": "YYYY-MM",
        "holderName": "FULL_NAME"
    }}

    Guidelines:
    - Use the vendor code format: VI (Visa), MC (MasterCard), AMEX (American Express)
    - Validate card number length (between 13 and 19 digits).
    - Validate expiry date format as YYYY-MM.
    - Do not guess missing details; set them to null.
    """

    # Initialize the LLM
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

    # Create the prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", query)
    ])

    # Extract card details from the query
    try:
        chain = prompt | llm

        response = chain.invoke({"query": query})
        card_details = json.loads(response.content)
        print(f"Extracted Card Details from Query: {json.dumps(card_details, indent=2)}")
        return card_details
    except Exception as e:
        print(f"Error extracting card details: {e}")
        return {
            "vendorCode": None,
            "cardNumber": None,
            "expiryDate": None,
            "holderName": None
        }


def collect_card_details(missing_details: Dict[str, str]) -> Dict[str, str]:
    """
    Collect missing credit card details interactively from the user.

    Args:
        missing_details (Dict[str, str]): Card details extracted from the query.

    Returns:
        Dict[str, str]: Complete card details.
    """
    print("\nEnter Missing Credit Card Details:")

    while not missing_details.get("vendorCode"):
        missing_details["vendorCode"] = input("Card Vendor (e.g., VI for Visa, MC for MasterCard): ").upper()

    if not missing_details.get("cardNumber"):
        card_number = input("Card Number:(13-19 digits) ").strip()
        while not card_number.isdigit() or len(card_number) < 13 or len(card_number) > 19:
            card_number = input("Card Number:(13-19 digits) ").strip()
        missing_details["cardNumber"] = card_number

    if not missing_details.get("expiryDate"):
        expiry_date = input("Card Expiry Date (YYYY-MM): ").strip()
        try:
            datetime.strptime(expiry_date, "%Y-%m")
            missing_details["expiryDate"] = expiry_date
        except ValueError:
            raise ValueError("Invalid expiry date format. Use YYYY-MM.")

    if not missing_details.get("holderName"):
        missing_details["holderName"] = input("Card Holder Name: ").strip()

    return missing_details


def convert_to_human_readable_result(flight_booking_result: Dict[str, Any], hotel_booking_result: Dict[str, Any]):
    system_prompt = """
    You are an expert at converting structured booking results into human-readable format.
    You have the results from flight and hotel bookings.
    Your task is to extract only the relevant details and output them in a concise format.
    """
        
    # Initialize the LLM
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        
    # Create the prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{flight_booking_result} {hotel_booking_result}")
    ])
        
    # Create the chain
    chain = prompt | llm
    
    try:
        response = chain.invoke({
            "flight_booking_result": json.dumps(flight_booking_result),
            "hotel_booking_result": json.dumps(hotel_booking_result)
        })

        print(f"Human Readable Result: {response.content}")
    except Exception as e:
        print(f"Error converting to human-readable result: {e}")


def book_flight(query: str):
    """
    Main flight booking process.
    
    Args:
        query (str): Natural language flight booking request
    """
    flight_tool = AmadeusFlightBookingTool()
    
    flight_tool_openai = format_tool_to_openai_function(flight_tool)

    # print(f"Flight Tool OpenAI: {json.dumps(flight_tool_openai, indent=2)}")

    # Extract flight parameters
    flight_params = AmadeusFlightBookingTool.extract_parameters_with_llm(
        query, 
        flight_tool_openai
    )

    print(f"Flight Parameters: {json.dumps(flight_params, indent=2)}")
    
    # Prepare travelers details
    travelers_details = []
    
    # Extract traveler details from the initial query
    traveler_details = flight_tool.extract_traveler_details(query)
    traveler_details['id'] = '1'
    travelers_details.append(traveler_details)

    
    # Additional travelers if needed
    while True:
        add_more = input("Do you want to add another traveler? (yes/no): ").lower()
        if add_more != 'yes':
            break
        
        additional_traveler = input("Enter additional traveler details: ")
        additional_traveler_details = flight_tool.extract_traveler_details(additional_traveler)
        additional_traveler_details['id'] = str(len(travelers_details) + 1)
        travelers_details.append(additional_traveler_details)
    

    # Collect credit card details
    card_details = extract_card_details_from_query(query)
    complete_card_details = collect_card_details(card_details)


    # Combine parameters for booking
    booking_params = {
        'originLocationCode': flight_params.get('originLocationCode', ''),
        'destinationLocationCode': flight_params.get('destinationLocationCode', ''),
        'departureDate': flight_params.get('departureDate', ''),
        'returnDate': flight_params.get('returnDate', ''),
        'adults': len(travelers_details),
        'max': flight_params.get('max', 5),
        'travelers_details': travelers_details,
        'card_details': complete_card_details
    }
    
    print("\nFlight Booking Parameters:")
    print(json.dumps(booking_params, indent=2))
    
    # Perform booking (simplified for demonstration)
    flight_booking_result = flight_tool._run(**booking_params)
    
    hotel_booking_result = flight_tool._run_hotel_booking(**booking_params)

    itinerary_result = flight_tool._run_itinerary(**booking_params)

    # Display booking details
    print("\nBooking Details:")
    print(json.dumps(flight_booking_result, indent=2))

    print("\nHotel Booking Details:")
    print(json.dumps(hotel_booking_result, indent=2))
    
    # print("\Itinerary:")
    # print(json.dumps(itinerary_result, indent=2))

    # convert_to_human_readable_result(flight_booking_result, hotel_booking_result)
    
# Example usage
if __name__ == "__main__":
    sample_query = "Book me a trip to New York from 20th December 2024 to 5th January 2025. I am currently located at New Delhi."
    book_flight(sample_query)
