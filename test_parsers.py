import os
from parsers.pdf_parser import NPTELPDFParser
from parsers.marksheet_parser import MarksheetParser
from core.comparator import CourseComparator

def run_full_test():
    # 1. Setup paths
    current_dir = os.getcwd()
    syllabus_folder = os.path.join(current_dir, "input", "syllabus")
    marksheet_folder = os.path.join(current_dir, "input", "marksheets")

    # 2. Initialize components
    syllabus_parser = NPTELPDFParser()
    marksheet_parser = MarksheetParser()
    comparator = CourseComparator()

    print(f"{'='*60}")
    print("STARTING ANALYSIS...")
    print(f"{'='*60}")

    # 3. Parse Syllabus (Planned Courses)
    pdf_files = [f for f in os.listdir(syllabus_folder) if f.endswith('.pdf')]
    if not pdf_files:
        print("ERROR: No syllabus PDF found in input/syllabus/")
        return
        
    planned_courses = syllabus_parser.parse_pdf(os.path.join(syllabus_folder, pdf_files[0]))

    # 4. Parse Marksheets (Past Subjects)
    past_subjects = []
    marksheet_files = [f for f in os.listdir(marksheet_folder) if f.endswith('.pdf')]
    
    for pdf in marksheet_files:
        # The new parser returns a raw list of subject strings
        subjects = marksheet_parser.parse_marksheet(os.path.join(marksheet_folder, pdf))
        past_subjects.extend(subjects)
    
    # Remove duplicates from past subjects
    past_subjects = list(set(past_subjects))

    # 5. Run Comparator (Logic: Check syllabus courses against past subject list)
    # threshold=90 ensures high accuracy
    final_list = comparator.flag_already_studied(planned_courses, past_subjects, threshold=90)

    print(f"\n{'='*60}")
    print(f"FINAL ANALYSIS REPORT")
    print(f"{'='*60}")
    
    if not final_list:
        print("No courses detected.")
    else:
        for course in final_list:
            # FORCE it to grab the 9-digit numeric ID, not the string code!
            course_id = course.get('course_id', 'N/A')
            
            if course.get("already_studied"):
                print(f"[!!! ALREADY STUDIED (RED) !!!] {course['title']} (ID: {course_id})")
            else:
                print(f"[NEW COURSE (WHITE)] {course['title']} (ID: {course_id})")

if __name__ == "__main__":
    run_full_test()