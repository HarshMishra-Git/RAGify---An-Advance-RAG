from app import app, socketio

if __name__ == "__main__":
    socketio.run(app, host="127.0.0.1", port=3000, debug=True, allow_unsafe_werkzeug=True)