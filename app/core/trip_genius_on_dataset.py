import pandas as pd
import json
import time
from app.core.booking_agent import initiate_bookings
from app.core.utils import compare_parameters

def process_bookings(input_csv, output_csv, short_dataset=False):
    # Read the dataset from the input CSV file
    df = pd.read_csv(input_csv)
    
    # If short_dataset is True, use a subset of the data
    if short_dataset:
        df = df.head(2)
    
    results = []
    total_match_percentage = 0
    total_entries = len(df)
    flight_api_calls = 0
    flight_api_success = 0
    hotel_api_calls = 0
    hotel_api_success = 0
    itinerary_api_calls = 0
    itinerary_api_success = 0
    llm_calls_count = 0
    total_time = 0
    total_intent_match_percentage = 0
    
    for index, row in df.iterrows():
        input_text = row['Input']
        baseline_params = json.loads(row['Parameters'])
        baseline_intent = row['Intent']
        
        # Measure the time taken to run the initiate_bookings function
        start_time = time.time()
        # results_dict = initiate_bookings(input_text, interactive_mode=False, verbose=False, use_real_api = True)

        # initiate_bookings is a generator, but in non-interactive mode it won't yield.
        # So we try to advance the generator once and catch the StopIteration to get the return value.
        gen = initiate_bookings(input_text, interactive_mode=False, verbose=False, use_real_api=True)
        try:
            # Attempt to advance the generator
            next(gen)
            # If the code reaches here, it means something was yielded, which we do not expect.
            # If that happens, we'll just exhaust the generator.
            for _ in gen:
                pass
            # Since we expected no yields, this scenario is unexpected.
            # Set results_dict to an empty dict or handle differently as needed.
            results_dict = {}
        except StopIteration as e:
            # The generator returned a value rather than yielding.
            # e.value should contain the dictionary returned by initiate_bookings.
            results_dict = e.value if hasattr(e, 'value') else {}

        end_time = time.time()
        execution_time = end_time - start_time
        total_time += execution_time
        
        generated_params = results_dict.get('booking_params', {})
        
        # Collect API call data
        flight_api_calls += results_dict.get('flight_api_calls', 0)
        flight_api_success += results_dict.get('flight_api_success', 0)
        hotel_api_calls += results_dict.get('hotel_api_calls', 0)
        hotel_api_success += results_dict.get('hotel_api_success', 0)
        itinerary_api_calls += results_dict.get('itinerary_api_calls', 0)
        itinerary_api_success += results_dict.get('itinerary_api_calls', 0)
        llm_calls_count += results_dict.get('llm_calls', 0)
        
        # Compare the generated parameters with the baseline parameters
        match_percentage = compare_parameters(generated_params, baseline_params)
        total_match_percentage += match_percentage

        if baseline_intent.lower().strip() in results_dict.get('intent', "").lower().strip():
            total_intent_match_percentage+=1

        # Store the results for each entry
        results.append({
            "Input": input_text,
            "Baseline Parameters": json.dumps(baseline_params),
            "Generated Parameters": json.dumps(generated_params),
            "Match Percentage": f"{match_percentage:.2f}%",
            "Flight API Calls": results_dict.get('flight_api_calls', 0),
            "Flight API Success": results_dict.get('flight_api_success', 0),
            "Hotel API Calls": results_dict.get('hotel_api_calls', 0),
            "Hotel API Success": results_dict.get('hotel_api_success', 0),
            "LLM Calls": results_dict.get('llm_calls', 0),
            "Execution Time (s)": f"{execution_time:.2f}",
            "Baseline Intent": baseline_intent,
            "Generated Intent": results_dict.get('intent', ""),
        })
    
    # Create a DataFrame with the results
    results_df = pd.DataFrame(results)
    
    # Save the results to an output CSV file
    results_df.to_csv(output_csv, index=False)
    
    # Calculate and display the overall match percentage and average execution time
    overall_match_percentage = total_match_percentage / total_entries if total_entries > 0 else 0
    overall_intent_match_percentage = (total_intent_match_percentage / total_entries)*100 if total_entries > 0 else 0
    average_execution_time = total_time / total_entries if total_entries > 0 else 0
    print(f"Overall Match Percentage: {overall_match_percentage:.2f}%")
    print(f"Overall Intent Match Percentage: {overall_intent_match_percentage:.2f}%")
    print(f"Total Flight API Calls: {flight_api_calls}")
    print(f"Successful Flight API Calls: {flight_api_success}")
    print(f"Total Hotel API Calls: {hotel_api_calls}")
    print(f"Successful Hotel API Calls: {hotel_api_success}")
    print(f"Total Itinerary API Calls: {itinerary_api_calls}")
    print(f"Successful Itinerary API Calls: {itinerary_api_success}")
    print(f"Total LLM Calls: {llm_calls_count}")
    print(f"Average Execution Time: {average_execution_time:.2f} seconds")

# Example usage
if __name__ == "__main__":
    input_csv_path = "./data/travel_booking_dataset_1.csv"
    output_csv_path = "./data/booking_results_4o.csv"

    #input_csv_path = "./data/travel_booking_dataset_short.csv"
    #output_csv_path = "./data/booking_results_short.csv"
    
    process_bookings(input_csv_path, output_csv_path)