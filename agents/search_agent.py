from __future__ import annotations

import logging

from config import AppConfig
from models.schemas import SearchResult
from services.web_search import WebSearchService

logger = logging.getLogger(__name__)


class SearchAgent:
    def __init__(self, config: AppConfig, web_search: WebSearchService) -> None:
        self.config = config
        self.web_search = web_search

    def run(self) -> list[SearchResult]:
        logger.info("Searching startup hiring sources with provider=%s", self.config.search_provider)
        return self.web_search.search(self.config.search_queries)
