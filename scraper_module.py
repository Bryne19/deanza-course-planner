#!/usr/bin/env python3
"""
De Anza College Schedule Scraper
Scrapes course information from the De Anza schedule listings page.
Uses cloudscraper to bypass Cloudflare protection.
"""

import cloudscraper
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Optional
import time
from urllib.parse import quote

# Pre-compile regex patterns for better performance
CRN_PATTERN = re.compile(r'\b(\d{5})\b')
TIME_PATTERN = re.compile(r'(\d{1,2}:\d{2}\s*[AP]M)\s*-\s*(\d{1,2}:\d{2}\s*[AP]M)', re.I)
NAME_PATTERN_LAST_FIRST = re.compile(r'^([A-Z][a-z]+(?:-[A-Z][a-z]+)?),\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)$')
NAME_PATTERN_FIRST_LAST = re.compile(r'^([A-Z][a-z]+\s+[A-Z][a-z]+)$')
NAME_PATTERN_FIRST_M_LAST = re.compile(r'^([A-Z][a-z]+\s+[A-Z]\.\s+[A-Z][a-z]+)$')
EXCLUDE_TERMS = {'view', 'footnote', 'math', 'calculus', 'class', 'meets', 
                 'campus', 'online', 'hybrid', 'tba', 'tbd', 'am', 'pm', 'open', 'wl'}


def normalize_name(name: str) -> list:
    """
    Normalize a name by splitting on spaces and handling concatenated names.
    Handles cases like "Roderic (Rick)Taylor" -> ["roderic", "taylor"]
    or "RodericTaylor" -> ["roderic", "taylor"]
    or "Christopher N.Bradley" -> ["christopher", "bradley"]
    """
    # Remove content in parentheses (like "(Rick)") - we don't need it for matching
    name_clean = re.sub(r'\([^)]*\)', '', name)
    name_clean = name_clean.replace(',', ' ')
    
    # Replace periods followed by capital letters with space (handles "N.Bradley" -> "N Bradley")
    name_clean = re.sub(r'\.([A-Z])', r' \1', name_clean)
    
    # First try splitting on spaces
    parts = name_clean.split()
    
    # If we only got one part (no spaces), try to split on capital letters
    # This handles cases like "RodericTaylor" or "Roderic(Rick)Taylor" or "PatrickMcDonnell" or "MorganMcKnight"
    if len(parts) == 1:
        # Handle special prefixes like "Mc", "Mac", "O'", "De", "Van", etc.
        # These should be kept with the following name part
        # Strategy: First split on capital letters, then merge prefixes with following parts
        
        # Split on capital letter boundaries: [A-Z] followed by lowercase
        # This gives us ["Morgan", "Mc", "Knight"] for "MorganMcKnight"
        split_parts = re.findall(r'[A-Z][^A-Z]*', parts[0])
        
        if len(split_parts) >= 2:
            # Merge special prefixes with the following part
            # Prefixes that should be merged: Mc, Mac, O', De, Van, Von, La, Le, St, Saint
            special_prefixes = ['Mc', 'Mac', 'O\'', 'De', 'Van', 'Von', 'La', 'Le', 'St', 'Saint']
            merged = []
            i = 0
            while i < len(split_parts):
                current = split_parts[i]
                # Check if current part is a special prefix
                if current in special_prefixes and i < len(split_parts) - 1:
                    # Merge prefix with next part: "Mc" + "Knight" -> "McKnight"
                    merged.append(current + split_parts[i+1])
                    i += 2
                else:
                    merged.append(current)
                    i += 1
            parts = merged
        elif len(split_parts) == 1:
            # If we only got one part, try to find lowercase-to-uppercase boundary
            # This handles "rodericTaylor" -> ["roderic", "Taylor"] or "rodericMcKnight" -> ["roderic", "McKnight"]
            match = re.match(r'^([a-z]+)([A-Z].*)', parts[0])
            if match:
                first = match.group(1)
                rest = match.group(2)
                # Try to split the rest part
                rest_parts = re.findall(r'[A-Z][^A-Z]*', rest)
                if len(rest_parts) >= 2:
                    # Merge prefixes in rest_parts
                    special_prefixes = ['Mc', 'Mac', 'O\'', 'De', 'Van', 'Von', 'La', 'Le', 'St', 'Saint']
                    merged_rest = []
                    i = 0
                    while i < len(rest_parts):
                        if rest_parts[i] in special_prefixes and i < len(rest_parts) - 1:
                            merged_rest.append(rest_parts[i] + rest_parts[i+1])
                            i += 2
                        else:
                            merged_rest.append(rest_parts[i])
                            i += 1
                    parts = [first] + merged_rest
                else:
                    parts = [first, rest]
    
    # Filter out very short parts (single letters, empty strings) and normalize
    # Keep single letters only if they're part of initials (like "N" in "Christopher N Bradley")
    filtered_parts = []
    for i, p in enumerate(parts):
        p_clean = p.lower().strip().replace('.', '')
        if len(p_clean) > 1:
            filtered_parts.append(p_clean)
        elif len(p_clean) == 1 and i > 0 and i < len(parts) - 1:
            # Single letter in the middle is likely a middle initial - skip it
            continue
        elif len(p_clean) == 1:
            # Single letter at start or end - might be valid, but skip for now
            continue
    
    return filtered_parts


