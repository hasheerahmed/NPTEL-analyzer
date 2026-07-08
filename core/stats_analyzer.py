class StatsAnalyzer:
    """
    Processes the raw run_wise_stats array from a resolved course
    and calculates aggregated historical metrics for display.
    """

    def __init__(self):
        pass

    def _safe_float(self, val):
        try:
            return float(val) if val else 0.0
        except (ValueError, TypeError):
            return 0.0

    def _safe_int(self, val):
        try:
            return int(val) if val else 0
        except (ValueError, TypeError):
            return 0

    def analyze(self, course):
        if not course: return None

        metrics = {
            "course_id": course.get("course_id", "N/A"),
            "title": course.get("title", "Unknown"),
            "duration_weeks": course.get("duration_weeks", 0),
            "url": course.get("url", ""),
            "registered": 0,
            "certified": 0,
            "minimum_marks": 0.0,
            "maximum_marks": 0.0,
            "average": 0.0,
            "pass_ratio": 0.0,
            "easy_to_score_ratio": 0.0
        }

        if not course.get("stats_status"): return metrics
        run_stats = course.get("run_wise_stats", [])
        if not run_stats: return metrics

        total_registered = 0
        total_certified = 0
        sum_max_marks = 0.0
        sum_min_marks = 0.0
        sum_avg_marks = 0.0
        valid_runs_count = 0

        for run in run_stats:
            # Use safe casters so empty API fields don't crash the loop
            registered = self._safe_int(run.get("Registered"))
            certified = self._safe_int(run.get("Certified"))
            max_mark = self._safe_float(run.get("max_mark"))
            min_mark = self._safe_float(run.get("min_mark"))
            avg_mark = self._safe_float(run.get("average"))

            total_registered += registered
            total_certified += certified

            if max_mark > 0:
                sum_max_marks += max_mark
                sum_min_marks += min_mark
                sum_avg_marks += avg_mark
                valid_runs_count += 1

        metrics["registered"] = total_registered
        metrics["certified"] = total_certified

        if valid_runs_count > 0:
            metrics["maximum_marks"] = round(sum_max_marks / valid_runs_count, 2)
            metrics["minimum_marks"] = round(sum_min_marks / valid_runs_count, 2)
            metrics["average"] = round(sum_avg_marks / valid_runs_count, 2)

        if total_registered > 0:
            metrics["pass_ratio"] = round((total_certified / total_registered) * 100, 2)

        if metrics["maximum_marks"] > 0:
            metrics["easy_to_score_ratio"] = round((metrics["average"] / metrics["maximum_marks"]) * 100, 2)

        return metrics

    def analyze_many(self, courses):
        return [self.analyze(c) for c in courses if self.analyze(c)]