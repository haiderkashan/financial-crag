import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings
from backend.app.services.email_service import email_service


async def run_email_verification() -> bool:
    """End-to-end verification for Sub-Phase 1.3 email dispatch."""
    print("=" * 70)
    print("SUB-PHASE 1.3: ASYNCHRONOUS SMTP EMAIL DISPATCH VERIFICATION")
    print("=" * 70)

    test_email = "analyst_qa@example.com"
    test_token = f"sec_test_token_{uuid4().hex}"

    print(f"Target Recipient: {test_email}")
    print(f"SMTP_DEV_MODE:    {settings.SMTP_DEV_MODE}")
    print(f"SMTP Host:        {settings.SMTP_HOST or 'None (Using Dev Mode)'}")
    print(f"SMTP Port:        {settings.SMTP_PORT}")
    print(f"SMTP Sender:      {settings.SMTP_FROM_EMAIL}")
    print("-" * 70)

    # 1. Template Rendering Verification
    print("\n[TEST 1] Testing Jinja2 Template Compilation & Variable Interpolation...")
    try:
        context = {
            "email": test_email,
            "verify_url": f"{settings.FRONTEND_URL}/auth/verify?token={test_token}",
            "backup_code": test_token[:8].upper(),
            "token": test_token,
            "expire_minutes": settings.MAGIC_LINK_EXPIRE_MINUTES,
            "project_name": settings.PROJECT_NAME,
        }
        html_output = email_service.render_template("magic_link.html", context)
        text_output = email_service.render_template("magic_link.txt", context)

        assert test_email in html_output
        assert test_token in html_output
        assert "border-radius: 0px" in html_output
        assert "#F7F7F5" in html_output
        assert test_email in text_output
        assert test_token in text_output
        print("[PASS] Both HTML and Plain-Text templates rendered and validated.")
    except Exception as e:
        print(f"[FAIL] Template rendering failed: {e}")
        return False

    # 2. Dispatch Verification (Dev Mode or Live SMTP)
    print("\n[TEST 2] Executing Asynchronous Email Dispatch...")
    try:
        success = await email_service.send_magic_link_email(
            email=test_email,
            token=test_token,
        )
        if success:
            print("[PASS] Email dispatch executed successfully.")
        else:
            print("[FAIL] Email dispatch returned False.")
            return False
    except Exception as e:
        print(f"[FAIL] Unexpected error during email dispatch: {e}")
        return False

    print("\n" + "=" * 70)
    print("[ALL PASS] Sub-Phase 1.3 Asynchronous Email Dispatcher Verified!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    result = asyncio.run(run_email_verification())
    sys.exit(0 if result else 1)
