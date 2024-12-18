import unittest
from unittest.mock import patch, MagicMock
from app.core.booking_agent import FlightBookingTool, HotelBookingTool, ItinerarySuggestionTool
import os

class TestFlightBookingTool(unittest.TestCase):
    
    @patch.dict(os.environ, {"AMADEUS_CLIENT_ID": "test_client_id", "AMADEUS_CLIENT_SECRET": "test_client_secret"})
    @patch("requests.post")
    @patch("requests.get")
    def test_flight_booking_success(self, mock_get, mock_post):
        # Mock token response
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {'access_token': 'fake_access_token'}
        
        # Mock flight offers response
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {"data": [{"itineraries": [{"segments": [{"departure": {"iataCode": "JFK", "at": "2024-12-20T10:00"}, "arrival": {"iataCode": "LAX", "at": "2024-12-20T13:00"}, "carrierCode": "AA"}]}], "price": {"grandTotal": "500", "currency": "USD"}}], "dictionaries": {"carriers": {"AA": "American Airlines"}}}
        
        tool = FlightBookingTool()
        result = tool._run(
            originLocationCode="JFK",
            destinationLocationCode="LAX",
            departureDate="2024-12-20",
            returnDate="2024-12-25",
            adults=1,
            verbose=False,
            interactive_mode=False
        )
        
        self.assertIn("data", result)
        self.assertEqual(result["_flight_api_calls"], 2)
        self.assertEqual(result["_flight_api_success"], 2)

    @patch.dict(os.environ, {})
    def test_flight_booking_missing_credentials(self):
        tool = FlightBookingTool()
        result = tool._run(
            originLocationCode="JFK",
            destinationLocationCode="LAX",
            departureDate="2024-12-20",
            returnDate="2024-12-25",
            adults=1,
            verbose=False,
            interactive_mode=False
        )
        
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Missing credentials for Amadeus API.")

class TestHotelBookingTool(unittest.TestCase):

    @patch.dict(os.environ, {"AMADEUS_CLIENT_ID": "test_client_id", "AMADEUS_CLIENT_SECRET": "test_client_secret"})
    @patch("requests.post")
    @patch("requests.get")
    def test_hotel_booking_success(self, mock_get, mock_post):
        # Mock token response
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {'access_token': 'fake_access_token'}
        
        # Mock hotel offers response
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {"data": [{"hotelId": "HOTEL1", "hotel": {"name": "Test Hotel"}, "offers": [{"price": {"total": "300", "currency": "USD"}, "checkInDate": "2024-12-20", "checkOutDate": "2024-12-25"}]}]}
        
        tool = HotelBookingTool()
        result = tool._run(
            originLocationCode="JFK",
            destinationLocationCode="NYC",
            departureDate="2024-12-20",
            returnDate="2024-12-25",
            adults=1,
            travelers_details=[],
            verbose=False,
            interactive_mode=False
        )

        self.assertIn("data", result)
        self.assertEqual(result["_hotel_api_calls"], 2)
        self.assertEqual(result["_hotel_api_success"], 2)

class TestItinerarySuggestionTool(unittest.TestCase):

    @patch.dict(os.environ, {"AMADEUS_CLIENT_ID": "test_client_id", "AMADEUS_CLIENT_SECRET": "test_client_secret"})
    @patch("requests.post")
    @patch("requests.get")
    def test_itinerary_success(self, mock_get, mock_post):
        # Mock token response
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {'access_token': 'fake_access_token'}
        
        # Mock activities response
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {"data": [{"name": "Test Activity", "geoCode": {"latitude": 40.7128, "longitude": -74.0060}}]}
        
        tool = ItinerarySuggestionTool()
        result = tool._run(
            originLocationCode="JFK",
            destinationLocationCode="NYC",
            departureDate="2024-12-20",
            returnDate="2024-12-25",
            adults=1,
            destinationCountry="US",
            destinationCity="New York",
            verbose=False,
            interactive_mode=False
        )

        self.assertIn("travel_plan", result)
        self.assertEqual(result["_itinerary_api_calls"], 2)
        self.assertEqual(result["_itinerary_api_success"], 2)

if __name__ == "__main__":
    unittest.main()