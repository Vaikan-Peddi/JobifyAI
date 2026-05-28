from __future__ import annotations

import json
import logging
from typing import Any

import requests

from config import AppConfig
from models.schemas import Company, ExtractionResult, Job, ScrapedPage

logger = logging.getLogger(__name__)


EXTRACTION_PROMPT = """
You extract startup hiring data from the provided page text and links.
Return strict JSON only with this shape:
{
  "companies": [{
    "company_name": "",
    "website": "",
    "category": "",
    "description": "",
    "headquarters": "",
    "hiring_page": "",
    "careers_page": "",
    "confidence_score": 0.0,
    "notes": ""
  }],
  "jobs": [{
    "company_name": "",
    "role_title": "",
    "role_category": "",
    "experience_level": "",
    "location": "",
    "work_mode": "",
    "application_link": "",
    "job_description_url": "",
    "required_skills": [],
    "fresher_friendly": true,
    "confidence_score": 0.0,
    "notes": ""
  }]
}
Only extract jobs that appear in the page text or links. Do not invent companies, jobs, locations, or links.
Prioritize software engineering, backend, frontend, full-stack, AI/ML, data engineering, applied AI, and LLM roles.
"""


class LLMService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def extract(self, page: ScrapedPage) -> ExtractionResult:
        provider = self.config.llm_provider.lower()
        if provider == "openai":
            return self._openai_extract(page)
        if provider == "ollama":
            return self._ollama_extract(page)
        return ExtractionResult()

    def _openai_extract(self, page: ScrapedPage) -> ExtractionResult:
        if not self.config.openai_api_key and not self.config.openai_base_url:
            logger.warning("OpenAI-compatible API not configured; using heuristic extraction only.")
            return ExtractionResult()
        base_url = (self.config.openai_base_url or "https://api.openai.com/v1").rstrip("/")
        model = self.config.openai_model or "gpt-4o-mini"
        headers = {"Authorization": f"Bearer {self.config.openai_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": self._page_payload(page)},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        response = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return self._parse_json(content, page)

    def _ollama_extract(self, page: ScrapedPage) -> ExtractionResult:
        payload = {
            "model": self.config.ollama_model,
            "prompt": f"{EXTRACTION_PROMPT}\n\n{self._page_payload(page)}",
            "stream": False,
            "format": "json",
        }
        response = requests.post(f"{self.config.ollama_base_url.rstrip('/')}/api/generate", json=payload, timeout=120)
        response.raise_for_status()
        content = response.json().get("response", "{}")
        return self._parse_json(content, page)

    def _page_payload(self, page: ScrapedPage) -> str:
        links = "\n".join(page.links[:100])
        return f"Source URL: {page.url}\nTitle: {page.title}\nLinks:\n{links}\n\nPage text:\n{page.text[:30000]}"

    def _parse_json(self, content: str, page: ScrapedPage) -> ExtractionResult:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.warning("LLM returned invalid JSON for %s: %s", page.url, exc)
            return ExtractionResult()
        return self._to_result(data, page)

    def _to_result(self, data: dict[str, Any], page: ScrapedPage) -> ExtractionResult:
        companies: list[Company] = []
        jobs: list[Job] = []
        for item in data.get("companies", []):
            try:
                item.setdefault("source_url", page.url)
                companies.append(Company(**item))
            except Exception as exc:
                logger.debug("Skipping invalid LLM company: %s", exc)
        for item in data.get("jobs", []):
            try:
                item.setdefault("source_url", page.url)
                jobs.append(Job(**item))
            except Exception as exc:
                logger.debug("Skipping invalid LLM job: %s", exc)
        return ExtractionResult(companies=companies, jobs=jobs)
