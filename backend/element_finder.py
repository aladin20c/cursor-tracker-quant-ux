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

    min_html_similarity: float = 0.7
    min_text_similarity: float = 0.7
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
                print(f"Fuzzy HTML match: {best_score:.2%}")
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
                                match_method='fuzzy_text',
                                confidence=similarity,
                                original_data=event_data
                            )
                            
        except Exception as e:
            print(f" Fuzzy text failed: {str(e)[:50]}")
        return None
    
    # ============================================================================
    # Position
    # ============================================================================

    async def _find_by_position(self, event_data: Dict, event_number: int) -> Optional[ElementMatch]:
        """Find element by approximate position"""
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
    
