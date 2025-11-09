"""
Lightweight PII detection using only regex patterns.
No external dependencies beyond Python's built-in re module.
"""

import re
from typing import List, NamedTuple


class PIIMatch(NamedTuple):
    """Represents a detected PII match."""
    start: int
    end: int
    entity_type: str
    confidence: float


class URLDetector:
    """URL detector with protocol requirement and intelligent boundary detection."""

    def __init__(self):
        # Common protocols that use :// format
        protocols = r'(?:https?|ftps?|sftp|ssh|wss?|git|file|telnet|ldaps?|smb|nfs)'
        self.pattern = re.compile(
            rf'{protocols}://[^\s]+',
            re.IGNORECASE
        )
        self.sentence_enders = '.,:;!?\'"'

    def extract(self, text: str) -> List[PIIMatch]:
        """Extract URLs with proper boundary detection."""
        matches = []
        for match in self.pattern.finditer(text):
            cleaned_url = self._clean_url(match.group())
            if cleaned_url:
                end = match.start() + len(cleaned_url)
                matches.append(PIIMatch(
                    start=match.start(),
                    end=end,
                    entity_type='URL',
                    confidence=0.85
                ))
        return matches

    def _clean_url(self, url: str) -> str:
        """Remove trailing punctuation intelligently."""
        url = url.rstrip(self.sentence_enders)

        # Balance paired delimiters
        for opener, closer in [('(', ')'), ('[', ']'), ('{', '}')]:
            while url.endswith(closer):
                if url.count(opener) >= url.count(closer):
                    break
                url = url[:-1]

        return url


class PIIDetector:
    """Lightweight PII detector using only regex patterns."""

    def __init__(self):
        # Compile regex patterns for better performance
        self.patterns = {
            'CREDIT_CARD': re.compile(
                r'\b(?:'
                r'4[0-9]{3}[-\s]?[0-9]{4}[-\s]?[0-9]{4}[-\s]?[0-9]{4}(?:[0-9]{3})?|'  # Visa with formatting
                r'5[1-5][0-9]{2}[-\s]?[0-9]{4}[-\s]?[0-9]{4}[-\s]?[0-9]{4}|'  # MasterCard with formatting
                r'3[47][0-9]{2}[-\s]?[0-9]{6}[-\s]?[0-9]{5}|'  # Amex with formatting
                r'4[0-9]{12}(?:[0-9]{3})?|'  # Visa without formatting
                r'5[1-5][0-9]{14}|'  # MasterCard without formatting
                r'3[47][0-9]{13}|'  # American Express without formatting
                r'3[0-9]{13}|'  # Diners Club
                r'6(?:011|5[0-9]{2})[0-9]{12}'  # Discover
                r')\b'
            ),
            # IBAN (International Bank Account Number)
            'IBAN': re.compile(
                r'\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}([A-Z0-9]?){0,16}\b'
            ),
        }

    def validate_credit_card(self, number: str) -> bool:
        """Validate credit card using Luhn algorithm"""
        digits = re.sub(r'\D', '', number)  # Remove non-digits
        if not digits:
            return False

        total = 0
        for i, digit in enumerate(reversed(digits)):
            n = int(digit)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        return total % 10 == 0

    def validate_iban(self, iban: str) -> bool:
        """Validate IBAN using MOD-97 algorithm"""
        # Remove spaces and convert to uppercase
        iban = re.sub(r'\s', '', iban).upper()

        # IBAN must be at least 15 characters
        if len(iban) < 15:
            return False

        # Move first 4 characters to the end
        rearranged_iban = iban[4:] + iban[:4]

        # Convert letters to numbers (A=10, B=11, ..., Z=35)
        numeric_iban = ""
        for char in rearranged_iban:
            if char.isdigit():
                numeric_iban += char
            elif char.isalpha():
                numeric_iban += str(ord(char) - ord('A') + 10)
            else:
                return False  # Invalid character

        try:
            return int(numeric_iban) % 97 == 1
        except ValueError:
            return False

    def analyze(self, text: str) -> List[PIIMatch]:
        """
        Analyze text and return detected PII matches.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of PIIMatch objects with detected PII
        """
        matches = []

        # Extract other PII using regex patterns
        for entity_type, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                matched_text = match.group()

                # Calculate base confidence
                confidence = self._calculate_confidence(entity_type, matched_text)

                # Validation gates - boost confidence for validated entities
                if entity_type == 'CREDIT_CARD':
                    if not self.validate_credit_card(matched_text):
                        continue  # Skip if Luhn validation fails
                    confidence = 0.99  # Near-certainty for validated credit cards

                if entity_type == 'IBAN':
                    if not self.validate_iban(matched_text):
                        continue  # Skip if MOD-97 validation fails
                    confidence = 0.99  # Near-certainty for validated IBANs

                matches.append(PIIMatch(
                    start=match.start(),
                    end=match.end(),
                    entity_type=entity_type,
                    confidence=confidence
                ))

        # Sort by start position and remove overlaps (keep highest confidence)
        return self._resolve_overlaps(matches)

    def _calculate_confidence(self, entity_type: str, matched_text: str) -> float:
        """Calculate confidence score based on entity type and matched text."""
        # Base confidence scores
        base_scores = {
            'CREDIT_CARD': 0.85,  # Will be 0.99 after Luhn validation
            'IBAN': 0.85,  # Will be 0.99 after MOD-97 validation
        }

        return base_scores.get(entity_type, 0.5)

    def _resolve_overlaps(self, matches: List[PIIMatch]) -> List[PIIMatch]:
        """Resolve overlapping matches by keeping the highest confidence one."""
        if not matches:
            return []

        # Sort by start position, then by confidence (descending)
        sorted_matches = sorted(matches, key=lambda m: (m.start, -m.confidence))
        resolved = []

        for current in sorted_matches:
            # Check if current match overlaps with any already resolved match
            overlaps = False
            for existing in resolved:
                if not (current.end <= existing.start or current.start >= existing.end):
                    # There's an overlap - keep the higher confidence one
                    if current.confidence > existing.confidence:
                        resolved.remove(existing)
                        resolved.append(current)
                    overlaps = True
                    break

            if not overlaps:
                resolved.append(current)

        # Sort final results by start position
        return sorted(resolved, key=lambda m: m.start)


# Global instance for easy access
_detector = None


def detect_pii(text: str) -> List[PIIMatch]:
    """
    Detect PII in text using regex patterns.
    
    Args:
        text: Input text to analyze
        
    Returns:
        List of PIIMatch objects with detected PII
    """
    global _detector
    if _detector is None:
        _detector = PIIDetector()

    return _detector.analyze(text)
