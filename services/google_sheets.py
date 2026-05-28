from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from models.schemas import Company, Job

logger = logging.getLogger(__name__)


COMPANY_COLUMNS = [
    "company_id",
    "company_name",
    "website",
    "category",
    "description",
    "headquarters",
    "hiring_page",
    "careers_page",
    "source_url",
    "discovered_at",
    "confidence_score",
    "notes",
]

JOB_COLUMNS = [
    "job_id",
    "company_id",
    "company_name",
    "role_title",
    "role_category",
    "experience_level",
    "location",
    "work_mode",
    "application_link",
    "job_description_url",
    "source_url",
    "required_skills",
    "fresher_friendly",
    "confidence_score",
    "discovered_at",
    "notes",
]

NEW_THIS_RUN_COLUMNS = JOB_COLUMNS.copy()

APPLICATION_TRACKER_COLUMNS = [
    "job_id",
    "company_name",
    "role_title",
    "application_link",
    "fit_score",
    "status",
    "applied_date",
    "resume_used",
    "referral_contact",
    "notes",
    "next_action",
]


@dataclass
class UpsertResult:
    companies_written: int = 0
    jobs_written: int = 0
    new_jobs_written: int = 0
    application_tracker_written: int = 0


class GoogleSheetsService:
    def __init__(self, credentials_file: str, spreadsheet_name: str) -> None:
        self.credentials_file = credentials_file
        self.spreadsheet_name = spreadsheet_name

    def upsert(self, companies: list[Company], jobs: list[Job], new_jobs: list[Job] | None = None) -> UpsertResult:
        new_jobs = new_jobs or []
        client = self._client()
        spreadsheet = self._open_or_create_spreadsheet(client)
        companies_ws = self._worksheet(spreadsheet, "Companies", COMPANY_COLUMNS)
        jobs_ws = self._worksheet(spreadsheet, "Jobs", JOB_COLUMNS)
        new_jobs_ws = self._worksheet(spreadsheet, "New This Run", NEW_THIS_RUN_COLUMNS)
        tracker_ws = self._worksheet(spreadsheet, "Application Tracker", APPLICATION_TRACKER_COLUMNS)
        return UpsertResult(
            companies_written=self._upsert_rows(companies_ws, COMPANY_COLUMNS, [self._company_row(c) for c in companies], "company_id"),
            jobs_written=self._upsert_rows(jobs_ws, JOB_COLUMNS, [self._job_row(j) for j in jobs], "job_id"),
            new_jobs_written=self._replace_rows(new_jobs_ws, NEW_THIS_RUN_COLUMNS, [self._job_row(j) for j in new_jobs]),
            application_tracker_written=self._append_missing_rows(
                tracker_ws,
                APPLICATION_TRACKER_COLUMNS,
                [self._tracker_row(j) for j in new_jobs],
                "job_id",
            ),
        )

    def _client(self) -> gspread.Client:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_file(self.credentials_file, scopes=scopes)
        return gspread.authorize(credentials)

    def _open_or_create_spreadsheet(self, client: gspread.Client) -> Any:
        try:
            return client.open(self.spreadsheet_name)
        except gspread.SpreadsheetNotFound:
            logger.info("Creating spreadsheet: %s", self.spreadsheet_name)
            return client.create(self.spreadsheet_name)

    def _worksheet(self, spreadsheet: Any, title: str, columns: list[str]) -> Any:
        try:
            worksheet = spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=title, rows=1000, cols=len(columns))
        self._ensure_header(worksheet, columns)
        return worksheet

    def _ensure_header(self, worksheet: Any, columns: list[str]) -> None:
        values = worksheet.get_all_values()
        if not values:
            worksheet.append_row(columns)
            return
        if values[0] != columns:
            worksheet.update("1:1", [columns])

    def _upsert_rows(self, worksheet: Any, columns: list[str], rows: list[dict[str, Any]], id_column: str) -> int:
        if not rows:
            return 0
        values = worksheet.get_all_values()
        if not values:
            worksheet.append_row(columns)
            values = [columns]
        header = values[0]
        id_index = header.index(id_column)
        existing = {row[id_index]: idx + 2 for idx, row in enumerate(values[1:]) if len(row) > id_index and row[id_index]}

        written = 0
        append_values: list[list[Any]] = []
        for row in rows:
            row_values = [self._cell_value(row.get(column, "")) for column in columns]
            row_id = str(row[id_column])
            if row_id in existing:
                worksheet.update(f"A{existing[row_id]}", [row_values])
            else:
                append_values.append(row_values)
            written += 1
        if append_values:
            worksheet.append_rows(append_values)
        return written

    def _replace_rows(self, worksheet: Any, columns: list[str], rows: list[dict[str, Any]]) -> int:
        worksheet.clear()
        worksheet.append_row(columns)
        if rows:
            worksheet.append_rows([[self._cell_value(row.get(column, "")) for column in columns] for row in rows])
        return len(rows)

    def _append_missing_rows(self, worksheet: Any, columns: list[str], rows: list[dict[str, Any]], id_column: str) -> int:
        if not rows:
            return 0
        values = worksheet.get_all_values()
        if not values:
            worksheet.append_row(columns)
            values = [columns]
        header = values[0]
        id_index = header.index(id_column)
        existing_ids = {row[id_index] for row in values[1:] if len(row) > id_index and row[id_index]}
        append_values: list[list[Any]] = []
        for row in rows:
            row_id = str(row[id_column])
            if row_id in existing_ids:
                continue
            append_values.append([self._cell_value(row.get(column, "")) for column in columns])
            existing_ids.add(row_id)
        if append_values:
            worksheet.append_rows(append_values)
        return len(append_values)

    def _company_row(self, company: Company) -> dict[str, Any]:
        return company.model_dump()

    def _job_row(self, job: Job) -> dict[str, Any]:
        row = job.model_dump()
        row["required_skills"] = ", ".join(job.required_skills)
        return row

    def _tracker_row(self, job: Job) -> dict[str, Any]:
        return {
            "job_id": job.job_id,
            "company_name": job.company_name,
            "role_title": job.role_title,
            "application_link": job.application_link or job.job_description_url,
            "fit_score": job.confidence_score,
            "status": "To Review",
            "applied_date": "",
            "resume_used": "",
            "referral_contact": "",
            "notes": job.notes,
            "next_action": "Review and apply",
        }

    def _cell_value(self, value: Any) -> Any:
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if value is None:
            return ""
        return value
