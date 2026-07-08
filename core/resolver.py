from core.catalog import CatalogManager

class Resolver:
    """
    Resolves user input into the best matching NPTEL course
    by automatically detecting if the input is a Course ID, 
    Course Code, or Course Title.
    """

    def __init__(self):
        self.catalog = CatalogManager()

    # ----------------------------------------------------------
    # Helper to clean up direct lookups
    def _direct_match(self, query_str):
        # 1. Check for Course ID
        if query_str.isdigit():
            course = self.catalog.get_course(query_str)
            if course:
                course["score"] = 100.0
                return course
        
        # 2. Check for Course Code
        if query_str.startswith("noc"):
            course = self.catalog.get_by_course_code(query_str)
            if course:
                course["score"] = 100.0
                return course
        return None

    # ----------------------------------------------------------

    def get_course(self, course_id):
        """
        Direct lookup for ID (Used by PDF parsers).
        """
        return self.catalog.get_course(course_id)

    # ----------------------------------------------------------

    def resolve(self, query):
        query_str = str(query).strip().lower()
        if not query_str: return None

        # Try ID/Code first
        match = self._direct_match(query_str)
        if match: return match

        # Default to Title Search
        results = self.catalog.search_by_title(query=query_str, top_n=1)
        return results[0] if results else None

    # ----------------------------------------------------------

    def resolve_many(self, queries):
        return [self.resolve(q) for q in queries if self.resolve(q) is not None]

    # ----------------------------------------------------------

    def search(self, query, top_n=10):
        query_str = str(query).strip().lower()
        if not query_str: return []

        match = self._direct_match(query_str)
        if match: return [match]

        # --- THE OVERRIDE DICTIONARY ---
        # Map problematic PDF strings directly to their correct NPTEL Course IDs
        manual_overrides = {
            "human computer interaction": "106106575",
            # Add future edge cases here as you find them!
            # "pdf subject name": "correct_course_id"
        }

        if query_str in manual_overrides:
            override_id = manual_overrides[query_str]
            course = self.get_course(override_id)
            if course:
                course["score"] = 100.0 # Force a perfect score
                return [course]

        # If no override, proceed with normal RapidFuzz title search
        return self.catalog.search_by_title(query=query_str, top_n=top_n)