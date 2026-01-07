const SERVER_URL = 'http://localhost:8080';

let state = {
    isConnected: false,
    sessionStatus: "IDLE", // IDLE, RUNNING, PAUSED
    sessionName: "",       // User input
    serverSessionName: ""  // Actual folder name
};

/************************************************/
/*****************Heartbeat*backend**************/
/************************************************/
setInterval(async () => {
    try { 
        const response = await fetch(`${SERVER_URL}/verify`);
        if (response.ok) { 
            state.isConnected = true;
        }else {
            throw new Error("Server error");
        }
        
    } catch (error) {
        state.isConnected = false;
        // Auto-pause if connection drops
        if (state.sessionStatus === "RUNNING") {
            state.sessionStatus = "PAUSED";
        }
    }
    chrome.runtime.sendMessage({ action: "STATUS_UPDATE", state: state }).catch(() => {});
}, 6000);


/************************************************/
/*****************with*popup.js******************/
/************************************************/

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {

    if (request.action === "GET_STATUS") {
        sendResponse(state);
    } 
    else if (request.action === "UPDATE_SESSION") {
        handleSessionUpdate(request, sendResponse);        
        return true; 
    }
});


// Helper function to handle the async backend calls
async function handleSessionUpdate(request, sendResponse) {
    const { status, name } = request.payload;
    const oldStatus = state.sessionStatus;

    // 1. STARTING A SESSION (IDLE -> RUNNING)
    if (status === "RUNNING" && oldStatus === "IDLE") {
        try {
            
            const response = await fetch(`${SERVER_URL}/start-session`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ session_name: name })
            });
            const data = await response.json();

            state.sessionStatus = "RUNNING";
            state.sessionName = name; 
            state.serverSessionName = data.session_name;

            sendResponse({ success: true, newState: state });
            recordEvent("SESSION_STARTED", state.serverSessionName);
            logCurrentTab(state.serverSessionName);

        } catch (error) {
            sendResponse({ success: false, error: "Backend error" });
        }
    } 

    // 2. ANY OTHER CHANGE (Pause, Resume, End)
    else {
        // Update local state immediately
        if(status) state.sessionStatus = status;
        if(name !== undefined) state.sessionName = name;
        
        // If Ending, clear the server name
        if (status === "IDLE") {
            recordEvent("SESSION_END", state.serverSessionName);
            state.serverSessionName = "";
        } else if (status === "PAUSED") {
            recordEvent("SESSION_PAUSED", state.serverSessionName);
        }else if (oldStatus ==="PAUSED" && status === "RUNNING"){
            recordEvent("SESSION_RESUMED", state.serverSessionName);
            logCurrentTab(state.serverSessionName);
        }

        sendResponse({ success: true, newState: state });
    }
}

// Simple helper to send markers without waiting for response
function recordEvent(label, sessionName) {
    if (!sessionName) return;

    fetch(`${SERVER_URL}/record-page`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            session_name: sessionName,
            url: label, // "SESSION_END", "SESSION_PAUSED", etc
            window_size: "N/A"
        })
    }).catch(err => console.log("Log error:", err));
}

function logCurrentTab(sessionName) {
    chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
        if (tabs && tabs[0] && tabs[0].url) {
            const tab = tabs[0];
            fetch(`${SERVER_URL}/record-page`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    session_name: sessionName,
                    url: tab.url,
                    window_size: `${tab.width}x${tab.height}`
                })
            }).catch(err => console.error("Snapshot error:", err));
        }
    });
}



chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    // Only record if RUNNING and page is done loading
    if (state.sessionStatus === "RUNNING" && changeInfo.status === 'complete' && tab.url) {
        if (!state.serverSessionName) return;

        fetch(`${SERVER_URL}/record-page`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                session_name: state.serverSessionName,
                url: tab.url,
                window_size: `${tab.width}x${tab.height}`
            })
        }).catch(err => console.error(err));
    }
});