const els = {
    dot: document.getElementById('statusDot'),
    text: document.getElementById('statusText'),
    input: document.getElementById('sessionName'),
    start: document.getElementById('startBtn'),
    pause: document.getElementById('pauseBtn'),
    resume: document.getElementById('resumeBtn'),
    end: document.getElementById('endBtn')
};

// Local variable to track if user is currently typing
let isUserTyping = false;

function updateUI(state) {
    const { isConnected, sessionStatus, sessionName } = state;

    // 1. Connection UI
    if (isConnected) {
        els.dot.className = "dot green";
        els.text.textContent = "Connected";
    } else {
        els.dot.className = "dot red";
        els.text.textContent = "Disconnected";
    }

    // 2. Input Field Management
    // Only overwrite value if user is NOT typing, or if session is locked (RUNNING/PAUSED)
    if (!isUserTyping || sessionStatus !== "IDLE") {
        els.input.value = sessionName || "";
    }

    // Lock input if session is active
    els.input.disabled = (sessionStatus !== "IDLE");

    // 3. Button Visibility
    hideAllButtons();
    
    // Check local input value for validation, not just state
    const currentName = els.input.value.trim();
    const canStart = isConnected && currentName.length > 0;

    if (sessionStatus === "IDLE") {
        els.start.classList.remove('hidden');
        els.start.disabled = !canStart; 
    } else if (sessionStatus === "RUNNING") {
        els.pause.classList.remove('hidden');
        els.end.classList.remove('hidden');
    } else if (sessionStatus === "PAUSED") {
        els.resume.classList.remove('hidden');
        els.end.classList.remove('hidden');
    }
}

function hideAllButtons() {
    [els.start, els.pause, els.resume, els.end].forEach(b => b.classList.add('hidden'));
}



// --- Communication ---

function syncState() {
    chrome.runtime.sendMessage({ action: "GET_STATUS" }, (state) => {
        if(state) updateUI(state);
    });
}

function sendUpdate(status) {
    chrome.runtime.sendMessage({ 
        action: "UPDATE_SESSION", 
        payload: { status: status, name: els.input.value } 
    }, (response) => {
        updateUI(response.newState);
    });
}

// --- Listeners ---

// Fix: Don't sync entire state on input, just validate button locally
els.input.addEventListener('input', () => {
    isUserTyping = true;
    // We just manually trigger a UI refresh to check button validity
    // We fake a state object to avoid fetching from background while typing
    chrome.runtime.sendMessage({ action: "GET_STATUS" }, (state) => {
         // Keep the typed name in the UI, don't let state overwrite it yet
         updateUI({ ...state, sessionName: els.input.value });
    });
});

els.input.addEventListener('blur', () => {
    isUserTyping = false;
    // When user leaves the field, save the name to background
    sendUpdate("IDLE"); 
});

els.start.addEventListener('click', () => sendUpdate("RUNNING"));
els.pause.addEventListener('click', () => sendUpdate("PAUSED"));
els.resume.addEventListener('click', () => sendUpdate("RUNNING"));
els.end.addEventListener('click', () => {
    chrome.runtime.sendMessage({ 
        action: "UPDATE_SESSION", 
        payload: { status: "IDLE", name: "" } 
    }, (response) => {
        isUserTyping = false; // Reset typing flag
        updateUI(response.newState);
    });
});

// Initial Load
syncState();

// Listen for background changes (heartbeat)
chrome.storage.onChanged.addListener((changes) => {
    if (changes.appState) {
        updateUI(changes.appState.newValue);
    }
});