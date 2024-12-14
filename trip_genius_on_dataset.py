import pandas as pd
import json
from bookings_script import initiate_bookings

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
    Compare two sets of booking parameters, including nested keys, and calculate the percentage of matching parameters.
    Print detailed mismatches for debugging purposes.
    """
    flat_generated = flatten_json(generated)
    flat_baseline = flatten_json(baseline)
    
    total_keys = len(flat_baseline)
    matched_keys = 0
    mismatches = []
    
    for key, baseline_value in flat_baseline.items():
        generated_value = flat_generated.get(key, "Missing in generated")
        if generated_value == baseline_value:
            matched_keys += 1
        else:
            mismatches.append((key, baseline_value, generated_value))
    
    match_percentage = (matched_keys / total_keys) * 100 if total_keys > 0 else 0
    
    if mismatches:
        print("Mismatched Parameters:")
        for key, baseline_value, generated_value in mismatches:
            print(f"  Key: {key}\n    Baseline: {baseline_value}\n    Generated: {generated_value}\n")
    
    return match_percentage

def process_bookings(input_csv, output_csv, short_dataset=False):
    # Read the dataset from the input CSV file
    df = pd.read_csv(input_csv)
    
    # If short_dataset is True, use a subset of the data
    if short_dataset:
        df = df.head(1)
    
    results = []
    total_match_percentage = 0
    total_entries = len(df)
    
    for index, row in df.iterrows():
        print(f"Processing entry {index + 1} of {total_entries}...")
        input_text = row['Input']
        baseline_params = json.loads(row['Parameters'])
        
        # Generate booking parameters using the initiate_bookings function
        results_dict = initiate_bookings(input_text, interactive_mode=False, verbose=False)
        generated_params = results_dict.get('booking_params', {})
        
        # Compare the generated parameters with the baseline parameters
        match_percentage = compare_parameters(generated_params, baseline_params)
        total_match_percentage += match_percentage
        
        # Store the results for each entry
        results.append({
            "Input": input_text,
            "Baseline Parameters": json.dumps(baseline_params),
            "Generated Parameters": json.dumps(generated_params),
            "Match Percentage": f"{match_percentage:.2f}%"
        })

        print(f"Match Percentage: {match_percentage:.2f}%\n")
    
    # Create a DataFrame with the results
    results_df = pd.DataFrame(results)
    
    # Save the results to an output CSV file
    results_df.to_csv(output_csv, index=False)
    
    # Calculate and display the overall match percentage
    overall_match_percentage = total_match_percentage / total_entries if total_entries > 0 else 0
    print(f"Overall Match Percentage: {overall_match_percentage:.2f}%")

# Example usage
if __name__ == "__main__":
    input_csv_path = "./data/travel_booking_dataset.csv"
    output_csv_path = "./data/booking_results.csv"
    
    process_bookings(input_csv_path, output_csv_path, short_dataset=True)