import json
import pandas as pd

# Define the dataset with natural language inputs and corresponding JSON parameters
dataset = [
    {
        "input": "Book a flight from New Delhi to New York, departing on December 20, 2024, and returning on January 5, 2025. It's for one adult, born on March 7, 1998. My name is RD Singh, and my contact email is jnnj@gmail.com. My phone number is +1 9144471153.",
        "parameters": {
            "originLocationCode": "DEL",
            "destinationLocationCode": "JFK",
            "departureDate": "2024-12-20",
            "returnDate": "2025-01-05",
            "adults": 1,
            "max": 5,
            "travelers_details": [
                {
                    "dateOfBirth": "1998-03-07",
                    "name": {"firstName": "RD", "lastName": "SINGH"},
                    "gender": "MALE",
                    "contact": {
                        "emailAddress": "jnnj@gmail.com",
                        "phones": [{"deviceType": "MOBILE", "countryCallingCode": "1", "number": "9144471153"}]
                    },
                    "id": "1"
                }
            ]
        }
    },
    {
        "input": "I need to book a round-trip flight for myself from Mumbai to London. I'll leave on January 10, 2025, and come back on January 25, 2025. My name is Aditi Sharma, born on February 15, 1995. My email is aditi.sharma@example.com, and my phone number is +44 7712345678.",
        "parameters": {
            "originLocationCode": "BOM",
            "destinationLocationCode": "LHR",
            "departureDate": "2025-01-10",
            "returnDate": "2025-01-25",
            "adults": 1,
            "max": 5,
            "travelers_details": [
                {
                    "dateOfBirth": "1995-02-15",
                    "name": {"firstName": "Aditi", "lastName": "Sharma"},
                    "gender": "FEMALE",
                    "contact": {
                        "emailAddress": "aditi.sharma@example.com",
                        "phones": [{"deviceType": "MOBILE", "countryCallingCode": "44", "number": "7712345678"}]
                    },
                    "id": "1"
                }
            ]
        }
    },
    {
        "input": "I'd like to book a flight for two people from Bengaluru to Paris. We want to leave on March 5, 2025, and return on March 20, 2025. My details: Aryan Gupta, born on July 12, 1990. The second traveler is Maya Patel, born on August 18, 1992. Contact email is aryan.gupta@email.com, and my phone number is +91 9876543210.",
        "parameters": {
            "originLocationCode": "BLR",
            "destinationLocationCode": "CDG",
            "departureDate": "2025-03-05",
            "returnDate": "2025-03-20",
            "adults": 2,
            "max": 5,
            "travelers_details": [
                {
                    "dateOfBirth": "1990-07-12",
                    "name": {"firstName": "Aryan", "lastName": "Gupta"},
                    "gender": "MALE",
                    "contact": {
                        "emailAddress": "aryan.gupta@email.com",
                        "phones": [{"deviceType": "MOBILE", "countryCallingCode": "91", "number": "9876543210"}]
                    },
                    "id": "1"
                },
                {
                    "dateOfBirth": "1992-08-18",
                    "name": {"firstName": "Maya", "lastName": "Patel"},
                    "gender": "FEMALE",
                    "contact": {
                        "emailAddress": "aryan.gupta@email.com",
                        "phones": [{"deviceType": "MOBILE", "countryCallingCode": "91", "number": "9876543210"}]
                    },
                    "id": "2"
                }
            ]
        }
    },
    {
        "input": "Book me a flight to Tokyo from San Francisco. Departing on April 15, 2025, and returning on April 30, 2025. My name is Kenji Tanaka, born on May 20, 1985. My email is kenji.t@example.co.jp, and my contact number is +81 9045678912.",
        "parameters": {
            "originLocationCode": "SFO",
            "destinationLocationCode": "HND",
            "departureDate": "2025-04-15",
            "returnDate": "2025-04-30",
            "adults": 1,
            "max": 5,
            "travelers_details": [
                {
                    "dateOfBirth": "1985-05-20",
                    "name": {"firstName": "Kenji", "lastName": "Tanaka"},
                    "gender": "MALE",
                    "contact": {
                        "emailAddress": "kenji.t@example.co.jp",
                        "phones": [{"deviceType": "MOBILE", "countryCallingCode": "81", "number": "9045678912"}]
                    },
                    "id": "1"
                }
            ]
        }
    }
]

# Create a DataFrame with two columns: Input and Parameters
df = pd.DataFrame(
    [(entry["input"], json.dumps(entry["parameters"], indent=None)) for entry in dataset],
    columns=["Input", "Parameters"]
)

# Save to CSV
output_csv_path = "./data/travel_booking_dataset.csv"
df.to_csv(output_csv_path, index=False)

# Read the CSV and display the data
df_read = pd.read_csv(output_csv_path)
df_read