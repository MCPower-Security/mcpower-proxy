"""
Client-side redaction implementation.

Input string → output string with all PII and secrets redacted using Gitleaks-based secret detection
and regex patterns for PII. Fully offline, deterministic, and idempotent.
"""

import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import List, Any, Optional, Tuple, Set, Dict

from jsonpath_ng import parse as jsonpath_parse

from .constants import (
    PII_PLACEHOLDERS,
    SECRETS_PLACEHOLDER,
    REDACTION_PLACEHOLDER_PATTERN,
    ZERO_WIDTH_CHARS
)
from .pii_rules import detect_pii

# Type alias for JSONPath cache values: (matches_set, prefix_tree)
JSONPathCacheValue = Tuple[Set[str], Dict[str, Any]]


class LRUCache:
    """
    Least Recently Used cache with size limit to prevent unbounded memory growth.
    Thread-safe for single-threaded usage (not thread-safe for concurrent access).
    """

    def __init__(self, max_size: int = 128):
        self.cache = OrderedDict()
        self.max_size = max_size

    def get(self, key) -> Optional[JSONPathCacheValue]:
        """Get value and mark as recently used."""
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def set(self, key, value: JSONPathCacheValue) -> None:
        """Set value and evict oldest if necessary."""
        if key in self.cache:
            # Update existing key
            self.cache[key] = value
            self.cache.move_to_end(key)
        else:
            # Add new key
            self.cache[key] = value
            # Evict oldest if over limit
            if len(self.cache) > self.max_size:
                self.cache.popitem(last=False)  # Remove oldest (first) item

    def clear(self) -> None:
        """Clear all cached entries."""
        self.cache.clear()

    def size(self) -> int:
        """Get current cache size."""
        return len(self.cache)


# noinspection PyClassHasNoInit
@dataclass
class RedactionSpan:
    """Represents a span of text to be redacted."""
    start: int
    end: int
    replacement: str
    source: str  # 'secrets' or 'pii'

    @property
    def length(self) -> int:
        return self.end - self.start


