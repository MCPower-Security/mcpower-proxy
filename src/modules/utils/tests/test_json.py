# src/wrapper/tests/test_json.py

import unittest
from dataclasses import dataclass
from enum import Enum
from typing import List

from modules.utils.json import safe_json_dumps
from pydantic import BaseModel


class TestSafeJsonDumps(unittest.TestCase):
    """Tests for the `safe_json_dumps` function."""

    def test_safe_json_dumps_with_dict(self):
        """Test serialization of a standard dictionary."""
        data = {"key": "value", "number": 42}
        result = safe_json_dumps(data)
        expected = '{"key": "value", "number": 42}'
        self.assertEqual(expected, result)

    def test_safe_json_dumps_with_list(self):
        """Test serialization of a list."""
        data = ["item1", "item2", 42]
        result = safe_json_dumps(data)
        expected = '["item1", "item2", 42]'
        self.assertEqual(expected, result)

    def test_safe_json_dumps_with_enum(self):
        """Test serialization of an Enum."""

        class SampleEnum(Enum):
            ITEM1 = "item1"
            ITEM2 = "item2"

        data = {"enum": SampleEnum.ITEM1}
        result = safe_json_dumps(data)
        expected = '{"enum": "item1"}'
        self.assertEqual(expected, result)

    def test_safe_json_dumps_with_dataclass(self):
        """Test serialization of a dataclass."""

        @dataclass
        class SampleDataclass:
            key: str
            value: int

        data = SampleDataclass(key="test", value=123)
        result = safe_json_dumps(data)
        expected = '{"key": "test", "value": 123}'
        self.assertEqual(expected, result)

    def test_safe_json_dumps_with_pydantic_model(self):
        """Test serialization of a Pydantic BaseModel."""

        class SampleModel(BaseModel):
            name: str
            age: int

        data = SampleModel(name="John Doe", age=30)
        result = safe_json_dumps(data)
        expected = '{"name":"John Doe","age":30}'
        self.assertEqual(expected, result)

    def test_safe_json_dumps_with_nested_data(self):
        """Test serialization of a nested structure with mixed types."""

        @dataclass
        class InnerDataclass:
            inner_key: str
            inner_value: int

        class InnerModel(BaseModel):
            name: str
            items: List[str]

        class Color(Enum):
            RED = "RED"
            GREEN = "GREEN"

        data = {
            "dataclass": InnerDataclass(inner_key="inner", inner_value=99),
            "pydantic_model": InnerModel(name="Model", items=["a", "b"]),
            "enum": Color.RED,
        }
        result = safe_json_dumps(data)
        expected = (
            '{"dataclass": {"inner_key": "inner", "inner_value": 99}, '
            '"pydantic_model": {"name": "Model", "items": ["a", "b"]}, '
            '"enum": "RED"}'
        )
        self.assertEqual(expected, result)

    def test_safe_json_dumps_with_fallback_to_string(self):
        """Test serialization of an unsupported object with fallback to string."""

        class UnsupportedObject:
            pass

        data = {"unsupported": UnsupportedObject()}
        result = safe_json_dumps(data)
        expected = '{"unsupported": {}}'
        self.assertEqual(expected, result)

    def test_safe_json_dumps_with_getattr_default(self):
        """Test serialization when using getattr with default empty dict fallback."""
        # This pattern is commonly used to safely extract attributes that might not exist
        # getattr({}, 'foo', {}) returns {} when 'foo' attribute doesn't exist
        data = getattr({}, 'foo', {})
        result = safe_json_dumps(data)
        expected = '{}'
        self.assertEqual(expected, result)


if __name__ == "__main__":
    unittest.main()
