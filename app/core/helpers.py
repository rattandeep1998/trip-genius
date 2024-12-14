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
        'country':'Country code of the destination location(e.g., US for New York). Donot leave empty',
        'city':'Full city name of the destination city(e.g., New York City for New York or NYC).  Donot leave empty',
        'currencyCode':'Country currency of the source location(originLocationCode e.g., USD for New York). Donot leave empty',
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
