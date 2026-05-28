from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


DEFAULT_SEARCH_QUERIES = [
    "top startups hiring software engineers new grad",
    "startups hiring entry level software engineer",
    "YC startups hiring software engineer",
    "AI startups hiring new grad software engineer",
    "AI startups hiring machine learning engineer entry level",
    "startup careers software engineer intern new grad",
    "venture backed startups hiring engineers",
    "wellfound startups hiring software engineer",
    "YC Work at a Startup software engineer",
    "new grad software engineer startup jobs",
    "entry level AI engineer startup",
    "junior machine learning engineer startup",
]

DEFAULT_SEED_URLS = [
    "https://www.ycombinator.com/jobs",
    "https://wellfound.com/jobs",
    "https://jobs.ashbyhq.com/",
    "https://boards.greenhouse.io/",
    "https://jobs.lever.co/",
    "https://www.workatastartup.com/",
    "https://www.workable.com/jobs",
]


@dataclass
class AppConfig:
    serpapi_api_key: str = ""
    tavily_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    google_sheets_credentials_file: str = "service_account.json"
    google_sheet_name: str = "Startup Hiring Agent Results"
    search_provider: str = "seed"
    llm_provider: str = "mock"
    database_path: str = "data/startup_hiring_agent.sqlite3"
    max_companies: int = 50
    max_jobs_per_company: int = 10
    dry_run: bool = True
    write_sheets: bool = False
    output_csv: bool = True
    seed_urls: list[str] = field(default_factory=lambda: DEFAULT_SEED_URLS.copy())
    search_queries: list[str] = field(default_factory=lambda: DEFAULT_SEARCH_QUERIES.copy())
    request_delay_seconds: float = 1.0
    timeout_seconds: int = 15


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_config() -> AppConfig:
    load_dotenv()
    return AppConfig(
        serpapi_api_key=os.getenv("SERPAPI_API_KEY", ""),
        tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_base_url=os.getenv("OPENAI_BASE_URL", ""),
        openai_model=os.getenv("OPENAI_MODEL", ""),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1"),
        google_sheets_credentials_file=os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE", "service_account.json"),
        google_sheet_name=os.getenv("GOOGLE_SHEET_NAME", "Startup Hiring Agent Results"),
        search_provider=os.getenv("SEARCH_PROVIDER", "seed").lower(),
        llm_provider=os.getenv("LLM_PROVIDER", "mock").lower(),
        database_path=os.getenv("DATABASE_PATH", "data/startup_hiring_agent.sqlite3"),
        max_companies=int(os.getenv("MAX_COMPANIES", "50")),
        max_jobs_per_company=int(os.getenv("MAX_JOBS_PER_COMPANY", "10")),
        dry_run=_bool_env("DRY_RUN", True),
    )
