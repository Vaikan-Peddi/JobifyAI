from agents.validation_agent import ValidationAgent
from models.schemas import Job
from utils.text import detect_experience_level, fresher_signal_score


def test_positive_fresher_signals_win_for_new_grad() -> None:
    friendly, score, notes = fresher_signal_score(
        "New Grad Software Engineer",
        "Early career role for fresh graduates with 0-2 years experience.",
    )

    assert friendly is True
    assert score > 0.7
    assert "new grad" in notes.lower()


def test_senior_only_role_is_rejected() -> None:
    job = Job(
        company_name="Acme AI",
        company_id="cmp_123",
        role_title="Senior Staff Software Engineer",
        application_link="https://example.com/job",
        job_description_url="https://example.com/job",
        source_url="https://example.com/careers",
        experience_level="Unknown",
    )

    assert ValidationAgent()._is_valid_job(job) is False


def test_mixed_signals_are_explained() -> None:
    friendly, score, notes = fresher_signal_score(
        "Junior Machine Learning Engineer",
        "This page also mentions senior engineers, but this job is junior.",
    )

    assert friendly is False
    assert 0.15 <= score <= 0.85
    assert "Mixed fresher signals" in notes


def test_experience_level_detection() -> None:
    assert detect_experience_level("Software Engineer Intern, summer internship") == "Intern"
    assert detect_experience_level("Entry Level AI Engineer, 0-1 years") == "Entry Level"
