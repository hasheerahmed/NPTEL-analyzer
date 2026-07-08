from rapidfuzz import fuzz

class CourseComparator:
    def flag_already_studied(self, planned_courses, past_subjects, threshold=90):
        for course in planned_courses:
            course["already_studied"] = False
            course["matched_past_subject"] = None
            
            nptel_title = course.get("normalized_title", "").lower()

            for past_sub in past_subjects:
                # token_sort_ratio ignores word order and small filler words
                score = fuzz.token_sort_ratio(nptel_title, past_sub.lower())
                
                if score >= threshold:
                    course["already_studied"] = True
                    course["matched_past_subject"] = past_sub
                    break 
        return planned_courses