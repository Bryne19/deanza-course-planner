"""
Data models and utility functions for course scheduling
"""

import json
import os
import re
import sqlite3
import html
from datetime import datetime
from typing import List, Dict, Optional

# Day mapping
DAY_MAP = {
    'M': 'Monday',
    'T': 'Tuesday', 
    'W': 'Wednesday',
    'R': 'Thursday',
    'F': 'Friday',
    'S': 'Saturday',
    'U': 'Sunday'
}


def parse_class_time(class_time_str: str) -> Optional[Dict]:
    """
    Parse class time string into structured data.
    
    Example: "M W 08:30 AM-10:45 AM" -> {
        'days': ['M', 'W'],
        'day_names': ['Monday', 'Wednesday'],
        'start_time': '08:30 AM',
        'end_time': '10:45 AM',
        'start_minutes': 510,
        'end_minutes': 645,
        'duration_minutes': 135
    }
    """
    if not class_time_str or class_time_str == 'TBA':
        return None
    
    # Extract days (letters before time)
    days_match = re.match(r'^([MTWRFSU\s]+)', class_time_str)
    if not days_match:
        return None
    
    days = [d for d in days_match.group(1).strip() if d in DAY_MAP.keys()]
    if not days:
        return None
    
    # Extract time range
    time_match = re.search(r'(\d{1,2}:\d{2}\s*[AP]M)\s*-\s*(\d{1,2}:\d{2}\s*[AP]M)', class_time_str, re.I)
    if not time_match:
        return None
    
    start_str = time_match.group(1).strip()
    end_str = time_match.group(2).strip()
    
    try:
        # Convert to 24-hour format and minutes
        start_dt = datetime.strptime(start_str, '%I:%M %p')
        end_dt = datetime.strptime(end_str, '%I:%M %p')
        
        start_minutes = start_dt.hour * 60 + start_dt.minute
        end_minutes = end_dt.hour * 60 + end_dt.minute
        
        return {
            'days': days,
            'day_names': [DAY_MAP[d] for d in days],
            'start_time': start_str,
            'end_time': end_str,
            'start_minutes': start_minutes,
            'end_minutes': end_minutes,
            'duration_minutes': end_minutes - start_minutes
        }
    except ValueError:
        return None


def detect_conflicts(courses: List[Dict]) -> List[Dict]:
    """
    Detect time conflicts between courses.
    
    Returns list of conflict dictionaries with course pairs and conflicting days.
    """
    conflicts = []
    
    for i, course1 in enumerate(courses):
        if not course1.get('time_data'):
            continue
            
        for j, course2 in enumerate(courses[i+1:], i+1):
            if not course2.get('time_data'):
                continue
            
            time1 = course1['time_data']
            time2 = course2['time_data']
            
            # Check if they share any days
            shared_days = set(time1['days']) & set(time2['days'])
            
            if shared_days:
                # Check if time ranges overlap
                if (time1['start_minutes'] < time2['end_minutes'] and 
                    time1['end_minutes'] > time2['start_minutes']):
                    conflicts.append({
                        'course1': {
                            'crn': course1.get('crn'),
                            'course': course1.get('course'),
                            'professor': course1.get('professor')
                        },
                        'course2': {
                            'crn': course2.get('crn'),
                            'course': course2.get('course'),
                            'professor': course2.get('professor')
                        },
                        'conflicting_days': list(shared_days),
                        'time1': f"{time1['start_time']} - {time1['end_time']}",
                        'time2': f"{time2['start_time']} - {time2['end_time']}"
                    })
    
    return conflicts


