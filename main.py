from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table
from tqdm import tqdm

from agents.extraction_agent import ExtractionAgent
from agents.ranking_agent import RankingAgent
from agents.search_agent import SearchAgent
from agents.validation_agent import ValidationAgent
from config import AppConfig, load_config
from models.schemas import Company, Job, RunSummary, SearchResult
from services.database import JobDatabase
from services.google_sheets import GoogleSheetsService
from services.llm import LLMService
from services.scraper import Scraper
from services.source_adapters import SourceAdapterService
from services.web_search import WebSearchService
from utils.dedupe import dedupe_companies, dedupe_jobs
from utils.logging import configure_logging

logger = logging.getLogger(__name__)
console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover fresher-friendly startup software and AI jobs.")
    parser.add_argument("--max-companies", type=int, help="Maximum companies to keep.")
    parser.add_argument("--max-jobs", type=int, help="Maximum jobs per company.")
    parser.add_argument("--provider", choices=["seed", "serpapi", "tavily"], help="Search provider.")
    parser.add_argument("--llm-provider", choices=["mock", "openai", "ollama"], help="LLM extraction provider.")
    parser.add_argument("--dry-run", action="store_true", help="Print and write CSVs without Google Sheets writes.")
    parser.add_argument("--write-sheets", action="store_true", help="Write/upsert rows to Google Sheets.")
    parser.add_argument("--output-csv", action="store_true", default=True, help="Write local output CSV files.")
    parser.add_argument("--database-path", help="SQLite database path for incremental runs.")
    parser.add_argument("--seed-url", action="append", default=[], help="Additional seed URL. Can be passed multiple times.")
    parser.add_argument("--replace-seed-urls", action="store_true", help="Use only --seed-url values instead of default seeds.")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logs.")
    return parser.parse_args()


def apply_args(config: AppConfig, args: argparse.Namespace) -> AppConfig:
    if args.max_companies is not None:
        config.max_companies = args.max_companies
    if args.max_jobs is not None:
        config.max_jobs_per_company = args.max_jobs
    if args.provider:
        config.search_provider = args.provider
    if args.llm_provider:
        config.llm_provider = args.llm_provider
    if args.dry_run:
        config.dry_run = True
        config.write_sheets = False
    if args.write_sheets:
        config.write_sheets = True
        config.dry_run = False
    if args.replace_seed_urls:
        config.seed_urls = args.seed_url
    elif args.seed_url:
        config.seed_urls.extend(args.seed_url)
    if args.database_path:
        config.database_path = args.database_path
    return config


