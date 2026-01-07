/************************************************/
/*****************Ui*elements********************/
/************************************************/
const els = {
    dot: document.getElementById('statusDot'),
    text: document.getElementById('statusText'),
    input: document.getElementById('sessionName'),
    start: document.getElementById('startBtn'),
    pause: document.getElementById('pauseBtn'),
    resume: document.getElementById('resumeBtn'),
    end: document.getElementById('endBtn')
};

function hideAllButtons() {
    [els.start, els.pause, els.resume, els.end].forEach(b => b.classList.add('hidden'));
}

let isUserTyping = false;


/************************************************/
/************Sync Logic****************/
/************************************************/

// 1. Ask Background for current status immediately
chrome.runtime.sendMessage({ action: "GET_STATUS" }, (state) => {
    if(state) updateUI(state);
});

chrome.runtime.onMessage.addListener((msg) => {
    if (msg.action === "STATUS_UPDATE") {
        updateUI(msg.state);
    }
});

function sendUpdate(status) {
    chrome.runtime.sendMessage({ 
        action: "UPDATE_SESSION", 
        payload: { status: status, name: els.input.value } 
    }, (response) => {
        if(response && response.newState) updateUI(response.newState);
    });
}


/************************************************/
/*****************UI Updates*********************/
/************************************************/
function updateUI(state) {
    // Connection UI
    if (state.isConnected) {
        els.dot.className = "dot green";
        els.text.textContent = "Connected";
    } else {
        els.dot.className = "dot red";
        els.text.textContent = "Disconnected";
    }

    // Input Management
    if (!isUserTyping || state.sessionStatus !== "IDLE") {
        els.input.value = state.sessionName || "";
    }
    els.input.disabled = (state.sessionStatus !== "IDLE");

    // Buttons
    [els.start, els.pause, els.resume, els.end].forEach(b => b.classList.add('hidden'));
    
    const hasName = els.input.value.trim().length > 0;

    if (state.sessionStatus === "IDLE") {
        els.start.classList.remove('hidden');
        els.start.disabled = !(state.isConnected && hasName); 
    } else if (state.sessionStatus === "RUNNING") {
        els.pause.classList.remove('hidden');
        els.end.classList.remove('hidden');
    } else if (state.sessionStatus === "PAUSED") {
        els.resume.classList.remove('hidden');
        els.end.classList.remove('hidden');
    }
}




/************************************************/
/*****************Listeners**********************/
/************************************************/
els.input.addEventListener('input', () => { isUserTyping = true; });

els.input.addEventListener('blur', () => {
    isUserTyping = false; 
    sendUpdate("IDLE"); 
});

els.start.addEventListener('click', () => sendUpdate("RUNNING"));
els.pause.addEventListener('click', () => sendUpdate("PAUSED"));
els.resume.addEventListener('click', () => sendUpdate("RUNNING"));
els.end.addEventListener('click', () => { sendUpdate("IDLE");});



