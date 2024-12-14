from booking_agent import initiate_bookings
import json

# Example usage
if __name__ == "__main__":
    sample_query = "Book me a trip for Mr. Rattandeep Singh born on 7th March 1998 to New York from 20th December 2024 to 5th January 2025. I am currently located at New Delhi."
    
    results = initiate_bookings(sample_query, use_real_api=False)

    booking_params = results['booking_params']
    print("\nFlight Booking Parameters:")
    print(json.dumps(booking_params, indent=2))