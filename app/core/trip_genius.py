from app.core.booking_agent import initiate_bookings
import json

if __name__ == "__main__":
    sample_query = (
        "Book a flight from New Delhi to New York, departing on December 20, 2024, "
        "and returning on January 5, 2025. It's for one adult, born on March 7, 1998. "
        "My name is RD Singh, and my contact email is jnnj@gmail.com. "
        "My phone number is +1 9144471153."
    )

    sample_query = "I'd like to book a flight for two people from Bengaluru to Paris. We want to leave on March 5, 2025, and return on March 20, 2025. My details: Aryan Gupta, born on July 12, 1990. The second traveler is Maya Patel, born on August 18, 1992. Contact email is aryan.gupta@email.com, and my phone number is +91 9876543210."

    # Get the generator
    gen = initiate_bookings(sample_query)

    # Start execution of the generator until the first yield
    try:
        response = next(gen)  # This runs until the first yield
    except StopIteration as e:
        # If the generator finishes immediately without yielding, handle that
        final_result = e.value if hasattr(e, 'value') else None
        if final_result and 'booking_params' in final_result:
            print("\nFlight Booking Parameters:")
            print(json.dumps(final_result['booking_params'], indent=2))
        else:
            print("No booking parameters found.")
        exit(0)

    # This loop will continue until the generator is exhausted
    while True:
        # The `response` variable holds whatever was yielded by the generator
        # Display it to the user. It might be a question, a prompt, or a status update.
        print(response)

        # Prompt the user for input if needed
        user_input = input("Your input (or just press enter if not required): ")

        try:
            # Send the user input back into the generator to resume execution
            # The generator should have `input()` calls replaced by yields where needed.
            response = gen.send(user_input)
        except StopIteration as e:
            # The generator is done. `e.value` may contain the final result.
            final_result = e.value if hasattr(e, 'value') else None
            # if final_result and 'booking_params' in final_result:
            #     print("\nFlight Booking Parameters:")
            #     print(json.dumps(final_result['booking_params'], indent=2))
            # else:
            #     print("No booking parameters found.")

            if final_result:
                print("\nFinal Result:")
                print(json.dumps(final_result, indent=2))
            else:
                print("No booking parameters found.")
            break
