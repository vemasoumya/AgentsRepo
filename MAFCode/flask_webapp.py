from flask import Flask, render_template, request, jsonify, session
from agent_hotel_web import HotelAgent
import asyncio
import uuid
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Global agent instance and session store
agent = None
loop = None
sessions = {}  # session_id → AgentSession


def get_or_create_event_loop():
    global loop
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
    return loop


async def init_agent():
    global agent
    if agent is None:
        agent = HotelAgent()
        await agent.__aenter__()


def run_async(coro):
    lp = get_or_create_event_loop()
    return lp.run_until_complete(coro)


# Initialize agent at startup
run_async(init_agent())


@app.route('/')
def index():
    """Render the main chat interface."""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return render_template('index.html')


@app.route("/chat", methods=["POST"])
def chat():
    """Handle chat messages from the frontend."""
    try:
        data = request.get_json()
        user_message = data.get("message", "").strip()

        if not user_message:
            return jsonify({"error": "Empty message"}), 400

        session_id = session.get('session_id', str(uuid.uuid4()))

        if session_id not in sessions:
            sessions[session_id] = agent.create_session(session_id=session_id)

        response = run_async(agent.chat(user_message, session=sessions[session_id]))

        return jsonify({
            "response": response,
            "status": "success"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/clear', methods=['POST'])
def clear_chat():
    """Clear the chat history for this session."""
    session_id = session.get('session_id')
    if session_id:
        sessions.pop(session_id, None)
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)