// JavaScript for schedule visualization

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
const DAY_ABBREV = ['M', 'T', 'W', 'R', 'F'];
const TIME_SLOTS = [];
const COLORS = [
    'course-color-0', 'course-color-1', 'course-color-2', 'course-color-3', 'course-color-4',
    'course-color-5', 'course-color-6', 'course-color-7', 'course-color-8', 'course-color-9'
];

// Generate time slots (7:00 AM to 10:00 PM, 30-minute intervals)
for (let hour = 7; hour <= 22; hour++) {
    for (let minute = 0; minute < 60; minute += 30) {
        const timeStr = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
        TIME_SLOTS.push({
            time: timeStr,
            minutes: hour * 60 + minute
        });
    }
}

let courses = [];
let conflicts = [];
let courseColors = {};

document.addEventListener('DOMContentLoaded', function() {
    loadSchedule();
    
    // Refresh schedule when page becomes visible (user returns from search page)
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            loadSchedule();
        }
    });
    
    // Also refresh on focus
    window.addEventListener('focus', function() {
        loadSchedule();
    });
    
    document.getElementById('clearSchedule').addEventListener('click', function() {
        if (confirm('Are you sure you want to clear all courses from your schedule?')) {
            clearSchedule();
        }
    });
});

async function loadSchedule() {
    try {
        const response = await fetch('/api/schedule');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        courses = data.courses || [];
        conflicts = data.conflicts || [];
        
        console.log('Loaded courses:', courses.length);
        console.log('Loaded conflicts:', conflicts.length);
        
        updateSchedule();
        updateCourseList();
        updateConflicts();
    } catch (err) {
        console.error('Error loading schedule:', err);
        alert('Error loading schedule: ' + err.message);
    }
}

function updateSchedule() {
    const scheduleGrid = document.getElementById('scheduleGrid');
    const emptySchedule = document.getElementById('emptySchedule');
    const scheduleContainer = document.getElementById('scheduleContainer');
    
    if (courses.length === 0) {
        scheduleGrid.innerHTML = '';
        emptySchedule.classList.remove('hidden');
        scheduleContainer.classList.add('hidden');
        document.getElementById('courseCount').textContent = '0 courses';
        return;
    }
    
    emptySchedule.classList.add('hidden');
    scheduleContainer.classList.remove('hidden');
    
    // Build grid
    let html = '<div class="schedule-header">Time</div>';
    
    // Day headers
    DAYS.forEach(day => {
        html += `<div class="schedule-header">${day}</div>`;
    });
    
    // Time slots and cells
    TIME_SLOTS.forEach(slot => {
        html += `<div class="schedule-time">${formatTime(slot.time)}</div>`;
        DAYS.forEach(day => {
            html += `<div class="schedule-cell" data-day="${day}" data-time="${slot.minutes}"></div>`;
        });
    });
    
    scheduleGrid.innerHTML = html;
    
    // Assign colors to courses
    assignColors();
    
    // Place courses on schedule
    courses.forEach((course, index) => {
        if (course.time_data) {
            placeCourse(course, index);
        }
    });
    
    document.getElementById('courseCount').textContent = `${courses.length} course${courses.length !== 1 ? 's' : ''}`;
}

function assignColors() {
    courseColors = {};
    courses.forEach((course, index) => {
        if (course.crn) {
            courseColors[course.crn] = COLORS[index % COLORS.length];
        }
    });
}

function placeCourse(course, index) {
    const timeData = course.time_data;
    if (!timeData) {
        console.warn('No time_data for course:', course);
        return;
    }
    
    const startMinutes = timeData.start_minutes;
    const endMinutes = timeData.end_minutes;
    const duration = endMinutes - startMinutes;
    
    if (duration <= 0) {
        console.warn('Invalid duration for course:', course);
        return;
    }
    
    // Find starting row - find the slot that's closest but not after start time
    let startRow = -1;
    for (let i = 0; i < TIME_SLOTS.length; i++) {
        if (TIME_SLOTS[i].minutes >= startMinutes) {
            startRow = i;
            break;
        }
    }
    
    if (startRow === -1) {
        console.warn('Could not find start row for course:', course);
        return;
    }
    
    // Calculate number of rows to span
    const rowSpan = Math.ceil(duration / 30);
    
    // Handle both day abbreviations and full names
    const courseDays = timeData.days || timeData.day_names || [];
    
    courseDays.forEach(day => {
        // Convert day abbreviation to full name if needed
        let dayName = day;
        if (day.length === 1) {
            const dayMap = {'M': 'Monday', 'T': 'Tuesday', 'W': 'Wednesday', 'R': 'Thursday', 'F': 'Friday', 'S': 'Saturday', 'U': 'Sunday'};
            dayName = dayMap[day] || day;
        }
        
        if (!DAYS.includes(dayName)) {
            // Skip weekends or invalid days
            return;
        }
        
        const cell = document.querySelector(
            `[data-day="${dayName}"][data-time="${TIME_SLOTS[startRow].minutes}"]`
        );
        
        if (cell) {
            // Check if cell already has a course block (conflict)
            const existingBlock = cell.querySelector('.course-block');
            if (existingBlock) {
                console.warn('Cell already occupied:', dayName, TIME_SLOTS[startRow].minutes);
            }
            
            const courseBlock = document.createElement('div');
            courseBlock.className = `course-block ${courseColors[course.crn] || COLORS[index % COLORS.length]}`;
            
            // Check if this course has conflicts
            const hasConflict = conflicts.some(conflict => {
                const conflictDays = conflict.conflicting_days || [];
                return (conflict.course1.crn === course.crn || conflict.course2.crn === course.crn) &&
                       conflictDays.some(cd => {
                           // Handle both abbreviations and full names
                           const conflictDay = cd.length === 1 ? 
                               {'M': 'Monday', 'T': 'Tuesday', 'W': 'Wednesday', 'R': 'Thursday', 'F': 'Friday'}[cd] : cd;
                           return conflictDay === dayName || conflictDay === day;
                       });
            });
            
            if (hasConflict) {
                courseBlock.classList.add('conflict');
            }
            
            courseBlock.style.position = 'absolute';
            courseBlock.style.top = '2px';
            courseBlock.style.left = '2px';
            courseBlock.style.right = '2px';
            courseBlock.style.height = `${rowSpan * 60 - 4}px`;
            courseBlock.style.zIndex = hasConflict ? '10' : '1';
            
            courseBlock.innerHTML = `
                <div class="course-block-title">${course.course || 'Unknown'}</div>
                <div class="course-block-time">${timeData.start_time || ''} - ${timeData.end_time || ''}</div>
                <div class="course-block-prof">${course.professor || 'TBA'}</div>
            `;
            
            courseBlock.title = `${course.course || 'Unknown'} - ${course.professor || 'TBA'}\n${timeData.start_time || ''} - ${timeData.end_time || ''}`;
            
            cell.style.position = 'relative';
            cell.appendChild(courseBlock);
        } else {
            console.warn('Could not find cell for:', dayName, TIME_SLOTS[startRow].minutes);
        }
    });
}

