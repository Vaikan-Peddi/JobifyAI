from __future__ import annotations

import logging
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from config import AppConfig
from models.schemas import ScrapedPage

logger = logging.getLogger(__name__)


class Scraper:
    CAREER_TERMS = ("career", "careers", "job", "jobs", "greenhouse", "lever", "ashby", "workable", "apply")

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "startup-hiring-agent/1.0 "
                    "(ethical research bot; contact: configure-your-email@example.com)"
                )
            }
        )

    def fetch(self, url: str) -> ScrapedPage:
        if url.startswith("sample://"):
            return self._sample_page(url)
        time.sleep(self.config.request_delay_seconds)
        try:
            response = self._get(url)
            return self._parse(url, response.url, response.text)
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", url, exc)
            return ScrapedPage(url=url, final_url=url, error=str(exc))

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def _get(self, url: str) -> requests.Response:
        response = self.session.get(url, timeout=self.config.timeout_seconds)
        response.raise_for_status()
        return response

    def _parse(self, url: str, final_url: str, html: str) -> ScrapedPage:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        links = self._extract_links(soup, final_url)
        text = soup.get_text("\n", strip=True)
        career_links = [link for link in links if any(term in link.lower() for term in self.CAREER_TERMS)]
        return ScrapedPage(url=url, final_url=final_url, title=title, text=text[:80_000], links=links, career_links=career_links)

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        links: list[str] = []
        for tag in soup.find_all("a", href=True):
            href = tag.get("href", "").strip()
            if not href or href.startswith(("mailto:", "tel:", "javascript:")):
                continue
            links.append(urljoin(base_url, href))
        return list(dict.fromkeys(links))[:500]

    def sample_pages(self) -> list[ScrapedPage]:
        return [self._sample_page("sample://aurora-ai-careers"), self._sample_page("sample://forgebase-jobs")]

    def _sample_page(self, url: str) -> ScrapedPage:
        if "forgebase" in url:
            text = """
Forgebase Careers
Forgebase is a venture-backed developer tools startup building data infrastructure for engineering teams.
Location: New York, Remote US
Open roles:
Junior Backend Engineer - Python, APIs, PostgreSQL. Entry level, 0-2 years experience. Remote.
Software Engineer Intern - Summer internship for university students. React, TypeScript, Node.
Senior Staff Platform Architect - 10+ years experience.
Apply at https://jobs.ashbyhq.com/forgebase/junior-backend-engineer
Apply at https://jobs.ashbyhq.com/forgebase/software-engineer-intern
"""
            links = [
                "https://www.forgebase.example/careers",
                "https://jobs.ashbyhq.com/forgebase/junior-backend-engineer",
                "https://jobs.ashbyhq.com/forgebase/software-engineer-intern",
            ]
            return ScrapedPage(
                url=url,
                final_url="https://www.forgebase.example/careers",
                title="Forgebase Careers",
                text=text,
                links=links,
                career_links=links,
            )
        text = """
Aurora AI Labs Jobs
Aurora AI Labs is an AI startup building applied LLM products for customer operations.
Headquarters: San Francisco, CA
Hiring:
New Grad Software Engineer, Full Stack - Early career role for fresh graduates. Python, React, LLM APIs. Hybrid San Francisco.
Entry Level AI Engineer - 0-1 years experience, no prior experience with production ML required. Remote.
Principal Machine Learning Engineer - 7+ years experience.
Applications:
https://jobs.lever.co/aurora-ai-labs/new-grad-software-engineer
https://jobs.lever.co/aurora-ai-labs/entry-level-ai-engineer
"""
        links = [
            "https://www.auroraailabs.example/careers",
            "https://jobs.lever.co/aurora-ai-labs/new-grad-software-engineer",
            "https://jobs.lever.co/aurora-ai-labs/entry-level-ai-engineer",
        ]
        return ScrapedPage(
            url=url,
            final_url="https://www.auroraailabs.example/careers",
            title="Aurora AI Labs Jobs",
            text=text,
            links=links,
            career_links=links,
        )
