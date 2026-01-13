import pandas as pd
import asyncio
from playwright.async_api import async_playwright
from pathlib import Path
import json
import difflib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ElementMatch:
    """Represents a found element with match information"""
    element: any  # Playwright element handle
    bbox: Dict[str, float]
    number: int
    selector: str
    match_method: str
    confidence: float
    original_data: Dict

@dataclass
class SearchConfig:
    """Configuration for element search strategies"""
    use_css_selector: bool = True
    use_fuzzy_html: bool = True
    use_fuzzy_text: bool = True
    use_position: bool = True
    use_similarity: bool = True

    css_selector_timeout: int = 1000
    min_html_similarity: float = 0.8
    min_text_similarity: float = 0.7
    position_tolerance: int = 50
    max_elements_to_check: int = 100

# ============================================================================
# ELEMENT SEARCH ENGINE
# ============================================================================

class ElementFinder:
    """Modular element finder with multiple fallback strategies"""
    
    def __init__(self, page, config: SearchConfig = None):
        self.page = page
        self.config = config or SearchConfig()
        
    async def find_element(self, event_data: Dict, event_number: int) -> Optional[ElementMatch]:
        """
        Try multiple strategies to find an element based on recorded data
        Returns the best match found
        """
        strategies = []
        
        # Strategy 1: CSS Selector (Primary)
        if self.config.use_css_selector and event_data.get('selector'):
            match = await self._find_by_css_selector(event_data, event_number)
            if match:
                return match
                
        # Strategy 2: Fuzzy HTML Matching
        if self.config.use_fuzzy_html and event_data.get('outerHTML'):
            match = await self._find_by_fuzzy_html(event_data, event_number)
            if match and match.confidence >= self.config.min_html_similarity:
                return match
                
        # Strategy 3: Fuzzy Text Matching
        if self.config.use_fuzzy_text and event_data.get('innerText'):
            match = await self._find_by_fuzzy_text(event_data, event_number)
            if match and match.confidence >= self.config.min_text_similarity:
                return match
                
        # Strategy 4: Position-based Search
        if self.config.use_position:
            match = await self._find_by_position(event_data, event_number)
            if match:
                return match
                
        # Strategy 5: Similar Element Search
        if self.config.use_similarity:
            match = await self._find_similar_element(event_data, event_number)
            if match:
                return match
                
        return None
    
    async def _find_by_css_selector(self, event_data: Dict, event_number: int) -> Optional[ElementMatch]:
        """Find element using CSS selector"""
        try:
            selector = event_data['selector']
            element = await self.page.query_selector(selector)
            
            if element:
                bbox = await element.bounding_box()
                if bbox:
                    return ElementMatch(
                        element=element,
                        bbox=bbox,
                        number=event_number,
                        selector=selector,
                        match_method='css_selector',
                        confidence=1.0,
                        original_data=event_data
                    )
        except Exception as e:
            print(f"   ⚠️  CSS selector failed: {str(e)[:50]}")
        return None
    
    async def _find_by_fuzzy_html(self, event_data: Dict, event_number: int) -> Optional[ElementMatch]:
        """Find element by comparing HTML similarity"""
        try:
            original_html = event_data['outerHTML']
            if not original_html or len(original_html) < 10:
                return None
                
            # Extract tag and key attributes from original HTML
            tag_name = event_data.get('tagName', '').lower()
            
            # Get all elements of the same type
            all_elements = await self.page.query_selector_all(tag_name)
            all_elements = all_elements[:self.config.max_elements_to_check]
            
            best_match = None
            best_score = 0
            
            for element in all_elements:
                current_html = await element.evaluate('el => el.outerHTML')
                
                # Calculate similarity
                similarity = self._calculate_html_similarity(original_html, current_html)
                
                if similarity > best_score:
                    best_score = similarity
                    bbox = await element.bounding_box()
                    if bbox:
                        best_match = ElementMatch(
                            element=element,
                            bbox=bbox,
                            number=event_number,
                            selector=f"fuzzy_html_{tag_name}",
                            match_method='fuzzy_html',
                            confidence=similarity,
                            original_data=event_data
                        )
            
            if best_match:
                print(f"   🔍 Fuzzy HTML match: {best_score:.2%}")
                return best_match
                
        except Exception as e:
            print(f"   ⚠️  Fuzzy HTML failed: {str(e)[:50]}")
        return None
    
    async def _find_by_fuzzy_text(self, event_data: Dict, event_number: int) -> Optional[ElementMatch]:
        """Find element by comparing text content"""
        try:
            original_text = event_data.get('innerText', '').strip()
            if not original_text or len(original_text) < 3:
                return None
            
            # Get elements that could contain text
            selectors = ['a', 'button', 'span', 'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'label']
            
            for selector in selectors:
                elements = await self.page.query_selector_all(selector)
                elements = elements[:self.config.max_elements_to_check]
                
                for element in elements:
                    current_text = await element.text_content() or ''
                    current_text = current_text.strip()
                    
                    if not current_text:
                        continue
                    
                    similarity = difflib.SequenceMatcher(
                        None, 
                        original_text.lower(), 
                        current_text.lower()
                    ).ratio()
                    
                    if similarity >= self.config.min_text_similarity:
                        bbox = await element.bounding_box()
                        if bbox:
                            return ElementMatch(
                                element=element,
                                bbox=bbox,
                                number=event_number,
                                selector=f"fuzzy_text_{selector}",
                                match_method='fuzzy_text',
                                confidence=similarity,
                                original_data=event_data
                            )
                            
        except Exception as e:
            print(f"   ⚠️  Fuzzy text failed: {str(e)[:50]}")
        return None
    
    async def _find_by_position(self, event_data: Dict, event_number: int) -> Optional[ElementMatch]:
        """Find element by approximate position"""
        try:
            # Get recorded position
            viewport_x = event_data.get('x_viewport')
            viewport_y = event_data.get('y_viewport')
            scroll_y = event_data.get('scrollY', 0)
            
            if viewport_x is None or viewport_y is None:
                return None
            
            absolute_y = viewport_y + scroll_y
            
            # Get all elements near this position
            tolerance = self.config.position_tolerance
            
            # Use JavaScript to find element at coordinates
            element_at_point = await self.page.evaluate('''(x, y) => {
                return document.elementFromPoint(x, y);
            }''', viewport_x, viewport_y)
            
            if element_at_point:
                # Get the element handle
                element = await self.page.evaluate_handle('(el) => el', element_at_point)
                bbox = await element.bounding_box()
                
                if bbox:
                    return ElementMatch(
                        element=element,
                        bbox=bbox,
                        number=event_number,
                        selector='position_based',
                        match_method='position',
                        confidence=0.5,
                        original_data=event_data
                    )
                    
        except Exception as e:
            print(f"   ⚠️  Position search failed: {str(e)[:50]}")
        return None
    
    async def _find_similar_element(self, event_data: Dict, event_number: int) -> Optional[ElementMatch]:
        """Find element with similar characteristics"""
        try:
            tag_name = event_data.get('tagName', '').lower()
            class_name = event_data.get('className', '')
            element_id = event_data.get('id', '')
            
            # Build a flexible selector
            selector_parts = []
            if tag_name:
                selector_parts.append(tag_name)
            if element_id:
                selector_parts.append(f'#{element_id}')
            if class_name:
                # Take just the first class for simplicity
                first_class = class_name.split()[0] if class_name else ''
                if first_class:
                    selector_parts.append(f'.{first_class}')
            
            if selector_parts:
                selector = ''.join(selector_parts)
                elements = await self.page.query_selector_all(selector)
                
                if elements:
                    # Take the first matching element
                    element = elements[0]
                    bbox = await element.bounding_box()
                    
                    if bbox:
                        return ElementMatch(
                            element=element,
                            bbox=bbox,
                            number=event_number,
                            selector=selector,
                            match_method='similar_element',
                            confidence=0.3,
                            original_data=event_data
                        )
                        
        except Exception as e:
            print(f"   ⚠️  Similar element search failed: {str(e)[:50]}")
        return None
    
    def _calculate_html_similarity(self, html1: str, html2: str) -> float:
        """Calculate similarity between two HTML strings"""
        if not html1 or not html2:
            return 0.0
        
        # Simple similarity based on common substrings
        html1_lower = html1.lower()
        html2_lower = html2.lower()
        
        # Check for exact tag match
        import re
        tag1 = re.match(r'^<(\w+)', html1_lower)
        tag2 = re.match(r'^<(\w+)', html2_lower)
        
        if not tag1 or not tag2 or tag1.group(1) != tag2.group(1):
            return 0.0
        
        # Calculate string similarity
        return difflib.SequenceMatcher(None, html1_lower[:200], html2_lower[:200]).ratio()

# ============================================================================
# HIGHLIGHT MANAGER
# ============================================================================

class HighlightManager:
    """Manages highlighting and labeling elements on the page"""
    
    def __init__(self, page):
        self.page = page
        self.highlighted_elements = []
        
    async def setup(self):
        """Inject CSS for highlighting"""
        await self.page.add_style_tag(content='''
            .tracker-highlight {
                outline: 3px solid red !important;
                outline-offset: 2px !important;
                box-shadow: 0 0 0 3px rgba(255,0,0,0.3) !important;
            }
            .tracker-label {
                position: absolute !important;
                background: red !important;
                color: white !important;
                font-weight: bold !important;
                padding: 2px 6px !important;
                border-radius: 10px !important;
                font-size: 14px !important;
                z-index: 9999 !important;
                pointer-events: none !important;
            }
        ''')
    
    async def highlight_element(self, element_match: ElementMatch):
        """Highlight a single element and add label"""
        element = element_match.element
        
        # Add highlight
        await element.evaluate('''(element) => {
            element.classList.add('tracker-highlight');
        }''')
        
        # Add label
        bbox = element_match.bbox
        await self.page.evaluate('''({bbox, number, method}) => {
            const label = document.createElement('div');
            label.className = 'tracker-label';
            label.textContent = `${number} (${method})`;
            
            label.style.left = (bbox.x + bbox.width + 5) + 'px';
            label.style.top = (bbox.y - 5) + 'px';
            
            if (bbox.x + bbox.width + 100 > window.innerWidth) {
                label.style.left = (bbox.x - 25) + 'px';
            }
            
            document.body.appendChild(label);
        }''', {'bbox': bbox, 'number': element_match.number, 'method': element_match.match_method})
        
        self.highlighted_elements.append(element_match)
        
    async def take_screenshot(self, output_path: str):
        """Take screenshot of highlighted page"""
        await self.page.screenshot(path=output_path, full_page=True)

# ============================================================================
# MAIN APPLICATION
# ============================================================================

async def highlight_clicked_elements(csv_file: str, target_url: str, output_file: str = 'element_highlights.png'):
    """
    Main function to find and highlight clicked elements
    """
    
    # 1. Read and filter the CSV
    print(f"📁 Reading CSV: {csv_file}")
    df = pd.read_csv(csv_file)
    
    # Filter by URL and click events only
    df = df[(df['url'] == target_url) & (df['type'] == 'click')]
    df = df.sort_values('timestamp')
    
    if len(df) == 0:
        print(f"❌ No click events found for URL: {target_url}")
        return
    
    print(f"✅ Found {len(df)} click events")
    
    # 2. Launch Chrome browser
    print("🚀 Launching Chrome browser...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel='chrome',
            headless=False,
            args=['--start-maximized']
        )
        
        page = await browser.new_page()
        
        # 3. Wait for user to navigate manually
        print("\n" + "="*60)
        print("⚠️  MANUAL SETUP REQUIRED")
        print("="*60)
        print("1. The Chrome browser has opened")
        print("2. Please manually navigate to:")
        print(f"   {target_url}")
        print("3. Login/setup your account if needed")
        print("4. Make sure the page is fully loaded")
        print("5. Then return here and press Enter to continue...")
        print("="*60 + "\n")
        
        await page.goto('about:blank')
        input("Press Enter after you've navigated to the correct page and logged in...")
        
        # 4. Verify we're on the correct page
        current_url = page.url
        if target_url not in current_url:
            print(f"⚠️  Warning: You're on {current_url}")
            print(f"   Expected URL containing: {target_url}")
            confirm = input("Continue anyway? (y/n): ")
            if confirm.lower() != 'y':
                await browser.close()
                return
        
        print(f"🌐 Current page: {current_url}")
        
        # 5. Initialize modules
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
        
        # 6. Process each click event
        print("\n🔍 Finding and highlighting clicked elements...")
        
        found_elements = []
        not_found = []
        
        for i, (_, event) in enumerate(df.iterrows(), 1):
            print(f"\n[{i}] Searching for element...")
            
            # Convert event row to dictionary
            event_data = event.to_dict()
            
            # Try to find the element
            element_match = await finder.find_element(event_data, i)
            
            if element_match:
                print(f"   ✓ Found via {element_match.match_method} (confidence: {element_match.confidence:.0%})")
                
                # Highlight the element
                await highlighter.highlight_element(element_match)
                found_elements.append(element_match)
                
                # Small delay to avoid overwhelming the page
                await page.wait_for_timeout(100)
            else:
                print(f"   ❌ Could not find element")
                not_found.append({
                    'number': i,
                    'selector': event_data.get('selector', ''),
                    'tag': event_data.get('tagName', '')
                })
        
        # 7. Take screenshot
        print(f"\n📸 Taking screenshot...")
        await highlighter.take_screenshot(output_file)
        print(f"✅ Screenshot saved to: {output_file}")
        
        # 8. Create summary report
        await _generate_summary_report(found_elements, not_found, df, output_file)
        
        # 9. Cleanup
        keep_open = input("\nKeep browser open to inspect elements? (y/n): ")
        if keep_open.lower() != 'y':
            await browser.close()
        else:
            print("Browser will remain open. Close it manually when done.")
        
        print("✨ Done!")

async def _generate_summary_report(found_elements: List[ElementMatch], not_found: List, df, output_file: str):
    """Generate and display summary report"""
    print("\n" + "="*60)
    print("📊 SUMMARY REPORT")
    print("="*60)
    print(f"Total clicks in CSV: {len(df)}")
    print(f"Elements successfully found: {len(found_elements)}")
    print(f"Elements not found: {len(not_found)}")
    
    # Method breakdown
    if found_elements:
        print("\n📈 Match Methods Used:")
        methods = {}
        for elem in found_elements:
            methods[elem.match_method] = methods.get(elem.match_method, 0) + 1
        
        for method, count in methods.items():
            print(f"  {method}: {count} elements")
    
    # Confidence statistics
    if found_elements:
        avg_confidence = sum(e.confidence for e in found_elements) / len(found_elements)
        print(f"\n🎯 Average confidence: {avg_confidence:.1%}")
    
    # Save detailed report
    save_data = input("\nSave detailed report to JSON? (y/n): ")
    if save_data.lower() == 'y':
        report_data = {
            'summary': {
                'total_clicks': len(df),
                'found': len(found_elements),
                'not_found': len(not_found),
                'success_rate': len(found_elements) / len(df) if len(df) > 0 else 0
            },
            'found_elements': [
                {
                    'number': e.number,
                    'selector': e.selector,
                    'match_method': e.match_method,
                    'confidence': e.confidence,
                    'position': {
                        'x': e.bbox['x'],
                        'y': e.bbox['y'],
                        'width': e.bbox['width'],
                        'height': e.bbox['height']
                    }
                }
                for e in found_elements
            ],
            'not_found_elements': not_found
        }
        
        json_file = output_file.replace('.png', '_report.json')
        with open(json_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        print(f"📁 Detailed report saved to: {json_file}")

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    # Set up paths
    DATA_DIR = Path(__file__).resolve().parent / "data"
    event_file = DATA_DIR / "Test" / "events.csv"
    
    # Check if file exists
    if not event_file.exists():
        print(f"❌ Error: File not found at {event_file}")
        print("Please make sure the CSV file exists in the data/Test/ directory.")
        return
    
    # Run the async function
    asyncio.run(highlight_clicked_elements(
        str(event_file), 
        "https://letterboxd.com/", 
        'element_highlights.png'
    ))

if __name__ == '__main__':
    main()