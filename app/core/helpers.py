from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from typing import Dict, Any, List
import json

def get_parameter_description(param: str) -> str:
    descriptions = {
        'originLocationCode': 'City/airport IATA code from which the traveler will depart (e.g., JFK for New York)',
        'destinationLocationCode': 'City/airport IATA code to which the traveler is going (e.g., DEL for Delhi)',
        'departureDate': 'Date of departure in ISO 8601 YYYY-MM-DD format (e.g., 2024-12-30)',
        'returnDate': 'Date of return in ISO 8601 YYYY-MM-DD format (e.g., 2025-01-05)',
        'adults': 'Number of adult travelers (age 12 or older)',
        'max': 'Maximum number of flight offers to return (must be >= 1, default 250)',
        'travelPlanPreference': 'Preference for itinerary (Take from user input, leave empty if not specified explicitly)',
        'country':'Country code of the destination location from with the traveller will arrive(e.g., US for New York). Donot leave empty.',
        'city':'Full city name of the destination city from with the traveller will arrive(e.g., New York City for New York or NYC).  Donot leave empty.',
        'currencyCode':'Country currency of the source location from with the traveller will depart(originLocationCode e.g., USD for New York). Donot leave empty',
    }
    
    return descriptions.get(param, 'No description available')

def extract_single_param_value_llm(param: str, input_value: str, extract_parameters_model: str, verbose: bool = True) -> str:
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
    
    response = chain.invoke({
        "input_value": input_value
    })

    if verbose:
        print(f"Extracted Parameter '{param}': {response.content}")

    return response.content

def extract_parameters_with_llm(
    query: str,
    function_spec: Dict[str, Any],
    extract_parameters_model: str,
    interactive_mode: bool = True,
    verbose: bool = True,
):
    llm_calls_count = 0
    parameters_details = "\n\t".join([
        f"- {param}: {get_parameter_description(param)} "
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

    if verbose:
        print(f"Extracted Parameters: {json.dumps(extracted_params, indent=2)}")

    required_params = function_spec['parameters'].get('required', [])

    for param in required_params:
        while param not in extracted_params:
            input_value = input(f"Please provide a value for '{param}' - {get_parameter_description(param)}: ").strip()

            llm_calls_count += 1
            
            extracted_params[param] = extract_single_param_value_llm(param, input_value, extract_parameters_model, verbose)
            #print(f"'{param}' is a required parameter. Please provide a value.")

    return extracted_params, llm_calls_count   

def parse_traveler_details(traveler_details: Dict[str, Any], extract_parameters_model: str, verbose: bool = True) -> Dict[str, Any]:
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
        parsed_traveller_details = chain.invoke({"traveler_input": traveler_details_str})
        parsed_traveller_details = json.loads(parsed_traveller_details.content)

        if verbose:
            print(f"Parsed Traveler Details: {json.dumps(parsed_traveller_details, indent=2)}")

        return parsed_traveller_details
    except Exception as e:
        if verbose:
            print(f"Error parsing traveler details: {e}")
        return traveler_details


def extract_traveler_details(extract_parameters_model: str, traveler_input: str = None, interactive_mode: bool = True, verbose: bool = True):
    llm_calls_count = 0

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
    
    llm_calls_count += 1
    extracted_details = parse_traveler_details(extracted_details, extract_parameters_model, verbose)

    return extracted_details, llm_calls_count


def convert_to_human_readable_result(flight_booking_result: Dict[str, Any], hotel_booking_result: Dict[str, Any], itinerary_result: str, convert_to_human_results_model: str, verbose: bool = True):
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

