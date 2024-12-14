from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.core.booking_agent import initiate_bookings

app = FastAPI(title="Travel Booking Agent API")

class BookingRequest(BaseModel):
    query: str
    interactive_mode: bool = False
    verbose: bool = True
    use_real_api: bool = True

@app.post("/initiate_bookings")
def initiate_bookings_endpoint(request: BookingRequest):
    try:
        result = initiate_bookings(
            query=request.query,
            interactive_mode=request.interactive_mode,
            verbose=request.verbose,
            use_real_api=request.use_real_api,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))