from __future__ import annotations

from models.schemas import Company, Job
from utils.dedupe import assign_company_id, assign_job_id
from utils.text import FRESHER_NEGATIVE_KEYWORDS, FRESHER_POSITIVE_KEYWORDS, fresher_signal_score, is_software_related, normalize_text


class ValidationAgent:
    def validate_companies(self, companies: list[Company]) -> list[Company]:
        valid: list[Company] = []
        for company in companies:
            if not company.company_name or company.company_name == "Unknown":
                continue
            company.confidence_score = max(0.0, min(company.confidence_score, 1.0))
            valid.append(assign_company_id(company))
        return valid

    def validate_jobs(self, jobs: list[Job], companies_by_name: dict[str, Company]) -> tuple[list[Job], int]:
        valid: list[Job] = []
        skipped = 0
        for job in jobs:
            if not self._is_valid_job(job):
                skipped += 1
                continue
            company = companies_by_name.get(job.company_name.lower())
            if company:
                job.company_id = company.company_id
            if not job.company_id:
                skipped += 1
                continue

            friendly, signal_score, notes = fresher_signal_score(job.role_title, f"{job.notes} {' '.join(job.required_skills)}")
            if job.fresher_friendly != friendly and "Mixed fresher signals" in notes:
                job.notes = f"{job.notes} {notes}".strip()
            job.fresher_friendly = job.fresher_friendly or friendly
            job.confidence_score = min(1.0, max(job.confidence_score, signal_score))
            valid.append(assign_job_id(job))
        return valid, skipped

    def _is_valid_job(self, job: Job) -> bool:
        if not job.company_name or not job.role_title:
            return False
        if not (job.application_link or job.job_description_url):
            return False
        if not job.source_url:
            return False
        if not is_software_related(job.role_title, " ".join(job.required_skills)):
            return False
        combined = normalize_text(f"{job.role_title} {job.notes}")
        has_positive = any(keyword in combined for keyword in FRESHER_POSITIVE_KEYWORDS)
        has_negative = any(keyword in combined for keyword in FRESHER_NEGATIVE_KEYWORDS)
        if has_negative and not has_positive:
            return False
        if job.experience_level == "Not Fresher Friendly" and not has_positive:
            return False
        return True
