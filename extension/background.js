let state = {
    isConnected: false,
    sessionStatus: "IDLE",
    sessionName: ""
};

// HEARTBEAT (6 Seconds)
setInterval(async () => {
    try {
        const response = await fetch('http://localhost:8080/verify');
        if (response.ok) {
            if (!state.isConnected) console.log("Connection Established");
            state.isConnected = true;
        } else {
            throw new Error("Server error");
        }
    } catch (error) {
        state.isConnected = false;
        // Auto-pause if connection drops
        if (state.sessionStatus === "RUNNING") {
            state.sessionStatus = "PAUSED";
        }
    }
    chrome.storage.local.set({ appState: state });
}, 6000);


// MESSAGE LISTENER
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log("Message Received:", request.action);

    if (request.action === "GET_STATUS") {
        sendResponse(state);
    } 
    else if (request.action === "UPDATE_SESSION") {
        if(request.payload.status) state.sessionStatus = request.payload.status;
        // Only update name if provided (don't overwrite with empty if not intended)
        if(request.payload.name !== undefined) state.sessionName = request.payload.name;
        
        chrome.storage.local.set({ appState: state });
        sendResponse({ success: true, newState: state });
    }
});