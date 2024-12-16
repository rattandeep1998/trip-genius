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

def extract_single_param_value_llm(param: str, param_description: str, input_value: str, extract_parameters_model: str, verbose: bool = True) -> str:
    system_prompt = f"""
    You are an expert at extracting structured parameters for a flight booking API function.

    **Task**: Extract the value of the parameter '{param}' from the given user input.
    **Parameter Description**: {param_description}

    ### Extraction Guidelines:
    1. **Location Extraction**:
    - For location-related inputs (origin or destination), extract the **IATA airport code** (e.g., JFK, LHR).
    - If the exact IATA code is not specified, infer the closest major airport IATA code.
    - Only return the 3-letter IATA code. Do not include any additional text.

    2. **Date Format**:
    - For date inputs, use the **YYYY-MM-DD** format.
    - If the year is not mentioned, assume the current year.

    3. **Default Values**:
    - If the travel preference parameter is missing, return `'tourism'`.

    4. **Strict Matching**:
    - Match the parameter exactly as described in the function specification.

    5. **Edge Cases**:
    - If the input is unclear or contains multiple locations, choose the most relevant one.
    - If unsure about the parameter, return null.

    ### Examples:
    - **Input**: "New York"  
    **Output**: "JFK"

    - **Input**: "Tokyo"  
    **Output**: "HND"

    - **Input**: "March 15th 2024"  
    **Output**: "2024-03-15"

    ### Output Instructions:
    - Return **only** the extracted parameter value as a string.
    - Ensure the type is compatible with the expected parameter.
    - If extraction is not possible, return ''.
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
        return extracted_params, llm_calls_count
    
    # Remove extracted parameters whose value is null
    extracted_params = {k: v for k, v in extracted_params.items() if v is not None}

    if verbose:
        print(f"Extracted Parameters: {json.dumps(extracted_params, indent=2)}")

    required_params = function_spec['parameters'].get('required', [])

    for param in required_params:
        while param not in extracted_params:
            param_description = get_parameter_description(param)
            required_param_input = f"Please provide a value for '{param}' - {param_description}: "
            input_value = yield {"type": "prompt", "text": required_param_input}
            # input_value = input(required_param_input)
            input_value = input_value.strip()

            llm_calls_count += 1
            
            extracted_param_value = extract_single_param_value_llm(param, param_description, input_value, extract_parameters_model, verbose)
            
            if extracted_param_value is None or extracted_param_value == "''":
                debug_message = f"Extraction failed for parameter '{param}'. Please provide a valid value."
                print(debug_message)
                yield {"type": "message", "text": debug_message}
                continue

            extracted_params[param] = extracted_param_value
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
    - If there are multiple travellers identify all in the form of json and return as a list
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
    Input could have multiple travelers. Identify each one carefully and double-check.

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
    - Do not make up any information and default to null if unsure.
    - Use uppercase for names.
    - Validate email format.
    - Format phone number with country code if present.
    - Infer gender from input if not explicitly provided.
    - If details are missing, return null for those fields.
    - If only one email address is provided, use it for all travelers.
    - If only one phone number is provided, use it for all travelers.
    - Return a list of JSON objects if multiple travelers are identified.
    - Return a list of single JSON object if only one traveler is found.
    - Return type is list
    """
    
    llm = ChatOpenAI(model=extract_parameters_model, temperature=0)        
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{traveler_input}")
    ])
    
    chain = prompt | llm
    
    all_extracted_details = {}
    if traveler_input:
        try:
            if verbose:
                print(f"Traveller Details Input: {traveler_input}")
            
            llm_calls_count += 1
            response = chain.invoke({"traveler_input": traveler_input})
            all_extracted_details = json.loads(response.content)
        except Exception as e:
            all_extracted_details = {}
            print(f"Error extracting traveler details: {e}")
    
    if verbose:
        print(f"Extracted Traveler Details: {json.dumps(all_extracted_details, indent=2)}")

    # If not is iterative mode and function is run on the entire dataset, then return the extracted parameters without asking for human input
    if not interactive_mode:
        return all_extracted_details, llm_calls_count
    
    # Interactive validation and completion
    def validate_input(prompt_text, validator=None):
        while True:
            user_input = yield {"type": "prompt", "text": prompt_text}
            # user_input = input(prompt_text)
            user_input = user_input.strip()
            
            if validator is None or validator(user_input):
                return user_input
    
    # Validate and complete full name
    if not isinstance(all_extracted_details, list):
        all_extracted_details = [all_extracted_details]
    for extracted_details in all_extracted_details:
        if not extracted_details.get('name') or not all(extracted_details['name'].values()):
            full_name = yield from validate_input("Enter full name (First Last): ")
            name_parts = full_name.split()
            extracted_details['name'] = {
                "firstName": name_parts[0].upper(),
                "lastName": ' '.join(name_parts[1:]).upper()
            }
    
    # Validate date of birth
    for extracted_details in all_extracted_details:
        if not extracted_details.get('dateOfBirth'):
            dob = yield from validate_input("Enter date of birth: ")
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
    for extracted_details in all_extracted_details:
        if not extracted_details.get('gender'):
            gender = yield from validate_input("Enter gender: ")
            extracted_details['gender'] = gender

        # gender = validate_input(
        #     "Enter gender (Male/Female): ", 
        #     lambda g: g.upper() in ['MALE', 'FEMALE']
        # ).upper()
        # extracted_details['gender'] = gender
    
    # Validate email
    for extracted_details in all_extracted_details:
        if not extracted_details.get('contact') or not extracted_details['contact'].get('emailAddress'):
            email = yield from validate_input(
                "Enter email address: ", 
                lambda e: '@' in e and '.' in e
            )

            if not extracted_details.get('contact'):
                extracted_details['contact'] = {}

            extracted_details['contact']['emailAddress'] = email
    
    # Validate phone number
    for extracted_details in all_extracted_details:
        if not extracted_details['contact'].get('phones') or not extracted_details['contact']['phones'][0].get('number') or not extracted_details['contact']['phones'][0].get('countryCallingCode'):
            phone = yield from validate_input("Enter phone number (with country code): ")
            
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
        print(f"Traveler details before parsing: {json.dumps(all_extracted_details, indent=2)}")
    
    llm_calls_count += 1
    all_extracted_details = parse_traveler_details(all_extracted_details, extract_parameters_model, verbose)

    return all_extracted_details, llm_calls_count


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

        # If travel_plan is not present in the itinerary result
        if 'travel_plan' not in itinerary_result:
            complete_summary = response.content
        # If flight_booking_result empty json object and hotel_booking_result empty json object
        elif not flight_booking_result and not hotel_booking_result:
            complete_summary = " \nTravel Plan:\n" + itinerary_result.get('travel_plan', '')
        else:
            complete_summary = response.content + " \nTravel Plan:\n" + itinerary_result.get('travel_plan', '')
        
        if verbose:
            print(f"Human Readable Result: {complete_summary}")

        return complete_summary
        
    except Exception as e:
        if verbose:
            print(f"Error converting to human-readable result: {e}")
        return ""

