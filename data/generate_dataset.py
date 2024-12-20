import json
import pandas as pd

# Define the dataset with natural language inputs and corresponding JSON parameters
dataset = [
    #Flight booking
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
        },
        "intent":"flight"
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
        },
        "intent":"flight"
    },
    #Flight booking for multiple travellers
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
        },
        "intent":"flight"
    },
    #Hotel Booking
    {
    "input": "I need a hotel in Paris from January 10 to January 15, 2025, for two adults. Please use INR as the currency. The travelers are Anjali Sharma (born July 3, 1990) and Raj Verma (born March 20, 1992). Contact: 9000567393, anjani@gmail.com",
    "parameters": {
        "originLocationCode": "",
        "destinationLocationCode": "PAR",
        "departureDate": "2025-01-10",
        "returnDate": "2025-01-15",
        "adults": 2,
        "max": 5,
        "originCurrencyCode": "INR",
        "travelers_details": [
            {
                "dateOfBirth": "1990-07-03",
                "name": {"firstName": "Anjali", "lastName": "Sharma"},
                "gender": "FEMALE",
                "contact": {"emailAddress": "anjani@gmail.com", "phones": [{"deviceType": "MOBILE", "countryCallingCode": "1", "number": "9000567393"}]},
                "id": "1"
            },
            {
                "dateOfBirth": "1992-03-20",
                "name": {"firstName": "Raj", "lastName": "Verma"},
                "gender": "MALE",
                "contact": {"emailAddress": "anjani@gmail.com", "phones": [{"deviceType": "MOBILE", "countryCallingCode": "1", "number": "9000567393"}]},
                "id": "2"
            }
            ]
            },
        "intent":"hotel"
    },
    #Hotel booking for multiple travellers
    {
        "input": "Book me a hotel to Tokyo from San Francisco. Departing on April 15, 2025, and returning on April 30, 2025. My name is Kenji Tanaka, born on May 20, 1985. My email is kenji.t@example.co.jp, and my contact number is +81 9045678912.",
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
        },
        "intent":"hotel"
    },
    #Travel Plan
    {
    "input": "Provide travel plan from Los Angeles to Tokyo on February 14, 2025, returning February 28, 2025.",
    "parameters": {
        "originLocationCode": "LAX",
        "destinationLocationCode": "NRT",
        "departureDate": "2025-02-14",
        "returnDate": "2025-02-28",
        "adults": 0,
        "max": 5,
        "travelers_details": []
        },
        "intent":"itinerary"
    },
    #Trip Booking
    {
    "input": "Plan a solo trip to Bali from New York for 7 days starting from March 10, 2025. I want to explore beaches, try local cuisine, and visit cultural landmarks. My name is Anya Kapoor, born on Feb 7 2005 and my contact email is anya.kapoor@gmail.com, 3121234567",
    "parameters": {
        "originLocationCode": "JFK",
        "destinationLocationCode": "DPS",
        "departureDate": "2025-03-10",
        "returnDate": "2025-03-17",
        "adults": 1,
        "travelPlanPreference": "Explore beaches, local cuisine, cultural landmarks",
        "max": 5,
        "travelers_details": [
            {
                "dateOfBirth": "2005-02-07",
                "name": {"firstName": "Anya", "lastName": "Kapoor"},
                "gender": "FEMALE",
                "contact": {
                    "emailAddress": "anya.kapoor@gmail.com",
                    "phones": [{"deviceType": "MOBILE", "countryCallingCode": "1", "number": "3121234567"}]
                },
                "id": "1"
            }
            ]
        },
        "intent":"trip"
    },
    #Group Trip Booking
    {
    "input": "Plan a trip for my family of 4 (2 adults and 2 children, ages 5 and 8). Departure from Sydney to Singapore on April 5, 2025, and return on April 12, 2025. The adults are John Doe (born June 12, 1980) and Jane Doe (born August 30, 1982). The children are Bobby Joe(born June 12, 2005) and Sherly Doe (born August 30, 2006) .email: john.doe@email.com, phone:5121234567",
    "parameters": {
        "originLocationCode": "SYD",
        "destinationLocationCode": "SIN",
        "departureDate": "2025-04-05",
        "returnDate": "2025-04-12",
        "adults": 4,
        "max": 5,
        "travelers_details": [
            {
                "dateOfBirth": "1980-06-12",
                "name": {"firstName": "John", "lastName": "Doe"},
                "gender": "MALE",
                "contact": {
                    "emailAddress": "john.doe@email.com",
                    "phones": [{"deviceType": "MOBILE", "countryCallingCode": "1", "number": "5121234567"}]
                },
                "id": "1"
            },
            {
                "dateOfBirth": "1982-08-30",
                "name": {"firstName": "Jane", "lastName": "Doe"},
                "gender": "FEMALE",
                "contact": {
                    "emailAddress": "john.doe@email.com",
                    "phones": [{"deviceType": "MOBILE", "countryCallingCode": "1", "number": "5121234567"}]
                },
                "id": "2"
            },
            {
                "dateOfBirth": "2005-06-12",
                "name": {"firstName": "Bobby", "lastName": "Doe"},
                "gender": "MALE",
               "contact": {
                    "emailAddress": "john.doe@email.com",
                    "phones": [{"deviceType": "MOBILE", "countryCallingCode": "1", "number": "5121234567"}]
                },
                "id": "3"
            },
            {
                "dateOfBirth": "2006-08-30",
                "name": {"firstName": "Sherly", "lastName": "Doe"},
                "gender": "FEMALE",
                "contact": {
                    "emailAddress": "john.doe@email.com",
                    "phones": [{"deviceType": "MOBILE", "countryCallingCode": "1", "number": "5121234567"}]
                },
                "id": "4"
            }
            ]
            },
        "intent":"trip"
    },
    {
    "input": "I want to plan a trip to Tokyo from New York. I’ll depart on February 15, 2025, and return on February 25, 2025. It’s just me. My name is Mrs Anna Johnson, born on January 12, 1990. My email is anna.johnson@example.com, and my phone number is +1 9175551234.",
    "parameters": {
        "originLocationCode": "JFK",
        "destinationLocationCode": "NRT",
        "departureDate": "2025-02-15",
        "returnDate": "2025-02-25",
        "adults": 1,
        "max": 5,
        "travelers_details": [
            {
                "dateOfBirth": "1990-01-12",
                "name": {"firstName": "Anna", "lastName": "Johnson"},
                "gender": "FEMALE",
                "contact": {
                    "emailAddress": "anna.johnson@example.com",
                    "phones": [{"deviceType": "MOBILE", "countryCallingCode": "1", "number": "9175551234"}]
                },
                "id": "1"
            }
        ]
    },
    "intent":"trip"
    }
]

# Create a DataFrame with two columns: Input and Parameters
df = pd.DataFrame(
    [(entry["input"], json.dumps(entry["parameters"], indent=None), entry["intent"]) for entry in dataset],
    columns=["Input", "Parameters", "Intent"]
)

# Save to CSV
output_csv_path = "./data/travel_booking_dataset_1.csv"
df.to_csv(output_csv_path, index=False)

# Read the CSV and display the data
df_read = pd.read_csv(output_csv_path)
df_read