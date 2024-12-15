from booking_agent import initiate_bookings
import json

# Example usage
if __name__ == "__main__":
    # sample_query = "Book me a trip for Mr. Rattandeep Singh born on 7th March 1998 to New York from 20th December 2024 to 5th January 2025. I am currently located at New Delhi."
    
    sample_query = "Book me a trip for Mr. Rattandeep Singh born on 7th March 1998 to New York from 20th December 2024 to 5th January 2025. I am currently located at New Delhi."

    sample_query = "Book a flight from New Delhi to New York, departing on December 20, 2024, and returning on January 5, 2025. It's for one adult, born on March 7, 1998. My name is RD Singh, and my contact email is jnnj@gmail.com. My phone number is +1 9144471153."
    
    # sample_query = "Hello"
    
    results = initiate_bookings(sample_query)

    booking_params = results['booking_params']
    print("\nFlight Booking Parameters:")
    print(json.dumps(booking_params, indent=2))