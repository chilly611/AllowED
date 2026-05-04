"""
VA Lighthouse API Client — Live Sandbox Integration
=====================================================
Connects to the real VA Lighthouse APIs using sandbox credentials.

Currently supports:
  - Veteran Confirmation API (sandbox key active)
  - Benefits Intake API (key needed — register separately)

Credentials stored in .env file (never committed to version control).

Rate limit: 60 requests/minute per consumer key.
"""

import json
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

# Try to import requests; if not available, provide helpful error
try:
    import requests
except ImportError:
    raise ImportError(
        "Install requests: pip install requests --break-system-packages"
    )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def load_env(env_path: str = None) -> dict:
    """Load credentials from .env file."""
    if env_path is None:
        # Check common locations
        candidates = [
            os.path.join(os.path.dirname(__file__), ".env"),
            os.path.join(os.path.dirname(__file__), "mnt", "VA Project", ".env"),
            "/sessions/friendly-bold-galileo/mnt/VA Project/.env",
        ]
        for path in candidates:
            if os.path.exists(path):
                env_path = path
                break

    if not env_path or not os.path.exists(env_path):
        return {}

    env = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    return env


@dataclass
class APIConfig:
    """API configuration loaded from .env."""
    vet_confirm_sandbox_key: str = ""
    benefits_intake_sandbox_key: str = ""
    vet_confirm_prod_key: str = ""
    benefits_intake_prod_key: str = ""

    @classmethod
    def from_env(cls, env_path: str = None) -> "APIConfig":
        env = load_env(env_path)
        return cls(
            vet_confirm_sandbox_key=env.get("VA_VET_CONFIRM_SANDBOX_KEY", ""),
            benefits_intake_sandbox_key=env.get("VA_BENEFITS_INTAKE_SANDBOX_KEY", ""),
            vet_confirm_prod_key=env.get("VA_VET_CONFIRM_PROD_KEY", ""),
            benefits_intake_prod_key=env.get("VA_BENEFITS_INTAKE_PROD_KEY", ""),
        )


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Tracks VA Lighthouse rate limits from response headers.
    60 requests/minute per consumer key.
    Pauses automatically when remaining < safety_threshold.
    """

    def __init__(self, safety_threshold: int = 5):
        self.limit = 60
        self.remaining = 60
        self.reset_seconds = 60
        self.safety_threshold = safety_threshold
        self.last_request_time = 0.0

    def update_from_headers(self, headers: dict):
        """Parse rate limit headers from API response."""
        self.limit = int(headers.get("RateLimit-Limit", self.limit))
        self.remaining = int(headers.get("RateLimit-Remaining", self.remaining))
        self.reset_seconds = int(headers.get("RateLimit-Reset", self.reset_seconds))

    def wait_if_needed(self):
        """Block if we're close to the rate limit."""
        if self.remaining <= self.safety_threshold:
            wait_time = self.reset_seconds + 1
            print(f"  [Rate Limit] Only {self.remaining} requests left. "
                  f"Waiting {wait_time}s for reset...")
            time.sleep(wait_time)
            self.remaining = self.limit  # Assume reset happened

    @property
    def status(self) -> str:
        return f"{self.remaining}/{self.limit} (reset in {self.reset_seconds}s)"


# ---------------------------------------------------------------------------
# Veteran Confirmation API Client
# ---------------------------------------------------------------------------