function formatTime(timeStr) {
    const [hours, minutes] = timeStr.split(':');
    const hour = parseInt(hours);
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour > 12 ? hour - 12 : (hour === 0 ? 12 : hour);
    return `${displayHour}:${minutes} ${ampm}`;
}

function updateCourseList() {
    const coursesList = document.getElementById('coursesList');
    coursesList.innerHTML = '';
    
    if (courses.length === 0) {
        coursesList.innerHTML = '<p>No courses added yet.</p>';
        return;
    }
    
    courses.forEach((course, index) => {
        const item = document.createElement('div');
        // Get the color class for this course (same as used in schedule)
        const colorClass = courseColors[course.crn] || COLORS[index % COLORS.length];
        item.className = `selected-course-item ${colorClass}`;
        
        const hasConflict = conflicts.some(conflict => 
            conflict.course1.crn === course.crn || conflict.course2.crn === course.crn
        );
        
        const rating = course.ratings?.rating;
        const difficulty = course.ratings?.difficulty;
        const numRatings = course.ratings?.num_ratings;
        
        item.innerHTML = `
            <div class="selected-course-info">
                <strong>${course.course} - CRN: ${course.crn} ${hasConflict ? '⚠️' : ''}</strong>
                <span>Professor: ${course.professor}</span>
                <span>Time: ${course.class_time}</span>
                <span>Format: ${course.format}</span>
                ${rating ? `
                <div class="schedule-rating">
                    <strong>⭐ Rating:</strong> ${rating.toFixed(1)}/5.0${numRatings ? ` (${numRatings} ratings)` : ''}
                    ${difficulty ? ` | <strong>Difficulty:</strong> ${difficulty.toFixed(1)}/5.0` : ''}
                </div>
                ` : '<span class="no-rating">⭐ Rating: Not available</span>'}
            </div>
            <button class="btn btn-remove" onclick="removeCourse('${course.crn}')">Remove</button>
        `;
        
        coursesList.appendChild(item);
    });
}

function updateConflicts() {
    const conflictsSection = document.getElementById('conflicts');
    const conflictsList = document.getElementById('conflictsList');
    
    if (conflicts.length === 0) {
        conflictsSection.classList.add('hidden');
        return;
    }
    
    conflictsSection.classList.remove('hidden');
    conflictsList.innerHTML = '';
    
    conflicts.forEach(conflict => {
        const item = document.createElement('div');
        item.className = 'conflict-item';
        item.innerHTML = `
            <strong>⚠️ Conflict Detected</strong>
            <p><strong>${conflict.course1.course}</strong> (${conflict.course1.professor}) - ${conflict.time1}</p>
            <p><strong>${conflict.course2.course}</strong> (${conflict.course2.professor}) - ${conflict.time2}</p>
            <p>Conflicting days: ${conflict.conflicting_days.join(', ')}</p>
        `;
        conflictsList.appendChild(item);
    });
}

async function removeCourse(crn) {
    if (!confirm('Remove this course from your schedule?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/courses/${crn}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            loadSchedule(); // Reload schedule
        } else {
            alert('Error: ' + (data.error || 'Failed to remove course'));
        }
    } catch (err) {
        alert('Network error: ' + err.message);
    }
}

async function clearSchedule() {
    try {
        const response = await fetch('/api/clear', {
            method: 'POST'
        });
        
        if (response.ok) {
            loadSchedule(); // Reload schedule
        } else {
            alert('Error clearing schedule');
        }
    } catch (err) {
        alert('Network error: ' + err.message);
    }
}

