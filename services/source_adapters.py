from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests

from config import AppConfig
from models.schemas import ScrapedPage

logger = logging.getLogger(__name__)


class SourceAdapterService:
    """Prefer structured public ATS APIs before falling back to generic HTML scraping."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "startup-hiring-agent/2.0"})

    def fetch(self, url: str) -> ScrapedPage | None:
        host = urlparse(url).netloc.lower()
        try:
            if "greenhouse.io" in host:
                return self._greenhouse(url)
            if "lever.co" in host:
                return self._lever(url)
            if "ashbyhq.com" in host:
                return self._ashby(url)
        except Exception as exc:
            logger.info("Structured adapter failed for %s: %s", url, exc)
        return None

    def _greenhouse(self, url: str) -> ScrapedPage | None:
        token = self._path_token(url, ignored={"boards", "jobs"})
        if not token:
            return None
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
        response = self.session.get(api_url, params={"content": "true"}, timeout=self.config.timeout_seconds)
        response.raise_for_status()
        data = response.json()
        jobs = data.get("jobs", [])
        if not jobs:
            return None
        company = self._company_from_token(token)
        lines = [f"{company} Greenhouse Jobs"]
        links: list[str] = []
        for job in jobs:
            title = job.get("title", "")
            location = (job.get("location") or {}).get("name", "Unknown")
            absolute_url = job.get("absolute_url", "")
            content = self._strip_html(job.get("content", ""))
            lines.append(f"{title} - Location: {location}. {content[:1200]}")
            if absolute_url:
                links.append(absolute_url)
        return ScrapedPage(url=url, final_url=url, title=f"{company} Greenhouse Jobs", text="\n".join(lines), links=links, career_links=links)

    def _lever(self, url: str) -> ScrapedPage | None:
        token = self._path_token(url, ignored={"jobs", "postings"})
        if not token:
            return None
        api_url = f"https://api.lever.co/v0/postings/{token}"
        response = self.session.get(api_url, params={"mode": "json"}, timeout=self.config.timeout_seconds)
        response.raise_for_status()
        jobs = response.json()
        if not jobs:
            return None
        company = self._company_from_token(token)
        lines = [f"{company} Lever Jobs"]
        links: list[str] = []
        for job in jobs:
            title = job.get("text", "")
            location = (job.get("categories") or {}).get("location", "Unknown")
            hosted_url = job.get("hostedUrl", "")
            description = self._strip_html(job.get("descriptionPlain", "") or job.get("description", ""))
            lines.append(f"{title} - Location: {location}. {description[:1200]}")
            if hosted_url:
                links.append(hosted_url)
        return ScrapedPage(url=url, final_url=url, title=f"{company} Lever Jobs", text="\n".join(lines), links=links, career_links=links)

    def _ashby(self, url: str) -> ScrapedPage | None:
        token = self._path_token(url, ignored={"jobs"})
        if not token:
            return None
        api_url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
        response = self.session.get(api_url, timeout=self.config.timeout_seconds)
        response.raise_for_status()
        data = response.json()
        jobs = data.get("jobs", [])
        if not jobs:
            return None
        company = self._company_from_token(token)
        lines = [f"{company} Ashby Jobs"]
        links: list[str] = []
        for job in jobs:
            title = job.get("title", "")
            location = job.get("location", "Unknown")
            job_url = job.get("jobUrl", "") or job.get("applyUrl", "")
            description = self._strip_html(job.get("descriptionHtml", ""))
            lines.append(f"{title} - Location: {location}. {description[:1200]}")
            if job_url:
                links.append(job_url)
        return ScrapedPage(url=url, final_url=url, title=f"{company} Ashby Jobs", text="\n".join(lines), links=links, career_links=links)

    def _path_token(self, url: str, ignored: set[str]) -> str:
        parts = [part for part in urlparse(url).path.split("/") if part]
        for part in parts:
            if part.lower() not in ignored:
                return part
        host = urlparse(url).netloc.split(".")[0]
        return host if host not in {"api", "boards", "jobs"} else ""

    def _company_from_token(self, token: str) -> str:
        return token.replace("-", " ").replace("_", " ").title()

    def _strip_html(self, value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()