class CourseManager:
    """Manages course data persistence"""
    
    def __init__(self, data_file='data/selected_courses.json'):
        # Get the directory where this file is located
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_file = os.path.join(base_dir, data_file)
        self.ensure_data_dir()
    
    def ensure_data_dir(self):
        """Ensure data directory exists"""
        data_dir = os.path.dirname(self.data_file)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)
    
    def load_courses(self) -> List[Dict]:
        """Load courses from JSON file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    return data.get('courses', [])
            except (json.JSONDecodeError, IOError):
                return []
        return []
    
    def save_courses(self, courses: List[Dict]):
        """Save courses to JSON file"""
        data = {
            'last_updated': datetime.now().isoformat(),
            'courses': courses
        }
        try:
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Error saving courses: {e}")
    
    def get_courses(self) -> List[Dict]:
        """Get all courses"""
        return self.load_courses()
    
    def add_course(self, course: Dict):
        """Add a course to the schedule"""
        courses = self.load_courses()
        
        # Check if course already exists (by CRN)
        crn = course.get('crn')
        if crn:
            courses = [c for c in courses if c.get('crn') != crn]
        
        courses.append(course)
        self.save_courses(courses)
    
    def remove_course(self, crn: str):
        """Remove a course by CRN"""
        courses = self.load_courses()
        courses = [c for c in courses if c.get('crn') != crn]
        self.save_courses(courses)
    
    def clear_courses(self):
        """Clear all courses"""
        self.save_courses([])


class PlannedClassesDB:
    """Manages planned classes in SQLite database"""
    
    def __init__(self, db_file='data/planned_classes.db'):
        # Get the directory where this file is located
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_file = os.path.join(base_dir, db_file)
        self.ensure_data_dir()
        self.init_db()
    
    def ensure_data_dir(self):
        """Ensure data directory exists"""
        data_dir = os.path.dirname(self.db_file)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)
    
    def init_db(self):
        """Initialize the database with planned_classes table"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS planned_classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name TEXT NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    
    def _validate_class_name(self, class_name: str) -> str:
        """Validate and sanitize class name"""
        # Remove leading/trailing whitespace
        class_name = class_name.strip()
        # Limit length
        if len(class_name) > 100:
            raise ValueError("Class name must be 100 characters or less")
        # Allow alphanumeric, spaces, hyphens, and common course code characters
        if not re.match(r'^[A-Z0-9\s\-\.]+$', class_name, re.IGNORECASE):
            raise ValueError("Class name contains invalid characters. Only letters, numbers, spaces, hyphens, and periods are allowed.")
        return class_name
    
    def _sanitize_notes(self, notes: str) -> str:
        """Sanitize notes field"""
        # Remove leading/trailing whitespace
        notes = notes.strip()
        # Limit length
        if len(notes) > 500:
            raise ValueError("Notes must be 500 characters or less")
        return notes
    
    def add_class(self, class_name: str, notes: str = "") -> int:
        """Add a planned class to the database"""
        # Validate and sanitize input
        class_name = self._validate_class_name(class_name)
        notes = self._sanitize_notes(notes)
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO planned_classes (class_name, notes, created_at, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (class_name, notes))
        class_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return class_id
    
    def get_all_classes(self) -> List[Dict]:
        """Get all planned classes"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, class_name, notes, created_at, updated_at
            FROM planned_classes
            ORDER BY created_at DESC
        ''')
        rows = cursor.fetchall()
        conn.close()
        # Escape HTML in returned data to prevent XSS
        result = []
        for row in rows:
            row_dict = dict(row)
            # Escape HTML entities for safe display
            row_dict['class_name'] = html.escape(row_dict['class_name'])
            row_dict['notes'] = html.escape(row_dict['notes']) if row_dict['notes'] else ''
            result.append(row_dict)
        return result
    
    def delete_class(self, class_id: int) -> bool:
        """Delete a planned class by ID"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM planned_classes WHERE id = ?', (class_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted
    
    def update_class(self, class_id: int, class_name: str, notes: str = "") -> bool:
        """Update a planned class"""
        # Validate and sanitize input
        class_name = self._validate_class_name(class_name)
        notes = self._sanitize_notes(notes)
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE planned_classes
            SET class_name = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (class_name, notes, class_id))
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated
    
    def clear_all(self):
        """Clear all planned classes"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM planned_classes')
        conn.commit()
        conn.close()

