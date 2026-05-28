from models.schemas import Company, Job
from services.database import JobDatabase
from utils.dedupe import assign_company_id, assign_job_id


def test_database_tracks_new_jobs_only_once(tmp_path) -> None:
    db = JobDatabase(str(tmp_path / "jobs.sqlite3"))
    company = assign_company_id(Company(company_name="Acme AI", website="https://acme.ai"))
    job = assign_job_id(
        Job(
            company_id=company.company_id,
            company_name=company.company_name,
            role_title="New Grad Software Engineer",
            application_link="https://jobs.lever.co/acme/new-grad-software-engineer",
            job_description_url="https://jobs.lever.co/acme/new-grad-software-engineer",
            source_url="https://acme.ai/careers",
            fresher_friendly=True,
        )
    )

    first = db.persist([company], [job])
    second = db.persist([company], [job])
    db.close()

    assert len(first.new_jobs or []) == 1
    assert len(second.new_jobs or []) == 0
