# main.py - WITH NEW HEATMAP VISUALIZER
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
from pathlib import Path
import sys

# Import from our separate modules
from element_finder import ElementFinder, SearchConfig

from heatmap_visualizer import (
    HighlightManager, 
    HeatmapVisualizer,
    VisualizationConfig
)


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
    
    
    print(f"Found {len(df)} events")
    return df


# ============================================================================
# MAIN PROCESSING FUNCTION WITH NEW VISUALIZER
# ============================================================================

async def process_heatmap(csv_file: str, heatmap_type: str, target_url: str, output_file: str):
    """
    Enhanced heatmap processing with new visualizer
    """
    
    df = read_data(csv_file, heatmap_type, target_url)
    if df is None or len(df) == 0: return
    
    # Get visualization configuration
    viz_config = VisualizationConfig(
        highlight_elements=False,          
        show_mouse_heatmap=True,          
        include_undetected_clicks=True,   
        heatmap_intensity=0.7,            
        #heatmap_blur_radius=20,           
        circle_size=15,            
        show_click_numbers=False,          
        color_scheme="hot"
    )
    
    print("Opening Chrome browser...")
    
    async with async_playwright() as p:
        
        # Browser with anti-detection
        browser = await p.chromium.launch(
            channel="chrome",
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        page = await browser.new_page()
        
        # Hide webdriver flag
        await page.add_init_script(""" Object.defineProperty(navigator, 'webdriver', { get: () => false }); """)

        await page.goto(target_url)
        
        # MANUAL NAVIGATION
        print("\n" + "="*60)
        print("MANUAL NAVIGATION REQUIRED")
        print("="*60)
        print("1. Browser will open")
        print(f"2. MANUALLY go to: {target_url}")
        print("3. MANUALLY login if needed")
        print("4. MANUALLY solve any CAPTCHA")
        print("5. When you're on the target page, return here")
        print("6. Press Enter to continue")
        print("="*60 + "\n")
        
        input("Press Enter AFTER you're logged in and on the target page...")
        
        
        # Initialize modules
        search_config = SearchConfig(
            use_css_selector=True,
            use_fuzzy_html=True,
            use_fuzzy_text=True,
            use_position=True,
            use_similarity=True
        )
        
        finder = ElementFinder(page, search_config)
        highlighter = HighlightManager(page, viz_config)
        heatmap_viz = HeatmapVisualizer(page, viz_config)
        
        # Setup highlighting CSS
        await highlighter.setup()
        
        # Process events
        print(f"\nProcessing {len(df)} events...")

        
        for i, (_, event) in enumerate(df.iterrows(), 1):

            if i % 10 == 0: print(f"  Processed {i}/{len(df)}...")
            
            event_data = event.to_dict()
            element_match = await finder.find_element(event_data, i)
            
            if element_match:
                
                await highlighter.highlight_element(element_match)
                await heatmap_viz.add_click(event_data, element_match, i)
                
            else:
                
                await heatmap_viz.add_click(event_data, None, i)
            
            # Small delay to avoid overwhelming
            await asyncio.sleep(0.01)
        
        print()
        


        # Render heatmap if configured
        if viz_config.show_mouse_heatmap:
            print("\nRendering heatmap...")
            await heatmap_viz.render_heatmap()
        
        print(f"\nTaking screenshot...")
        await highlighter.take_screenshot(output_file)
        
        await browser.close()
        print("Visualization complete!")




# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================

def main():
    DATA_DIR = Path(__file__).resolve().parent / "data"

    print(f"Heatmap Generator")
    print("="*50)
    
    if len(sys.argv) < 4:
        print(f"Error: Expected 3 arguments, got {len(sys.argv)-1}")
        print("Usage: python main.py <session_name> <heatmap_type> <target_url>")
        print("\nArguments:")
        print("  session_name: Name of session folder in data/")
        print("  heatmap_type: 'click', 'hover', 'scroll', or 'all'")
        print("  target_url:   URL to analyze (e.g., https://example.com)")
        return
    
    session_name = sys.argv[1]
    heatmap_type = sys.argv[2]
    target_url = sys.argv[3]
    
    # Validate heatmap type
    valid_types = ["click", "hover", "scroll", "all"]
    if heatmap_type not in valid_types:
        print(f"Error: Invalid heatmap type '{heatmap_type}'")
        print(f"Must be one of: {', '.join(valid_types)}")
        return
    
    # Handle "ALL_SESSIONS" special case
    if session_name == "ALL_SESSIONS":
        print("Generating Heatmaps for all sessions")
        print("Error: Not implemented yet.")
        return
    
    # Check if session exists
    session_folder = DATA_DIR / session_name
    event_file = session_folder / "events.csv"
    
    if not session_folder.exists():
        print(f"Session folder not found: {session_folder}")
        return
    
    if not event_file.exists():
        print(f"Event file not found: {event_file}")
        return
    
    # Generate output filename
    safe_url = strip_url(target_url)[:50]
    output_file_name = f"{session_name}_{heatmap_type}_{safe_url}.png"
    output_file = session_folder / output_file_name
    
    print(f"\nSession: {session_name}")
    print(f" Type:    {heatmap_type}")
    print(f" URL:     {target_url}")
    print(f" Output:  {output_file}")
    print("="*50)
    print("="*50)
    
    # Run the processing
    try:
        asyncio.run(process_heatmap(
            str(event_file),
            heatmap_type,
            target_url,
            str(output_file)
        ))
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()