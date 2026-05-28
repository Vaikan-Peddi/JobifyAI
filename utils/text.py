from __future__ import annotations

import re
from urllib.parse import urlparse


SOFTWARE_ROLE_KEYWORDS = [
    "software",
    "backend",
    "front-end",
    "frontend",
    "full-stack",
    "full stack",
    "ai engineer",
    "artificial intelligence",
    "machine learning",
    "ml engineer",
    "data engineer",
    "applied ai",
    "llm",
    "devops",
    "mobile",
    "ios",
    "android",
]

FRESHER_POSITIVE_KEYWORDS = [
    "intern",
    "internship",
    "new grad",
    "university graduate",
    "graduate software engineer",
    "entry level",
    "junior",
    "associate software engineer",
    "early career",
    "0-1 years",
    "0 - 1 years",
    "0-2 years",
    "0 - 2 years",
    "no prior experience",
    "fresh graduate",
    "fresher",
]

FRESHER_NEGATIVE_KEYWORDS = [
    "senior",
    "staff",
    "principal",
    "lead",
    "manager",
    "architect",
    "5+ years",
    "7+ years",
    "10+ years",
]


def normalize_text(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[\u2010-\u2015]", "-", value)
    value = re.sub(r"[^a-z0-9+.#/\-\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_name(value: str) -> str:
    value = normalize_text(value)
    value = re.sub(r"\b(inc|llc|ltd|corp|corporation|company|co)\b\.?", "", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_role_title(value: str) -> str:
    value = normalize_text(value)
    value = re.sub(r"\b(remote|hybrid|onsite|on-site|us|usa|united states)\b", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -_/")


def domain_from_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def classify_role(title: str, description: str = "") -> str:
    text = normalize_text(f"{title} {description}")
    if any(k in text for k in ["backend", "back end", "api", "infrastructure"]):
        return "Backend"
    if any(k in text for k in ["frontend", "front-end", "front end", "react", "vue"]):
        return "Frontend"
    if any(k in text for k in ["full stack", "full-stack"]):
        return "Full Stack"
    if any(k in text for k in ["machine learning", " ml ", "ml engineer"]):
        return "Machine Learning"
    if any(k in text for k in ["ai engineer", "applied ai", "llm", "artificial intelligence"]):
        return "AI Engineering"
    if "data engineer" in text:
        return "Data Engineering"
    if any(k in text for k in ["devops", "sre", "site reliability"]):
        return "DevOps"
    if any(k in text for k in ["mobile", "ios", "android", "react native"]):
        return "Mobile"
    if "software" in text or "engineer" in text or "developer" in text:
        return "Software Engineering"
    return "Other"


def is_software_related(title: str, description: str = "") -> bool:
    text = normalize_text(f"{title} {description}")
    return any(keyword in text for keyword in SOFTWARE_ROLE_KEYWORDS)


def detect_work_mode(text: str) -> str:
    normalized = normalize_text(text)
    if "remote" in normalized:
        return "Remote"
    if "hybrid" in normalized:
        return "Hybrid"
    if any(k in normalized for k in ["onsite", "on site", "on-site", "office"]):
        return "Onsite"
    return "Unknown"


def detect_experience_level(text: str) -> str:
    normalized = normalize_text(text)
    if "intern" in normalized or "internship" in normalized:
        return "Intern"
    if any(k in normalized for k in ["new grad", "university graduate", "fresh graduate"]):
        return "New Grad"
    if "junior" in normalized or "associate software engineer" in normalized:
        return "Junior"
    if "entry level" in normalized:
        return "Entry Level"
    if any(k in normalized for k in ["0-1 years", "0 - 1 years", "0-2 years", "0 - 2 years"]):
        return "0-2 Years"
    if any(k in normalized for k in FRESHER_NEGATIVE_KEYWORDS):
        return "Not Fresher Friendly"
    return "Unknown"


def fresher_signal_score(title: str, description: str = "") -> tuple[bool, float, str]:
    text = normalize_text(f"{title} {description}")
    positive = [keyword for keyword in FRESHER_POSITIVE_KEYWORDS if keyword in text]
    negative = [keyword for keyword in FRESHER_NEGATIVE_KEYWORDS if keyword in text]
    score = len(positive) * 2 - len(negative) * 2
    if positive and negative:
        friendly = score > 0
        notes = (
            f"Mixed fresher signals. Positive: {', '.join(positive)}. "
            f"Negative: {', '.join(negative)}. Score={score}."
        )
        return friendly, max(0.15, min(0.85, 0.5 + score * 0.1)), notes
    if positive:
        return True, min(1.0, 0.65 + len(positive) * 0.08), f"Fresher-friendly wording: {', '.join(positive)}."
    if negative:
        return False, 0.15, f"Senior-only wording: {', '.join(negative)}."
    return False, 0.35, "No explicit fresher-friendly wording found."


def infer_company_name_from_url(url: str) -> str:
    domain = domain_from_url(url)
    if not domain:
        return "Unknown"
    stem = domain.split(".")[0]
    return stem.replace("-", " ").replace("_", " ").title()