def match_professor_name_strict(search_name: str, card_name: str) -> bool:
    """
    Strict name matching that requires both first AND last name to match.
    Handles middle names/initials and concatenated names gracefully.
    
    Examples:
    - "Clare Nguyen" matches "Clare M. Nguyen" ✓
    - "Clare Nguyen" matches "Clare Nguyen" ✓
    - "Roderic Taylor" matches "Roderic (Rick)Taylor" ✓
    - "Roderic Taylor" matches "RodericTaylor" ✓
    - "Christopher Bradley" matches "Christopher N.Bradley" ✓
    - "Christopher Bradley" matches "Christopher N Bradley" ✓
    - "Clare Nguyen" does NOT match "John Nguyen" ✗
    - "Clare Nguyen" does NOT match "Clare Smith" ✗
    """
    # Normalize both names (this will remove middle initials/names)
    search_parts = normalize_name(search_name)
    card_parts = normalize_name(card_name)
    
    # Need at least first and last name from search
    if len(search_parts) < 2:
        return False
    
    if len(card_parts) < 2:
        return False
    
    # Extract first and last from search name
    # normalize_name already filters out middle initials, so we get [first, last]
    search_first = search_parts[0]
    search_last = search_parts[-1]
    
    # Extract first and last from card name (middle initials already filtered out)
    card_first = card_parts[0]
    card_last = card_parts[-1]
    
    # Match first and last names
    first_matches = search_first == card_first
    last_matches = search_last == card_last
    
    if first_matches and last_matches:
        return True
    
    # Try "Last, First" format (reversed)
    if len(card_parts) >= 2:
        card_first_alt = card_parts[-1]
        card_last_alt = card_parts[0]
        if search_first == card_first_alt and search_last == card_last_alt:
            return True
    
    return False


# No longer needed - cloudscraper doesn't require browser processes


