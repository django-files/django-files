"""Shared helpers for the test suite.

Credentials are generated at import time rather than hard-coded, so no real-
looking secret ever lives in the source tree (keeps secret scanners quiet) while
staying constant within a single test run so create/login pairs match.
"""

import secrets

# Strong, random password used wherever a test creates and authenticates a user.
# The fixed suffix guarantees it satisfies Django's AUTH_PASSWORD_VALIDATORS
# (length, mixed case, digit, symbol, not all-numeric, not a common password).
TEST_PASSWORD = secrets.token_urlsafe(24) + "aA1!"

# A different value for "wrong password" negative tests.
WRONG_PASSWORD = secrets.token_urlsafe(8) + "zZ9?"

# Intentionally weak: used to assert the password validators reject it.
WEAK_PASSWORD = "123456"  # nosec B105  # NOSONAR
