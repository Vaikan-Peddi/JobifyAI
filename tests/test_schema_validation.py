import pytest
from pydantic import ValidationError

from models.schemas import Company, Job


def test_company_confidence_must_be_between_zero_and_one() -> None:
    with pytest.raises(ValidationError):
        Company(company_name="Acme AI", confidence_score=1.5)


def test_job_role_category_is_restricted() -> None:
    with pytest.raises(ValidationError):
        Job(
            company_name="Acme AI",
            role_title="New Grad Software Engineer",
            role_category="Sales",
            application_link="https://example.com/job",
            job_description_url="https://example.com/job",
            source_url="https://example.com/careers",
        )


def test_minimal_valid_job() -> None:
    job = Job(
        company_name="Acme AI",
        role_title="Software Engineer Intern",
        application_link="https://example.com/job",
        job_description_url="https://example.com/job",
        source_url="https://example.com/careers",
    )

    assert job.company_name == "Acme AI"
    assert job.required_skills == []
