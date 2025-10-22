"""
Lightweight PII detection using only regex patterns.
No external dependencies beyond Python's built-in re module.
"""

import re
from typing import List, Tuple, NamedTuple


class PIIMatch(NamedTuple):
    """Represents a detected PII match."""
    start: int
    end: int
    entity_type: str
    confidence: float


class PIIDetector:
    """Lightweight PII detector using only regex patterns."""
    
    def __init__(self):
        # Compile regex patterns for better performance
        self.patterns = {
            'EMAIL_ADDRESS': re.compile(
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                re.IGNORECASE
            ),
            'US_SSN': re.compile(
                r'\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}\b'
            ),
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
            'IP_ADDRESS': re.compile(
                r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
                r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
            ),
            'URL': re.compile(
                r'https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.-])*)?(?:\?(?:[\w&=%.-])*)?(?:\#(?:[\w.-])*)?',
                re.IGNORECASE
            ),
            'US_PASSPORT': re.compile(
                r'\b[A-Z]{1,2}[0-9]{6,9}\b'
            ),
            'US_DRIVER_LICENSE': re.compile(
                r'\b[A-Z]{1,2}[0-9]{5,8}\b'
            ),
            # Common crypto addresses
            'CRYPTO_ADDRESS': re.compile(
                r'\b(?:'
                r'[13][a-km-zA-HJ-NP-Z1-9]{25,34}|'  # Bitcoin
                r'0x[a-fA-F0-9]{40}|'  # Ethereum
                r'[LM3][a-km-zA-HJ-NP-Z1-9]{26,33}'  # Litecoin
                r')\b'
            ),
            # IBAN (International Bank Account Number)
            'IBAN': re.compile(
                r'\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}([A-Z0-9]?){0,16}\b'
            ),
        }
    
    def analyze(self, text: str) -> List[PIIMatch]:
        """
        Analyze text and return detected PII matches.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of PIIMatch objects with detected PII
        """
        matches = []
        
        for entity_type, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                # Calculate confidence based on pattern specificity
                confidence = self._calculate_confidence(entity_type, match.group())
                
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
            'EMAIL_ADDRESS': 0.95,
            'PHONE_NUMBER': 0.85,
            'US_SSN': 0.90,
            'CREDIT_CARD': 0.85,
            'IP_ADDRESS': 0.90,
            'URL': 0.80,
            'US_PASSPORT': 0.70,
            'US_DRIVER_LICENSE': 0.65,
            'CRYPTO_ADDRESS': 0.95,
            'IBAN': 0.85,
        }
        
        base_score = base_scores.get(entity_type, 0.5)
        
        # Adjust based on length and format
        if entity_type == 'PHONE_NUMBER':
            # Higher confidence for formatted phone numbers
            if any(char in matched_text for char in '()-. '):
                base_score += 0.1
        elif entity_type == 'CREDIT_CARD':
            # Higher confidence for properly formatted cards
            if '-' in matched_text or ' ' in matched_text:
                base_score += 0.1
        elif entity_type in ['US_PASSPORT', 'US_DRIVER_LICENSE']:
            # Lower confidence for very short matches
            if len(matched_text) < 6:
                base_score -= 0.2
        
        return min(1.0, base_score)
    
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
