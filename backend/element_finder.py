# element_finder.py
import difflib
import re
from typing import Dict, Optional
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

    min_html_similarity: float = 0.8
    min_text_similarity: float = 0.8
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
    
    # ============================================================================
    # CSS SELECTOR
    # ============================================================================

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
                        match_method='css_selector',
                        confidence=1.0,
                        original_data=event_data
                    )
        except Exception as e:
            print(f"CSS selector failed: {str(e)[:50]}")
        return None
    

    # ============================================================================
    # HTML
    # ============================================================================

    async def _find_by_fuzzy_html(self, event_data: Dict, event_number: int) -> Optional[ElementMatch]:
        """Find element by comparing HTML similarity"""
        try:
            original_html = event_data['outerHTML']
            if not original_html or len(original_html) < 10:
                return None
                
            # Extract tag and key attributes from original HTML
            tag_name = event_data.get('tagName', '').lower()
            
            # Get all elements of the same type with maximum number of max_elements_to_check
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
                            match_method='fuzzy_html',
                            confidence=similarity,
                            original_data=event_data
                        )
            
            if best_match:
                #print(f"Fuzzy HTML match: {best_score:.2%}")
                return best_match
                
        except Exception as e:
            print(f"Fuzzy HTML failed: {str(e)[:50]}")
        return None
    

    def _calculate_html_similarity(self, html1: str, html2: str) -> float:
        """Calculate similarity between two HTML strings"""
        if not html1 or not html2:
            return 0.0
        
        # Simple similarity based on common substrings
        html1_lower = html1.lower()
        html2_lower = html2.lower()
        
        # Check for exact tag match
        tag1 = re.match(r'^<(\w+)', html1_lower)
        tag2 = re.match(r'^<(\w+)', html2_lower)
        
        if not tag1 or not tag2 or tag1.group(1) != tag2.group(1): return 0.0
        
        return difflib.SequenceMatcher(None, html1_lower[:200], html2_lower[:200]).ratio()

    # ============================================================================
    # TEXT
    # ============================================================================


    async def _find_by_fuzzy_text(self, event_data: Dict, event_number: int) -> Optional[ElementMatch]:
        """Find element by comparing text content"""
        try:
            original_text = event_data.get('innerText', '')
            if original_text is None: original_text = ''
            else: original_text = str(original_text)
            original_text = original_text.strip()

            if not original_text or len(original_text) < 3:
                return None
            
            # Get elements that could contain text
            selectors = ['a', 'button', 'span', 'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'label']
            
            for selector in selectors:
                elements = await self.page.query_selector_all(selector)
                elements = elements[:self.config.max_elements_to_check]
                
                for element in elements:
                    current_text = await element.text_content() or ''

                    if current_text is None: current_text = ''
                    else: current_text = str(current_text)

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
                                match_method='fuzzy_text',
                                confidence=similarity,
                                original_data=event_data
                            )
                            
        except Exception as e:
            print(f" Fuzzy text failed: {str(e)[:50]}")
        return None
    
    # ============================================================================
    # OTHER
    # ============================================================================

    async def _find_similar_element(self, event_data: Dict, event_number: int) -> Optional[ElementMatch]:
        """Find element with similar characteristics"""
        try:
            tag_name = event_data.get('tagName', '').lower()
            class_name = event_data.get('className', '')

            if class_name is None: class_name = ''
            else: class_name = str(class_name)

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
                            match_method='similar_element',
                            confidence=0.3,
                            original_data=event_data
                        )
                        
        except Exception as e:
            print(f"Similar element search failed: {str(e)[:50]}")
        return None
    
    # ============================================================================
    # Position
    # ============================================================================
    async def _find_by_position(self, event_data: Dict, event_number: int) -> Optional[ElementMatch]:
        """Find element by absolute position in document"""
        try:
            # Get recorded data
            viewport_x = float(event_data.get('x_viewport', 0))
            viewport_y = float(event_data.get('y_viewport', 0))
            scroll_x = float(event_data.get('scrollX', 0))
            scroll_y = float(event_data.get('scrollY', 0))
            doc_w = float(event_data.get('docWidth', 1920))
            doc_h = float(event_data.get('docHeight', 1080))
            
            element_top = float(event_data.get('element_top', 0))
            element_left = float(event_data.get('element_left', 0))
            element_width = float(event_data.get('element_width', 0))
            element_height = float(event_data.get('element_height', 0))
            tag_name = event_data.get('tagName', '').lower()
            
            # Get current document size
            current_doc_w = await self.page.evaluate('document.documentElement.scrollWidth')
            current_doc_h = await self.page.evaluate('document.documentElement.scrollHeight')
            
            # ====================== CALCULATE ABSOLUTE POSITIONS ======================
            # Step 1: Old absolute position in document
            old_absolute_x = viewport_x + scroll_x
            old_absolute_y = viewport_y + scroll_y
            
            # Step 2: Normalize to percentages
            percent_x = old_absolute_x / doc_w if doc_w > 0 else 0
            percent_y = old_absolute_y / doc_h if doc_h > 0 else 0
            
            # Step 3: Current absolute position in document
            current_absolute_x = percent_x * current_doc_w
            current_absolute_y = percent_y * current_doc_h
            
            # ====================== METHOD 1: Find element at absolute click position ======================
            # Scroll to the absolute position first
            await self.page.evaluate(f'''
                window.scrollTo({current_absolute_x - 100}, {current_absolute_y - 300});
            ''')
            
            await self.page.wait_for_timeout(300)
            
            # Get current scroll to calculate viewport position
            current_scroll = await self.page.evaluate('''() => ({
                scrollX: window.scrollX,
                scrollY: window.scrollY
            })''')
            
            current_scroll_x = current_scroll['scrollX']
            current_scroll_y = current_scroll['scrollY']
            
            # Calculate position in current viewport
            viewport_x_now = current_absolute_x - current_scroll_x
            viewport_y_now = current_absolute_y - current_scroll_y
            
            # Get viewport size for bounds
            viewport_w = await self.page.evaluate('window.innerWidth')
            viewport_h = await self.page.evaluate('window.innerHeight')
            
            # Ensure within viewport
            viewport_x_now = max(0, min(viewport_x_now, viewport_w - 1))
            viewport_y_now = max(0, min(viewport_y_now, viewport_h - 1))
            
            # Find element at that position - USE elementsFromPoint instead
            elements_at_point = await self.page.evaluate('''({x, y}) => {
                return document.elementsFromPoint(x, y);
            }''', {'x': viewport_x_now, 'y': viewport_y_now})
            
            if elements_at_point and len(elements_at_point) > 0:
                # Try each element until we find one that matches
                for element_js in elements_at_point:
                    try:
                        # Get element handle
                        element = await self.page.evaluate_handle('el => el', element_js)
                        
                        # Get tag name - WITH ERROR HANDLING
                        element_tag = await self.page.evaluate('''(el) => {
                            return el ? el.tagName ? el.tagName.toLowerCase() : null : null;
                        }''', element)
                        
                        if element_tag is None:
                            continue
                            
                        if not tag_name or element_tag == tag_name:
                            bbox = await element.bounding_box()
                            if bbox:
                                return ElementMatch(
                                    element=element,
                                    bbox=bbox,
                                    number=event_number,
                                    match_method='position_absolute',
                                    confidence=0.8,
                                    original_data=event_data
                                )
                    except Exception as e:
                        # Skip this element and try the next one
                        continue
            
            # ====================== METHOD 2: Find element by absolute element position ======================
            if element_left > 0 and element_top > 0:
                # element_left and element_top are already absolute in document
                element_left_percent = element_left / doc_w if doc_w > 0 else 0
                element_top_percent = element_top / doc_h if doc_h > 0 else 0
                
                # Current absolute element position
                current_element_absolute_x = element_left_percent * current_doc_w
                current_element_absolute_y = element_top_percent * current_doc_h
                
                # Scroll to element position
                await self.page.evaluate(f'''
                    window.scrollTo({current_element_absolute_x - 100}, {current_element_absolute_y - 300});
                ''')
                
                await self.page.wait_for_timeout(300)
                
                # Get current scroll again
                current_scroll = await self.page.evaluate('''() => ({
                    scrollX: window.scrollX,
                    scrollY: window.scrollY
                })''')
                
                current_scroll_x = current_scroll['scrollX']
                current_scroll_y = current_scroll['scrollY']
                
                # Calculate element position in viewport
                element_viewport_x = current_element_absolute_x - current_scroll_x
                element_viewport_y = current_element_absolute_y - current_scroll_y
                
                # Ensure within viewport
                element_viewport_x = max(0, min(element_viewport_x, viewport_w - 1))
                element_viewport_y = max(0, min(element_viewport_y, viewport_h - 1))
                
                # Find element - USE elementsFromPoint instead
                elements_at_point = await self.page.evaluate('''({x, y}) => {
                    return document.elementsFromPoint(x, y);
                }''', {'x': element_viewport_x, 'y': element_viewport_y})
                
                if elements_at_point and len(elements_at_point) > 0:
                    # Try each element until we find one that matches
                    for element_js in elements_at_point:
                        try:
                            element = await self.page.evaluate_handle('el => el', element_js)
                            
                            # Get tag name - WITH ERROR HANDLING
                            element_tag = await self.page.evaluate('''(el) => {
                                return el ? el.tagName ? el.tagName.toLowerCase() : null : null;
                            }''', element)
                            
                            if element_tag is None:
                                continue
                                
                            if not tag_name or element_tag == tag_name:
                                bbox = await element.bounding_box()
                                if bbox:
                                    # Check size similarity
                                    if element_width > 0 and element_height > 0:
                                        width_diff = abs(bbox['width'] - element_width)
                                        height_diff = abs(bbox['height'] - element_height)
                                        
                                        if width_diff < 50 and height_diff < 50:
                                            return ElementMatch(
                                                element=element,
                                                bbox=bbox,
                                                number=event_number,
                                                match_method='position_element',
                                                confidence=0.7,
                                                original_data=event_data
                                            )
                        except Exception as e:
                            # Skip this element and try the next one
                            continue
            
            return None
                        
        except Exception as e:
            print(f"Position search failed: {str(e)}")
            return None