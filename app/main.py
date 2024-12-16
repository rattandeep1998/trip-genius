from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.core.booking_agent import initiate_bookings
import uuid
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware

SESSIONS = {}

app = FastAPI(title="Travel Booking Agent API")

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Allows your React frontend to connect
    allow_credentials=True,
    allow_methods=["*"],    # Allows all methods (POST, GET, etc.)
    allow_headers=["*"],    # Allows all headers
)

class BookingRequest(BaseModel):
    query: str
    interactive_mode: bool = True
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

        session_id = str(uuid.uuid4())
        SESSIONS[session_id] = result

        try:
            response = next(result)
            type = response.get("type", "message")
            text = response.get("text", "")
            return {"session_id": session_id, "content": text, "type": type}
        except StopIteration as e:
            final_result = e.value

            type = "message"
            text = final_result.get("complete_summary", "")

            del SESSIONS[session_id]
            return {"session_id": session_id, "type": type, "content": text, "done": True}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ContinueBookingRequest(BaseModel):
    session_id: str
    user_input: Optional[str] = None

@app.post("/continue_booking")
def continue_booking(request: ContinueBookingRequest):
    session_id = request.session_id
    user_input = request.user_input

    if session_id not in SESSIONS:
        raise HTTPException(status_code=400, detail="Invalid session_id")
    
    function = SESSIONS[session_id]

    try:
        # Send user input to the generator and get the next yielded response
        response = function.send(user_input)
        type = response.get("type", "message")
        text = response.get("text", "")
        return {"session_id": session_id, "content": text, "type": type}
    except StopIteration as e:
        final_result = e.value

        type = "message"
        text = final_result.get("complete_summary", "")

        del SESSIONS[session_id]
        return {"session_id": session_id, "type": type, "content": text, "done": True}
    except Exception as e:
        # Handle any other exceptions
        del SESSIONS[session_id]
        raise HTTPException(status_code=500, detail=str(e))
