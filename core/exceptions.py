"""
core/exceptions.py
====================
Custom exception hierarchy for all CEA-related errors.
"""
from __future__ import annotations


class CEAError(Exception):
    """Base exception for all CEA-related errors."""


class INPBuildError(CEAError):
    """Raised when the .inp file cannot be constructed from a formulation."""


class CEAExecutionError(CEAError):
    """Raised when the FCEA2.exe subprocess fails or times out."""


class ParseError(CEAError):
    """Raised when the .out file cannot be parsed (e.g. missing header)."""


class ValidationError(CEAError):
    """Raised when a formulation fails pre-flight validation."""