class VeteranConfirmationClient:
    """
    VA Lighthouse Veteran Confirmation API.

    Verifies whether an individual is a veteran based on PII.
    Use this BEFORE certification to confirm veteran status.

    Sandbox: https://sandbox-api.va.gov/services/veteran-confirmation/v1
    Production: https://api.va.gov/services/veteran-confirmation/v1

    Required fields: ssn, first_name, last_name, birth_date,
                     streetAddressLine1, city, state, zipCode, country
    """

    SANDBOX_URL = "https://sandbox-api.va.gov/services/veteran-confirmation/v1"
    PRODUCTION_URL = "https://api.va.gov/services/veteran-confirmation/v1"

    def __init__(self, config: APIConfig, mode: str = "sandbox"):
        self.mode = mode
        self.config = config

        if mode == "sandbox":
            self.base_url = self.SANDBOX_URL
            self.api_key = config.vet_confirm_sandbox_key
        elif mode == "production":
            self.base_url = self.PRODUCTION_URL
            self.api_key = config.vet_confirm_prod_key
        else:
            raise ValueError(f"Invalid mode: {mode}. Use 'sandbox' or 'production'.")

        if not self.api_key:
            raise ValueError(
                f"No API key found for mode '{mode}'. "
                f"Check .env file for VA_VET_CONFIRM_{'SANDBOX' if mode == 'sandbox' else 'PROD'}_KEY."
            )

        self.rate_limiter = RateLimiter()
        self.request_log: list[dict] = []

    def confirm_veteran_status(
        self,
        ssn: str,
        first_name: str,
        last_name: str,
        birth_date: str,       # YYYY-MM-DD format
        street_address: str,
        city: str,
        state: str,
        zip_code: str,
        country: str = "US",
        middle_name: str = "",
        gender: str = "",
    ) -> dict:
        """
        Check if an individual has veteran status.

        Returns:
            {
                "veteran_status": "confirmed" | "not confirmed",
                "not_confirmed_reason": "..." (if not confirmed),
                "api_status": 200,
                "rate_limit": "56/60 (reset in 37s)"
            }
        """

        # Build request payload
        payload = {
            "ssn": ssn.replace("-", ""),  # Strip dashes
            "first_name": first_name,
            "last_name": last_name,
            "birth_date": birth_date,
            "streetAddressLine1": street_address,
            "city": city,
            "state": state,
            "zipCode": zip_code,
            "country": country,
        }

        if middle_name:
            payload["middle_name"] = middle_name
        if gender:
            payload["gender"] = gender

        # Check rate limit before sending
        self.rate_limiter.wait_if_needed()

        # Send request
        headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{self.base_url}/status",
                headers=headers,
                json=payload,
                timeout=30,
            )

            # Update rate limiter
            self.rate_limiter.update_from_headers(dict(response.headers))

            # Log the request (without sensitive data)
            self.request_log.append({
                "timestamp": datetime.now().isoformat(),
                "endpoint": "/status",
                "status_code": response.status_code,
                "name": f"{first_name} {last_name}",
                "rate_remaining": self.rate_limiter.remaining,
            })

            if response.status_code == 200:
                data = response.json()
                return {
                    "veteran_status": data.get("veteran_status", "unknown"),
                    "not_confirmed_reason": data.get("not_confirmed_reason", ""),
                    "api_status": 200,
                    "rate_limit": self.rate_limiter.status,
                }
            elif response.status_code == 429:
                return {
                    "veteran_status": "error",
                    "not_confirmed_reason": "Rate limit exceeded",
                    "api_status": 429,
                    "rate_limit": self.rate_limiter.status,
                    "retry_after": self.rate_limiter.reset_seconds,
                }
            else:
                error_data = response.json() if response.text else {}
                return {
                    "veteran_status": "error",
                    "not_confirmed_reason": json.dumps(error_data),
                    "api_status": response.status_code,
                    "rate_limit": self.rate_limiter.status,
                }

        except requests.exceptions.Timeout:
            return {
                "veteran_status": "error",
                "not_confirmed_reason": "Request timed out",
                "api_status": 0,
                "rate_limit": self.rate_limiter.status,
            }
        except requests.exceptions.ConnectionError as e:
            return {
                "veteran_status": "error",
                "not_confirmed_reason": f"Connection error: {e}",
                "api_status": 0,
                "rate_limit": self.rate_limiter.status,
            }


# ---------------------------------------------------------------------------
# Pipeline Integration Helper
# ---------------------------------------------------------------------------

