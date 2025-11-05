"""
JSON utilities for safe serialization and JSONC parsing
"""
import json
from dataclasses import is_dataclass, asdict
from enum import Enum
from typing import Any

from jsonc_parser.parser import JsoncParser
from pydantic import BaseModel, AnyUrl


def to_dict(value: Any) -> Any:
    """
    Convert any value to a dict/primitive structure suitable for JSON serialization.
    Handles dataclasses, Pydantic models, dicts, lists, Enums, and nested structures.
    
    Args:
        value: Any value to convert
        
    Returns:
        Dict, list, or primitive value ready for JSON serialization
    """
    if value is None:
        return None
    elif isinstance(value, (str, int, float, bool)):
        return value
    elif isinstance(value, Enum):
        # Convert Enum to its value for JSON serialization
        return value.value
    elif isinstance(value, dict):
        return {k: to_dict(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        return [to_dict(item) for item in value]
    elif is_dataclass(value):
        # Use asdict and recursively convert Enums to their values
        return to_dict(asdict(value))
    elif hasattr(value, 'model_dump'):
        return value.model_dump()
    elif hasattr(value, '__dict__'):
        # Extract __dict__ for objects, excluding private attrs only
        return {k: to_dict(v) for k, v in value.__dict__.items() if not k.startswith('_')}
    else:
        # Last resort - convert to string
        return str(value)


def safe_json_dumps(obj: Any, **kwargs) -> str:
    """
    Safely serialize objects to JSON, using Pydantic's built-in serialization when available
    """
    # If it's a Pydantic BaseModel, use its built-in JSON serialization
    if isinstance(obj, BaseModel):
        return obj.model_dump_json(**kwargs)

    # If it's a dict or list that might contain Pydantic objects, use custom serializer
    def default_serializer(o):
        if isinstance(o, BaseModel):
            return o.model_dump()
        if isinstance(o, AnyUrl):
            return str(o)
        # Handle Enums by converting to their value
        if isinstance(o, Enum):
            return o.value
        # Handle dataclasses properly - recursively convert via to_dict to handle nested Enums
        if is_dataclass(o):
            return to_dict(o)
        # Handle other objects with dict method
        if hasattr(o, 'dict') and callable(o.dict):
            return o.dict()
        if hasattr(o, '__dict__'):
            return o.__dict__
        # Fallback to string representation
        return str(o)

    return json.dumps(obj, default=default_serializer, **kwargs)


def stringify_jsonc(obj: Any, **kwargs) -> str:
    """
    Serialize object to JSONC format when possible, falling back to regular JSON
    
    Args:
        obj: The object to serialize
        **kwargs: Additional arguments passed to the serializer
        
    Returns:
        JSONC string representation
    """
    try:
        # Use regular JSON for serialization
        return json.dumps(obj, **kwargs)
    except Exception:
        # Fallback to safe_json_dumps if regular json.dumps fails
        return safe_json_dumps(obj, **kwargs)


def parse_jsonc(text: str) -> Any:
    """
    Parse JSONC (JSON with Comments) text using jsonc-parser, falling back to regular JSON if parsing fails
    
    Args:
        text: The JSONC/JSON string to parse
        
    Returns:
        Parsed object
        
    Raises:
        json.JSONDecodeError: If parsing fails with both JSONC and JSON parsers
    """
    try:
        # Use jsonc-parser for JSONC handling (comments support)
        return JsoncParser.parse_str(text)
    except Exception as e:
        # If JSONC parsing fails, try regular JSON as fallback
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Re-raise the original JSONC error if JSON also fails
            raise json.JSONDecodeError(f"JSONC parsing failed: {str(e)}", text, 0)
