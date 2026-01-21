import sys
import pandas as pd
import numpy as np
import time
from pathlib import Path
from typing import List, Dict
from playwright.sync_api import sync_playwright, Page, Browser
from datetime import datetime

############################################################
############################################################
############################################################

DATA_DIR = Path(__file__).resolve().parent / "data"

VAR_CLICK = 0
VAR_HOVER = 1
VAR_SCROLL = 2
VAR_ALL = 3


############################################################
############################################################
############################################################


def read_and_filter_events(csv_path: Path, target_url: str,  sort_by_time: bool = True) -> Optional[pd.DataFrame]:

    try:
        
        df = pd.read_csv(csv_path,sep=",",header=0)
        
        df['url'] = df['url'].astype(str).str.rstrip('/')
        target_url_normalized = target_url.rstrip('/')
        
        url_events = df[df['url'] == target_url_normalized].copy()
        
        
        if len(url_events) == 0:
            print("No events found for this URL")
            return None
        else :
            print(f"Found {len(url_events)} events for URL: {target_url}")

        
        # Clean selector column - remove empty or NaN selectors
        url_events = url_events[url_events['selector'].notna() & (url_events['selector'] != '')].copy()
        print(f"Events with valid selectors: {len(url_events)}")
        
        if sort_by_time :
            ...
        
        # Fill NaN values with empty strings for text columns
        text_columns = ['selector', 'id', 'tagName', 'className', 'innerText', 'type']
        for col in text_columns:
            if col in url_events.columns:
                url_events[col] = url_events[col].fillna('').astype(str)
        
        return url_events
        
    except Exception as e:
        print(f"Error reading CSV with pandas: {e}")
        return None

def analyze_click_patterns(df: pd.DataFrame):
    """Analyze and print click patterns from the DataFrame"""
    if df is None or len(df) == 0:
        return
    
    print("\n" + "="*60)
    print("CLICK PATTERN ANALYSIS")
    print("="*60)
    
    print(f"Total clicks on this page: {len(df)}")
    
    # Analyze by event type
    if 'type' in df.columns:
        type_counts = df['type'].value_counts()
        print(f"\nEvent types:")
        for event_type, count in type_counts.items():
            print(f"  {event_type}: {count}")
    
    # Most clicked selectors
    selector_stats = df['selector'].value_counts()
    print(f"\nTop 10 most clicked elements:")
    for selector, count in selector_stats.head(10).items():
        # Truncate long selectors for display
        selector_display = selector if len(selector) <= 70 else selector[:67] + "..."
        print(f"  {count:3d} clicks: {selector_display}")
    
    # Click frequency over time
    if 'datetime' in df.columns:
        df['hour_minute'] = df['datetime'].dt.strftime('%H:%M')
        time_counts = df['hour_minute'].value_counts().sort_index()
        if len(time_counts) > 0:
            print(f"\nClick timeline (first few):")
            for time_str, count in time_counts.head(5).items():
                print(f"  {time_str}: {count} clicks")
    
    # Element types clicked
    if 'tagName' in df.columns:
        tag_counts = df['tagName'].value_counts()
        print(f"\nHTML elements clicked:")
        for tag, count in tag_counts.items():
            if tag:  # Skip empty tags
                print(f"  {tag}: {count}")




