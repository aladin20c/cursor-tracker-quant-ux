console.log("✅ UX Recorder: Content script loaded");

document.addEventListener('click', (event) => {
    
    // 1. Capture Data
    const data = {
        x: event.pageX,
        y: event.pageY,
        timestamp: Date.now(),
        window_size: `${window.innerWidth}x${window.innerHeight}`,
        target: event.target.tagName
    };

    console.log("✅ Click detected:", data.x, data.y);

    // 2. Safety Check before sending
    if (chrome.runtime && chrome.runtime.sendMessage) {
        chrome.runtime.sendMessage({ action: "LOG_CLICK", payload: data });
    } else {
        console.log("⚠️ Connection lost. Please refresh this page to reconnect to the extension.");
    }

}, true);