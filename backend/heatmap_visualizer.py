# heatmap_visualizer.py - SIMPLIFIED
import json
import math
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from element_finder import ElementMatch


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class VisualizationConfig:
    """Configuration for visualization options"""
    highlight_elements: bool = True
    show_mouse_heatmap: bool = True
    include_undetected_clicks: bool = True
    heatmap_intensity: float = 1.0
    circle_size: int = 10  # Simple circle size
    show_click_numbers: bool = True
    color_scheme: str = "hot"  # hot, warm, cool


# ============================================================================
# DYNAMIC POSITION CALCULATOR
# ============================================================================

class DynamicPositionCalculator:
    """Calculates click positions accounting for screen differences"""
    
    @staticmethod
    def calculate_absolute_position(event_data: Dict, current_page_state: Dict) -> Optional[Tuple[float, float]]:
        try:
            # Get recorded data
            recorded_viewport_x = float(event_data.get('x_viewport', 0))
            recorded_viewport_y = float(event_data.get('y_viewport', 0))
            recorded_scroll_x = float(event_data.get('scrollX', 0))
            recorded_scroll_y = float(event_data.get('scrollY', 0))
            recorded_doc_w = float(event_data.get('docWidth', 1920))
            recorded_doc_h = float(event_data.get('docHeight', 1080))
            
            # Get current state
            current_doc_w = current_page_state['doc_w']
            current_doc_h = current_page_state['doc_h']
            
            # Absolute position in old document
            old_absolute_x = recorded_viewport_x + recorded_scroll_x
            old_absolute_y = recorded_viewport_y + recorded_scroll_y
            
            # Normalize to percentages
            percent_x = old_absolute_x / recorded_doc_w if recorded_doc_w > 0 else 0
            percent_y = old_absolute_y / recorded_doc_h if recorded_doc_h > 0 else 0
            
            # Absolute position in current document
            current_absolute_x = percent_x * current_doc_w
            current_absolute_y = percent_y * current_doc_h
            
            return (current_absolute_x, current_absolute_y)
            
        except Exception as e:
            print(f"Position calculation failed: {e}")
            return None
    
    @staticmethod
    def calculate_element_relative_position(element_bbox: Dict[str, float], event_data: Dict) -> Optional[Tuple[float, float]]:
        """
        Calculate click position relative to element bounds
        Uses element_relative_x/y for precision
        """
        try:
            element_rel_x = float(event_data.get('element_relative_x', 0))
            element_rel_y = float(event_data.get('element_relative_y', 0))
            
            absolute_x = element_bbox['x'] + element_rel_x
            absolute_y = element_bbox['y'] + element_rel_y
            
            if (element_bbox['x'] <= absolute_x <= element_bbox['x'] + element_bbox['width'] and
                element_bbox['y'] <= absolute_y <= element_bbox['y'] + element_bbox['height']):
                return (absolute_x, absolute_y)
            
        except:
            pass
        
        return (
            element_bbox['x'] + element_bbox['width'] / 2,
            element_bbox['y'] + element_bbox['height'] / 2
        )


# ============================================================================
# SIMPLE HEATMAP VISUALIZER
# ============================================================================

