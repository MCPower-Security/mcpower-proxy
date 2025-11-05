"""
IDE Tools - IDE Safety Validation Module

Provides validation and user confirmation for AI-generated operations in IDEs.
Supports multiple IDEs with per-IDE handlers.
"""

from .router import main as router_main

__all__ = [
    "router_main",
]
