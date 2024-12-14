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