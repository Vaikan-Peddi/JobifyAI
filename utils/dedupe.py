from __future__ import annotations

import hashlib

from models.schemas import Company, Job
from utils.text import domain_from_url, normalize_name, normalize_role_title


def stable_hash(value: str, length: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def company_key(company: Company) -> str:
    domain = domain_from_url(company.website or company.careers_page or company.hiring_page)
    return domain or normalize_name(company.company_name)


def job_key(job: Job) -> str:
    link = job.application_link or job.job_description_url
    return "|".join(
        [
            normalize_name(job.company_name),
            normalize_role_title(job.role_title),
            link.strip().lower(),
            job.job_description_url.strip().lower(),
        ]
    )


def assign_company_id(company: Company) -> Company:
    key = company_key(company)
    company.company_id = f"cmp_{stable_hash(key)}"
    return company


def assign_job_id(job: Job) -> Job:
    base = "|".join([job.company_id, normalize_role_title(job.role_title), (job.application_link or job.job_description_url).lower()])
    job.job_id = f"job_{stable_hash(base)}"
    return job


def dedupe_companies(companies: list[Company]) -> tuple[list[Company], int]:
    seen: dict[str, Company] = {}
    duplicates = 0
    for company in companies:
        company = assign_company_id(company)
        key = company.company_id
        existing = seen.get(key)
        if existing is None:
            seen[key] = company
            continue
        duplicates += 1
        if company.confidence_score > existing.confidence_score:
            seen[key] = company
    return list(seen.values()), duplicates


def dedupe_jobs(jobs: list[Job]) -> tuple[list[Job], int]:
    seen: dict[str, Job] = {}
    duplicates = 0
    for job in jobs:
        job = assign_job_id(job)
        key = job.job_id
        existing = seen.get(key)
        if existing is None:
            seen[key] = job
            continue
        duplicates += 1
        if job.confidence_score > existing.confidence_score:
            seen[key] = job
    return list(seen.values()), duplicates
