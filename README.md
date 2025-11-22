# De Anza Course Scheduler - Web Application

A Flask-based web application for searching De Anza College courses, viewing professor ratings, and building a conflict-free weekly schedule.

## Features

- 🔍 **Course Search**: Search for courses by department, course code, and term
- ⭐ **Professor Ratings**: Automatically fetch ratings from RateMyProfessors
- 📅 **Schedule Visualization**: Interactive weekly schedule grid
- ⚠️ **Conflict Detection**: Automatically detect and highlight time conflicts
- 💾 **Data Persistence**: Save your selected courses locally

## Installation

1. Install dependencies:
```bash
cd web_app
pip install -r ../requirements.txt
```

2. Ensure you have Chrome browser installed (for Selenium)

## Running the Application

**Option 1: Use the run script (recommended - handles port conflicts):**
```bash
cd web_app
python run.py
```

**Option 2: Run app.py directly:**
```bash
cd web_app
python app.py
# Or specify a port: python app.py 5002
```

Then open your browser and navigate to: `http://localhost:5001` (or the port shown in the terminal)

**Note:** If you get a "Port already in use" error, the run script will automatically find a free port, or you can specify a different port as an argument.

## Project Structure

```
web_app/
├── app.py                 # Flask main application
├── models.py              # Data models and conflict detection
├── scraper_module.py     # Course scraper (from parent directory)
├── templates/
│   ├── index.html        # Course search page
│   └── schedule.html     # Schedule view page
├── static/
│   ├── css/
│   │   ├── style.css     # Main styles
│   │   └── schedule.css  # Schedule grid styles
│   └── js/
│       ├── main.js       # Search page JavaScript
│       └── schedule.js   # Schedule visualization JavaScript
└── data/
    └── selected_courses.json  # Stored courses (auto-created)
```

## API Endpoints

- `GET /` - Main search page
- `GET /schedule` - Schedule view page
- `POST /api/search` - Search for courses
- `GET /api/courses` - Get all selected courses
- `POST /api/courses` - Add a course to schedule
- `DELETE /api/courses/<crn>` - Remove a course
- `GET /api/schedule` - Get schedule with conflicts
- `POST /api/clear` - Clear all courses

## Usage

1. **Search for Courses**: Enter department (e.g., MATH), course code (e.g., 1A), and term (e.g., W2026)
2. **View Results**: See all sections with professor ratings sorted by rating
3. **Add to Schedule**: Click "Add to Schedule" on any course
4. **View Schedule**: Navigate to "My Schedule" tab to see your weekly schedule
5. **Check Conflicts**: Conflicts are automatically detected and highlighted in red

## Data Storage

Selected courses are stored in `data/selected_courses.json`. This file is automatically created and updated when you add/remove courses.

## Notes

- The scraper uses Selenium with headless Chrome
- Professor ratings are fetched from RateMyProfessors
- Schedule conflicts are detected automatically
- The schedule grid shows Monday-Friday, 7:00 AM - 10:00 PM

## Troubleshooting

- **ChromeDriver issues**: Make sure Chrome is installed. The app uses webdriver-manager to auto-download ChromeDriver
- **Slow loading**: Professor rating fetching may take time. Be patient!
- **No courses found**: Verify the course code and term are correct

