from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from config import AppConfig
from models.schemas import Company, ExtractionResult, Job, ScrapedPage
from services.llm import LLMService
from utils.text import (
    FRESHER_NEGATIVE_KEYWORDS,
    FRESHER_POSITIVE_KEYWORDS,
    classify_role,
    detect_experience_level,
    detect_work_mode,
    fresher_signal_score,
    infer_company_name_from_url,
    is_software_related,
    normalize_text,
)

logger = logging.getLogger(__name__)


class ExtractionAgent:
    ROLE_LINE_RE = re.compile(
        r"(?P<title>(?:software|backend|frontend|front-end|full[- ]stack|ai|machine learning|ml|data|devops|mobile|ios|android|llm|applied ai)[^\n|•]{0,90}?(?:engineer|developer|intern|graduate|new grad|associate))",
        re.IGNORECASE,
    )

    def __init__(self, config: AppConfig, llm_service: LLMService) -> None:
        self.config = config
        self.llm_service = llm_service

    def run(self, page: ScrapedPage) -> ExtractionResult:
        llm_result = self.llm_service.extract(page)
        heuristic_result = self._heuristic_extract(page)
        return ExtractionResult(
            companies=[*llm_result.companies, *heuristic_result.companies],
            jobs=[*llm_result.jobs, *heuristic_result.jobs],
        )

    def _heuristic_extract(self, page: ScrapedPage) -> ExtractionResult:
        company_name = self._guess_company_name(page)
        careers_page = self._first_career_link(page) or page.final_url or page.url
        company = Company(
            company_name=company_name,
            website=self._guess_website(page),
            category=self._guess_category(page.text),
            description=self._short_description(page.text),
            headquarters=self._guess_location(page.text),
            hiring_page=careers_page,
            careers_page=careers_page,
            source_url=page.url,
            confidence_score=0.45 if company_name != "Unknown" else 0.25,
            notes="Extracted with rule-based heuristics.",
        )

        jobs: list[Job] = []
        seen_titles: set[str] = set()
        for title, context in self._candidate_role_contexts(page):
            normalized_title = title.lower().strip()
            if normalized_title in seen_titles or not is_software_related(title, context):
                continue
            seen_titles.add(normalized_title)
            friendly, signal_score, notes = fresher_signal_score(title, context)
            experience = detect_experience_level(f"{title} {context}")
            link = self._best_job_link(title, page)
            jobs.append(
                Job(
                    company_name=company_name,
                    role_title=self._clean_role_title(title),
                    role_category=classify_role(title, context),
                    experience_level=experience,
                    location=self._guess_location(context),
                    work_mode=detect_work_mode(context),
                    application_link=link,
                    job_description_url=link or page.final_url or page.url,
                    source_url=page.url,
                    required_skills=self._extract_skills(context),
                    fresher_friendly=friendly,
                    confidence_score=min(0.9, signal_score + 0.1),
                    notes=notes,
                )
            )

        return ExtractionResult(companies=[company] if jobs or company_name != "Unknown" else [], jobs=jobs)

    def _guess_company_name(self, page: ScrapedPage) -> str:
        title = page.title.strip()
        if title:
            title = re.split(r"\s[-|]\s| careers| jobs| hiring", title, flags=re.IGNORECASE)[0].strip()
            if 2 <= len(title) <= 60:
                return title
        return infer_company_name_from_url(page.final_url or page.url)

    def _guess_website(self, page: ScrapedPage) -> str:
        final = page.final_url or page.url
        return final.split("/careers")[0].split("/jobs")[0]

    def _first_career_link(self, page: ScrapedPage) -> str:
        if page.career_links:
            return page.career_links[0]
        return ""

    def _guess_category(self, text: str) -> str:
        lowered = text.lower()
        if any(k in lowered for k in ["ai", "llm", "machine learning"]):
            return "AI/ML"
        if any(k in lowered for k in ["fintech", "payments", "banking"]):
            return "Fintech"
        if any(k in lowered for k in ["health", "medical", "clinical"]):
            return "Healthtech"
        if any(k in lowered for k in ["developer tools", "devtools", "infrastructure"]):
            return "Developer Tools"
        return "Startup"

    def _short_description(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        return cleaned[:280]

    def _guess_location(self, text: str) -> str:
        patterns = [
            r"(San Francisco|New York|NYC|Seattle|Austin|Boston|Los Angeles|Remote|United States|US|USA|Canada|London|Bengaluru|Bangalore|India)",
            r"Location:\s*([A-Za-z ,/-]{2,60})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return "Unknown"

    def _candidate_role_contexts(self, page: ScrapedPage) -> list[tuple[str, str]]:
        lines = [line.strip() for line in page.text.splitlines() if line.strip()]
        candidates: list[tuple[str, str]] = []
        for i, line in enumerate(lines):
            normalized_line = normalize_text(line)
            if normalized_line.startswith(("apply at", "applications", "apply here", "http", "www")):
                continue
            has_negative = any(keyword in normalized_line for keyword in FRESHER_NEGATIVE_KEYWORDS)
            has_positive = any(keyword in normalized_line for keyword in FRESHER_POSITIVE_KEYWORDS)
            if has_negative and not has_positive:
                continue
            context = line
            leading_title = re.split(r"\s+-\s+|\s+\|\s+", line, maxsplit=1)[0].strip()
            if is_software_related(leading_title) and any(
                keyword in normalize_text(leading_title)
                for keyword in ["engineer", "developer", "intern", "graduate"]
            ):
                candidates.append((leading_title, context))
                continue
            for match in self.ROLE_LINE_RE.finditer(line):
                candidates.append((match.group("title"), context))

        if candidates:
            return candidates
        for link in page.links:
            text = link.rsplit("/", 1)[-1].replace("-", " ").replace("_", " ")
            normalized_text = normalize_text(text)
            has_negative = any(keyword in normalized_text for keyword in FRESHER_NEGATIVE_KEYWORDS)
            has_positive = any(keyword in normalized_text for keyword in FRESHER_POSITIVE_KEYWORDS)
            if has_negative and not has_positive:
                continue
            if is_software_related(text):
                candidates.append((text.title(), link))
        return candidates

    def _clean_role_title(self, title: str) -> str:
        title = re.sub(r"\s+", " ", title).strip(" -|•")
        return title[:120]

    def _best_job_link(self, title: str, page: ScrapedPage) -> str:
        words = [word for word in re.split(r"[^a-z0-9]+", title.lower()) if len(word) > 2]
        for link in page.links:
            lowered = link.lower()
            if any(word in lowered for word in words) and any(k in lowered for k in ["job", "career", "greenhouse", "lever", "ashby", "workable", "apply"]):
                return urljoin(page.final_url or page.url, link)
        return page.final_url or page.url

    def _extract_skills(self, text: str) -> list[str]:
        skills = ["Python", "JavaScript", "TypeScript", "React", "Node", "SQL", "AWS", "Docker", "Kubernetes", "PyTorch", "TensorFlow", "LLM"]
        lowered = text.lower()
        return [skill for skill in skills if skill.lower() in lowered][:8]
