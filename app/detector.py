"""Simple rule-based security alert detection (no machine learning)."""

import re

RULES = (
    (
        "failed-authentication",
        re.compile(r"failed (?:login|password|authentication)|invalid password", re.I),
        "high",
        "Possible failed authentication attempt",
    ),
    (
        "unauthorized-access",
        re.compile(r"unauthorized|access denied|permission denied", re.I),
        "high",
        "Possible unauthorized access attempt",
    ),
    (
        "service-failure",
        re.compile(r"connection refused|service unavailable|critical error", re.I),
        "medium",
        "Possible service failure",
    ),
)


def detect_alert(message: str) -> dict | None:
    """Return the first matching alert rule, or None for a normal log."""
    for rule, pattern, severity, explanation in RULES:
        if pattern.search(message):
            return {"rule": rule, "severity": severity, "explanation": explanation}
    return None
