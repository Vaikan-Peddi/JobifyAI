from services.google_sheets import COMPANY_COLUMNS, GoogleSheetsService, JOB_COLUMNS


class FakeWorksheet:
    def __init__(self) -> None:
        self.values: list[list[str]] = []

    def get_all_values(self) -> list[list[str]]:
        return self.values

    def append_row(self, row: list[str]) -> None:
        self.values.append([str(value) for value in row])

    def append_rows(self, rows: list[list[str]]) -> None:
        self.values.extend([[str(value) for value in row] for row in rows])

    def update(self, range_name: str, rows: list[list[str]]) -> None:
        if range_name == "1:1":
            if self.values:
                self.values[0] = [str(value) for value in rows[0]]
            else:
                self.values.append([str(value) for value in rows[0]])
            return
        row_index = int(range_name[1:]) - 1
        while len(self.values) <= row_index:
            self.values.append([])
        self.values[row_index] = [str(value) for value in rows[0]]

    def clear(self) -> None:
        self.values.clear()


def test_upsert_rows_updates_existing_company() -> None:
    worksheet = FakeWorksheet()
    service = GoogleSheetsService("unused.json", "unused")
    service._ensure_header(worksheet, COMPANY_COLUMNS)

    first = {"company_id": "cmp_1", "company_name": "Old Name"}
    second = {"company_id": "cmp_1", "company_name": "New Name"}

    assert service._upsert_rows(worksheet, COMPANY_COLUMNS, [first], "company_id") == 1
    assert service._upsert_rows(worksheet, COMPANY_COLUMNS, [second], "company_id") == 1

    assert len(worksheet.values) == 2
    assert worksheet.values[1][COMPANY_COLUMNS.index("company_name")] == "New Name"


def test_upsert_rows_appends_new_job() -> None:
    worksheet = FakeWorksheet()
    service = GoogleSheetsService("unused.json", "unused")
    service._ensure_header(worksheet, JOB_COLUMNS)

    first = {"job_id": "job_1", "company_id": "cmp_1", "role_title": "Software Engineer Intern"}
    second = {"job_id": "job_2", "company_id": "cmp_1", "role_title": "Entry Level AI Engineer"}

    service._upsert_rows(worksheet, JOB_COLUMNS, [first, second], "job_id")

    assert len(worksheet.values) == 3
    assert worksheet.values[2][JOB_COLUMNS.index("job_id")] == "job_2"


def test_application_tracker_only_appends_missing_jobs() -> None:
    worksheet = FakeWorksheet()
    service = GoogleSheetsService("unused.json", "unused")
    columns = ["job_id", "company_name", "status"]
    service._ensure_header(worksheet, columns)

    first = {"job_id": "job_1", "company_name": "Acme", "status": "To Review"}
    changed = {"job_id": "job_1", "company_name": "Acme", "status": "Applied"}

    assert service._append_missing_rows(worksheet, columns, [first], "job_id") == 1
    assert service._append_missing_rows(worksheet, columns, [changed], "job_id") == 0
    assert worksheet.values[1][columns.index("status")] == "To Review"
