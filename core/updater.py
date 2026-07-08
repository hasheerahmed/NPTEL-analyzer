import json
import os
import re
from datetime import datetime
import concurrent.futures

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup


class CatalogUpdater:

    URL = "https://nptel.ac.in/courses"
    DETAILS_API = "https://nptel.ac.in/api/subject-details/{}"
    STATS_API = "https://nptel.ac.in/api/stats/{}"
    COURSE_PAGE_URL = "https://nptel.ac.in/courses/{}"

    def __init__(self, output_path="data/course_catalog.json"):

        self.output_path = output_path
        
        # 1. Configure a robust session with browser spoofing
        self.session = requests.Session()
        
        # Spoof a modern Chrome browser so NPTEL doesn't block the requests
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": "https://nptel.ac.in/courses"
        })

        # 2. Keep the retry logic for pure network timeouts
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    # ----------------------------------------------------------

    def normalize_title(self, title):

        title = str(title).replace("NOC:", "")
        title = title.replace("-", " ")
        title = title.replace("(", " ")
        title = title.replace(")", " ")

        title = " ".join(title.lower().split())

        return title

    # ----------------------------------------------------------

    def extract_duration_weeks(self, page_html):
        """
        Derives course duration (in weeks) from the course page's
        embedded SvelteKit hydration data (view-source:https://nptel.ac.in/courses/{id}).

        Two different courses can format their week units differently
        (e.g. 'Week 1' vs 'week-01'), so this uses a two-tier approach:

        Tier 1 - Authoritative: when the page has syllabus data, it includes
        a `meta` array with an explicit entry like:
            {label:"Duration",value:"12 weeks"}
        This is the most reliable source when present.

        Tier 2 - Fallback: when `syllabus` is null (as seen on some courses),
        fall back to counting the `units` array, matching week names
        regardless of format - 'Week 1', 'week-01', 'Week_12', 'WEEK 3', etc.
        Non-week units like {id:13,name:"Live Session",...} are naturally
        excluded since they don't match the week-name pattern.

        This is more reliable than the /api/downloads/ assignments list,
        since assignments are only present once published, whereas every
        course page lists its full week structure regardless.
        """
        if not page_html:
            return 0

        # Tier 1: syllabus.meta Duration field, e.g. {label:"Duration",value:"12 weeks"}
        meta_match = re.search(
            r'label:"Duration",value:"\s*(\d+)\s*weeks?\s*"',
            page_html,
            re.IGNORECASE
        )
        if meta_match:
            return int(meta_match.group(1))

        # Tier 2: fall back to the units array, format-agnostic on separators
        unit_matches = re.findall(
            r'name:"week[\s\-_]?0*(\d+)"',
            page_html,
            re.IGNORECASE
        )
        if unit_matches:
            return max(int(m) for m in unit_matches)

        return 0

    # ----------------------------------------------------------

    def fetch_course_details(self, course_info):
        """
        Worker function designed to run in parallel. 
        It hits the Details and Stats APIs, plus the course page itself,
        for a single course: extracts metadata, compiles a list of all
        historical course codes, grabs analytics, and derives the course
        duration in weeks from the page's embedded unit structure.
        """
        course_id = course_info["course_id"]
        collected_codes = set()

        # 1. Fetch Subject Details (Metadata)
        try:
            details_url = self.DETAILS_API.format(course_id)
            details_response = self.session.get(details_url, timeout=10)
            
            if details_response.status_code == 200:
                payload = details_response.json()
                
                if "data" in payload and isinstance(payload["data"], dict):
                    data = payload["data"]
                    
                    current_code = str(data.get("courseid", "")).strip()
                    if current_code and current_code.lower() != "none":
                        collected_codes.add(current_code)
                    
                    if data.get("title"):
                        raw_title = data.get("title")
                        course_info["title"] = raw_title.replace("NOC:", "").strip()
                        course_info["normalized_title"] = self.normalize_title(raw_title)
                        
                    course_info["duration"] = data.get("duration", "")
                    course_info["registration"] = data.get("registration", "")
                    course_info["exam"] = data.get("exam", "")
                    
                    if data.get("professor"):
                        course_info["professor"] = data.get("professor")
                    if data.get("institutename"):
                        course_info["institute"] = data.get("institutename")

        except Exception:
            pass 

        # 2. Fetch Stats & Historical Course Codes
        try:
            stats_url = self.STATS_API.format(course_id)
            stats_response = self.session.get(stats_url, timeout=10)
            
            if stats_response.status_code == 200:
                payload = stats_response.json()
                
                if "data" in payload and isinstance(payload["data"], list) and len(payload["data"]) > 0:
                    stats_data = payload["data"][0]
                    
                    course_info["stats_status"] = True
                    
                    course_info["total_enrolled"] = stats_data.get("Enrolled", "0")
                    course_info["total_registered"] = stats_data.get("Registered", "0")
                    course_info["total_certified"] = stats_data.get("Certified", "0")
                    
                    run_wise = stats_data.get("run_wise_stats", [])
                    course_info["run_wise_stats"] = run_wise
                    
                    for run in run_wise:
                        historical_code = str(run.get("noc_courseid", "")).strip()
                        if historical_code and historical_code.lower() != "none":
                            collected_codes.add(historical_code)
                            
        except Exception:
            pass

        # 3. Fetch the course page itself (used solely to derive duration in weeks
        #    from the embedded `units` structure — works whether or not
        #    assignments have been published for the course)
        course_info["duration_weeks"] = 0
        try:
            page_url = self.COURSE_PAGE_URL.format(course_id)
            page_response = self.session.get(page_url, timeout=15)

            if page_response.status_code == 200:
                course_info["duration_weeks"] = self.extract_duration_weeks(page_response.text)

        except Exception:
            pass

        course_info["course_codes"] = list(collected_codes)

        return course_info

    # ----------------------------------------------------------

    def update(self):

        print("=" * 80)
        print("Downloading latest NPTEL catalog...")
        print("=" * 80)

        response = self.session.get(self.URL)

        if response.status_code != 200:
            raise Exception("Unable to download NPTEL catalog.")

        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.find_all("div", class_="course-card")

        base_courses = []

        for card in cards:
            link = card.find("a")
            if link is None:
                continue

            href = link.get("href", "")
            if "/courses/" not in href:
                continue

            course_id = href.split("/")[-1]
            title = ""
            discipline = ""
            professor = ""
            institute = ""

            name = card.find("div", class_="name")
            if name:
                title = name.get_text(strip=True)

            dep = card.find("div", class_="discipline")
            if dep:
                discipline = dep.get_text(strip=True)

            meta = card.find("div", class_="meta-data")
            if meta:
                spans = meta.find_all("span")
                if len(spans) >= 1:
                    professor = spans[0].get_text(" ", strip=True)
                if len(spans) >= 2:
                    institute = spans[1].get_text(" ", strip=True)

            base_courses.append({
                "course_id": course_id,
                "course_codes": [],
                "title": title.replace("NOC:", "").strip(),
                "normalized_title": self.normalize_title(title),
                "aliases": [],
                "discipline": discipline,
                "professor": professor,
                "institute": institute,
                "duration": "",
                "duration_weeks": 0,
                "registration": "",
                "exam": "",
                "url": f"https://nptel.ac.in/courses/{course_id}",
                "stats_status": False,
                "total_enrolled": "0",
                "total_registered": "0",
                "total_certified": "0",
                "run_wise_stats": []
            })

        total_courses = len(base_courses)
        print(f"Found {total_courses} courses. Fetching APIs in parallel...")
        print("Scraping Subject Details, Course Codes, Analytics, and Duration...\n")

        final_courses = []

        # Reduced max_workers to 20 to mimic natural traffic patterns
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            
            future_to_course = {
                executor.submit(self.fetch_course_details, course): course 
                for course in base_courses
            }

            completed = 0
            for future in concurrent.futures.as_completed(future_to_course):
                enriched_course = future.result()
                final_courses.append(enriched_course)
                
                completed += 1
                if completed % 100 == 0 or completed == total_courses:
                    print(f"Processed {completed} / {total_courses} courses...")

        catalog = {
            "metadata": {
                "version": datetime.now().strftime("%Y-%m-%d"),
                "last_updated": datetime.now().isoformat(),
                "source": self.URL,
                "total_courses": len(final_courses)
            },
            "courses": final_courses
        }

        os.makedirs("data", exist_ok=True)

        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(
                catalog,
                f,
                indent=4,
                ensure_ascii=False
            )

        print()
        print("=" * 80)
        print("Catalog Updated Successfully")
        print("=" * 80)
        print()
        print("Courses :", len(final_courses))
        print("Saved to :", self.output_path)