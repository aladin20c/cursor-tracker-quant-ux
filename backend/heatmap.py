# main.py - MINIMAL FIX
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
from pathlib import Path
import sys

# Import from our separate modules
from element_finder import ElementFinder, SearchConfig
from heatmap_visualizer import HighlightManager, generate_summary_report


# ============================================================================
# DATA PARSING FUNCTIONS
# ============================================================================

def strip_url(target_url: str):
    target_url = target_url.strip().casefold()
    index = target_url.find("www.")
    if index != -1: 
        target_url = target_url[index + 4:]
    target_url = target_url.rstrip('/\\')
    return target_url
    

def read_data(csv_file: str, heatmap_type: str, target_url: str):
    """
    function to read csv files and parse elements
    """
    print(f"Reading CSV: {csv_file}")
    df = pd.read_csv(csv_file)

    target_url = strip_url(target_url)
    df['url'] = df['url'].apply(strip_url)
    
    if heatmap_type in ["click", "hover"]:
        df = df[(df['url'] == target_url) & (df['type'] == heatmap_type)]
    else:   
        df = df[(df['url'] == target_url)]

    df = df.sort_values('timestamp')
    
    print(f"Found {len(df)} {heatmap_type} events")
    return df




# ============================================================================
# MAIN PROCESSING FUNCTION - MINIMAL ANTI-DETECTION
# ============================================================================

async def process_heatmap(csv_file: str, heatmap_type: str, target_url: str, output_file: str):
    """
    SIMPLE heatmap processing with MINIMAL anti-detection
    """
    # Read data
    df = read_data(csv_file, heatmap_type, target_url)
    if df is None or len(df) == 0:
        return
    
    print("🚀 Opening Chrome browser...")
    
    async with async_playwright() as p:
        # SIMPLE browser launch with ONE anti-detection flag
        browser = await p.chromium.launch(
            channel="chrome",
            headless=False,
            args=['--disable-blink-features=AutomationControlled']  # ONLY ADD THIS LINE
        )
        
        page = await browser.new_page()
        
        # ADD THIS: Hide the webdriver flag
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false
            });
        """)
        
        # MANUAL NAVIGATION ONLY
        print("\n" + "="*60)
        print("IMPORTANT: You must login MANUALLY")
        print("="*60)
        print("1. Browser will open")
        print(f"2. MANUALLY go to: {target_url}")
        print("3. MANUALLY login if needed")
        print("4. MANUALLY solve any CAPTCHA")
        print("5. When you're on the target page, return here")
        print("6. Press Enter to continue")
        print("="*60 + "\n")
        
        # Don't even try to automate navigation
        # User handles everything manually
        
        input("Press Enter AFTER you're logged in and on the target page...")
        
        # Get current URL
        try:
            current_url = page.url
            print(f"🌐 Current page: {current_url}")
        except:
            print("⚠️  Could not get current URL")
        
        # Initialize modules
        config = SearchConfig(
            use_css_selector=True,
            use_fuzzy_html=True,
            use_fuzzy_text=True,
            use_position=True,
            use_similarity=True
        )
        
        finder = ElementFinder(page, config)
        highlighter = HighlightManager(page)
        await highlighter.setup()
        
        # Process events
        print(f"\n🔍 Finding elements...")
        
        found_elements = []
        not_found = []
        
        for i, (_, event) in enumerate(df.iterrows(), 1):
            print(f"[{i}] ", end="", flush=True)
            
            event_data = event.to_dict()
            element_match = await finder.find_element(event_data, i)
            
            if element_match:
                print(f"✓", end="", flush=True)
                await highlighter.highlight_element(element_match)
                found_elements.append(element_match)
            else:
                print(f"✗", end="", flush=True)
                not_found.append({
                    'number': i,
                    'selector': event_data.get('selector', ''),
                    'tag': event_data.get('tagName', '')
                })
            
            # Small pause
            await asyncio.sleep(0.01)
        
        print()  # New line
        
        # Take screenshot
        print(f"\n📸 Taking screenshot...")
        await highlighter.take_screenshot(output_file)
        print(f"✅ Screenshot: {output_file}")
        
        # Report
        await generate_summary_report(found_elements, not_found, df, output_file)
        
        # Cleanup
        keep_open = input("\nKeep browser open? (y/n): ")
        if keep_open.lower() != 'y':
            await browser.close()
        
        print("✨ Done!")


# ============================================================================
# MAIN (same as before)
# ============================================================================

def main():
    DATA_DIR = Path(__file__).resolve().parent / "data"

    print(f"🔍 Heatmap Generator - Simple Mode")
    
    if len(sys.argv) < 4:
        print(f"Error: Expected 3 arguments, got {len(sys.argv)-1}")
        print("Usage: python main.py <session_name> <heatmap_type> <target_url>")
        return
    
    session_name = sys.argv[1]
    heatmap_type = sys.argv[2]
    target_url = sys.argv[3]
    
    valid_types = ["click", "hover", "scroll", "all"]
    if heatmap_type not in valid_types:
        print(f"Error: Invalid heatmap type '{heatmap_type}'")
        return
    
    if session_name == "ALL_SESSIONS":
        print("Not implemented yet.")
        return
    
    session_folder = DATA_DIR / session_name
    event_file = session_folder / "events.csv"
    
    if not session_folder.exists() or not event_file.exists():
        print(f"Error: Session '{session_name}' not found")
        return
    
    safe_url = target_url.replace('://', '_').replace('/', '_')[:50]
    output_file = f"{session_name}_{heatmap_type}_{safe_url}.png"
    
    asyncio.run(process_heatmap(
        str(event_file),
        heatmap_type,
        target_url,
        output_file
    ))


if __name__ == '__main__':
    main()