#!/usr/bin/env python3
"""
Flask Web Application for De Anza College Course Scheduler
"""

from flask import Flask, render_template, request, jsonify
import json
import os
from datetime import datetime
from models import parse_class_time, detect_conflicts, CourseManager, PlannedClassesDB
from scraper_module import DeAnzaScheduleScraper

app = Flask(__name__)
# Use environment variable for secret key, fallback to a default for development
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-key-change-in-production-' + os.urandom(16).hex())

# Initialize course manager
course_manager = CourseManager()

# Initialize planned classes database
planned_classes_db = PlannedClassesDB()

# Initialize scraper (will be created on first use)
scraper = None

def get_scraper():
    """Get or create scraper instance"""
    global scraper
    if scraper is None:
        scraper = DeAnzaScheduleScraper(headless=True)
    # cloudscraper doesn't need validation - it's stateless
    return scraper

def reset_scraper():
    """Force reset the scraper instance"""
    global scraper
    try:
        if scraper:
            scraper.close()
    except:
        pass
    scraper = None


@app.route('/')
def index():
    """Main page - course search"""
    return render_template('index.html')


@app.route('/schedule')
def schedule():
    """Schedule view page"""
    return render_template('schedule.html')


@app.route('/api/search', methods=['POST'])
def search_course():
    """Search for courses"""
    try:
        data = request.json
        department = data.get('department', '').strip().upper()
        course_code = data.get('course_code', '').strip().upper()
        term = data.get('term', '').strip().upper()
        
        if not department or not course_code or not term:
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Create a fresh scraper for each search to avoid state issues
        # This is more reliable than reusing the same instance
        scraper_instance = None
        courses = []
        
        try:
            print(f"\n[SEARCH] Starting search for {department} {course_code} {term}")
            scraper_instance = DeAnzaScheduleScraper(headless=True)
            courses = scraper_instance.search_course(department, course_code, term)
            print(f"[SEARCH] Found {len(courses) if courses else 0} courses")
        except Exception as scrape_error:
            # Log the error
            error_msg = str(scrape_error)
            print(f"[SEARCH ERROR] {error_msg}")
            import traceback
            traceback.print_exc()
            
            # Clean up failed scraper
            try:
                if scraper_instance:
                    scraper_instance.close()
            except:
                pass
            
            # Wait a bit before retrying to let processes clean up
            import time
            time.sleep(3)
            
            # Try once more with a fresh scraper
            try:
                print(f"[SEARCH] Retrying search for {department} {course_code} {term}")
                scraper_instance = DeAnzaScheduleScraper(headless=True)
                courses = scraper_instance.search_course(department, course_code, term)
                print(f"[SEARCH] Retry found {len(courses) if courses else 0} courses")
            except Exception as retry_error:
                print(f"[SEARCH ERROR] Retry failed: {retry_error}")
                try:
                    if scraper_instance:
                        scraper_instance.close()
                except:
                    pass
                return jsonify({
                    'error': f'Scraper error: {str(retry_error)}',
                    'message': 'Failed to fetch courses. Please try again.',
                    'course_name': f"{department} {course_code}",
                    'term': term
                }), 500
        if not courses:
            print(f"[SEARCH] No courses found for {department} {course_code} {term}")
            return jsonify({
                'courses': [], 
                'message': 'No courses found',
                'course_name': f"{department} {course_code}",
                'term': term
            })
        
        # Collect unique professor names
        professors = []
        professor_set = set()
        for course in courses:
            prof_name = course.get('professor', 'TBA')
            if prof_name != 'TBA' and prof_name not in professor_set:
                professors.append(prof_name)
                professor_set.add(prof_name)
        
        # Fetch ratings for professors (before closing scraper)
        professor_ratings = {}
        if professors and scraper_instance:
            print(f"[RATINGS] Fetching ratings for {len(professors)} professors...")
            for i, prof_name in enumerate(professors, 1):
                try:
                    print(f"[RATINGS] [{i}/{len(professors)}] Fetching {prof_name}...", end=' ', flush=True)
                    ratings = scraper_instance.get_professor_ratings(prof_name)
                    if ratings:
                        professor_ratings[prof_name] = ratings
                        print(f"✓ {ratings.get('rating', 'N/A')}/5.0")
                    else:
                        print("✗")
                except Exception as e:
                    print(f"✗ (error: {e})")
            print(f"[RATINGS] Fetched ratings for {len(professor_ratings)}/{len(professors)} professors")
        
        # Add ratings to courses
        for course in courses:
            prof_name = course.get('professor', 'TBA')
            if prof_name in professor_ratings:
                course['ratings'] = professor_ratings[prof_name]
                course['sort_rating'] = professor_ratings[prof_name].get('rating', 0.0)
            else:
                course['ratings'] = None
                course['sort_rating'] = 0.0
        
        # Sort by rating
        courses_sorted = sorted(courses, key=lambda x: (
            x['sort_rating'] == 0.0,
            -x['sort_rating']
        ))
        
        # Parse time data for each course
        for course in courses_sorted:
            time_data = parse_class_time(course.get('class_time', ''))
            if time_data:
                course['time_data'] = time_data
        
        # Clean up scraper AFTER fetching ratings
        try:
            if scraper_instance:
                scraper_instance.close()
        except Exception as e:
            print(f"[SEARCH] Error closing scraper: {e}")
        
        return jsonify({
            'courses': courses_sorted,
            'term': term,
            'course_name': f"{department} {course_code}"
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/courses', methods=['GET'])
def get_courses():
    """Get all selected courses"""
    courses = course_manager.get_courses()
    return jsonify({'courses': courses})


@app.route('/api/courses', methods=['POST'])
def add_course():
    """Add a course to the schedule"""
    try:
        data = request.json
        course = data.get('course')
        
        if not course:
            return jsonify({'error': 'No course data provided'}), 400
        
        # Normalize course code to uppercase
        if 'course' in course:
            course['course'] = course['course'].upper()
        
        # Parse time data
        time_data = parse_class_time(course.get('class_time', ''))
        if time_data:
            course['time_data'] = time_data
        
        # Add course
        course_manager.add_course(course)
        
        # Check for conflicts
        all_courses = course_manager.get_courses()
        conflicts = detect_conflicts(all_courses)
        
        return jsonify({
            'success': True,
            'conflicts': conflicts,
            'message': 'Course added successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/courses/<crn>', methods=['DELETE'])
def remove_course(crn):
    """Remove a course from the schedule"""
    try:
        course_manager.remove_course(crn)
        
        # Recheck conflicts after removal
        all_courses = course_manager.get_courses()
        conflicts = detect_conflicts(all_courses)
        
        return jsonify({
            'success': True,
            'conflicts': conflicts,
            'message': 'Course removed successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/schedule', methods=['GET'])
def get_schedule():
    """Get schedule with conflict detection"""
    courses = course_manager.get_courses()
    conflicts = detect_conflicts(courses)
    
    return jsonify({
        'courses': courses,
        'conflicts': conflicts
    })


@app.route('/api/clear', methods=['POST'])
def clear_schedule():
    """Clear all courses from schedule"""
    course_manager.clear_courses()
    return jsonify({'success': True, 'message': 'Schedule cleared'})


@app.route('/api/planned-classes', methods=['GET'])
def get_planned_classes():
    """Get all planned classes"""
    classes = planned_classes_db.get_all_classes()
    return jsonify({'classes': classes})


@app.route('/api/planned-classes', methods=['POST'])
def add_planned_class():
    """Add a planned class"""
    data = request.get_json()
    class_name = data.get('class_name', '').strip()
    
    if not class_name:
        return jsonify({'error': 'Class name is required'}), 400
    
    notes = data.get('notes', '').strip()
    class_id = planned_classes_db.add_class(class_name, notes)
    return jsonify({'success': True, 'id': class_id, 'message': 'Class added successfully'})


@app.route('/api/planned-classes/<int:class_id>', methods=['DELETE'])
def delete_planned_class(class_id):
    """Delete a planned class"""
    deleted = planned_classes_db.delete_class(class_id)
    if deleted:
        return jsonify({'success': True, 'message': 'Class deleted successfully'})
    else:
        return jsonify({'error': 'Class not found'}), 404


@app.route('/api/planned-classes/<int:class_id>', methods=['PUT'])
def update_planned_class(class_id):
    """Update a planned class"""
    data = request.get_json()
    class_name = data.get('class_name', '').strip()
    notes = data.get('notes', '').strip()
    
    if not class_name:
        return jsonify({'error': 'Class name is required'}), 400
    
    updated = planned_classes_db.update_class(class_id, class_name, notes)
    if updated:
        return jsonify({'success': True, 'message': 'Class updated successfully'})
    else:
        return jsonify({'error': 'Class not found'}), 404


@app.route('/api/planned-classes/clear', methods=['POST'])
def clear_planned_classes():
    """Clear all planned classes"""
    planned_classes_db.clear_all()
    return jsonify({'success': True, 'message': 'All planned classes cleared'})


if __name__ == '__main__':
    import sys
    # Try to use port 5001, fallback to 5000 if unavailable
    port = 5000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    
    try:
        app.run(debug=True, host='0.0.0.0', port=port)
    except OSError as e:
        if 'Address already in use' in str(e):
            print(f"\n⚠️  Port {port} is already in use.")
            print(f"   Try running: python app.py {port + 1}")
            print(f"   Or kill the process using port {port}\n")
            sys.exit(1)
        else:
            raise

