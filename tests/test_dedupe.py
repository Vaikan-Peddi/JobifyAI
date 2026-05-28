from models.schemas import Company, Job
from utils.dedupe import assign_company_id, assign_job_id, dedupe_companies, dedupe_jobs


def test_company_ids_are_stable_by_domain() -> None:
    first = assign_company_id(Company(company_name="Acme AI", website="https://www.acme.ai/careers"))
    second = assign_company_id(Company(company_name="Acme AI Inc.", website="https://acme.ai/jobs"))

    assert first.company_id == second.company_id


def test_dedupe_jobs_by_company_role_and_link() -> None:
    company = assign_company_id(Company(company_name="Acme AI", website="https://acme.ai"))
    jobs = [
        assign_job_id(
            Job(
                company_id=company.company_id,
                company_name="Acme AI",
                role_title="New Grad Software Engineer",
                application_link="https://jobs.lever.co/acme/new-grad-software",
                job_description_url="https://jobs.lever.co/acme/new-grad-software",
                source_url="https://acme.ai/careers",
                fresher_friendly=True,
            )
        ),
        assign_job_id(
            Job(
                company_id=company.company_id,
                company_name="Acme AI Inc.",
                role_title="New Grad Software Engineer - Remote",
                application_link="https://jobs.lever.co/acme/new-grad-software",
                job_description_url="https://jobs.lever.co/acme/new-grad-software",
                source_url="https://acme.ai/careers",
                fresher_friendly=True,
            )
        ),
    ]

    deduped, duplicates = dedupe_jobs(jobs)

    assert len(deduped) == 1
    assert duplicates == 1


def test_dedupe_companies_keeps_higher_confidence() -> None:
    low = Company(company_name="Forgebase", website="https://forgebase.example", confidence_score=0.2)
    high = Company(company_name="Forgebase", website="https://www.forgebase.example/careers", confidence_score=0.9)

    deduped, duplicates = dedupe_companies([low, high])

    assert duplicates == 1
    assert deduped[0].confidence_score == 0.9