class RedactionEngine:
    """Core redaction engine using PII detection and Gitleaks."""

    # Performance optimization: Simple bounded cache for compiled JSONPath expressions
    _jsonpath_expr_cache = {}
    _MAX_EXPR_CACHE = 64

    # Performance optimization: LRU cache for JSONPath matches to prevent memory leaks
    _jsonpath_cache = LRUCache(max_size=128)

    # Performance optimization: Pre-compiled regex patterns
    _compiled_regexes = {
        'placeholder': re.compile(REDACTION_PLACEHOLDER_PATTERN),
        'path_brackets': re.compile(r'\.\[(\d+)\]')
    }

    @staticmethod
    def redact(value: Any, ignored_keys: List[str] = None, include_keys: List[str] = None) -> Any:
        """
        Main redaction function that handles any data type.
        
        Args:
            value: Input data to redact (dict, list, str, int, float, bool, etc.)
            ignored_keys: Optional list of dot-notation paths to ignore during redaction
            include_keys: Optional list of dot-notation paths to redact (all others ignored)
            
        Returns:
            Data with PII and secrets replaced by placeholders, preserving original types
            
        Raises:
            ValueError: If both ignored_keys and include_keys are provided
        """
        if ignored_keys and include_keys:
            raise ValueError("Cannot specify both ignored_keys and include_keys - use one or the other")

        return RedactionEngine._redact_with_path(value, ignored_keys or [], include_keys or [], "", value)

    @staticmethod
    def _redact_with_path(value: Any, ignored_keys: List[str], include_keys: List[str], current_path: str,
                          root_data: Any) -> Any:
        """
        Internal redaction function that tracks the current path.
        """
        # Performance optimization: fastest type checks first
        if value is None:
            return None

        if isinstance(value, bool):
            return value  # Booleans can never contain sensitive data - fastest check

        if isinstance(value, (int, float)):
            # Preserve type if no redaction needed
            str_value = str(value)
            redacted_str = RedactionEngine._redact_string(str_value)
            return value if str_value == redacted_str else redacted_str

        if isinstance(value, str):
            return RedactionEngine._redact_string(value)

        if isinstance(value, dict):
            return RedactionEngine._redact_dict(value, ignored_keys, include_keys, current_path, root_data)

        if isinstance(value, list):
            return RedactionEngine._redact_list(value, ignored_keys, include_keys, current_path, root_data)

        # For other types, convert to string and redact
        return RedactionEngine._redact_string(str(value))

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Strip zero-width characters efficiently."""
        # Fast path - check if normalization is needed
        if not any(char in text for char in ZERO_WIDTH_CHARS):
            return text

        # Single pass with translation table (much faster)
        translation_table = str.maketrans('', '', ''.join(ZERO_WIDTH_CHARS))
        return text.translate(translation_table)

    @staticmethod
    def _detect_secrets(text: str) -> List[RedactionSpan]:
        """Detect secrets using Gitleaks-based patterns."""
        spans = []

        # Use compiled rules (based on Gitleaks patterns) for secrets detection
        from . import gitleaks_rules as GL
        # Scan line-by-line for performance and to reduce pathological matches
        offset = 0
        for line in text.split('\n'):
            line_lower = line.lower()
            candidate_indices = GL.candidate_rule_indices(line_lower)
            if candidate_indices and line:
                for idx in candidate_indices:
                    _, regex, secret_group, _ = GL.COMPILED_RULES[idx]
                    for match in regex.finditer(line):
                        # Use the specified group, or fall back to group 0 if it doesn't exist
                        try:
                            if secret_group and match.lastindex and secret_group <= match.lastindex:
                                s, e = match.span(secret_group)
                            else:
                                s, e = match.span(0)
                        except (IndexError, AttributeError):
                            s, e = match.span(0)

                        if s < e:
                            spans.append(RedactionSpan(
                                start=offset + s,
                                end=offset + e,
                                replacement=SECRETS_PLACEHOLDER,
                                source='secrets'
                            ))
            offset += len(line) + 1  # +1 for the split '\n'

        return spans

    @staticmethod
    def _detect_pii(text: str) -> List[RedactionSpan]:
        """Detect PII using regex patterns."""
        spans = []

        # Use PII detection
        results = detect_pii(text)

        # Convert results to redaction spans
        for result in results:
            placeholder = PII_PLACEHOLDERS.get(
                result.entity_type,
                PII_PLACEHOLDERS["DEFAULT"]
            )

            spans.append(RedactionSpan(
                start=result.start,
                end=result.end,
                replacement=placeholder,
                source='pii'
            ))

        return spans

    @staticmethod
    def _resolve_overlaps(spans: List[RedactionSpan]) -> List[RedactionSpan]:
        """Resolve overlapping spans - longest span wins."""
        if not spans:
            return []

        # Sort by start position
        sorted_spans = sorted(spans, key=lambda s: s.start)
        resolved = []

        for current_span in sorted_spans:
            # Check for overlaps with already resolved spans
            overlaps = False

            for i, existing_span in enumerate(resolved):
                if RedactionEngine._spans_overlap(current_span, existing_span):
                    overlaps = True
                    # Keep the longer span
                    if current_span.length > existing_span.length:
                        resolved[i] = current_span
                    break

            if not overlaps:
                resolved.append(current_span)

        return resolved

    @staticmethod
    def _spans_overlap(span1: RedactionSpan, span2: RedactionSpan) -> bool:
        """Check if two spans overlap."""
        return not (span1.end <= span2.start or span2.end <= span1.start)

    @staticmethod
    def _apply_idempotency_guard(text: str, spans: List[RedactionSpan]) -> List[RedactionSpan]:
        """Remove spans that would redact inside existing placeholders."""
        if not spans:
            return []

        # Find existing redaction placeholders
        placeholder_spans = []
        # Performance optimization: Use pre-compiled regex
        for match in RedactionEngine._compiled_regexes['placeholder'].finditer(text):
            placeholder_spans.append((match.start(), match.end()))

        # Filter out spans that overlap with existing placeholders
        filtered_spans = []
        for span in spans:
            overlaps_placeholder = False

            for ph_start, ph_end in placeholder_spans:
                if not (span.end <= ph_start or span.start >= ph_end):
                    overlaps_placeholder = True
                    break

            if not overlaps_placeholder:
                filtered_spans.append(span)

        return filtered_spans

    @staticmethod
    def _apply_redactions(text: str, spans: List[RedactionSpan]) -> str:
        """Apply redactions right-to-left to avoid index shifting, preserving JSON structure."""
        if not spans:
            return text

        # Sort spans by start position (descending) for right-to-left processing
        # Processing right-to-left ensures earlier spans' positions remain valid
        # since replacements to the right don't affect positions to the left
        sorted_spans = sorted(spans, key=lambda s: s.start, reverse=True)

        result = text

        for span in sorted_spans:
            # Replacements to the right don't shift positions to the left
            start_pos = span.start
            end_pos = span.end

            # Bounds check
            if start_pos < 0 or end_pos > len(result) or start_pos >= len(result):
                continue

            replacement = span.replacement

            # Simply replace the matched text with the redaction placeholder
            # Do NOT expand to surrounding quotes - this breaks nested JSON
            # The redaction placeholders are designed to be valid string content as-is

            # Apply the redaction
            result = result[:start_pos] + replacement + result[end_pos:]

        return result

    @staticmethod
    def _redact_dict(d: dict, ignored_keys: List[str], include_keys: List[str], current_path: str,
                     root_data: Any) -> dict:
        """Redact dictionary values, respecting ignored_keys or include_keys."""
        result = {}

        for key, value in d.items():
            # Build the path for this key
            key_path = RedactionEngine._build_path(current_path, str(key))

            # Determine if this path should be redacted
            if RedactionEngine._should_redact_path_enhanced(root_data, key_path, ignored_keys, include_keys,
                                                            current_path):
                # Recursively redact the value with updated path context
                result[key] = RedactionEngine._redact_with_path(value, ignored_keys, include_keys, key_path, root_data)
            else:
                # Keep the value as-is (no redaction for this path or any nested paths)
                result[key] = value

        return result

    @staticmethod
    def _redact_list(lst: list, ignored_keys: List[str], include_keys: List[str], current_path: str,
                     root_data: Any) -> list:
        """Redact list items, respecting ignored_keys or include_keys."""
        result = []

        for i, item in enumerate(lst):
            # Build the path for this index
            item_path = RedactionEngine._build_path(current_path, str(i))

            # Determine if this path should be redacted
            if RedactionEngine._should_redact_path_enhanced(root_data, item_path, ignored_keys, include_keys,
                                                            current_path):
                # Recursively redact the item with updated path context
                result.append(RedactionEngine._redact_with_path(item, ignored_keys, include_keys, item_path, root_data))
            else:
                # Keep the item as-is (no redaction for this path or any nested paths)
                result.append(item)

        return result

    @staticmethod
    def _redact_string(text: str) -> str:
        """Redact a string using the existing redaction pipeline."""
        if not text or not isinstance(text, str):
            return text

        normalized_text = RedactionEngine._normalize_text(text)
        redaction_spans: List[RedactionSpan] = []
        redaction_spans.extend(RedactionEngine._detect_secrets(normalized_text))
        redaction_spans.extend(RedactionEngine._detect_pii(normalized_text))
        resolved_spans = RedactionEngine._resolve_overlaps(redaction_spans)
        final_spans = RedactionEngine._apply_idempotency_guard(normalized_text, resolved_spans)
        return RedactionEngine._apply_redactions(normalized_text, final_spans)

    @staticmethod
    def _normalize_numeric_key(key: str) -> str:
        """Normalize numeric keys efficiently - only if needed."""
        if key and key[0] == '0' and len(key) > 1 and key.isdigit():
            # Only normalize if there are leading zeros
            return str(int(key))
        return key

    @staticmethod
    def _build_path(current_path: str, key: str) -> str:
        """
        Build a dot-notation path with consistent numeric key formatting.
        Normalizes numeric indices to remove leading zeros for consistency.
        Handles empty keys gracefully to prevent malformed paths.
        """
        # Normalize numeric keys efficiently
        normalized_key = RedactionEngine._normalize_numeric_key(key)

        # Handle empty keys to prevent paths like "user..email"
        if not normalized_key:
            return current_path

        if not current_path:
            return normalized_key

        return f"{current_path}.{normalized_key}"

    @staticmethod
    def _should_redact_path_enhanced(root_data: dict, path: str, ignored_keys: List[str], include_keys: List[str],
                                     current_path: str) -> bool:
        """
        Enhanced path matching using JSONPath when available, fallback to custom logic.
        
        Args:
            root_data: The root data object for JSONPath queries
            path: The current path (e.g., "user.email")
            ignored_keys: Paths to ignore (don't redact)
            include_keys: Paths to include (only redact these)
            current_path: Current traversal path
            
        Returns:
            True if the path should be redacted, False otherwise
        """
        return RedactionEngine._should_redact_path_jsonpath(root_data, path, ignored_keys, include_keys)

    @staticmethod
    def _should_redact_path_jsonpath(root_data: dict, path: str, ignored_keys: List[str],
                                     include_keys: List[str]) -> bool:
        """
        JSONPath-based path matching with LRU cache to prevent memory leaks.
        """
        # Performance optimization: Use frozenset for better cache key performance
        cache_key = (
            id(root_data),
            frozenset(ignored_keys) if ignored_keys else None,
            frozenset(include_keys) if include_keys else None
        )

        # Try to get from LRU cache
        cached_result = RedactionEngine._jsonpath_cache.get(cache_key)

        if cached_result is None:
            # Pre-compute all matches for this data/pattern combination
            all_matches = set()
            patterns = include_keys or ignored_keys or []

            for pattern in patterns:
                try:
                    # Expect proper JSONPath format (starting with $)
                    if not pattern.startswith('$'):
                        raise ValueError(f"Pattern must be in JSONPath format (start with $): {pattern}")

                    # Performance optimization: Use cached compiled expressions
                    if pattern not in RedactionEngine._jsonpath_expr_cache:
                        # Simple FIFO eviction if cache is full
                        if len(RedactionEngine._jsonpath_expr_cache) >= RedactionEngine._MAX_EXPR_CACHE:
                            # Remove oldest entry (first in dict)
                            oldest_key = next(iter(RedactionEngine._jsonpath_expr_cache))
                            del RedactionEngine._jsonpath_expr_cache[oldest_key]
                        RedactionEngine._jsonpath_expr_cache[pattern] = jsonpath_parse(pattern)
                    jsonpath_expr = RedactionEngine._jsonpath_expr_cache[pattern]

                    matches = jsonpath_expr.find(root_data)

                    for match in matches:
                        # Performance optimization: Single regex for path conversion
                        match_path = RedactionEngine._compiled_regexes['path_brackets'].sub(
                            r'.\1', str(match.full_path)
                        )
                        all_matches.add(match_path)

                except Exception:
                    # Fallback for invalid JSONPath patterns
                    continue

            # Build prefix tree for O(k) child matching
            prefix_tree = RedactionEngine._build_prefix_tree(all_matches)
            cached_result = (all_matches, prefix_tree)

            # Store in LRU cache (will evict oldest if necessary)
            RedactionEngine._jsonpath_cache.set(cache_key, cached_result)

        matches, prefix_tree = cached_result

        if include_keys:
            # include_keys mode: only redact if path matches or has matching children
            return RedactionEngine._path_matches_or_has_children(path, prefix_tree)
        elif ignored_keys:
            # ignored_keys mode: redact everything except matches and their children
            return not RedactionEngine._path_matches_or_has_children(path, prefix_tree)
        else:
            # No filtering: redact everything
            return True

    @staticmethod
    def _build_prefix_tree(matches: Set[str]) -> Dict[str, Any]:
        """
        Build a prefix tree for O(k) lookups with exact match tracking.
        Stores both exact matches and children for single-traversal lookup.
        """
        prefix_tree = {}

        for match in matches:
            parts = match.split('.')
            node = prefix_tree

            # Build tree path
            for i, part in enumerate(parts):
                if part not in node:
                    node[part] = {'_children': {}, '_is_match': False}

                if i == len(parts) - 1:
                    node[part]['_is_match'] = True  # Mark exact matches

                node = node[part]['_children']

        return prefix_tree

    @staticmethod
    def _has_matching_children_optimized(path: str, prefix_tree: Dict[str, Any]) -> bool:
        """
        Check if any matches are children of this path using prefix tree.
        Time complexity: O(k) where k is path depth, vs O(n) for linear search.
        """
        if not path:
            # Root path - check if tree has any entries
            return bool(prefix_tree)

        # Navigate to the node representing this path
        parts = path.split('.')
        node = prefix_tree

        for part in parts:
            if part not in node:
                # Path doesn't exist in tree
                return False
            node = node[part]['_children']

        # Check if there are any children under this path
        return bool(node)

    @staticmethod
    def _path_matches_or_has_children(path: str, prefix_tree: Dict[str, Any]) -> bool:
        """
        Single traversal for both exact match and children check.
        More efficient than separate set lookup + tree traversal.
        """
        if not path:
            return bool(prefix_tree)

        parts = path.split('.')
        node = prefix_tree

        for i, part in enumerate(parts):
            if part not in node:
                return False

            if i == len(parts) - 1:
                # Check if this exact path matches OR has children
                return node[part].get('_is_match', False) or bool(node[part]['_children'])

            node = node[part]['_children']

        return False

    @staticmethod
    def _has_matching_children_cached(path: str, matches: Set[str]) -> bool:
        """
        Legacy method - kept for backward compatibility.
        Check if any cached matches are children of this path.
        """
        path_prefix = path + "." if path else ""
        return any(match.startswith(path_prefix) for match in matches)

    @classmethod
    def clear_caches(cls) -> None:
        """
        Clear all caches to free memory. Useful for testing or memory management.
        """
        cls._jsonpath_expr_cache.clear()
        cls._jsonpath_cache.clear()

    @classmethod
    def get_cache_stats(cls) -> Dict[str, int]:
        """
        Get cache statistics for monitoring and debugging.
        """
        return {
            'jsonpath_expr_cache_size': len(cls._jsonpath_expr_cache),
            'jsonpath_expr_cache_max_size': cls._MAX_EXPR_CACHE,
            'jsonpath_cache_size': cls._jsonpath_cache.size(),
            'jsonpath_cache_max_size': cls._jsonpath_cache.max_size
        }


def redact(data: Any, ignored_keys: List[str] = None, include_keys: List[str] = None) -> Any:
    """
    Redact PII and secrets from any data type using built-in detectors only.
    
    Args:
        data: Input data to redact (dict, list, str, int, float, bool, etc.)
        ignored_keys: Optional list of dot-notation paths to ignore during redaction
        include_keys: Optional list of dot-notation paths to redact (all others ignored)
        
    Returns:
        Data with PII and secrets replaced by placeholders, preserving original types
        
    Raises:
        ValueError: If both ignored_keys and include_keys are provided
        
    This function is:
    - Fully offline (no network calls)
    - Deterministic (same input → same output)
    - Idempotent (redact(redact(x)) == redact(x))
    - Uses only library defaults (no custom patterns)
    """
    return RedactionEngine.redact(data, ignored_keys, include_keys)
