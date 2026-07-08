import os
import pdfplumber

class MarksheetParser:
    """
    Extracts a clean list of past subject names from a Marksheet PDF.
    Does NOT resolve them against the database.
    """

    def __init__(self):
        self.target_headers = ['course', 'subject', 'paper', 'title', 'name']
        self.ignore_headers = ['code', 'id', 'marks', 'grade', 'credit', 'total']

    def is_target_column(self, header_text):
        if not header_text: return False
        header_lower = str(header_text).lower().strip()
        for ignore in self.ignore_headers:
            if ignore in header_lower: return False
        for target in self.target_headers:
            if target in header_lower: return True
        return False

    def clean_subject(self, text):
        if not text: return ""
        cleaned = str(text).replace('\n', ' ').strip()
        if len(cleaned) < 4 or cleaned.isnumeric(): return ""
        return cleaned

    def parse_marksheet(self, file_path):
        if not os.path.exists(file_path): return []
        
        extracted_subjects = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        if not table: continue
                        target_col_idx, start_row_idx = -1, -1
                        
                        for row_idx, row in enumerate(table):
                            if not row: continue
                            for col_idx, cell_text in enumerate(row):
                                if self.is_target_column(cell_text):
                                    target_col_idx = col_idx
                                    start_row_idx = row_idx + 1
                                    break
                            if target_col_idx != -1: break
                            
                        if target_col_idx != -1:
                            for row in table[start_row_idx:]:
                                if len(row) > target_col_idx:
                                    clean_name = self.clean_subject(row[target_col_idx])
                                    if clean_name: extracted_subjects.append(clean_name)
                                    
            return list(set(extracted_subjects))
        except Exception:
            return []