class DeAnzaScheduleScraper:
    """Scraper for De Anza College schedule listings."""
    
    BASE_URL = "https://www.deanza.edu/schedule/"
    LISTINGS_URL = "https://www.deanza.edu/schedule/listings.html"
    
    def __init__(self, headless: bool = True, max_retries: int = 3):
        """
        Initialize the scraper with cloudscraper (no browser needed!).
        
        Args:
            headless: Kept for compatibility, but not used (cloudscraper doesn't use a browser)
            max_retries: Maximum number of retry attempts if requests fail (default: 3)
        """
        # Create cloudscraper session (handles Cloudflare automatically)
        self.scraper = cloudscraper.create_scraper()
        self.max_retries = max_retries
        print("[SCRAPER] Initialized with cloudscraper (no browser required!)")
    
    def __del__(self):
        """Clean up resources when the object is destroyed."""
        # cloudscraper doesn't need cleanup, but keep for compatibility
        pass
    
    def close(self):
        """Manually close and clean up resources."""
        # cloudscraper doesn't need cleanup, but keep for compatibility
        if hasattr(self, 'scraper'):
            self.scraper = None
        print("[SCRAPER] Scraper closed")
    
    def get_listings(self, department: str, term: str = "W2026") -> BeautifulSoup:
        """
        Fetch the listings page for a specific department and term.
        
        Args:
            department: Department code (e.g., 'MATH')
            term: Term code (e.g., 'W2026' for Winter 2026)
        
        Returns:
            BeautifulSoup object of the parsed HTML
        """
        url = f"{self.LISTINGS_URL}?dept={department}&t={term}"
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Use cloudscraper to fetch the page (handles Cloudflare automatically)
                response = self.scraper.get(url, timeout=15)
                
                # Check response status
                if response.status_code != 200:
                    raise Exception(f"HTTP {response.status_code}: {response.reason}")
                
                # Verify we got actual content
                if not response.text or len(response.text) < 100:
                    raise Exception("Received empty or invalid page content")
                
                # Check if we're stuck on Cloudflare or error page
                page_lower = response.text.lower()
                if 'cloudflare' in page_lower and 'checking your browser' in page_lower:
                    raise Exception("Stuck on Cloudflare check page. Please try again.")
                if 'error' in page_lower and '403' in page_lower:
                    raise Exception("Access denied (403). The website may be blocking requests.")
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Verify we're on the right page (should have course listings)
                page_title = soup.find('title')
                if page_title and 'error' in page_title.get_text().lower():
                    raise Exception(f"Error page detected: {page_title.get_text()}")
                
                print(f"[SCRAPER] Successfully fetched listings (attempt {attempt + 1})")
                return soup
                
            except Exception as e:
                last_error = e
                print(f"[SCRAPER] Fetch attempt {attempt + 1} failed: {e}")
            
                # Wait before retrying (exponential backoff)
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"[SCRAPER] Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
        
        # If all retries failed, raise the last error
        raise Exception(f"Failed to fetch listings after {self.max_retries} attempts: {last_error}")
    
    def parse_course_info(self, soup: BeautifulSoup, course_code: str, save_html: bool = False) -> List[Dict]:
        """
        Parse course information from the HTML.
        
        Args:
            soup: BeautifulSoup object of the listings page
            course_code: Course code to filter (e.g., 'MATH 1A')
            save_html: Whether to save HTML for debugging (default: False)
        
        Returns:
            List of dictionaries containing course information
        """
        if save_html:
            with open('debug_page.html', 'w', encoding='utf-8') as f:
                f.write(str(soup))
            print("Saved HTML to debug_page.html for inspection.")
        
        courses = []
        
        # Debug: Check if page has content
        page_text = soup.get_text()
        if len(page_text) < 100:
            print(f"[PARSE] Warning: Page seems empty or invalid (length: {len(page_text)})")
        
        # Check if course code appears on page
        if course_code.upper() not in page_text.upper():
            print(f"[PARSE] Warning: Course code '{course_code}' not found in page text")
            # Save HTML for debugging
            try:
                with open(f'debug_no_course_{course_code.replace(" ", "_")}.html', 'w', encoding='utf-8') as f:
                    f.write(str(soup))
                print(f"[PARSE] Saved debug HTML to debug_no_course_{course_code.replace(' ', '_')}.html")
            except:
                pass
        
        # Find all course rows - typically in a table
        tables = soup.find_all('table')
        print(f"[PARSE] Found {len(tables)} table(s)")
        
        if not tables:
            # Try to find course listings in other structures
            course_sections = soup.find_all(['div', 'tr'], class_=re.compile(r'course|section|listing', re.I))
            print(f"[PARSE] Found {len(course_sections)} course sections")
            
            if not course_sections:
                # Try to find any table rows
                course_sections = soup.find_all('tr')
                print(f"[PARSE] Found {len(course_sections)} table rows")
        
        # If we found tables, look for rows within them
        if tables:
            for table in tables:
                rows = table.find_all('tr')
                print(f"[PARSE] Processing table with {len(rows)} rows")
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) > 0:
                        # Extract text from all cells
                        row_text = ' '.join([cell.get_text(strip=True) for cell in cells])
                        
                        # Check if this row contains the course code
                        if course_code.upper() in row_text.upper():
                            course_info = self._extract_course_from_row(row, course_code, cells)
                            if course_info:
                                courses.append(course_info)
                                print(f"[PARSE] Found course: {course_info.get('crn')} - {course_info.get('professor')}")
        else:
            # Fallback: search for course code in the entire page
            if course_code.upper() in page_text.upper():
                # Try to find the course in various HTML structures
                course_elements = soup.find_all(string=re.compile(course_code, re.I))
                print(f"[PARSE] Found {len(course_elements)} elements containing course code")
                for element in course_elements:
                    parent = element.find_parent(['tr', 'div', 'li'])
                    if parent:
                        course_info = self._extract_course_from_element(parent, course_code)
                        if course_info:
                            courses.append(course_info)
        
        # Remove duplicates based on CRN
        seen_crns = set()
        unique_courses = []
        for course in courses:
            if course['crn'] not in seen_crns or course['crn'] == 'N/A':
                seen_crns.add(course['crn'])
                unique_courses.append(course)
        
        print(f"[PARSE] Returning {len(unique_courses)} unique courses")
        return unique_courses
    
    def _extract_course_from_row(self, row, course_code: str, cells=None) -> Dict:
        """Extract course information from a table row in a single pass for efficiency."""
        if cells is None:
            cells = row.find_all(['td', 'th'])
        
        # Pre-extract all cell texts once
        cell_texts = [cell.get_text(strip=True) for cell in cells]
        row_text_lower = ' '.join(cell_texts).lower()  # Compute once
        
        # Initialize variables
        crn = None
        professor = None
        class_time = None
        days = None
        is_online = None
        time_str = None
        
        # Single pass through cells to extract all information
        day_map = {'M': 'M', 'T': 'T', 'W': 'W', 'R': 'R', 'F': 'F', 'S': 'S', 'U': 'U'}
        
        for i, cell in enumerate(cells):
            text = cell.get_text(strip=True)
            text_upper = text.upper()
            
            # Extract CRN (usually first column)
            if not crn:
                crn_match = CRN_PATTERN.search(text)
                if crn_match:
                    crn = crn_match.group(1)
            
            # Extract days (in span with class "days")
            if not days:
                days_span = cell.find('span', class_='days')
                if days_span:
                    days_text = days_span.get_text(strip=True).replace('·', '')
                    if days_text:
                        days = ''.join([letter for letter in days_text if letter in day_map])
                        if len(days) > 1:
                            days = ' '.join(days)
            
            # Extract time
            if not time_str:
                time_match = TIME_PATTERN.search(text)
                if time_match:
                    time_str = text.strip()
                elif 'TBA' in text_upper:
                    time_str = 'TBA'
            
            # Extract professor (usually in an <a> tag)
            if not professor:
                prof_link = cell.find('a', href=re.compile(r'/directory/user'))
                if prof_link:
                    professor = prof_link.get_text(strip=True)
                elif text and crn and crn not in text and course_code.upper() not in text_upper:
                    # Try name patterns
                    if NAME_PATTERN_LAST_FIRST.match(text) or \
                       NAME_PATTERN_FIRST_LAST.match(text) or \
                       NAME_PATTERN_FIRST_M_LAST.match(text):
                        professor = text
                    elif 2 <= len(text.split()) <= 4:
                        words = text.split()
                        if all(word and word[0].isupper() for word in words):
                            text_lower = text.lower()
                            if not any(term in text_lower for term in EXCLUDE_TERMS) and not re.search(r'\d', text):
                                professor = text
        
        # Combine days and time
        if time_str:
            if days:
                class_time = f"{days} {time_str}"
            else:
                class_time = time_str
        
        # Determine online/in-person status (check once)
        hybrid_span = row.find('span', class_=re.compile(r'skittle.*hybrid', re.I))
        if hybrid_span or 'hybrid' in row_text_lower:
            is_online = 'Hybrid'
        elif 'fully online' in row_text_lower or ('online class' in row_text_lower and 'hybrid' not in row_text_lower):
            is_online = 'Online'
        elif 'fully on-campus' in row_text_lower or 'on-campus' in row_text_lower:
            is_online = 'In-Person'
        elif 'online' in row_text_lower and 'hybrid' not in row_text_lower:
            is_online = 'Online'
        
        # Return if we found at least CRN
        if crn:
            return {
                'course': course_code,
                'crn': crn,
                'professor': professor or 'TBA',
                'class_time': class_time or 'TBA',
                'format': is_online or 'Unknown'
            }
        
        return None
    
    def _extract_course_from_element(self, element, course_code: str) -> Dict:
        """Extract course information from a generic HTML element."""
        text = element.get_text(separator=' ', strip=True)
        
        # Try to extract information using regex patterns
        crn_match = re.search(r'\b\d{5}\b', text)
        crn = crn_match.group() if crn_match else None
        
        # Look for professor name pattern
        professor_match = re.search(r'([A-Z][a-z]+,?\s+[A-Z][a-z]+)', text)
        professor = professor_match.group(1) if professor_match else None
        
        # Look for time pattern
        time_match = re.search(r'([MTWRF]+.*?\d{1,2}:\d{2}[AP]?M?.*?\d{1,2}:\d{2}[AP]?M?)', text)
        class_time = time_match.group(1) if time_match else None
        
        # Check for online/in-person
        is_online = None
        if re.search(r'\bonline\b', text, re.I):
            is_online = 'Online'
        elif re.search(r'\bhybrid\b', text, re.I):
            is_online = 'Hybrid'
        elif re.search(r'\bin-person\b|\bon-campus\b', text, re.I):
            is_online = 'In-Person'
        
        if crn or professor:
            return {
                'course': course_code,
                'crn': crn or 'N/A',
                'professor': professor or 'TBA',
                'class_time': class_time or 'TBA',
                'format': is_online or 'Unknown'
            }
        
        return None
    
    def search_course(self, department: str, course_code: str, term: str = "W2026") -> List[Dict]:
        """
        Search for a specific course in a department.
        
        Args:
            department: Department code (e.g., 'MATH')
            course_code: Course code (e.g., '1A')
            term: Term code (default: 'W2026')
        
        Returns:
            List of course information dictionaries
        """
        soup = self.get_listings(department, term)
        full_course_code = f"{department} {course_code}"
        return self.parse_course_info(soup, full_course_code, save_html=False)
    
    def get_professor_ratings(self, professor_name: str, school_id: str = "1967") -> Optional[Dict]:
        """
        Get professor ratings from RateMyProfessors.
        
        Args:
            professor_name: Name of the professor (e.g., "James Mailhot")
            school_id: School ID for De Anza College (default: "1967")
        
        Returns:
            Dictionary with rating, num_ratings, and difficulty, or None if not found
        """
        try:
            # URL encode the professor name
            encoded_name = quote(professor_name)
            url = f"https://www.ratemyprofessors.com/search/professors/{school_id}?q={encoded_name}"
            
            # Use cloudscraper to fetch the page (handles Cloudflare automatically)
            response = self.scraper.get(url, timeout=15)
            
            if response.status_code != 200:
                print(f"[RATINGS] HTTP {response.status_code} for {professor_name}")
                return None
            
            # Parse the page - could be search results or profile page
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # First, try to parse from search results page (TeacherCard)
            # Look for TeacherCard elements - try multiple selectors
            teacher_cards = soup.find_all('a', class_=re.compile(r'TeacherCard', re.I))
            
            # Also try finding by href pattern
            if not teacher_cards:
                teacher_cards = soup.find_all('a', href=re.compile(r'/professor/', re.I))
            
            rating = None
            num_ratings = None
            difficulty = None
            
            # Try to find matching professor in search results using strict matching
            matching_card = None
            
            print(f"[RATINGS] Searching for professor: {professor_name}")
            
            if not teacher_cards:
                print(f"[RATINGS] ⚠ No teacher cards found on search results page for '{professor_name}'")
                return None
            
            # Try to find matching professor in search results using improved matching
            for card in teacher_cards:
                # Get professor name from card - try multiple selectors
                name_elem = card.find('div', class_=re.compile(r'CardName', re.I))
                if not name_elem:
                    # Try alternative selectors
                    name_elem = card.find('div', string=re.compile(r'[A-Z]', re.I))
                
                if name_elem:
                    card_name = name_elem.get_text(strip=True)
                    
                    # Use improved matching that handles concatenated names
                    if match_professor_name_strict(professor_name, card_name):
                        matching_card = card
                        print(f"[RATINGS] ✓ Matched: '{professor_name}' with '{card_name}'")
                        break
            
            # If no exact match found, return None (don't use first result)
            if not matching_card:
                # Log what we found for debugging
                found_names = []
                for card in teacher_cards[:3]:  # Check first 3 cards
                    name_elem = card.find('div', class_=re.compile(r'CardName', re.I))
                    if name_elem:
                        found_names.append(name_elem.get_text(strip=True))
                
                if found_names:
                    print(f"[RATINGS] ✗ No exact match found for '{professor_name}'. Found: {', '.join(found_names)}")
                else:
                    print(f"[RATINGS] ✗ No exact match found for '{professor_name}' (could not extract names from cards)")
                return None
            
            card_to_parse = matching_card
            
            # Extract professor URL from the card (it's an <a> tag)
            professor_url = None
            if card_to_parse and card_to_parse.name == 'a' and card_to_parse.get('href'):
                href = card_to_parse.get('href')
                if href.startswith('/professor/'):
                    professor_url = f"https://www.ratemyprofessors.com{href}"
                elif href.startswith('http'):
                    professor_url = href
            
            if card_to_parse:
                # Extract rating from CardNumRatingNumber
                rating_elem = card_to_parse.find('div', class_=re.compile(r'CardNumRating__CardNumRatingNumber', re.I))
                if rating_elem:
                    rating_text = rating_elem.get_text(strip=True)
                    try:
                        rating = float(rating_text)
                    except ValueError:
                        pass
                
                # Extract number of ratings from CardNumRatingCount
                count_elem = card_to_parse.find('div', class_=re.compile(r'CardNumRating__CardNumRatingCount', re.I))
                if count_elem:
                    count_text = count_elem.get_text(strip=True)
                    num_match = re.search(r'(\d+)', count_text)
                    if num_match:
                        num_ratings = int(num_match.group(1))
                
                # Extract difficulty from CardFeedback
                # Look for "level of difficulty" text and get the number before it
                feedback_items = card_to_parse.find_all('div', class_=re.compile(r'CardFeedback__CardFeedbackItem', re.I))
                for item in feedback_items:
                    item_text = item.get_text().lower()
                    if 'difficulty' in item_text:
                        difficulty_elem = item.find('div', class_=re.compile(r'CardFeedback__CardFeedbackNumber', re.I))
                        if difficulty_elem:
                            difficulty_text = difficulty_elem.get_text(strip=True)
                            try:
                                difficulty = float(difficulty_text)
                                break
                            except ValueError:
                                pass
                
                # Alternative: look for all CardFeedbackNumber and get the one with difficulty context
                if difficulty is None:
                    all_feedback_numbers = card_to_parse.find_all('div', class_=re.compile(r'CardFeedback__CardFeedbackNumber', re.I))
                    # Usually difficulty is the second feedback item
                    if len(all_feedback_numbers) >= 2:
                        # Check parent/sibling for "difficulty" text
                        for num_elem in all_feedback_numbers:
                            parent = num_elem.find_parent()
                            if parent:
                                parent_text = parent.get_text().lower()
                                if 'difficulty' in parent_text:
                                    try:
                                        difficulty = float(num_elem.get_text(strip=True))
                                        break
                                    except ValueError:
                                        pass
            
            # If we didn't find data in search results, try profile page format
            if rating is None:
                # Look for the rating value on profile page
                # Class: "RatingValue__Numerator-qw8sqy-2 duhvlP" (dynamic suffix)
                rating_elem = soup.find('div', class_=re.compile(r'RatingValue__Numerator', re.I))
                if rating_elem:
                    rating_text = rating_elem.get_text(strip=True)
                    try:
                        rating = float(rating_text)
                    except ValueError:
                        pass
            
            if num_ratings is None:
                # Look for number of ratings on profile page
                # <a href="#ratingsList">65&nbsp;ratings</a>
                ratings_link = soup.find('a', href='#ratingsList')
                if ratings_link:
                    ratings_text = ratings_link.get_text(strip=True)
                    num_match = re.search(r'(\d+)', ratings_text)
                    if num_match:
                        num_ratings = int(num_match.group(1))
            
            if difficulty is None:
                # Look for difficulty on profile page
                # Class: "FeedbackItem__FeedbackNumber-uof32n-1 ecFgca" (dynamic suffix)
                feedback_items = soup.find_all('div', class_=re.compile(r'FeedbackItem', re.I))
                
                for item in feedback_items:
                    item_text = item.get_text().lower()
                    if 'difficulty' in item_text:
                        difficulty_elem = item.find('div', class_=re.compile(r'FeedbackItem__FeedbackNumber', re.I))
                        if difficulty_elem:
                            difficulty_text = difficulty_elem.get_text(strip=True)
                            try:
                                difficulty = float(difficulty_text)
                                break
                            except ValueError:
                                pass
                
                # Alternative: Look for all FeedbackNumber divs
                if difficulty is None:
                    feedback_numbers = soup.find_all('div', class_=re.compile(r'FeedbackItem__FeedbackNumber', re.I))
                    if len(feedback_numbers) >= 2:
                        try:
                            difficulty = float(feedback_numbers[1].get_text(strip=True))
                        except (ValueError, IndexError):
                            pass
            
            if rating is not None or num_ratings is not None or difficulty is not None:
                return {
                    'rating': rating,
                    'num_ratings': num_ratings,
                    'difficulty': difficulty,
                    'url': professor_url  # Add professor profile URL
                }
            
            return None
            
        except Exception as e:
            # Silently fail - don't print error for each professor
            return None


