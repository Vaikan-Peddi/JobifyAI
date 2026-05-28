from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from models.schemas import Company, Job, utc_now_iso


@dataclass
class PersistResult:
    companies_upserted: int = 0
    jobs_upserted: int = 0
    new_jobs: list[Job] | None = None

    def __post_init__(self) -> None:
        if self.new_jobs is None:
            self.new_jobs = []


class JobDatabase:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self._migrate()

    def close(self) -> None:
        self.connection.close()

    def persist(self, companies: list[Company], jobs: list[Job]) -> PersistResult:
        now = utc_now_iso()
        new_jobs: list[Job] = []
        with self.connection:
            for company in companies:
                existing = self.connection.execute(
                    "select company_id, first_seen_at from companies where company_id = ?",
                    (company.company_id,),
                ).fetchone()
                first_seen_at = existing["first_seen_at"] if existing else now
                self.connection.execute(
                    """
                    insert into companies (
                        company_id, company_name, website, category, description, headquarters,
                        hiring_page, careers_page, source_url, discovered_at, first_seen_at,
                        last_seen_at, confidence_score, notes
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    on conflict(company_id) do update set
                        company_name=excluded.company_name,
                        website=excluded.website,
                        category=excluded.category,
                        description=excluded.description,
                        headquarters=excluded.headquarters,
                        hiring_page=excluded.hiring_page,
                        careers_page=excluded.careers_page,
                        source_url=excluded.source_url,
                        last_seen_at=excluded.last_seen_at,
                        confidence_score=excluded.confidence_score,
                        notes=excluded.notes
                    """,
                    (
                        company.company_id,
                        company.company_name,
                        company.website,
                        company.category,
                        company.description,
                        company.headquarters,
                        company.hiring_page,
                        company.careers_page,
                        company.source_url,
                        company.discovered_at,
                        first_seen_at,
                        now,
                        company.confidence_score,
                        company.notes,
                    ),
                )

            for job in jobs:
                existing = self.connection.execute("select job_id, first_seen_at from jobs where job_id = ?", (job.job_id,)).fetchone()
                if existing is None:
                    new_jobs.append(job)
                first_seen_at = existing["first_seen_at"] if existing else now
                self.connection.execute(
                    """
                    insert into jobs (
                        job_id, company_id, company_name, role_title, role_category, experience_level,
                        location, work_mode, application_link, job_description_url, source_url,
                        required_skills, fresher_friendly, confidence_score, discovered_at,
                        first_seen_at, last_seen_at, status, notes
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    on conflict(job_id) do update set
                        company_id=excluded.company_id,
                        company_name=excluded.company_name,
                        role_title=excluded.role_title,
                        role_category=excluded.role_category,
                        experience_level=excluded.experience_level,
                        location=excluded.location,
                        work_mode=excluded.work_mode,
                        application_link=excluded.application_link,
                        job_description_url=excluded.job_description_url,
                        source_url=excluded.source_url,
                        required_skills=excluded.required_skills,
                        fresher_friendly=excluded.fresher_friendly,
                        confidence_score=excluded.confidence_score,
                        last_seen_at=excluded.last_seen_at,
                        status='active',
                        notes=excluded.notes
                    """,
                    (
                        job.job_id,
                        job.company_id,
                        job.company_name,
                        job.role_title,
                        job.role_category,
                        job.experience_level,
                        job.location,
                        job.work_mode,
                        job.application_link,
                        job.job_description_url,
                        job.source_url,
                        json.dumps(job.required_skills),
                        int(job.fresher_friendly),
                        job.confidence_score,
                        job.discovered_at,
                        first_seen_at,
                        now,
                        "active",
                        job.notes,
                    ),
                )
        return PersistResult(companies_upserted=len(companies), jobs_upserted=len(jobs), new_jobs=new_jobs)

    def _migrate(self) -> None:
        with self.connection:
            self.connection.execute(
                """
                create table if not exists companies (
                    company_id text primary key,
                    company_name text not null,
                    website text,
                    category text,
                    description text,
                    headquarters text,
                    hiring_page text,
                    careers_page text,
                    source_url text,
                    discovered_at text,
                    first_seen_at text,
                    last_seen_at text,
                    confidence_score real,
                    notes text
                )
                """
            )
            self.connection.execute(
                """
                create table if not exists jobs (
                    job_id text primary key,
                    company_id text not null,
                    company_name text not null,
                    role_title text not null,
                    role_category text,
                    experience_level text,
                    location text,
                    work_mode text,
                    application_link text,
                    job_description_url text,
                    source_url text,
                    required_skills text,
                    fresher_friendly integer,
                    confidence_score real,
                    discovered_at text,
                    first_seen_at text,
                    last_seen_at text,
                    status text,
                    notes text
                )
                """
            )
