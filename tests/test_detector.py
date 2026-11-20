from app.detector import detect_alert


def test_failed_login_detected():
    result = detect_alert("Failed login for account alice")
    assert result is not None
    assert result["rule"] == "failed-authentication"
    assert result["severity"] == "high"


def test_permission_denied_detected():
    assert detect_alert("Permission denied when opening file")["rule"] == "unauthorized-access"


def test_service_failure_detected():
    assert detect_alert("Connection refused on port 5432")["rule"] == "service-failure"


def test_normal_log_not_flagged():
    assert detect_alert("User completed a routine backup successfully") is None
