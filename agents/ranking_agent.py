from __future__ import annotations

from models.schemas import Company, Job


class RankingAgent:
    def rank_companies(self, companies: list[Company], max_companies: int) -> list[Company]:
        return sorted(companies, key=lambda company: company.confidence_score, reverse=True)[:max_companies]

    def rank_jobs(self, jobs: list[Job], max_jobs_per_company: int) -> list[Job]:
        ranked = sorted(jobs, key=self._score_job, reverse=True)
        counts: dict[str, int] = {}
        limited: list[Job] = []
        for job in ranked:
            count = counts.get(job.company_id, 0)
            if count >= max_jobs_per_company:
                continue
            counts[job.company_id] = count + 1
            limited.append(job)
        return limited

    def _score_job(self, job: Job) -> float:
        score = job.confidence_score
        if job.fresher_friendly:
            score += 0.35
        if job.work_mode == "Remote":
            score += 0.1
        if job.application_link and job.application_link != job.source_url:
            score += 0.1
        if job.role_category in {"AI Engineering", "Machine Learning", "Software Engineering", "Full Stack", "Backend", "Frontend", "Data Engineering"}:
            score += 0.15
        return score