def parse_course_input(course_input: str) -> tuple:
    """
    Parse course input from user.
    
    Args:
        course_input: Course input in format like "MATH 1A" or "PHYS 4B"
    
    Returns:
        Tuple of (department, course_code) or (None, None) if invalid
    """
    course_input = course_input.strip().upper()
    
    # Split by space to get department and course code
    parts = course_input.split()
    
    if len(parts) < 2:
        return None, None
    
    # Department is the first part, course code is the rest
    department = parts[0]
    course_code = ' '.join(parts[1:])
    
    return department, course_code


def get_user_input() -> tuple:
    """
    Get course and term input from user.
    
    Returns:
        Tuple of (department, course_code, term)
    """
    print("="*60)
    print("De Anza College Schedule Scraper")
    print("="*60 + "\n")
    
    # Get course input
    while True:
        course_input = input("What classes are you considering? Please type in the exact format (e.g., 'PHYS 4B' or 'MATH 1A'): ").strip()
        
        if not course_input:
            print("Please enter a course (e.g., 'MATH 1A' or 'PHYS 4B').\n")
            continue
        
        department, course_code = parse_course_input(course_input)
        
        if not department or not course_code:
            print(f"Invalid format. Please use format like 'MATH 1A' or 'PHYS 4B'.\n")
            continue
        
        print(f"Course: {department} {course_code}")
        break
    
    # Get term input
    print("\nTerm format examples:")
    print("  - W2026 (Winter 2026)")
    print("  - S2026 (Spring 2026)")
    print("  - F2026 (Fall 2026)")
    print("  - SU2026 (Summer 2026)")
    
    while True:
        term = input("\nWhich quarter/term? (e.g., W2026): ").strip().upper()
        
        if not term:
            print("Please enter a term (e.g., 'W2026').\n")
            continue
        
        # Basic validation: should start with letter(s) and have 4 digits
        if not re.match(r'^[A-Z]+\d{4}$', term):
            print(f"Invalid term format. Please use format like 'W2026' (letter(s) followed by 4 digits).\n")
            continue
        
        print(f"Term: {term}")
        break
    
    return department, course_code, term