class HeatmapVisualizer:
    """Creates simple heatmaps with circles"""
    
    def __init__(self, page, config: VisualizationConfig = None):
        self.page = page
        self.config = config or VisualizationConfig()
        self.position_calculator = DynamicPositionCalculator()
        self.click_positions = []
        
    async def get_current_page_state(self) -> Dict:
        """Get current page dimensions and scroll"""
        state = await self.page.evaluate('''() => ({
            viewport_w: window.innerWidth,
            viewport_h: window.innerHeight,
            scroll_x: window.scrollX,
            scroll_y: window.scrollY,
            doc_w: document.documentElement.scrollWidth,
            doc_h: document.documentElement.scrollHeight
        })''')
        return state
    
    async def add_click(self, event_data: Dict, element_match: Optional[ElementMatch] = None, event_number: int = 0):
        """Add a click to heatmap data"""
        current_state = await self.get_current_page_state()
        
        if element_match and element_match.bbox:
            #position = self.position_calculator.calculate_element_relative_position(element_match.bbox, event_data)
            position = self.position_calculator.calculate_absolute_position(event_data, current_state)
            weight = element_match.confidence
            is_detected = True
        elif self.config.include_undetected_clicks:
            position = self.position_calculator.calculate_absolute_position(event_data, current_state)
            weight = 0.3
            is_detected = False
        else:
            return
        
        if position:
            self.click_positions.append({
                'x': position[0],
                'y': position[1],
                'weight': weight,
                'is_detected': is_detected,
                'number': event_number
            })
    
    async def render_heatmap(self):
        """Render simple circles for clicks"""
        if not self.click_positions or not self.config.show_mouse_heatmap:
            print(f"No click positions to render or heatmap disabled")
            print(f"Click positions: {len(self.click_positions)}")
            print(f"Show heatmap config: {self.config.show_mouse_heatmap}")
            return
        
        print(f"Rendering {len(self.click_positions)} clicks as circles")
        
        # Group nearby clicks to avoid too many circles
        grouped_clicks = self._group_nearby_clicks(self.click_positions)
        
        # Render simple circles
        await self._render_simple_circles(grouped_clicks)
    
    def _group_nearby_clicks(self, clicks: List[Dict]) -> List[Dict]:
        """Group nearby clicks to reduce overlap"""
        if len(clicks) < 20:
            return clicks
        
        clusters = []
        processed = set()
        
        for i, click in enumerate(clicks):
            if i in processed:
                continue
            
            cluster = [click]
            processed.add(i)
            
            for j, other_click in enumerate(clicks[i+1:], i+1):
                if j in processed:
                    continue
                
                distance = math.sqrt((other_click['x'] - click['x'])**2 + (other_click['y'] - click['y'])**2)
                if distance <= 20:  # Group within 20 pixels
                    cluster.append(other_click)
                    processed.add(j)
            
            total_weight = sum(c['weight'] for c in cluster)
            center_x = sum(c['x'] * c['weight'] for c in cluster) / total_weight
            center_y = sum(c['y'] * c['weight'] for c in cluster) / total_weight
            
            clusters.append({
                'x': center_x,
                'y': center_y,
                'weight': total_weight,
                'count': len(cluster),
                'is_detected': any(c['is_detected'] for c in cluster)
            })
        
        return clusters
    
    async def _render_simple_circles(self, clicks: List[Dict]):
        """Render simple colored circles for each click"""
        if not clicks:
            return
        
        # Get max weight for normalization
        max_weight = max(c['weight'] for c in clicks) if clicks else 1
        
        # Add CSS for circles
        await self.page.add_style_tag(content='''
            .click-circle {
                position: absolute !important;
                border-radius: 50% !important;
                pointer-events: none !important;
                z-index: 9998 !important;
            }
        ''')
        
        # Create all circles
        for click in clicks:
            intensity = click['weight'] / max_weight
            size = self.config.circle_size + (intensity * 10)  # Size based on intensity
            opacity = self.config.heatmap_intensity * (0.3 + intensity * 0.7)
            
            # Choose color
            if not click['is_detected']:
                color = f"rgba(0, 100, 255, {opacity})"  # Blue for undetected
            elif self.config.color_scheme == "hot":
                if intensity < 0.5:
                    g = int(255 * intensity * 2)
                    color = f"rgba(255, {g}, 0, {opacity})"
                else:
                    b = int(255 * (intensity - 0.5) * 2)
                    color = f"rgba(255, 255, {b}, {opacity})"
            elif self.config.color_scheme == "warm":
                r = int(150 + 105 * intensity)
                g = int(50 + 100 * intensity)
                b = int(255 - 255 * intensity)
                color = f"rgba({r}, {g}, {b}, {opacity})"
            else:  # cool
                r = int(100 * intensity)
                g = int(200 * intensity)
                color = f"rgba({r}, {g}, 255, {opacity})"
            
            # Create circle element
            await self.page.evaluate(f'''
                (function() {{
                    const circle = document.createElement('div');
                    circle.className = 'click-circle';
                    circle.style.left = '{click["x"] - size/2}px';
                    circle.style.top = '{click["y"] - size/2}px';
                    circle.style.width = '{size}px';
                    circle.style.height = '{size}px';
                    circle.style.backgroundColor = '{color}';
                    document.body.appendChild(circle);
                }})();
            ''')


# ============================================================================
# SIMPLE HIGHLIGHT MANAGER
# ============================================================================

class HighlightManager:
    """Simple element highlighting"""
    
    def __init__(self, page, config: VisualizationConfig = None):
        self.page = page
        self.config = config or VisualizationConfig()
        
    async def setup(self):
        """Inject CSS for highlighting"""
        if self.config.highlight_elements:
            await self.page.add_style_tag(content='''
                .tracker-highlight {
                    outline: 3px solid red !important;
                    outline-offset: 2px !important;
                }
                .tracker-label {
                    position: absolute !important;
                    background: red !important;
                    color: white !important;
                    font-weight: bold !important;
                    padding: 2px 6px !important;
                    border-radius: 10px !important;
                    font-size: 12px !important;
                    z-index: 9999 !important;
                    pointer-events: none !important;
                }
            ''')
    
    async def highlight_element(self, element_match: ElementMatch):
        """Highlight a single element"""
        if not self.config.highlight_elements:
            return
        
        element = element_match.element
        
        # Add highlight
        await element.evaluate('''(element) => {
            element.classList.add('tracker-highlight');
        }''')
        
        # Add label if enabled
        if self.config.show_click_numbers:
            bbox = element_match.bbox
            await self.page.evaluate('''({bbox, number, confidence}) => {
                const label = document.createElement('div');
                label.className = 'tracker-label';
                label.textContent = number + ' (' + Math.round(confidence * 100) + '%)';
                
                label.style.left = (bbox.x + bbox.width + 5) + 'px';
                label.style.top = (bbox.y - 5) + 'px';
                
                if (bbox.x + bbox.width + 100 > window.innerWidth) {
                    label.style.left = (bbox.x - 30) + 'px';
                }
                
                document.body.appendChild(label);
            }''', {
                'bbox': bbox, 
                'number': element_match.number, 
                'confidence': element_match.confidence
            })
    
    async def take_screenshot(self, output_path: str):
        """Take screenshot"""
        await self.page.screenshot(path=output_path, full_page=True)