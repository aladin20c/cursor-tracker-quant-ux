// ============================================================================
// CONFIG & STATE
// ============================================================================
let hoverTimeout = null;
let currentHoveredElement = null;
let lastMouseMoveTime = 0;
const HOVER_DELAY_MS = 500;
const THROTTLE_MS = 100;

console.log("✅ UX Recorder: Full Data Tracking Loaded");

// ============================================================================
// LISTENERS
// ============================================================================

// A. CLICK (Capture Phase)
document.addEventListener('click', (event) => {
    const target = getMeaningfulTarget(event.target);
    recordEvent(target, event, true); // isClick = true
}, true);

// B. HOVER (Throttled)
document.addEventListener('mousemove', (event) => {
    const now = Date.now();
    if (now - lastMouseMoveTime < THROTTLE_MS) return;
    lastMouseMoveTime = now;

    const rawElement = document.elementFromPoint(event.clientX, event.clientY);
    if (!rawElement) return;

    const element = getMeaningfulTarget(rawElement);

    if (element !== currentHoveredElement) {
        clearTimeout(hoverTimeout);
        currentHoveredElement = element;
        hoverTimeout = setTimeout(() => {
            recordEvent(element, event, false); // isClick = false
        }, HOVER_DELAY_MS);
    }
});

// ============================================================================
// CORE LOGIC
// ============================================================================

function getMeaningfulTarget(element) {
    const interactive = element.closest('button, a, input, [role="button"], select, textarea');
    return interactive || element;
}

function recordEvent(element, event, isClick) {
    if (!element) return;

    // 1. Calculate Coordinates
    const viewportX = event.clientX;
    const viewportY = event.clientY;
    const pageX = viewportX + window.scrollX;
    const pageY = viewportY + window.scrollY;

    // 2. Safety for HTML (prevent capturing massive Body tags)
    let safeHTML = element.outerHTML;
    if (element.tagName === 'BODY' || element.tagName === 'HTML') {
        safeHTML = `<${element.tagName.toLowerCase()}>[Full Page Container]</${element.tagName.toLowerCase()}>`;
    }

    // 3. CONSTRUCT THE FULL SNAPSHOT (Your exact structure)
    const snapshot = {
        type: isClick ? 'click' : 'hover',
        url: window.location.href,
        timestamp: new Date().toISOString(),

        // ELEMENT IDENTITY
        tagName: element.tagName,
        id: element.id || "",
        className: element.className || "",
        outerHTML: safeHTML,

        // COORDINATES
        viewportX: Math.round(viewportX),
        viewportY: Math.round(viewportY),
        pageX: Math.round(pageX),
        pageY: Math.round(pageY),

        // METADATA
        windowWidth: window.innerWidth,
        windowHeight: window.innerHeight
    };

    // 4. Send to Background
    if (chrome.runtime && chrome.runtime.sendMessage) {
        chrome.runtime.sendMessage({ action: "LOG_EVENT", payload: snapshot });
    }

    // 5. Visual Feedback
    if (isClick) {
        const originalOutline = element.style.outline;
        element.style.outline = '2px solid #e74c3c'; // Red flash for click
        setTimeout(() => { element.style.outline = originalOutline; }, 500);
    }
}