def validate_and_clean_selectors(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and validate CSS selectors
    """
    if df is None or len(df) == 0:
        return df
    
    # Make a copy to avoid modifying the original
    df_clean = df.copy()
    
    # Common issues with selectors and their fixes
    def clean_selector(selector: str) -> str:
        if not selector or pd.isna(selector):
            return ""
        
        selector = str(selector).strip()
        
        # Fix common issues
        # 1. Remove extra quotes
        selector = selector.replace('""', '"').replace("''", "'")
        
        # 2. Fix escaped quotes
        selector = selector.replace('\\"', '"').replace("\\'", "'")
        
        # 3. Ensure it starts with a valid character
        if selector and selector[0] not in '#.[a-zA-Z':
            # Try to find the first valid CSS selector pattern
            import re
            match = re.search(r'[#\.\[a-zA-Z]', selector)
            if match:
                selector = selector[match.start():]
        
        return selector
    
    df_clean['selector_clean'] = df_clean['selector'].apply(clean_selector)
    
    # Filter out invalid selectors
    valid_selectors = df_clean[df_clean['selector_clean'].str.match(r'^[#\.\[a-zA-Z]')].copy()
    
    print(f"Valid selectors after cleaning: {len(valid_selectors)}/{len(df)}")
    
    return valid_selectors

def highlight_elements_by_selector(page: Page, df: pd.DataFrame):
    """
    Highlight clicked elements on the page using CSS selectors
    
    Args:
        page: Playwright page object
        df: DataFrame containing click events with selectors
    """
    if df is None or len(df) == 0:
        print("No events to highlight")
        return
    
    # Clean selectors first
    df_clean = validate_and_clean_selectors(df)
    
    if len(df_clean) == 0:
        print("No valid selectors to highlight")
        return
    
    # JavaScript to inject for highlighting
    highlight_script = """
    // Function to highlight an element by selector with sequence-based styling
    function highlightElementBySelector(selector, clickNumber, totalClicks, elementInfo) {
        try {
            if (!selector || selector.trim() === '') {
                console.log('Empty selector provided');
                return { success: false, reason: 'empty selector' };
            }
            
            let elements;
            try {
                elements = document.querySelectorAll(selector);
            } catch (e) {
                console.log('Invalid selector syntax:', selector, e);
                return { success: false, reason: 'invalid selector', error: e.message };
            }
            
            if (elements.length === 0) {
                console.log('No elements found for selector:', selector);
                return { success: false, reason: 'no elements found', selector: selector };
            }
            
            // Calculate color based on click sequence (blue to red gradient)
            const hue = 240 * (1 - (clickNumber / totalClicks)); // Blue (240) to Red (0)
            const color = `hsl(${hue}, 100%, 50%)`;
            
            const results = [];
            
            elements.forEach((element, index) => {
                try {
                    // Store original styles for potential restoration
                    if (!element._originalStyles) {
                        element._originalStyles = {
                            border: element.style.border,
                            backgroundColor: element.style.backgroundColor,
                            position: element.style.position,
                            boxSizing: element.style.boxSizing,
                            borderRadius: element.style.borderRadius,
                            transition: element.style.transition
                        };
                    }
                    
                    // Add colored border based on click sequence
                    element.style.border = `3px solid ${color}`;
                    element.style.borderRadius = '4px';
                    element.style.boxSizing = 'border-box';
                    
                    // Add a semi-transparent background with sequence-based opacity
                    const opacity = 0.1 + 0.3 * (clickNumber / totalClicks);
                    element.style.backgroundColor = `rgba(${hue === 0 ? '255,0,0' : '0,0,255'}, ${opacity})`;
                    
                    // Add transition for smooth appearance
                    element.style.transition = 'all 0.3s ease';
                    
                    // Ensure element has relative positioning for badge
                    element.style.position = 'relative';
                    
                    // Add a tooltip on hover with sequence info
                    const elementId = element.id ? `ID: ${element.id}\\n` : '';
                    const elementClass = element.className ? `Class: ${element.className}\\n` : '';
                    element.title = `Click #${clickNumber}/${totalClicks}\\n` +
                                  `Selector: ${selector}\\n` +
                                  `${elementId}${elementClass}` +
                                  `Tag: ${element.tagName}\\n` +
                                  `Elements matched: ${elements.length}`;
                    
                    // Add a small number badge for sequence (only for first element if multiple)
                    if (index === 0) {
                        const badge = document.createElement('div');
                        badge.textContent = clickNumber;
                        badge.style.position = 'absolute';
                        badge.style.top = '-12px';
                        badge.style.right = '-12px';
                        badge.style.backgroundColor = color;
                        badge.style.color = 'white';
                        badge.style.borderRadius = '50%';
                        badge.style.width = '24px';
                        badge.style.height = '24px';
                        badge.style.fontSize = '12px';
                        badge.style.display = 'flex';
                        badge.style.alignItems = 'center';
                        badge.style.justifyContent = 'center';
                        badge.style.zIndex = '10000';
                        badge.style.fontWeight = 'bold';
                        badge.style.boxShadow = '0 2px 5px rgba(0,0,0,0.3)';
                        badge.style.pointerEvents = 'none';
                        
                        // Add badge as a child if element can contain it
                        if (element.appendChild) {
                            element.appendChild(badge);
                            element._highlightBadge = badge;
                        }
                    }
                    
                    results.push({
                        success: true,
                        selector: selector,
                        elementIndex: index,
                        tagName: element.tagName,
                        id: element.id,
                        className: element.className
                    });
                    
                } catch (elementError) {
                    console.log(`Error highlighting element ${index} for selector ${selector}:`, elementError);
                    results.push({
                        success: false,
                        selector: selector,
                        elementIndex: index,
                        error: elementError.message
                    });
                }
            });
            
            return {
                success: true,
                totalElements: elements.length,
                results: results
            };
            
        } catch (error) {
            console.error('Error in highlightElementBySelector:', error);
            return { success: false, reason: 'execution error', error: error.message };
        }
    }
    
    // Function to try alternative selectors if primary fails
    function tryAlternativeSelectors(primarySelector, id, className, tagName) {
        const alternatives = [];
        
        // Try by ID if available
        if (id && id.trim()) {
            alternatives.push(`#${id.replace(/([:.[\]])/g, '\\\\$1')}`);
        }
        
        // Try by class if available
        if (className && className.trim()) {
            // Split multiple classes and try combinations
            const classes = className.split(/\s+/).filter(c => c);
            if (classes.length > 0) {
                // Try with all classes
                alternatives.push(`.${classes.join('.')}`);
                // Try with first class
                alternatives.push(`.${classes[0]}`);
            }
        }
        
        // Try by tag name if available
        if (tagName && tagName.trim()) {
            alternatives.push(tagName.toLowerCase());
        }
        
        // Try combination of tag and class
        if (tagName && className) {
            const classes = className.split(/\s+/).filter(c => c);
            if (classes.length > 0) {
                alternatives.push(`${tagName.toLowerCase()}.${classes.join('.')}`);
            }
        }
        
        return alternatives;
    }
    
    // Store functions globally
    window.highlightElementBySelector = highlightElementBySelector;
    window.tryAlternativeSelectors = tryAlternativeSelectors;
    """
    
    # Inject the highlighting functions
    page.evaluate(highlight_script)
    
    successful_highlights = 0
    total_clicks = len(df_clean)
    selector_stats = {}
    
    print(f"\nAttempting to highlight {total_clicks} elements...")
    
    for idx, event in df_clean.iterrows():
        try:
            selector = event.get('selector_clean', event.get('selector', ''))
            element_id = event.get('id', '')
            element_class = event.get('className', '')
            tag_name = event.get('tagName', '')
            click_number = event.get('click_sequence', idx + 1)
            
            print(f"\nProcessing click #{click_number}:")
            print(f"  Selector: {selector[:80]}{'...' if len(selector) > 80 else ''}")
            
            # Try to highlight with primary selector
            result = page.evaluate("""async (selector, clickNumber, totalClicks, id, className, tagName) => {
                // Try primary selector first
                const primaryResult = await window.highlightElementBySelector(selector, clickNumber, totalClicks, {id, className, tagName});
                
                if (primaryResult.success) {
                    return { method: 'primary', ...primaryResult };
                }
                
                // If primary failed, try alternatives
                const alternatives = window.tryAlternativeSelectors(selector, id, className, tagName);
                
                for (let i = 0; i < alternatives.length; i++) {
                    const altResult = await window.highlightElementBySelector(alternatives[i], clickNumber, totalClicks, {id, className, tagName});
                    if (altResult.success) {
                        return { method: 'alternative', alternative: alternatives[i], ...altResult };
                    }
                }
                
                return { method: 'failed', primaryResult };
                
            }""", selector, int(click_number), total_clicks, element_id, element_class, tag_name)
            
            # Track statistics
            if result.get('success', False):
                successful_highlights += 1
                elements_highlighted = result.get('totalElements', 1)
                method = result.get('method', 'unknown')
                
                if method == 'alternative':
                    print(f"  ✅ Highlighted using alternative selector: {result.get('alternative', 'unknown')}")
                else:
                    print(f"  ✅ Highlighted {elements_highlighted} element(s)")
                
                # Update selector stats
                if selector not in selector_stats:
                    selector_stats[selector] = {'success': 0, 'elements': 0}
                selector_stats[selector]['success'] += 1
                selector_stats[selector]['elements'] += elements_highlighted
            else:
                reason = result.get('reason', 'unknown')
                print(f"  ❌ Failed: {reason}")
                if 'error' in result:
                    print(f"     Error: {result['error'][:100]}")
            
            # Small delay to see highlighting sequence
            time.sleep(0.2)
            
        except Exception as e:
            print(f"  ❌ Error processing click #{idx + 1}: {str(e)[:100]}")
            continue
    
    # Print summary
    print(f"\n" + "="*60)
    print("HIGHLIGHTING SUMMARY")
    print("="*60)
    print(f"Successfully highlighted: {successful_highlights}/{total_clicks} clicks")
    
    # Show selector success rates
    if selector_stats:
        print(f"\nSelector success rates:")
        for selector, stats in list(selector_stats.items())[:10]:  # Show top 10
            success_rate = (stats['success'] / df_clean['selector'].value_counts()[selector]) * 100
            print(f"  {selector[:50]}...: {stats['success']} succeeded ({success_rate:.1f}%)")
    
    # Add info overlay
    info_overlay = f"""
    // Create an info overlay
    const overlay = document.createElement('div');
    overlay.id = 'click-heatmap-overlay';
    overlay.style.position = 'fixed';
    overlay.style.top = '10px';
    overlay.style.right = '10px';
    overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.9)';
    overlay.style.color = 'white';
    overlay.style.padding = '15px';
    overlay.style.borderRadius = '8px';
    overlay.style.zIndex = '10001';
    overlay.style.fontFamily = 'Arial, sans-serif';
    overlay.style.fontSize = '13px';
    overlay.style.boxShadow = '0 4px 20px rgba(0,0,0,0.5)';
    overlay.style.maxWidth = '350px';
    overlay.style.lineHeight = '1.4';
    overlay.style.backdropFilter = 'blur(5px)';
    
    const title = document.createElement('div');
    title.style.fontSize = '16px';
    title.style.fontWeight = 'bold';
    title.style.marginBottom = '10px';
    title.style.color = '#4CAF50';
    title.innerHTML = '🎯 Click Heatmap (Selector-based)';
    
    const stats = document.createElement('div');
    stats.innerHTML = `
        <div style="margin-bottom: 5px;">✅ Successfully highlighted: {successful_highlights}/{total_clicks}</div>
        <div style="margin-bottom: 5px;">🎨 Color gradient: Early (blue) → Late (red)</div>
        <div style="margin-bottom: 5px;">🔢 Numbers: Click sequence order</div>
        <div style="margin-bottom: 5px;">🖱️ Hover over elements for selector details</div>
        <div style="margin-top: 10px; font-size: 11px; opacity: 0.8;">
            Using CSS selectors for accurate element identification
        </div>
    `;
    
    overlay.appendChild(title);
    overlay.appendChild(stats);
    
    // Add close button
    const closeBtn = document.createElement('button');
    closeBtn.textContent = '×';
    closeBtn.style.position = 'absolute';
    closeBtn.style.top = '5px';
    closeBtn.style.right = '5px';
    closeBtn.style.background = 'none';
    closeBtn.style.border = 'none';
    closeBtn.style.color = 'white';
    closeBtn.style.fontSize = '16px';
    closeBtn.style.cursor = 'pointer';
    closeBtn.style.width = '20px';
    closeBtn.style.height = '20px';
    closeBtn.style.borderRadius = '50%';
    closeBtn.style.display = 'flex';
    closeBtn.style.alignItems = 'center';
    closeBtn.style.justifyContent = 'center';
    closeBtn.onclick = function() { overlay.style.display = 'none'; };
    
    overlay.appendChild(closeBtn);
    document.body.appendChild(overlay);
    """
    
    page.evaluate(info_overlay, successful_highlights=successful_highlights, total_clicks=total_clicks)

def generate_heatmap_for_session(session_folder: Path, url: str):
    """
    Main function to generate heatmap for a session using selector-based approach
    """
    event_file = session_folder / "events.csv"
    
    if not event_file.exists():
        print(f"Error: events.csv not found. Please make sure the file exists in {event_file}")
        return
    
    # Read and filter events
    df = read_and_filter_events(event_file, url, sort_by_time=True)
    
    if df is None or len(df) == 0:
        print(f"No valid events found for URL: {url}")
        return
    
    # Analyze click patterns
    analyze_click_patterns(df)
    
    # Launch browser
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--start-maximized', '--disable-dev-shm-usage']
        )
        
        # Set up context with larger viewport
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        page = context.new_page()
        
        # Navigate to URL
        print(f"\n🌐 Navigating to: {url}")
        page.goto(url, wait_until='networkidle', timeout=30000)
        
        # Wait for page to fully load
        page.wait_for_load_state('networkidle')
        time.sleep(3)  # Wait for dynamic content
        
        input("\n📄 Page loaded! Press ENTER to highlight clicked elements...")
        
        # Highlight elements using selectors
        highlight_elements_by_selector(page, df)
        
        # Options menu
        print("\n" + "="*60)
        print("OPTIONS MENU")
        print("="*60)
        print("1. 📸 Take screenshot (full page)")
        print("2. 💾 Save as HTML with highlights")
        print("3. 📊 Export analysis report")
        print("4. 🔄 Re-highlight elements")
        print("5. ❌ Exit")
        print("="*60)
        
        choice = input("\nYour choice (1-5): ").strip()
        
        timestamp = int(time.time())
        
        if choice == '1':
            screenshot_path = session_folder / f"heatmap_selector_{timestamp}.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"✅ Screenshot saved to: {screenshot_path}")
            
        elif choice == '2':
            html_path = session_folder / f"heatmap_selector_{timestamp}.html"
            html_content = page.content()
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"✅ HTML saved to: {html_path}")
            
        elif choice == '3':
            # Create analysis report
            report_path = session_folder / f"analysis_{timestamp}.txt"
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"Click Analysis Report - {datetime.now()}\n")
                f.write(f"URL: {url}\n")
                f.write(f"Total events: {len(df)}\n\n")
                
                # Write selector statistics
                f.write("TOP SELECTORS:\n")
                top_selectors = df['selector'].value_counts().head(20)
                for selector, count in top_selectors.items():
                    f.write(f"{count:4d} | {selector}\n")
            
            print(f"✅ Analysis report saved to: {report_path}")
            
        elif choice == '4':
            # Re-highlight with different colors
            print("Re-highlighting elements...")
            highlight_elements_by_selector(page, df)
            input("Press ENTER when done...")
        
        print("\nClosing browser...")
        browser.close()

if __name__ == "__main__":
    # Configure paths
    session_folder = Path("./session_data")
    url = "https://letterboxd.com/"
    
    # Run the heatmap generator
    generate_heatmap_for_session(session_folder, url)



############################################################
############################################################
############################################################


def generate_heatmap_for_session(session_folder,heatmap_type,url) :
    event_file = session_folder / "events.csv"

    if not event_file.exists():
        print(f"Error: events.csv not found. Please make sure the file exists in {event_file}")
        return
    
    #asyncio.run(highlight_clicked_elements( str(event_file), "https://letterboxd.com/",'element_highlights.png'))

    



def generate_average_heatmaps(heatmap_type,url) :
    print("ERROR : NOT IMPLEMENETED YET")
    return



############################################################
############################################################
############################################################

def main():

    print(f"[{sys.argv[0]}] executing script for generating heatmaps...")
    
    if len(sys.argv) < 4 :
        print(f"Error: You passed only {len(sys.argv)} arguments. You must pass at lease as arguments the name of the session and the type of heatmap to generate and the target url") 
        return


    heatmap_type = 0
    if sys.argv[2]=="CLICK" :
        heatmap_type = 0
    elif sys.argv[2]=="HOVER" :
        heatmap_type = 1
    elif sys.argv[2]=="SCROLL":
        heatmap_type = 2
    elif sys.argv[2]=="ALL" :
        heatmap_type = 3
    else :
        print(f"Error: You passed {sys.argv[2]} as the type of teh heatnmap. It must be equal to HOVER or CLICK or SCROLL or ALL") 
        return

    

    if sys.argv[1] == "ALL_SESSIONS" :
        print("Generating Heatmaps for all the sessions")
        print("Error: Not implemented yet.")
        generate_average_heatmaps(heatmap_type,sys.argv[3])
    
    else :
        session_folder  = DATA_DIR / sys.argv[1]

        if not session_folder.exists():
            print(f"Error: {sys.argv[1]} Session not found. Please make sure the Session fodler exists in the data/ directory.")
            return
        
        generate_heatmap_for_session(session_folder,heatmap_type,sys.argv[3])
    
if __name__ == '__main__':
    main()