def run(config: AppConfig) -> RunSummary:
    search_agent = SearchAgent(config, WebSearchService(config))
    scraper = Scraper(config)
    source_adapters = SourceAdapterService(config)
    extraction_agent = ExtractionAgent(config, LLMService(config))
    validation_agent = ValidationAgent()
    ranking_agent = RankingAgent()

    summary = RunSummary()
    search_results = search_agent.run()
    summary.total_sources_searched = len(search_results)

    all_companies: list[Company] = []
    all_jobs: list[Job] = []
    for result in tqdm(search_results, desc="Scraping sources"):
        page = source_adapters.fetch(result.url) or scraper.fetch(result.url)
        if page.error:
            summary.errors.append(f"{result.url}: {page.error}")
            continue
        extraction = extraction_agent.run(page)
        all_companies.extend(extraction.companies)
        all_jobs.extend(extraction.jobs)

    if not all_jobs and config.search_provider == "seed":
        logger.info("No jobs found from public seed fetches; using bundled sample pages for mock-mode demonstration.")
        for page in scraper.sample_pages():
            extraction = extraction_agent.run(page)
            all_companies.extend(extraction.companies)
            all_jobs.extend(extraction.jobs)
            summary.total_sources_searched += 1

    companies, _ = dedupe_companies(validation_agent.validate_companies(all_companies))
    companies = ranking_agent.rank_companies(companies, config.max_companies)
    companies_by_name = {company.company_name.lower(): company for company in companies}

    validated_jobs, skipped_invalid = validation_agent.validate_jobs(all_jobs, companies_by_name)
    jobs, skipped_duplicate_jobs = dedupe_jobs(validated_jobs)
    jobs = ranking_agent.rank_jobs(jobs, config.max_jobs_per_company)

    summary.companies_discovered = len(companies)
    summary.jobs_discovered = len(jobs)
    database = JobDatabase(config.database_path)
    try:
        persist_result = database.persist(companies, jobs)
    finally:
        database.close()
    new_jobs = persist_result.new_jobs or []
    summary.new_jobs_discovered = len(new_jobs)
    summary.fresher_friendly_jobs_found = sum(1 for job in jobs if job.fresher_friendly)
    summary.skipped_duplicate_jobs = skipped_duplicate_jobs
    summary.skipped_invalid_jobs = skipped_invalid

    if config.output_csv:
        write_csv(companies, jobs, new_jobs)
    if config.write_sheets:
        result = GoogleSheetsService(config.google_sheets_credentials_file, config.google_sheet_name).upsert(companies, jobs, new_jobs)
        summary.company_rows_written = result.companies_written
        summary.job_rows_written = result.jobs_written
        summary.new_job_rows_written = result.new_jobs_written
        summary.application_tracker_rows_written = result.application_tracker_written

    print_results(companies, jobs, summary, dry_run=config.dry_run)
    return summary


def write_csv(companies: list[Company], jobs: list[Job], new_jobs: list[Job] | None = None) -> None:
    output_dir = Path(__file__).parent / "data"
    output_dir.mkdir(exist_ok=True)
    pd.DataFrame([company.model_dump() for company in companies]).to_csv(output_dir / "output_companies.csv", index=False)
    pd.DataFrame([job_to_csv_row(job) for job in jobs]).to_csv(output_dir / "output_jobs.csv", index=False)
    pd.DataFrame([job_to_csv_row(job) for job in (new_jobs or [])]).to_csv(output_dir / "output_new_jobs.csv", index=False)


def job_to_csv_row(job: Job) -> dict[str, object]:
    row = job.model_dump()
    row["required_skills"] = ", ".join(job.required_skills)
    return row


def print_results(companies: list[Company], jobs: list[Job], summary: RunSummary, dry_run: bool) -> None:
    mode = "DRY RUN" if dry_run else "WRITE MODE"
    console.rule(f"Startup Hiring Agent Summary ({mode})")
    summary_table = Table(show_header=True, header_style="bold")
    summary_table.add_column("Metric")
    summary_table.add_column("Value", justify="right")
    for key, value in summary.model_dump().items():
        if key == "errors":
            value = len(value)
        summary_table.add_row(key.replace("_", " ").title(), str(value))
    console.print(summary_table)

    jobs_table = Table(title="Top Fresher-Friendly Jobs", show_lines=False)
    for column in ["Company", "Role", "Level", "Mode", "Location", "Confidence", "Apply"]:
        jobs_table.add_column(column)
    for job in jobs[:15]:
        jobs_table.add_row(
            job.company_name,
            job.role_title,
            job.experience_level,
            job.work_mode,
            job.location,
            f"{job.confidence_score:.2f}",
            job.application_link or job.job_description_url,
        )
    console.print(jobs_table)

    if summary.errors:
        console.print(f"[yellow]Encountered {len(summary.errors)} fetch/extraction errors. First error: {summary.errors[0]}[/yellow]")
    console.print(f"[green]CSV files written to {(Path(__file__).parent / 'data').resolve()}[/green]")


def main() -> None:
    args = parse_args()
    configure_logging(verbose=args.verbose)
    config = apply_args(load_config(), args)
    run(config)


if __name__ == "__main__":
    main()