def main():
    """Interactive scraper for De Anza schedule."""
    scraper = None

    loop = True
    while loop:
        try:
            # Get user input
            department, course_code, term = get_user_input()
            
            print("\n" + "="*60)
            print(f"Searching for {department} {course_code} courses for {term}...")
            print("="*60 + "\n")
            
            scraper = DeAnzaScheduleScraper(headless=True)
            
            print("Accessing De Anza schedule website...")
            print(f"URL: {scraper.LISTINGS_URL}?dept={department}&t={term}\n")
            
            courses = scraper.search_course(department, course_code, term)
            
            if courses:
                print(f"Found {len(courses)} section(s) for {department} {course_code}:\n")
                
                # Collect unique professor names
                professors = []
                professor_set = set()
                for course in courses:
                    prof_name = course.get('professor', 'TBA')
                    if prof_name != 'TBA' and prof_name not in professor_set:
                        professors.append(prof_name)
                        professor_set.add(prof_name)
                
                print(f"Found {len(professors)} unique professor(s). Fetching ratings from RateMyProfessors...\n")
                
                # Get ratings for each professor
                professor_ratings = {}
                for i, prof_name in enumerate(professors, 1):
                    print(f"  [{i}/{len(professors)}] Fetching ratings for {prof_name}...", end=' ', flush=True)
                    ratings = scraper.get_professor_ratings(prof_name)
                    if ratings:
                        professor_ratings[prof_name] = ratings
                        print("✓")
                    else:
                        print("✗ (not found)")
                
                print("\n" + "="*60)
                print("Course Sections with Professor Ratings (Sorted by Rating):")
                print("="*60 + "\n")
                
                # Add ratings to each course and prepare for sorting
                for course in courses:
                    prof_name = course.get('professor', 'TBA')
                    if prof_name in professor_ratings:
                        course['ratings'] = professor_ratings[prof_name]
                        # Add rating value for sorting (use 0 if None)
                        course['sort_rating'] = professor_ratings[prof_name].get('rating') if professor_ratings[prof_name].get('rating') is not None else 0.0
                    else:
                        course['ratings'] = None
                        course['sort_rating'] = 0.0  # Put courses without ratings at the end
                
                # Sort courses by rating (highest to lowest)
                # Courses without ratings go to the end
                courses_sorted = sorted(courses, key=lambda x: (
                    x['sort_rating'] == 0.0,  # False (0) comes before True (1), so ratings come first
                    -x['sort_rating']  # Negative for descending order (highest first)
                ))
                
                # Display courses with ratings (sorted)
                for i, course in enumerate(courses_sorted, 1):
                    print(f"Section {i}:")
                    print(f"  CRN: {course['crn']}")
                    print(f"  Professor: {course['professor']}")
                    
                    # Display ratings if available
                    if course.get('ratings'):
                        ratings = course['ratings']
                        if ratings.get('rating') is not None:
                            print(f"  Rating: {ratings['rating']}/5.0", end='')
                            if ratings.get('num_ratings'):
                                print(f" ({ratings['num_ratings']} ratings)", end='')
                            print()
                        if ratings.get('difficulty') is not None:
                            print(f"  Difficulty: {ratings['difficulty']}/5.0")
                    
                    print(f"  Class Time: {course['class_time']}")
                    print(f"  Format: {course['format']}")
                    print()
            else:
                print(f"No courses found for {department} {course_code} in {term}.")
                print("\nPossible reasons:")
                print("  - The course may not be offered in this term")
                print("  - The course code or department may be incorrect")
                print("  - The term code may be invalid")
                print("\nPlease verify the course and term on the De Anza website.")
                
        except KeyboardInterrupt:
            print("\n\nScraping cancelled by user.")
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if scraper:
                scraper.close()

        if input("Do you want to search for another course? (y/n): ").strip().lower() == 'n':
            loop = False
            break
        loop = True



if __name__ == "__main__":
    main()
