"""
Client-side data redaction module for PII and secrets detection.

Uses regex patterns with zero external dependencies:
- Custom regex patterns for PII detection
- Gitleaks-based patterns for secrets detection

Fully offline, deterministic, and idempotent.
"""

from .redactor import redact

__all__ = ['redact']
