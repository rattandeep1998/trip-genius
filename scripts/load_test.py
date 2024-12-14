import pandas as pd
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

def flatten_json(nested_json, parent_key="", sep="."):
    """
    Flatten a nested JSON object.
    """
    items = []
    for k, v in nested_json.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_json(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            for i, item in enumerate(v):
                items.extend(flatten_json(item, f"{new_key}[{i}]", sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def compare_parameters(generated, baseline):
    """
    Compare two sets of booking parameters and return the match percentage.
    """
    flat_generated = flatten_json(generated)
    flat_baseline = flatten_json(baseline)
    
    total_keys = len(flat_baseline)
    matched_keys = sum(1 for k, v in flat_baseline.items() if flat_generated.get(k) == v)
    
    return (matched_keys / total_keys) * 100 if total_keys > 0 else 0

def load_test_api(input_csv, output_csv, endpoint, num_threads=10):
    """
    Perform load testing on the initiate_bookings API endpoint with parallel requests.
    
    Parameters:
        - input_csv (str): Path to the input CSV file containing queries.
        - output_csv (str): Path to save the load test results.
        - endpoint (str): The API endpoint URL.
        - num_threads (int): Number of concurrent threads.
    """
    # Read the dataset
    df = pd.read_csv(input_csv)
    
    results = []
    total_requests = len(df)
    total_time = 0
    successful_requests = 0
    failed_requests = 0
    flight_api_calls = 0
    flight_api_success = 0
    hotel_api_calls = 0
    hotel_api_success = 0
    llm_calls_count = 0
    total_match_percentage = 0
    
    def send_request(input_text, baseline_params):
        start_time = time.time()
        try:
            response = requests.post(endpoint, json={"query": input_text})
            response_time = time.time() - start_time
            if response.status_code == 200:
                response_data = response.json()
                generated_params = response_data.get("booking_params", {})
                match_percentage = compare_parameters(generated_params, baseline_params)
                return {
                    "status": "Success", 
                    "response_time": response_time, 
                    "response": response_data,
                    "flight_api_calls": response_data.get("flight_api_calls", 0),
                    "flight_api_success": response_data.get("flight_api_success", 0),
                    "hotel_api_calls": response_data.get("hotel_api_calls", 0),
                    "hotel_api_success": response_data.get("hotel_api_success", 0),
                    "llm_calls": response_data.get("llm_calls", 0),
                    "baseline_params": json.dumps(baseline_params),
                    "generated_params": json.dumps(generated_params),
                    "match_percentage": match_percentage
                }
            else:
                return {"status": "Fail", "response_time": response_time, "error": response.text}
        except Exception as e:
            response_time = time.time() - start_time
            return {"status": "Fail", "response_time": response_time, "error": str(e)}
    
    # Run the requests in parallel
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        future_to_input = {executor.submit(send_request, row['Input'], json.loads(row['Parameters'])): row for _, row in df.iterrows()}
        
        for future in as_completed(future_to_input):
            row = future_to_input[future]
            input_text = row['Input']
            baseline_params = json.loads(row['Parameters'])
            result = future.result()
            total_time += result["response_time"]
            
            if result["status"] == "Success":
                successful_requests += 1
                flight_api_calls += result["flight_api_calls"]
                flight_api_success += result["flight_api_success"]
                hotel_api_calls += result["hotel_api_calls"]
                hotel_api_success += result["hotel_api_success"]
                llm_calls_count += result["llm_calls"]
                total_match_percentage += result["match_percentage"]
            else:
                failed_requests += 1
            
            # Collect results
            results.append({
                "Input": input_text,
                "Status": result["status"],
                "Response Time (s)": f"{result['response_time']:.2f}",
                "Flight API Calls": result.get("flight_api_calls", 0),
                "Successful Flight API Calls": result.get("flight_api_success", 0),
                "Hotel API Calls": result.get("hotel_api_calls", 0),
                "Successful Hotel API Calls": result.get("hotel_api_success", 0),
                "LLM Calls": result.get("llm_calls", 0),
                "Baseline Parameters": result.get("baseline_params", ""),
                "Generated Parameters": result.get("generated_params", ""),
                "Match Percentage": f"{result.get('match_percentage', 0):.2f}%",
                "Error": result.get("error", "")
            })
    
    # Create a DataFrame with the results
    results_df = pd.DataFrame(results)
    
    # Save the results to an output CSV file
    results_df.to_csv(output_csv, index=False)
    
    # Calculate and display performance metrics
    average_response_time = total_time / total_requests if total_requests > 0 else 0
    success_rate = (successful_requests / total_requests) * 100 if total_requests > 0 else 0
    overall_match_percentage = total_match_percentage / successful_requests if successful_requests > 0 else 0
    
    print("\nLoad Test Summary:")
    print(f"Total Requests: {total_requests}")
    print(f"Successful Requests: {successful_requests}")
    print(f"Failed Requests: {failed_requests}")
    print(f"Success Rate: {success_rate:.2f}%")
    print(f"Average Response Time: {average_response_time:.2f} seconds")
    print(f"Overall Match Percentage: {overall_match_percentage:.2f}%")
    print(f"Total Flight API Calls: {flight_api_calls}")
    print(f"Successful Flight API Calls: {flight_api_success}")
    print(f"Total Hotel API Calls: {hotel_api_calls}")
    print(f"Successful Hotel API Calls: {hotel_api_success}")
    print(f"Total LLM Calls: {llm_calls_count}")

if __name__ == "__main__":
    input_csv_path = "../data/travel_booking_dataset_short.csv"
    output_csv_path = "../data/load_test_results.csv"
    endpoint_url = "http://127.0.0.1:8000/initiate_bookings"
        
    load_test_api(input_csv_path, output_csv_path, endpoint_url, num_threads=1)
