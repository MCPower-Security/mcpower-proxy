"""
Constants for client-side redaction.
"""

# PII entity type to placeholder mappings
PII_PLACEHOLDERS = {
    "CREDIT_CARD": "[REDACTED-CREDIT-CARD]",
    "CRYPTO_ADDRESS": "[REDACTED-CRYPTO]",
    "EMAIL_ADDRESS": "[REDACTED-EMAIL]",
    "IBAN": "[REDACTED-IBAN]",
    "IP_ADDRESS": "[REDACTED-IP]",
    "LOCATION": "[REDACTED-LOCATION]",
    "PERSON": "[REDACTED-PERSON]",
    "PHONE_NUMBER": "[REDACTED-PHONE]",
    "MEDICAL_LICENSE": "[REDACTED-MEDICAL-LICENSE]",
    "URL": "[REDACTED-URL]",
    "US_BANK_NUMBER": "[REDACTED-BANK-NUMBER]",
    "US_DRIVER_LICENSE": "[REDACTED-DRIVER-LICENSE]",
    "US_ITIN": "[REDACTED-ITIN]",
    "US_PASSPORT": "[REDACTED-PASSPORT]",
    "US_SSN": "[REDACTED-SSN]",
    # Default fallback for any other entity types
    "DEFAULT": "[REDACTED-PII]"
}

# Secrets detection placeholder
SECRETS_PLACEHOLDER = "[REDACTED-SECRET]"

# Pattern to match existing redaction placeholders (for idempotency)
REDACTION_PLACEHOLDER_PATTERN = r'\[REDACTED-[A-Z-]+\]'

# Zero-width characters to normalize
ZERO_WIDTH_CHARS = [
    '\u200b',  # Zero Width Space
    '\u200c',  # Zero Width Non-Joiner
    '\u200d',  # Zero Width Joiner
    '\ufeff',  # Zero Width No-Break Space (BOM)
]
