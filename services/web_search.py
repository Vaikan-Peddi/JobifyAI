from __future__ import annotations

import logging

import requests

from config import AppConfig
from models.schemas import SearchResult

logger = logging.getLogger(__name__)


class WebSearchService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def search(self, queries: list[str]) -> list[SearchResult]:
        provider = self.config.search_provider.lower()
        if provider == "serpapi":
            return self._serpapi_search(queries)
        if provider == "tavily":
            return self._tavily_search(queries)
        return self._seed_search()

    def _seed_search(self) -> list[SearchResult]:
        return [
            SearchResult(
                title=f"Seed source: {url}",
                url=url,
                snippet="Configured public startup hiring/job-board seed URL.",
                provider="seed",
            )
            for url in self.config.seed_urls
        ]

    def _serpapi_search(self, queries: list[str]) -> list[SearchResult]:
        if not self.config.serpapi_api_key:
            logger.warning("SERPAPI_API_KEY missing; falling back to seed provider.")
            return self._seed_search()
        results: list[SearchResult] = []
        for query in queries:
            response = requests.get(
                "https://serpapi.com/search.json",
                params={"q": query, "engine": "google", "api_key": self.config.serpapi_api_key, "num": 5},
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            for item in data.get("organic_results", []):
                url = item.get("link")
                if url:
                    results.append(
                        SearchResult(
                            title=item.get("title", ""),
                            url=url,
                            snippet=item.get("snippet", ""),
                            provider="serpapi",
                        )
                    )
        return self._unique_results(results)

    def _tavily_search(self, queries: list[str]) -> list[SearchResult]:
        if not self.config.tavily_api_key:
            logger.warning("TAVILY_API_KEY missing; falling back to seed provider.")
            return self._seed_search()
        results: list[SearchResult] = []
        headers = {"Authorization": f"Bearer {self.config.tavily_api_key}"}
        for query in queries:
            response = requests.post(
                "https://api.tavily.com/search",
                json={"query": query, "search_depth": "basic", "max_results": 5},
                headers=headers,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            for item in data.get("results", []):
                url = item.get("url")
                if url:
                    results.append(
                        SearchResult(
                            title=item.get("title", ""),
                            url=url,
                            snippet=item.get("content", ""),
                            provider="tavily",
                        )
                    )
        return self._unique_results(results)

    def _unique_results(self, results: list[SearchResult]) -> list[SearchResult]:
        seen: set[str] = set()
        unique: list[SearchResult] = []
        for result in results:
            if result.url in seen:
                continue
            seen.add(result.url)
            unique.append(result)
        return unique
