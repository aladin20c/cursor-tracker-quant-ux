Cursor & UX Quant Tracker
This project is a Quantitative UX Research tool designed to track user behavior on websites. It captures high-fidelity interaction data (clicks, hovers, and scrolls) and stores them in a structured format to generate heatmaps and behavioral flowcharts.


Project Structure

/extension: The Chrome Extension (Frontend). It injects logic into websites to listen for user interactions.

/backend: A Python Flask/FastAPI server (app.py) that receives data batches from the extension and saves them.

/backend/data: The storage hub where interaction data is saved as .csv files for later analysis.





Getting Started

1. Setup the Backend

The backend acts as the "Receiver" for all tracked data.


Install dependencies: 

pip3 install flask flask-cors pandas

then : 

python3 ./backend/app.py




2. Install the Extension

Open Chrome and go to chrome://extensions/.

Enable Developer Mode (top right toggle).

Click Load unpacked and select your /extension folder.

Pin the extension to your toolbar.



