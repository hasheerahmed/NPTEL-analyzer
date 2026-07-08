import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename

from parsers.pdf_parser import NPTELPDFParser
from parsers.marksheet_parser import MarksheetParser
from core.comparator import CourseComparator
from core.resolver import Resolver
from core.stats_analyzer import StatsAnalyzer

app = Flask(__name__)
app.secret_key = "nptel_analyzer_secret_key" 

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

# --- Helper Functions ---
def get_last_updated_date():
    catalog_path = os.path.join(os.getcwd(), 'data', 'course_catalog.json')
    if os.path.exists(catalog_path):
        timestamp = os.path.getmtime(catalog_path)
        return datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y')
    return "Unknown"

def is_file_too_large(file, max_mb=1):
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0, os.SEEK_SET)
    return file_size > (max_mb * 1024 * 1024)

# --- Routes ---
@app.route('/')
def index():
    last_updated = get_last_updated_date()
    return render_template('index.html', courses=None, last_updated=last_updated)

@app.route('/analyze', methods=['POST'])
def analyze():
    last_updated = get_last_updated_date()
    input_mode = request.form.get('input_mode', 'pdf')
    sort_easy = request.form.get('sort_easy') == 'on'
    
    syllabus_parser = NPTELPDFParser()
    marksheet_parser = MarksheetParser()
    comparator = CourseComparator()
    resolver = Resolver()
    analyzer = StatsAnalyzer()

    planned_courses = []
    saved_marksheet_paths = []

    try:
        # --- INPUT MODE: TEXT ---
        if input_mode == 'text':
            manual_input = request.form.get('manual_courses', '')
            keywords = [k.strip() for k in manual_input.split(',') if k.strip()]
            
            for kw in keywords:
                results = resolver.search(kw, top_n=1)
                if results and results[0].get("score", 0) >= 80:
                    match = results[0]
                    if not any(c.get("course_id") == match.get("course_id") for c in planned_courses):
                        match["is_nptel"] = True
                        planned_courses.append(match)
                else:
                    planned_courses.append({
                        "course_id": "N/A",
                        "title": kw,
                        "is_nptel": False,
                        "already_studied": False
                    })

        # --- INPUT MODE: PDF ---
        elif input_mode == 'pdf':
            if 'syllabus_pdf' not in request.files:
                flash("Please upload a Syllabus PDF.")
                return redirect(url_for('index'))
                
            syllabus_file = request.files['syllabus_pdf']
            if syllabus_file.filename == '':
                flash("No Syllabus file selected.")
                return redirect(url_for('index'))

            if is_file_too_large(syllabus_file, max_mb=1):
                flash("Syllabus PDF must be under 1MB.")
                return redirect(url_for('index'))

            syllabus_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(syllabus_file.filename))
            syllabus_file.save(syllabus_path)
            planned_courses = syllabus_parser.parse_pdf(syllabus_path)

        # --- COMMON LOGIC: MARKSHEETS ---
        marksheet_files = request.files.getlist('marksheet_pdf')
        marksheet_files = [f for f in marksheet_files if f.filename != '']

        if len(marksheet_files) > 15:
            flash("You can only upload a maximum of 15 marksheets.")
            return redirect(url_for('index'))

        for m_file in marksheet_files:
            if is_file_too_large(m_file, max_mb=1):
                flash(f"Marksheet '{m_file.filename}' exceeds the 1MB limit.")
                return redirect(url_for('index'))
            
            m_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(m_file.filename))
            m_file.save(m_path)
            saved_marksheet_paths.append(m_path)

        # 1. Parse past subjects
        past_subjects = []
        for m_path in saved_marksheet_paths:
            past_subjects.extend(marksheet_parser.parse_marksheet(m_path))
        past_subjects = list(set(past_subjects)) 

        # 2. Flag studied courses
        compared_list = comparator.flag_already_studied(planned_courses, past_subjects, threshold=90)

        # 3. Analyze Stats & Merge Flags
        final_list = []
        for course in compared_list:
            stats = analyzer.analyze(course)
            # Carry over UI flags so HTML knows how to color the rows
            stats['is_nptel'] = course.get('is_nptel', True)
            stats['already_studied'] = course.get('already_studied', False)
            final_list.append(stats)

        # 4. Sorting Logic
        if sort_easy:
            final_list.sort(key=lambda x: x.get('easy_to_score_ratio', 0), reverse=True)

    except Exception as e:
        print(f"Error during analysis: {e}")
        flash("An error occurred while processing the inputs.")
        final_list = []
    
    finally:
        # Cleanup PDF files
        if input_mode == 'pdf' and 'syllabus_path' in locals() and os.path.exists(syllabus_path):
            os.remove(syllabus_path)
        for m_path in saved_marksheet_paths:
            if os.path.exists(m_path):
                os.remove(m_path)

    return render_template('index.html', courses=final_list, last_updated=last_updated)

if __name__ == '__main__':
    app.run(debug=True, port=5000)