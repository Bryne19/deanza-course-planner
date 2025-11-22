// Main JavaScript for course search page

document.addEventListener('DOMContentLoaded', function() {
    const searchForm = document.getElementById('searchForm');
    const loading = document.getElementById('loading');
    const results = document.getElementById('results');
    const error = document.getElementById('error');
    const coursesList = document.getElementById('coursesList');
    const resultsTitle = document.getElementById('resultsTitle');

    searchForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // Hide previous results and errors
        results.classList.add('hidden');
        error.classList.add('hidden');
        loading.classList.remove('hidden');
        
        // Hide professor chart when starting new search
        const chartCtx = document.getElementById('professorChart');
        if (chartCtx) {
            chartCtx.style.display = 'none';
        }
        if (professorChart) {
            professorChart.destroy();
            professorChart = null;
        }
        
        const department = document.getElementById('department').value.trim().toUpperCase();
        const course_code = document.getElementById('course_code').value.trim();
        const term = document.getElementById('term').value.trim().toUpperCase();
        
        try {
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    department: department,
                    course_code: course_code,
                    term: term
                })
            });
            
            const data = await response.json();
            
            console.log('Search response:', data); // Debug log
            
            if (response.ok) {
                if (data.error) {
                    showError(data.error);
                } else if (data.courses && data.courses.length > 0) {
                    displayResults(data);
                } else {
                    // No courses found - show message
                    const courseName = (data.course_name || 'your search').toUpperCase();
                    resultsTitle.textContent = `No courses found for ${courseName}${data.term ? ` (${data.term})` : ''}`;
                    coursesList.innerHTML = '<p>No courses found. Please check your search terms and try again.</p>';
                    results.classList.remove('hidden');
                    
                    // Hide chart when no courses found
                    const chartCtx = document.getElementById('professorChart');
                    if (chartCtx) {
                        chartCtx.style.display = 'none';
                    }
                    if (professorChart) {
                        professorChart.destroy();
                        professorChart = null;
                    }
                }
            } else {
                showError(data.error || data.message || 'An error occurred while searching for courses');
            }
        } catch (err) {
            console.error('Search error:', err);
            showError('Network error: ' + (err.message || 'Unknown error'));
        } finally {
            loading.classList.add('hidden');
        }
    });
    
    function displayResults(data) {
        // Safely handle course_name and convert to uppercase
        const courseName = (data.course_name || 'Courses').toUpperCase();
        const term = data.term || '';
        resultsTitle.innerHTML = `Results for ${courseName}${term ? ` (${term})` : ''} <span class="sort-indicator">(sorted by rating)</span>`;
        coursesList.innerHTML = '';
        
        if (!data.courses || data.courses.length === 0) {
            coursesList.innerHTML = '<p>No courses found.</p>';
            results.classList.remove('hidden');
            return;
        }
        
        data.courses.forEach((course, index) => {
            const card = createCourseCard(course, index);
            coursesList.appendChild(card);
        });
        
        results.classList.remove('hidden');
        
        // Update professor chart with search results
        updateProfessorChart(data.courses || []);
    }
    
    function createCourseCard(course, index) {
        const card = document.createElement('div');
        card.className = 'course-card';
        
        const rating = course.ratings?.rating;
        const difficulty = course.ratings?.difficulty;
        const numRatings = course.ratings?.num_ratings;
        const professorUrl = course.ratings?.url;
        
        let ratingClass = '';
        if (rating) {
            if (rating >= 4.0) ratingClass = 'high';
            else if (rating >= 3.0) ratingClass = 'medium';
            else ratingClass = 'low';
        }
        
        // Build professor name with optional link
        let professorDisplay = course.professor;
        if (professorUrl) {
            professorDisplay = `${course.professor} <a href="${professorUrl}" target="_blank" class="professor-link">(View on RateMyProfessors)</a>`;
        }
        
        card.innerHTML = `
            <h4>${course.course} - Section ${course.crn}</h4>
            <div class="course-info">
                <div class="course-info-item">
                    <strong>Professor:</strong>
                    <span>${professorDisplay}</span>
                </div>
                <div class="course-info-item">
                    <strong>Time:</strong>
                    <span>${course.class_time}</span>
                </div>
                <div class="course-info-item">
                    <strong>Format:</strong>
                    <span>${course.format}</span>
                </div>
            </div>
            ${rating ? `
            <div class="ratings-section">
                <div class="rating-display">
                    <strong>⭐ RateMyProfessors Rating:</strong>
                    <span class="rating ${ratingClass}">${rating.toFixed(1)}/5.0${numRatings ? ` (${numRatings} ratings)` : ''}</span>
                </div>
                ${difficulty ? `
                <div class="difficulty-display">
                    <strong>📊 Difficulty:</strong>
                    <span class="difficulty">${difficulty.toFixed(1)}/5.0</span>
                </div>
                ` : ''}
            </div>
            ` : `
            <div class="ratings-section">
                <span class="no-rating">⭐ Rating: Not available on RateMyProfessors</span>
            </div>
            `}
            <button class="btn btn-success" onclick="addCourse(${index})">Add to Schedule</button>
        `;
        
        // Store course data for addCourse function
        card.dataset.courseData = JSON.stringify(course);
        
        return card;
    }
    
    function showError(message) {
        error.textContent = message;
        error.classList.remove('hidden');
    }
    
    function updateProfessorChart(courses) {
        const ctx = document.getElementById('professorChart');
        if (!ctx) return;
        
        const professorData = {};
        
        courses.forEach(course => {
            const profName = (course.professor || "").trim();
            
            // Skip TBA or empty names
            if (!profName || profName.toUpperCase() === 'TBA') {
                return;
            }
            
            // FIXED: always initialize a professor, even if no ratings yet
            if (!professorData[profName]) {
                professorData[profName] = {
                    rating: course.ratings?.rating ?? null,
                    difficulty: course.ratings?.difficulty ?? null,
                    numRatings: course.ratings?.num_ratings ?? null
                };
            } else {
                // FIXED: use explicit null check, not falsy check
                const existing = professorData[profName];
                const newRatings = course.ratings;
                if (
                    existing.rating === null && 
                    newRatings?.rating !== null && 
                    newRatings?.rating !== undefined
                ) {
                    existing.rating = newRatings.rating;
                    existing.difficulty = newRatings.difficulty ?? existing.difficulty;
                    existing.numRatings = newRatings.num_ratings ?? existing.numRatings;
                }
            }
        });
        
        const professors = Object.keys(professorData);
        
        console.log(`[CHART] Collected ${professors.length} professors:`, professors);
        console.log(`[CHART] Total courses processed: ${courses.length}`);
        
        if (professors.length === 0) {
            ctx.style.display = 'none';
            if (professorChart) {
                professorChart.destroy();
                professorChart = null;
            }
            return;
        }
        
        ctx.style.display = 'block';
        
        // Create labels with number of ratings beside professor names
        const labelsWithRatings = professors.map(prof => {
            const numRatings = professorData[prof].numRatings;
            if (numRatings !== null && numRatings !== undefined && numRatings > 0) {
                return `${prof} (${numRatings} ratings)`;
            }
            return prof;
        });
        
        const ratings = professors.map(prof => professorData[prof].rating ?? 0);
        const difficulties = professors.map(prof => professorData[prof].difficulty ?? 0);
        
        // Color functions: rating (higher is better), difficulty (lower is better)
        // Use grey for missing data (null/0)
        const getRatingColor = (rating) => {
            if (!rating || rating === 0) return 'rgba(128, 128, 128, 0.5)'; // Grey for no data
            if (rating >= 4.0) return 'rgba(76, 175, 80, 0.8)';   // Green (good)
            if (rating >= 3.0) return 'rgba(255, 193, 7, 0.8)';   // Yellow (medium)
            return 'rgba(244, 67, 54, 0.8)';                      // Red (bad)
        };
        
        const getDifficultyColor = (difficulty) => {
            if (!difficulty || difficulty === 0) return 'rgba(128, 128, 128, 0.5)'; // Grey for no data
            if (difficulty <= 2.0) return 'rgba(76, 175, 80, 0.8)';   // Green (good - low difficulty)
            if (difficulty <= 3.5) return 'rgba(255, 193, 7, 0.8)';  // Yellow (medium)
            return 'rgba(244, 67, 54, 0.8)';                          // Red (bad - high difficulty)
        };
        
        const ratingColors = ratings.map(r => getRatingColor(r));
        const difficultyColors = difficulties.map(d => getDifficultyColor(d));
        
        // Destroy existing chart if it exists
        if (professorChart) {
            professorChart.destroy();
        }
        
        // Create horizontal bar chart
        professorChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labelsWithRatings,
                datasets: [
                    {
                        label: 'Top: Rating',
                        data: ratings,
                        backgroundColor: ratingColors,
                        borderColor: ratingColors.map(c => {
                            // Increase opacity for border: 0.8 -> 1.0, 0.5 -> 0.7
                            if (c.includes('0.8')) return c.replace('0.8', '1');
                            if (c.includes('0.5')) return c.replace('0.5', '0.7');
                            return c;
                        }),
                        borderWidth: 1,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Bottom: Difficulty',
                        data: difficulties,
                        backgroundColor: difficultyColors,
                        borderColor: difficultyColors.map(c => {
                            // Increase opacity for border: 0.8 -> 1.0, 0.5 -> 0.7
                            if (c.includes('0.8')) return c.replace('0.8', '1');
                            if (c.includes('0.5')) return c.replace('0.5', '0.7');
                            return c;
                        }),
                        borderWidth: 1,
                        yAxisID: 'y'
                    }
                ]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: {
                        left: 10,
                        right: 10,
                        top: 10,
                        bottom: 10
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        labels: {
                            color: '#FFFFFF',
                            boxWidth: 0,
                            padding: 15
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.dataset.label || '';
                                const value = context.parsed.x;
                                if (label.includes('Rating')) {
                                    if (value === 0) {
                                        return 'Rating: Not available';
                                    }
                                    return `Rating: ${value.toFixed(1)}/5.0`;
                                } else if (label.includes('Difficulty')) {
                                    if (value === 0) {
                                        return 'Difficulty: Not available';
                                    }
                                    return `Difficulty: ${value.toFixed(1)}/5.0`;
                                }
                                return `${label}: ${value}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        // Remove max limit to allow bars to extend as needed
                        ticks: {
                            color: '#D4D4D4',
                            stepSize: 0.5
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        }
                    },
                    y: {
                        ticks: {
                            color: '#D4D4D4',
                            font: { size: 12 },
                            maxRotation: 0,
                            minRotation: 0
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)',
                            display: false
                        }
                    }
                }
            }
        });
    }
});

// Global function to add course to schedule
async function addCourse(index) {
    const cards = document.querySelectorAll('.course-card');
    const card = cards[index];
    const courseData = JSON.parse(card.dataset.courseData);
    
    try {
        const response = await fetch('/api/courses', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                course: courseData
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            const conflictMsg = data.conflicts && data.conflicts.length > 0 
                ? `\n\n⚠️ Warning: ${data.conflicts.length} conflict(s) detected.` 
                : '';
            if (confirm('Course added to schedule!' + conflictMsg + '\n\nWould you like to view your schedule?')) {
                window.location.href = '/schedule';
            }
        } else {
            alert('Error: ' + (data.error || data.message || 'Failed to add course'));
        }
    } catch (err) {
        alert('Network error: ' + err.message);
    }
}

// Global variables
let professorChart = null;

// Planned Classes functionality
document.addEventListener('DOMContentLoaded', function() {
    const plannedClassForm = document.getElementById('plannedClassForm');
    const plannedClassesList = document.getElementById('plannedClassesList');
    
    // Load selected courses and chart on page load
    loadSelectedCourses();
    loadPlannedClasses();
    
    if (plannedClassForm) {
        // Handle form submission
        plannedClassForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const class_name = document.getElementById('planned_class_name').value.trim().toUpperCase();
            const notes = document.getElementById('planned_class_notes').value.trim();
            
            if (!class_name) {
                alert('Please enter a class name');
                return;
            }
            
            try {
                const response = await fetch('/api/planned-classes', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        class_name: class_name,
                        notes: notes
                    })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    // Clear form
                    plannedClassForm.reset();
                    // Reload list
                    loadPlannedClasses();
                } else {
                    alert('Error: ' + (data.error || 'Failed to add class'));
                }
            } catch (err) {
                alert('Network error: ' + err.message);
            }
        });
    }
    
    // Refresh selected courses when page becomes visible
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            loadSelectedCourses();
        }
    });
    
    window.addEventListener('focus', function() {
        loadSelectedCourses();
    });
    
    async function loadPlannedClasses() {
        if (!plannedClassesList) return;
        
        try {
            const response = await fetch('/api/planned-classes');
            const data = await response.json();
            
            if (response.ok) {
                displayPlannedClasses(data.classes || []);
            } else {
                plannedClassesList.innerHTML = '<p class="error">Error loading planned classes</p>';
            }
        } catch (err) {
            plannedClassesList.innerHTML = '<p class="error">Network error loading planned classes</p>';
        }
    }
    
    function displayPlannedClasses(classes) {
        if (!plannedClassesList) return;
        
        if (classes.length === 0) {
            plannedClassesList.innerHTML = '<p class="no-classes">No planned classes yet. Add one above!</p>';
            return;
        }
        
        let html = '<div class="planned-classes-grid">';
        classes.forEach(classItem => {
            const createdDate = new Date(classItem.created_at).toLocaleDateString();
            html += `
                <div class="planned-class-item">
                    <div class="planned-class-header">
                        <h4>${classItem.class_name}</h4>
                        <button class="btn btn-small btn-danger" onclick="deletePlannedClass(${classItem.id})">Delete</button>
                    </div>
                    ${classItem.notes ? `<p class="planned-class-notes">${classItem.notes}</p>` : ''}
                    <p class="planned-class-date">Added: ${createdDate}</p>
                </div>
            `;
        });
        html += '</div>';
        plannedClassesList.innerHTML = html;
    }
    
    // Make functions global
    window.deletePlannedClass = async function(classId) {
        if (!confirm('Are you sure you want to delete this planned class?')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/planned-classes/${classId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (response.ok) {
                loadPlannedClasses();
            } else {
                alert('Error: ' + (data.error || 'Failed to delete class'));
            }
        } catch (err) {
            alert('Network error: ' + err.message);
        }
    };
    
    // Load selected courses from schedule
    async function loadSelectedCourses() {
        const selectedCoursesList = document.getElementById('selectedCoursesList');
        if (!selectedCoursesList) return;
        
        try {
            const response = await fetch('/api/courses');
            const data = await response.json();
            
            if (response.ok) {
                displaySelectedCourses(data.courses || []);
            } else {
                selectedCoursesList.innerHTML = '<p class="error">Error loading courses</p>';
            }
        } catch (err) {
            selectedCoursesList.innerHTML = '<p class="error">Network error loading courses</p>';
        }
    }
    
    function displaySelectedCourses(courses) {
        const selectedCoursesList = document.getElementById('selectedCoursesList');
        if (!selectedCoursesList) return;
        
        if (courses.length === 0) {
            selectedCoursesList.innerHTML = '<p class="no-courses">No courses added to schedule yet.</p>';
            return;
        }
        
        let html = '';
        courses.forEach(course => {
            const rating = course.ratings?.rating;
            const numRatings = course.ratings?.num_ratings;
            html += `
                <div class="selected-course-card">
                    <h4>${course.course} - CRN: ${course.crn}</h4>
                    <div class="course-details">
                        <p><span class="label">Professor:</span> ${course.professor}</p>
                        <p><span class="label">Time:</span> ${course.class_time}</p>
                        <p><span class="label">Format:</span> ${course.format}</p>
                        ${rating ? `<p><span class="label">Rating:</span> ${rating.toFixed(1)}/5.0${numRatings ? ` (${numRatings} ratings)` : ''}</p>` : ''}
                    </div>
                    <button class="btn btn-small btn-danger" onclick="removeCourseFromSchedule('${course.crn}')">Remove</button>
                </div>
            `;
        });
        selectedCoursesList.innerHTML = html;
    }
    
    // Make function global
    window.removeCourseFromSchedule = async function(crn) {
        if (!confirm('Remove this course from your schedule?')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/courses/${crn}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (response.ok) {
                loadSelectedCourses();
                // Show success message
                alert('Course removed from schedule');
            } else {
                alert('Error: ' + (data.error || 'Failed to remove course'));
            }
        } catch (err) {
            alert('Network error: ' + err.message);
        }
    };
});

