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
    } else if (request.action === "LOG_EVENT") {
        // Only log if session is RUNNING
        if (state.sessionStatus === "RUNNING" && state.serverSessionName) {
            
            fetch(`${SERVER_URL}/record-event`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    session_name: state.serverSessionName,
                    ...request.payload 
                })
            }).catch(err => console.log("Drop:", err));
        }
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

            recordEvent("SESSION_RUNNING", state.serverSessionName)
            .then(() => logCurrentTab(state.serverSessionName))
            .then();

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
            recordEvent("SESSION_RESUMED", state.serverSessionName)
            .then(() => logCurrentTab(state.serverSessionName))
            .then();
        }

        sendResponse({ success: true, newState: state });
    }
}

// Simple helper to send markers without waiting for response
function recordEvent(label, sessionName) {
    return sendPageRecord(sessionName, label, "N/A", "N/A");
}

function logCurrentTab(sessionName) {
    return new Promise((resolve) => {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            const tab = tabs?.[0];
            if (tab?.url) {
                const size = `${tab.width}x${tab.height}`;
                sendPageRecord(sessionName, tab.url, tab.width, tab.height).then(resolve);
            } else {
                resolve();
            }
        });
    });
}



chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (state.sessionStatus !== "RUNNING") return;
    if (changeInfo.status !== 'complete') return;
    if (!tab.url || !state.serverSessionName) return;

    (async () => {
        await sendPageRecord(state.serverSessionName, tab.url, tab.width, tab.height);
    })();
});


chrome.tabs.onActivated.addListener(async ({ tabId }) => {
    if (state.sessionStatus !== "RUNNING" || !state.serverSessionName) return;

    const tab = await chrome.tabs.get(tabId);
    if (!tab.url) return;

    try {
        const tab = await chrome.tabs.get(tabId);
        if (!tab.url) return;
        await sendPageRecord(state.serverSessionName, tab.url, tab.width, tab.height);
    } catch (err) {
        console.error(err);
    }
});


function sendPageRecord(sessionName, url, width, height) {
    
    if (!sessionName || !url) return Promise.resolve();

    return fetch(`${SERVER_URL}/record-page`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            session_name: sessionName,
            url: url,
            window_size: `${width}x${height}`,
            timestamp: Date.now()
        })
    }).catch(err => console.error(err));
}