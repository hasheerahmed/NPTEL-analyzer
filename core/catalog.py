import json
import os
from datetime import datetime
from rapidfuzz import fuzz


class CatalogManager:
    """
    Handles all interactions with course_catalog.json
    """

    def __init__(self, catalog_path="data/course_catalog.json"):

        self.catalog_path = catalog_path

        self.metadata = {}

        self.courses = []

        self.load()

    # ----------------------------------------------------------

    def load(self):

        if not os.path.exists(self.catalog_path):
            raise FileNotFoundError(
                f"Catalog not found : {self.catalog_path}"
            )

        with open(self.catalog_path, "r", encoding="utf-8") as f:

            data = json.load(f)

        self.metadata = data.get("metadata", {})

        self.courses = data.get("courses", [])

    # ----------------------------------------------------------

    def save(self):

        data = {
            "metadata": self.metadata,
            "courses": self.courses
        }

        with open(self.catalog_path, "w", encoding="utf-8") as f:

            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False
            )

    # ----------------------------------------------------------

    def total_courses(self):

        return len(self.courses)

    # ----------------------------------------------------------

    def get_metadata(self):

        return self.metadata

    # ----------------------------------------------------------

    def get_course(self, course_id):
        """
        Universal Key Search: Search by exact Course ID (e.g., 105105157)
        """
        for course in self.courses:

            if str(course.get("course_id", "")) == str(course_id):

                return course

        return None

    # ----------------------------------------------------------

    def get_by_course_code(self, course_code):
        """
        Search by Course Code against the newly mapped historical list.
        (e.g., noc26-cs70, noc25-cs38)
        """
        search_code = str(course_code).lower().strip()
        
        for course in self.courses:
            
            # Retrieve the list of all historical codes for this ID
            codes = course.get("course_codes", [])
            
            # Check if the user's input matches ANY code in the course's history
            for code in codes:
                if str(code).lower().strip() == search_code:
                    return course

        return None

    # ----------------------------------------------------------

    def search_by_title(self, query, top_n=10):
        """
        Search by Course Title using RapidFuzz
        """
        query = query.lower().strip()

        results = []

        for course in self.courses:

            title = course.get("normalized_title", "")

            score = fuzz.WRatio(query, title)

            if query == title:
                score += 50

            elif query in title:
                score += 25

            if "(in hindi)" in title and "hindi" not in query:
                score -= 20

            if "(in english)" in title:
                score += 5

            item = course.copy()

            item["score"] = round(score, 2)

            results.append(item)

        results.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        return results[:top_n]

    # ----------------------------------------------------------

    def search(self, query, top_n=10):
        """
        Maintained for backward compatibility. 
        Routes to search_by_title.
        """
        return self.search_by_title(query, top_n)

    # ----------------------------------------------------------

    def last_updated(self):

        return self.metadata.get(
            "last_updated",
            "Unknown"
        )

    # ----------------------------------------------------------

    def days_old(self):

        if "last_updated" not in self.metadata:
            return None

        dt = datetime.fromisoformat(
            self.metadata["last_updated"]
        )

        return (datetime.now() - dt).days