def verify_veteran_before_certification(
    client: VeteranConfirmationClient,
    student_ssn: str,
    first_name: str,
    last_name: str,
    birth_date: str,
    street_address: str = "On File",
    city: str = "San Diego",
    state: str = "CA",
    zip_code: str = "92182",  # SDSU zip
) -> tuple[bool, str]:
    """
    Pre-certification check: verify veteran status before processing.

    Returns (can_proceed, message).
    - If confirmed: (True, "Veteran status confirmed")
    - If not confirmed: (False, reason) — route to SCO queue
    - If error: (False, error) — retry or manual check
    """
    result = client.confirm_veteran_status(
        ssn=student_ssn,
        first_name=first_name,
        last_name=last_name,
        birth_date=birth_date,
        street_address=street_address,
        city=city,
        state=state,
        zip_code=zip_code,
    )

    status = result["veteran_status"]

    if status == "confirmed":
        return True, "Veteran status confirmed via VA Lighthouse API."
    elif status == "not confirmed":
        reason = result.get("not_confirmed_reason", "Unknown")
        return False, (
            f"Veteran status NOT confirmed. Reason: {reason}. "
            f"Route to SCO for manual verification."
        )
    else:
        return False, (
            f"API error (HTTP {result['api_status']}): "
            f"{result.get('not_confirmed_reason', 'Unknown error')}. "
            f"Rate limit: {result['rate_limit']}."
        )


# ---------------------------------------------------------------------------
# Test — Live Sandbox Connection
# ---------------------------------------------------------------------------

def test_sandbox_connection():
    """
    Test the live sandbox connection.
    Uses the API key from .env to hit the real VA sandbox.
    """

    print("=" * 70)
    print("  VA LIGHTHOUSE — SANDBOX CONNECTION TEST")
    print("=" * 70)

    # Load config
    config = APIConfig.from_env()

    if not config.vet_confirm_sandbox_key:
        print("  ERROR: No sandbox key found in .env file.")
        print("  Create .env with: VA_VET_CONFIRM_SANDBOX_KEY=your_key_here")
        return False

    print(f"  API Key: ...{config.vet_confirm_sandbox_key[-8:]}")
    print(f"  Mode: sandbox")
    print(f"  Endpoint: {VeteranConfirmationClient.SANDBOX_URL}")

    # Create client
    client = VeteranConfirmationClient(config, mode="sandbox")

    # Test 1: Basic connectivity
    print(f"\n--- Test 1: Basic API call ---")
    result = client.confirm_veteran_status(
        ssn="000000000",          # Fake SSN for connectivity test
        first_name="Test",
        last_name="User",
        birth_date="1990-01-01",
        street_address="123 Test St",
        city="San Diego",
        state="CA",
        zip_code="92182",
    )

    print(f"  Status: {result['veteran_status']}")
    print(f"  Reason: {result.get('not_confirmed_reason', 'N/A')}")
    print(f"  HTTP: {result['api_status']}")
    print(f"  Rate: {result['rate_limit']}")

    api_working = result["api_status"] == 200
    print(f"\n  Connection: {'SUCCESS' if api_working else 'FAILED'}")

    # Test 2: Pipeline integration
    print(f"\n--- Test 2: Pipeline integration helper ---")
    can_proceed, message = verify_veteran_before_certification(
        client=client,
        student_ssn="000-00-0000",
        first_name="Test",
        last_name="Student",
        birth_date="1995-05-15",
    )
    print(f"  Can proceed: {can_proceed}")
    print(f"  Message: {message}")

    # Test 3: Rate limit tracking
    print(f"\n--- Test 3: Rate limit tracking ---")
    print(f"  Limit: {client.rate_limiter.limit}/min")
    print(f"  Remaining: {client.rate_limiter.remaining}")
    print(f"  Reset in: {client.rate_limiter.reset_seconds}s")

    # Summary
    print(f"\n  Requests made: {len(client.request_log)}")

    print("\n" + "=" * 70)

    if api_working:
        print("  SANDBOX IS LIVE. Ready for real test data.")
        print("  Check your email (paulina0101@gmail.com) for sandbox")
        print("  test personas — VA sends specific SSNs that return")
        print("  'confirmed' status in sandbox mode.")
    else:
        print("  SANDBOX CONNECTION FAILED. Check API key and network.")

    print("=" * 70)

    return api_working


if __name__ == "__main__":
    test_sandbox_connection()
