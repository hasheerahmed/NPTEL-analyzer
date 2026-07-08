import os
import pdfplumber
import re
from core.resolver import Resolver


class NPTELPDFParser:
    """
    Universal NPTEL syllabus PDF parser.

    Works in two modes, tried per page:
      1. TABLE MODE  - if pdfplumber detects a bordered/gridded table, walk
                        every cell (current behaviour, unchanged).
      2. TEXT MODE   - fallback for PDFs with no detectable table (plain
                        text lists, PDFs exported without visible borders,
                        different universities' formats, etc). Extracts
                        raw text, then strips leading serial numbers,
                        department abbreviations, and course codes from
                        each line using pattern rules instead of hardcoded
                        column positions - so it isn't tied to this one
                        PDF's layout.

    Both modes funnel every candidate string through the same
    is_valid_candidate() filter and the same resolver.search() matching,
    so behaviour stays consistent regardless of which mode found the text.
    """

    def __init__(self, debug=False):
        self.resolver = Resolver()
        self.debug = debug
        # Candidates that passed the filter but never hit the match
        # threshold - inspect this after parse_pdf() to see near-misses
        # instead of guessing why a course went missing.
        self.unmatched = []

        # Universal blacklist to kill non-course text instantly
        self.blacklist = [
            'http', 'www.', 'prof.', 'prof ', 'dr.', 'dr ', 'iit ', 'iisc ', 'iiser ', 'nit ',
            'university', 'institute', 'college', 'swayam', 'nptel', 'mooc',
            'instructor', 'duration', 'weeks', 'platform', 'credits', 'syllabus', 'dept'
        ]

        # A "code" token: mixes letters and digits with no spaces
        # (25MC6OECV1, noc23-cs109, EC101, etc.)
        self._code_re = re.compile(r'^[A-Za-z]*\d+[A-Za-z0-9\-]*$|^\d+[A-Za-z]+[A-Za-z0-9\-]*$')
        # A bare serial number, optionally bracketed/punctuated: 1, (2), 3.
        self._serial_re = re.compile(r'^\(?\d{1,3}\)?[\.\):]?$')

    # ----------------------------------------------------------------
    # Text normalization
    # ----------------------------------------------------------------
    def normalize_text(self, text):
        """
        Collapses PDF/typography artifacts that hurt fuzzy matching but
        carry no real meaning: curly quotes, en/em dashes, cid artifacts,
        stray whitespace.
        """
        text = re.sub(r'\(cid:\d+\)', '', text)
        text = text.replace('\u2019', "'").replace('\u2018', "'")   # ’ ‘ -> '
        text = text.replace('\u201c', '"').replace('\u201d', '"')   # “ ” -> "
        text = text.replace('\u2013', '-').replace('\u2014', '-')   # – — -> -
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    # ----------------------------------------------------------------
    # Candidate filtering
    # ----------------------------------------------------------------
    def is_valid_candidate(self, text):
        """
        Determines if a string is likely a course name.
        """
        text_lower = text.lower().strip()

        # 1. Reject if too short (e.g., "8", "12", "CS")
        if len(text_lower) < 8:
            return False

        # 2. Reject if it hits the blacklist (e.g., "IIT Kanpur", "Prof. John")
        if any(blacklisted in text_lower for blacklisted in self.blacklist):
            return False

        # 3. Reject purely alphanumeric codes without spaces (e.g., 25MC60ECV1, noc26-cs109)
        if " " not in text_lower and any(c.isdigit() for c in text_lower):
            return False

        return True

    # ----------------------------------------------------------------
    # Format-agnostic line cleanup (used by TEXT MODE fallback)
    # ----------------------------------------------------------------
    def strip_leading_codes(self, line):
        """
        Strips leading serial numbers, department abbreviations, and
        course codes from a raw text line, leaving just the course title.
        Rule-based (not tied to fixed column positions) so it generalizes
        to PDFs laid out differently from this one.

        Examples:
          "1 25MC6OECV1 Disaster management"      -> "Disaster management"
          "5 CV 25MC6OECV5 Soil And Water Cons.."  -> "Soil And Water Cons.."
          "noc23-cs31 Introduction to ML"          -> "Introduction to ML"
          "7 25MC6OEEC7 GPU Design"                -> "GPU Design"  (not eaten)
        """
        tokens = line.strip().split()
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            is_serial = bool(self._serial_re.match(tok))
            is_code = bool(self._code_re.match(tok)) and any(c.isdigit() for c in tok)
            # A dept abbreviation (all-caps, no digits) only counts as a
            # leading code IF the token right after it is itself a code -
            # this stops us from eating real title words like "GPU".
            is_dept_abbr = (
                tok.isupper() and 2 <= len(tok) <= 6 and not any(c.isdigit() for c in tok)
                and i + 1 < len(tokens)
                and bool(self._code_re.match(tokens[i + 1])) and any(c.isdigit() for c in tokens[i + 1])
            )
            if is_serial or is_code or is_dept_abbr:
                i += 1
                continue
            break
        return " ".join(tokens[i:])

    # ----------------------------------------------------------------
    # Matching
    # ----------------------------------------------------------------
    def _try_match(self, clean_line, resolved_courses):
        """
        Runs one candidate string through the resolver and appends it to
        resolved_courses if it clears the confidence bar. Records
        near-misses in self.unmatched for debugging.
        """
        results = self.resolver.search(clean_line, top_n=3)
        if not results:
            self.unmatched.append({"text": clean_line, "reason": "no_candidates"})
            return

        best = max(results, key=lambda r: r.get("score", 0))
        if best.get("score", 0) >= 90:
            if not any(c["course_id"] == best["course_id"] for c in resolved_courses):
                resolved_courses.append(best)
        else:
            self.unmatched.append({
                "text": clean_line,
                "best_title": best.get("title"),
                "score": best.get("score"),
            })

    # ----------------------------------------------------------------
    # TABLE MODE
    # ----------------------------------------------------------------
   # ----------------------------------------------------------------
    # TABLE MODE
    # ----------------------------------------------------------------
    def _parse_tables(self, page, resolved_courses):
        tables = page.extract_tables()
        found_any = False
        for table in tables:
            if not table:
                continue
            for row in table:
                if not row:
                    continue
                for cell in row:
                    if not cell:
                        continue
                        
                    # THE FIX: 
                    # 1. Remove hyphen+newline combinations (Tech-\nnologies -> Technologies)
                    # 2. Replace any remaining normal newlines with spaces so wrapped text stays on one line
                    cell_text = str(cell).replace('-\n', '').replace('\n', ' ')
                    
                    clean_line = self.normalize_text(cell_text)
                    if self.is_valid_candidate(clean_line):
                        found_any = True
                        self._try_match(clean_line, resolved_courses)
                        
        return found_any

    # ----------------------------------------------------------------
    # TEXT MODE (fallback for PDFs with no detectable table)
    # ----------------------------------------------------------------
    def _parse_text(self, page, resolved_courses):
        text = page.extract_text()
        if not text:
            return
        for raw_line in text.split('\n'):
            line = self.normalize_text(raw_line)
            if not line:
                continue
            title = self.strip_leading_codes(line)
            if self.is_valid_candidate(title):
                self._try_match(title, resolved_courses)

    # ----------------------------------------------------------------
    # Entry point
    # ----------------------------------------------------------------
    def parse_pdf(self, file_path):
        if not os.path.exists(file_path):
            return []

        resolved_courses = []
        self.unmatched = []

        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    had_table_data = self._parse_tables(page, resolved_courses)
                    # Only fall back to flat-text parsing if this page had
                    # no usable table - avoids double-processing the same
                    # course names through both paths.
                    if not had_table_data:
                        self._parse_text(page, resolved_courses)

            if self.debug and self.unmatched:
                print(f"\n--- {len(self.unmatched)} candidate(s) below match threshold ---")
                for u in self.unmatched:
                    if "score" in u:
                        print(f"  '{u['text']}' -> closest: '{u['best_title']}' (score {u['score']})")
                    else:
                        print(f"  '{u['text']}' -> no catalog candidates at all")

            return resolved_courses

        except Exception as e:
            print(f"Error parsing syllabus: {e}")
            return []