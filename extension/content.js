// ============================================================================
// CONFIG & STATE
// ============================================================================
console.log("[Content.js] Trtacking Cursor Activities");

const BATCH_SIZE = 10; // Send every 10 events
const BATCH_TIMEOUT_MS = 3000; // Or send after 1 second
let eventBatch = [];
let batchTimeout = null;

let hoverTimeout = null;
let currentHoveredElement = null;
let lastMouseMoveTime = 0;
const HOVER_DELAY_MS = 500;
const THROTTLE_MS = 100;

// ============================================================================
// LISTENERS
// ============================================================================

document.addEventListener('click', (event) => {
    const target = getMeaningfulTarget(event.target);
    recordEvent(target, event, 'click');
}, true);

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
            recordEvent(element, event, 'hover');
        }, HOVER_DELAY_MS);
    }
});


// ============================================================================
// CORE LOGIC & DATA CONSTRUCTION
// ============================================================================

function recordEvent(element, event, type) {
    if (!element) return;

    // 1. Capture State
    const scrollX = window.scrollX;
    const scrollY = window.scrollY;
    const viewportX = event.clientX;
    const viewportY = event.clientY;

    // 2. HTML Safety
    let safeHTML = element.outerHTML;
    if (safeHTML.length > 500) safeHTML = safeHTML.substring(0, 500) + "...";
    if (element.tagName === 'BODY' || element.tagName === 'HTML') safeHTML = "BODY_CONTAINER";

    // 3. CONSTRUCT YOUR EXACT DATA POINT
    const dataPoint = {
        type: type, // 'click' or 'hover'
        url: window.location.href,
        timestamp: Date.now(),

        // --- Element Identity ---
        selector: getCssSelector(element),
        tagName: element.tagName,
        id: element.id || null,
        className: element.className || null,
        innerText: element.innerText ? element.innerText.substring(0, 50) : null,
        outerHTML: safeHTML,

        // --- Coordinates ---
        x_viewport: Math.round(viewportX),
        y_viewport: Math.round(viewportY),
        x_page: Math.round(viewportX + scrollX),
        y_page: Math.round(viewportY + scrollY),

        // --- Context & Normalization ---
        scrollX: Math.round(scrollX),
        scrollY: Math.round(scrollY),
        viewportW: window.innerWidth,
        viewportH: window.innerHeight,
        docHeight: document.documentElement.scrollHeight,
        docWidth: document.documentElement.scrollWidth
    };

    // 4. Send to Background
    eventBatch.push(dataPoint);
    if (eventBatch.length >= BATCH_SIZE) {
        sendBatch();
    } else if (!batchTimeout) {
        batchTimeout = setTimeout(sendBatch, BATCH_TIMEOUT_MS);
    }
    //if (chrome.runtime && chrome.runtime.sendMessage) {chrome.runtime.sendMessage({ action: "LOG_EVENT", payload: dataPoint });}

    // 5. Visual Feedback
    if (type === 'click') {
        const originalOutline = element.style.outline;
        element.style.outline = '2px solid #e74c3c';
        setTimeout(() => { element.style.outline = originalOutline; }, 300);
    }
}

// ============================================================================
// HELPERS (Selector Generator)
// ============================================================================

function getMeaningfulTarget(element) {
    const interactive = element.closest('button, a, input, [role="button"], select, textarea');
    return interactive || element;
}

/**
 * Advanced Selector Generator
 * - Ignores IDs that look dynamic (contain numbers/hashes)
 * - Uses :nth-of-type for bulletproof precision
 * - Traverses up until it finds a "safe" container or hits the root
 */
function getCssSelector(el) {
    if (!(el instanceof Element)) return;
    
    const path = [];
    
    while (el.nodeType === Node.ELEMENT_NODE) {
        let selector = el.tagName.toLowerCase();
        
        // 1. INTELLIGENT ID CHECK
        // Only stop at an ID if it looks "Human-Readable" (no long numbers)
        if (el.id) {
            // Regex: Rejects IDs with 3+ consecutive numbers or random hashes
            const isDynamic = /\d{3,}/.test(el.id) || el.id.length > 30;
            
            if (!isDynamic) {
                selector += '#' + el.id;
                path.unshift(selector);
                break; // We trust this ID, stop traversing!
            }
        }

        // 2. CLASS NAMES (Optional Context)
        // We add classes for readability, but we don't trust them for uniqueness.
        if (el.className && typeof el.className === 'string') {
            const cleanClasses = el.className.trim().split(/\s+/).filter(c => {
                // Filter out common "state" classes that change (active, hover, visible)
                return c.length > 0 && !['active', 'focus', 'hover', 'open'].includes(c);
            });
            
            if (cleanClasses.length > 0) {
                selector += '.' + cleanClasses.join('.');
            }
        }

        // 3. STRUCTURAL PRECISION (:nth-of-type)
        // This is the "Anchor". It ensures that if there are 5 buttons, we get the 3rd one.
        let sibling = el;
        let nth = 1;
        while (sibling = sibling.previousElementSibling) {
            if (sibling.tagName === el.tagName) nth++;
        }
        selector += `:nth-of-type(${nth})`;

        path.unshift(selector);
        el = el.parentNode;
        
        // Stop if we hit the document root
        if (el.tagName === 'HTML') break;
    }
    
    return path.join(' > ');
}


// ============================================================================
// BATCH SENDING FUNCTION
// ============================================================================
function sendBatch() {
    if (batchTimeout) {
        clearTimeout(batchTimeout);
        batchTimeout = null;
    }
    if (eventBatch.length === 0) return;
    // Send the current batch
    const batchToSend = [...eventBatch];
    eventBatch = []; // Clear the queue

    if (chrome.runtime && chrome.runtime.sendMessage) {
        chrome.runtime.sendMessage({ 
            action: "LOG_EVENT_BATCH", 
            payload: batchToSend 
        });
    }
}


// ============================================================================
// CLEANUP ON PAGE UNLOAD
// ============================================================================
window.addEventListener('beforeunload', () => {
    sendBatch(); // Send any remaining events
    clearTimeout(hoverTimeout);
    clearTimeout(batchTimeout);
});

// ============================================================================
// SEND BATCH PERIODICALLY (safety net)
// ============================================================================
setInterval(() => {
    if (eventBatch.length > 0) {
        sendBatch();
    }
}, 5000); // Every 5 seconds