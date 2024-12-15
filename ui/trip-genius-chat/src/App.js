import React, { useState, useEffect, useRef } from 'react';

function App() {
  const [messages, setMessages] = useState([
    { role: 'bot', content: "Welcome to Trip Genius. Enter description of your trip:", isAppending: false }
  ]); 
  const [sessionId, setSessionId] = useState(null);
  const [userInput, setUserInput] = useState('');
  const [waitingForInput, setWaitingForInput] = useState(true);
  const [conversationDone, setConversationDone] = useState(false);
  const [needAutoContinue, setNeedAutoContinue] = useState(false);
  const [initiated, setInitiated] = useState(false); // To track if initiateBooking was called once

  // We no longer call initiateBooking on mount. The first call is triggered by user input.

  useEffect(() => {
    if (needAutoContinue && !conversationDone && !waitingForInput && sessionId && initiated) {
      console.log("Auto continuing booking after message...");
      continueBooking('');
      setNeedAutoContinue(false);
    }
  }, [needAutoContinue, conversationDone, waitingForInput, sessionId, initiated]);

  async function initiateBooking(query) {
    const requestData = {
      query: query
    };

    try {
      const res = await fetch('http://127.0.0.1:8000/initiate_bookings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData)
      });
      if (!res.ok) {
        console.error('Initiate booking request failed', res.statusText);
        return;
      }
      const data = await res.json();
      setInitiated(true); // Now the conversation is initiated
      handleBotResponse(data);
    } catch (error) {
      console.error('Network error while initiating booking:', error);
    }
  }

  async function continueBooking(userResponse) {
    if (!sessionId) {
      console.warn("No session_id available yet, cannot continue booking.");
      return;
    }

    const requestData = {
      session_id: sessionId,
      user_input: userResponse
    };

    console.log("Calling continueBooking with input:", userResponse);

    try {
      const res = await fetch('http://127.0.0.1:8000/continue_booking', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData)
      });
      if (!res.ok) {
        console.error('Continue booking request failed', res.statusText);
        return;
      }
      const data = await res.json();
      handleBotResponse(data);
    } catch (error) {
      console.error('Network error while continuing booking:', error);
    }
  }

  function handleBotResponse(data) {
    const { type, content, session_id, done } = data;
    console.log("Bot response received:", data);

    if (session_id && !sessionId) {
      setSessionId(session_id);
    }

    if (done) {
      // Conversation ends
      setMessages(prev => [...prev, { role: 'bot', content: content, isAppending: false }]);
      setMessages(prev => [...prev, { role: 'bot', content: "Thank you for using Trip Genius!", isAppending: false }]);
      setConversationDone(true);
      setWaitingForInput(false);
      return;
    }

    if (type === 'message') {
      // Just create a new bubble for each message
      setMessages(prev => [...prev, { role: 'bot', content: content, isAppending: false }]);
      setWaitingForInput(false);
      setNeedAutoContinue(true);  // We'll try to auto continue

    } else if (type === 'prompt') {
      // Display a prompt and await user input
      setMessages(prev => [...prev, { role: 'bot', content: content, isAppending: false }]);
      setWaitingForInput(true);
      setNeedAutoContinue(false);
    }
  }

  function handleUserSubmit(e) {
    e.preventDefault();
    if (!userInput.trim() || conversationDone) return;

    // The first submission if not initiated means user is providing the trip query for initiateBooking
    // If conversation is not initiated yet, we call initiateBooking with user query
    if (!initiated) {
      // User input is the initial query
      setMessages(prev => [...prev, { role: 'user', content: userInput, isAppending: false }]);
      initiateBooking(userInput);
    } else {
      // Conversation already initiated, so continue booking
      setMessages(prev => [...prev, { role: 'user', content: userInput, isAppending: false }]);
      continueBooking(userInput);
    }

    setUserInput('');
  }

  return (
    <div style={{ maxWidth: '600px', margin: '0 auto', fontFamily: 'Arial, sans-serif' }}>
      <h1>Trip Genius</h1>
      <div style={{
        border: '1px solid #ccc',
        padding: '10px',
        height: '500px',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column'
      }}>
        {messages.map((msg, index) => (
          <div
            key={index}
            style={{
              marginBottom: '10px',
              textAlign: msg.role === 'user' ? 'right' : 'left'
            }}
          >
            <div style={{
              display: 'inline-block',
              background: msg.role === 'user' ? '#daf1da' : '#f1f1f1',
              padding: '10px',
              borderRadius: '10px',
              maxWidth: '80%',
              whiteSpace: 'pre-wrap'
            }}>
              {msg.content}
            </div>
          </div>
        ))}
      </div>
      {!conversationDone && (
        <form onSubmit={handleUserSubmit} style={{ marginTop: '10px', display: 'flex' }}>
          <input
            type="text"
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
            placeholder={initiated ? "Type your response..." : "Describe your trip..."}
            style={{ flex: 1, padding: '10px' }}
          />
          <button type="submit" style={{ marginLeft: '10px', padding: '10px 20px' }}>
            {initiated ? "Send" : "Start"}
          </button>
        </form>
      )}
    </div>
  );
}

export default App;