def extract_missing_booking_parameters(
    booking_params: Dict[str, Any],
    extract_parameters_model: str,
    verbose: bool = True
):
    llm_calls_count = 0

    # Prepare the query with origin and destination location codes
    query = f"""
    Extract the destinationCountry, destinationCity, and originCurrencyCode from the following details:
    - Destination Location Code: {booking_params.get('destinationLocationCode', '')}
    - Origin Location Code: {booking_params.get('originLocationCode', '')}

    Ensure the extraction is accurate and do not make up any information.
    """

    system_prompt = """
    You are an expert at extracting structured parameters for a flight booking API function. Extract the values of the following parameters from the given details and return the response in JSON format:

    Parameters:
    - destinationCountry: The country corresponding to the destination location code. destinationCountry is in ISO 3166 Alpha-2 code format.
    - destinationCity: The city corresponding to the destination location code.
    - originCurrencyCode: The currency code corresponding to the origin location code.

    Extraction Guidelines:
    1. Use the destinationLocationCode to extract destinationCountry and destinationCity.
    2. Use the originLocationCode to extract originCurrencyCode.
    3. Do not make up any information; return null if unsure.
    4. Ensure extracted values are accurate and compatible with the expected types.
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
        extracted_params = {}

    for key in ['destinationCountry', 'destinationCity', 'originCurrencyCode']:
        if booking_params.get(key) == '' and extracted_params.get(key) is not None:
            booking_params[key] = extracted_params[key]

    if verbose:
        print(f"Extracted Missing Parameters: {json.dumps(extracted_params, indent=2)}")
        print(f"Updated Booking Parameters: {json.dumps(booking_params, indent=2)}")

    return booking_params, llm_calls_count
