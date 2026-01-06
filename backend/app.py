from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Allow the extension to talk to us

@app.route('/verify', methods=['GET'])
def verify():
    # The heartbeat endpoint
    print("💓 Heartbeat received")
    return jsonify({"status": "connected"}), 200

if __name__ == '__main__':
    print("🚀 Backend running on http://localhost:8080")
    app.run(host='0.0.0.0', port=8080, debug=True)