import pytest
from backend.app.core.config import settings
from backend.app.services.email_service import email_service


@pytest.mark.asyncio
async def test_email_template_rendering():
    """Verify that email templates render with correct context and strict styling."""
    context = {
        "email": "analyst@example.com",
        "verify_url": "http://localhost:3000/auth/verify?token=abc123token",
        "backup_code": "ABC12345",
        "token": "abc123token",
        "expire_minutes": 15,
        "project_name": "Financial SEC Due-Diligence CRAG API",
    }
    html = email_service.render_template("magic_link.html", context)
    text = email_service.render_template("magic_link.txt", context)

    # Design assertions
    assert "analyst@example.com" in html
    assert "abc123token" in html
    assert "#F7F7F5" in html  # Parchment background
    assert "border-radius: 0px" in html  # Brutalist square corners
    assert "ABC12345" in text
    assert "http://localhost:3000/auth/verify?token=abc123token" in text


@pytest.mark.asyncio
async def test_email_dispatch_dev_mode():
    """Verify that send_magic_link_email succeeds in dev mode without throwing errors."""
    original_mode = settings.SMTP_DEV_MODE
    try:
        settings.SMTP_DEV_MODE = True
        result = await email_service.send_magic_link_email(
            email="test_analyst@example.com",
            token="test_mock_token_12345678",
        )
        assert result is True
    finally:
        settings.SMTP_DEV_MODE = original_mode
