import os
import csv
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path


app = Flask(__name__)
CORS(app)
DATA_DIR = str(Path(__file__).resolve().parent / "data")


###########################################################
###########################################################
###########################################################
# The heartbeat endpoint
@app.route('/verify', methods=['GET'])
def verify():
    return jsonify({"status": "connected"}), 200



###########################################################
###########################################################
###########################################################
def get_new_folder_path(base_name):
    """
    Checks if a folder exists. If so, appends _1, _2, etc.
    Returns the clean, unique folder path and the final name.
    """
    if not base_name or base_name.strip() == "" : base_name = "Untitled_Session"
    clean_name = "".join([c for c in base_name if c.isalnum() or c in (' ', '_', '-')]).strip()
    clean_name = clean_name.replace(" ", "_")
    folder_path = os.path.join(DATA_DIR, clean_name)
    if not os.path.exists(folder_path): return folder_path, base_name
    
    counter = 1
    while True:
        new_name = f"{clean_name}_{counter}"
        new_path = os.path.join(DATA_DIR, new_name)
        if not os.path.exists(new_path): return new_path, new_name
        counter += 1


def initialize_csvs(folder_path):
    """Creates the two empty CSV files with headers"""
    os.makedirs(folder_path, exist_ok=True)
    
    # Page Log
    with open(os.path.join(folder_path, "pages.csv"), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "start_time", "window_size"])

    # Event Log
    with open(os.path.join(folder_path, "events.csv"), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "event_type", "target", "x", "y", "metadata"])



@app.route('/start-session', methods=['POST'])
def start_session():
    
    # Handle missing fields
    data = request.json or {}
    if "session_name" not in data:
        return jsonify({ "status": "error","message": "Missing required fields"}), 400
    
    requested_name = data.get("session_name")
    
    # Generate Unique Name
    folder_path, final_name = get_new_folder_path(requested_name)
    # Create Files
    initialize_csvs(folder_path)
    
    print(f"Created session : {final_name}")
    # Return the ACTUAL name used (in case of duplicates) so frontend knows it
    return jsonify({ "status": "started",  "session_name": final_name }), 200


###########################################################
###########################################################
###########################################################

@app.route('/record-page', methods=['POST'])
def record_page():

    # Handle missing fields
    data = request.json or {}
    if "url" not in data or "session_name" not in data or "window_size" not in data:
        return jsonify({ "status": "error","message": "Missing required fields"}), 400
    
    session_name = data.get("session_name")
    url = data.get("url")
    window_size = data.get("window_size")
    
    timestamp = data.get("timestamp")
    if not timestamp: timestamp = int(time.time() * 1000)
    
    # Handle empty new tabs
    if not url or (isinstance(url, str) and url.lower() in {"null", "undefined"}):
        url = "BLANK_TAB"
    
    # Get Path
    folder_path = os.path.join(DATA_DIR, session_name)
    if not os.path.exists(folder_path): return jsonify({"error": "Session not found"}), 404

    # Append to pages.csv
    file_path = os.path.join(folder_path, "pages.csv")
    with open(file_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([url, timestamp, window_size])
        
    print(f"Logged Page: {url} in {session_name}")
    return jsonify({"status": "logged"}), 200




###########################################################
###########################################################
###########################################################



@app.route('/record-event', methods=['POST'])
def record_event():
    data = request.json or {}
    session_name = data.get("session_name")
    
    if not session_name: return '', 204

    folder_path = os.path.join(DATA_DIR, session_name)
    if os.path.exists(folder_path):
        try:
            file_path = os.path.join(folder_path, "events.csv")
            
            # Check if we need headers
            write_header = not os.path.exists(file_path) or os.path.getsize(file_path) == 0
            
            with open(file_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                
                # 1. WRITE HEADERS (Exact match to your object keys)
                if write_header:
                    writer.writerow([
                        "timestamp", "type", "url", 
                        "selector", "tagName", "id", "className", "innerText", "outerHTML",
                        "x_viewport", "y_viewport", "x_page", "y_page",
                        "scrollX", "scrollY", "viewportW", "viewportH",
                        "docWidth", "docHeight"
                    ])

                # 2. WRITE ROW
                writer.writerow([
                    data.get("timestamp"),
                    data.get("type"),
                    data.get("url"),
                    # Element Identity
                    data.get("selector"),
                    data.get("tagName"),
                    data.get("id"),
                    data.get("className"),
                    data.get("innerText").replace("\n", " ").replace("\r", " "),
                    data.get("outerHTML").replace("\n", " ").replace("\r", " "),
                    # Coordinates
                    data.get("x_viewport"),
                    data.get("y_viewport"),
                    data.get("x_page"),
                    data.get("y_page"),
                    # Context
                    data.get("scrollX"),
                    data.get("scrollY"),
                    data.get("viewportW"),
                    data.get("viewportH"),
                    data.get("docWidth"),
                    data.get("docHeight")
                ])
                
            print(f" > {data.get('type').upper()} saved: {data.get('tagName')} ({data.get('x_viewport')},{data.get('y_viewport')})")

        except Exception as e:
            print(f"Error: {e}")

    return '', 204



# Main
if __name__ == '__main__':
    if not os.path.exists(DATA_DIR):
        print("Creating data directory...")
        os.makedirs(DATA_DIR)
    print("Backend running on http://localhost:8080")
    app.run(host='0.0.0.0', port=8080, debug=True)