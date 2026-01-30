# heatmap_visualizer.py
import json
from typing import List
from element_finder import ElementMatch  # Import from element_finder


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
# REPORT GENERATOR
# ============================================================================

async def generate_summary_report(found_elements: List[ElementMatch], not_found: List, df, output_file: str):
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