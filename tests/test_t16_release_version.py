"""T16 Release Version Verification Tests.

Automated verification that the CSMS v1.0.0 release identity is properly
implemented and consistently reported across all endpoints and interfaces.
"""

import json
import pytest


def test_health_endpoint_reports_correct_application_name(client):
    """Verify /health identifies the application as CSMS."""
    response = client.get("/health")
    assert response.status_code == 200, "/health should return 200 OK"
    
    data = json.loads(response.data)
    assert "application" in data, "Response should include 'application' field"
    assert data["application"] == "CSMS", "Application should be identified as CSMS"


def test_health_endpoint_reports_version_1_0_0(client):
    """Verify /health reports the correct release version 1.0.0."""
    response = client.get("/health")
    assert response.status_code == 200, "/health should return 200 OK"
    
    data = json.loads(response.data)
    assert "version" in data, "Response should include 'version' field"
    assert data["version"] == "1.0.0", "Version should be 1.0.0"


def test_health_endpoint_reports_healthy_status(client):
    """Verify /health reports a healthy/ok status."""
    response = client.get("/health")
    assert response.status_code == 200, "/health should return 200 OK"
    
    data = json.loads(response.data)
    assert "status" in data, "Response should include 'status' field"
    assert data["status"] in ["ok", "healthy", "OK", "HEALTHY"], \
        "Status should indicate health (ok or healthy)"


def test_health_endpoint_does_not_expose_secrets(client):
    """Verify /health does not expose sensitive information."""
    response = client.get("/health")
    data = json.loads(response.data)
    response_text = response.data.decode('utf-8')
    
    # Check for common sensitive values that should NOT be exposed
    sensitive_patterns = [
        "secret",
        "password",
        "token",
        "key",
        "credential",
        "DATABASE_PATH",
        "__pycache__",
        ".env",
        "traceback",
        "exception",
    ]
    
    for pattern in sensitive_patterns:
        assert pattern.lower() not in response_text.lower(), \
            f"/health should not expose: {pattern}"


def test_health_endpoint_json_response(client):
    """Verify /health returns valid JSON."""
    response = client.get("/health")
    assert response.content_type.lower().startswith("application/json"), \
        "/health should return JSON response"
    
    # Should not raise an exception
    data = json.loads(response.data)
    assert isinstance(data, dict), "Response should be a JSON object"


def test_home_page_displays_version_1_0_0(client):
    """Verify the home page UI displays v1.0.0."""
    response = client.get("/")
    assert response.status_code == 200, "Home page should load successfully"
    
    page_content = response.data.decode('utf-8')
    # Check for version display (various possible formats)
    version_found = any([
        "1.0.0" in page_content,
        "v1.0.0" in page_content,
    ])
    assert version_found, "Home page should display version 1.0.0"


def test_home_page_displays_application_name(client):
    """Verify the home page displays the full application name."""
    response = client.get("/")
    assert response.status_code == 200, "Home page should load successfully"
    
    page_content = response.data.decode('utf-8')
    assert "Community Services Management System" in page_content or "CSMS" in page_content, \
        "Home page should display the application name"


def test_version_consistency_across_endpoints(client):
    """Verify version 1.0.0 is consistently reported everywhere."""
    # Get version from /health
    health_response = client.get("/health")
    health_data = json.loads(health_response.data)
    health_version = health_data.get("version")
    
    # Get version from home page
    home_response = client.get("/")
    home_content = home_response.data.decode('utf-8')
    
    # Both should report 1.0.0
    assert health_version == "1.0.0", "/health should report 1.0.0"
    assert "1.0.0" in home_content, "Home page should show 1.0.0"


def test_config_app_version_is_1_0_0(app):
    """Verify the Flask app config has APP_VERSION = 1.0.0."""
    assert hasattr(app.config, "__getitem__"), "Config should be dict-like"
    assert "APP_VERSION" in app.config, "Config should have APP_VERSION"
    assert app.config["APP_VERSION"] == "1.0.0", "APP_VERSION should be 1.0.0"


def test_config_app_short_name_is_csms(app):
    """Verify the Flask app config has APP_SHORT_NAME = CSMS."""
    assert "APP_SHORT_NAME" in app.config, "Config should have APP_SHORT_NAME"
    assert app.config["APP_SHORT_NAME"] == "CSMS", "APP_SHORT_NAME should be CSMS"


def test_config_app_name_is_community_services(app):
    """Verify the Flask app config has full application name."""
    assert "APP_NAME" in app.config, "Config should have APP_NAME"
    assert "Community Services Management System" in app.config["APP_NAME"], \
        "APP_NAME should contain full application name"
