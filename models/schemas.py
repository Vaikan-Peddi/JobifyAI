from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


RoleCategory = Literal[
    "Backend",
    "Frontend",
    "Full Stack",
    "Software Engineering",
    "AI Engineering",
    "Machine Learning",
    "Data Engineering",
    "DevOps",
    "Mobile",
    "Other",
]

ExperienceLevel = Literal[
    "Intern",
    "New Grad",
    "Entry Level",
    "Junior",
    "0-2 Years",
    "Unknown",
    "Not Fresher Friendly",
]

WorkMode = Literal["Remote", "Hybrid", "Onsite", "Unknown"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SearchResult(BaseModel):
    title: str = ""
    url: str
    snippet: str = ""
    provider: str = "seed"


class ScrapedPage(BaseModel):
    url: str
    final_url: str
    title: str = ""
    text: str = ""
    links: list[str] = Field(default_factory=list)
    career_links: list[str] = Field(default_factory=list)
    error: str | None = None


class Company(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    company_id: str = ""
    company_name: str
    website: str = ""
    category: str = "Unknown"
    description: str = ""
    headquarters: str = ""
    hiring_page: str = ""
    careers_page: str = ""
    source_url: str = ""
    discovered_at: str = Field(default_factory=utc_now_iso)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    notes: str = ""

    @field_validator("website", "hiring_page", "careers_page", "source_url", mode="before")
    @classmethod
    def stringify_urls(cls, value: object) -> str:
        if isinstance(value, HttpUrl):
            return str(value)
        return "" if value is None else str(value)


class Job(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    job_id: str = ""
    company_id: str = ""
    company_name: str
    role_title: str
    role_category: RoleCategory = "Other"
    experience_level: ExperienceLevel = "Unknown"
    location: str = "Unknown"
    work_mode: WorkMode = "Unknown"
    application_link: str = ""
    job_description_url: str = ""
    source_url: str = ""
    required_skills: list[str] = Field(default_factory=list)
    fresher_friendly: bool = False
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    discovered_at: str = Field(default_factory=utc_now_iso)
    notes: str = ""

    @field_validator("application_link", "job_description_url", "source_url", mode="before")
    @classmethod
    def stringify_urls(cls, value: object) -> str:
        if isinstance(value, HttpUrl):
            return str(value)
        return "" if value is None else str(value)


class ExtractionResult(BaseModel):
    companies: list[Company] = Field(default_factory=list)
    jobs: list[Job] = Field(default_factory=list)


class RunSummary(BaseModel):
    total_sources_searched: int = 0
    companies_discovered: int = 0
    jobs_discovered: int = 0
    new_jobs_discovered: int = 0
    fresher_friendly_jobs_found: int = 0
    company_rows_written: int = 0
    job_rows_written: int = 0
    new_job_rows_written: int = 0
    application_tracker_rows_written: int = 0
    skipped_duplicate_jobs: int = 0
    skipped_invalid_jobs: int = 0
    errors: list[str] = Field(default_factory=list)
