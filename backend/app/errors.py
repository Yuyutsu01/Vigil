"""
Vigil Application Error Hierarchy.
Defines foundational configuration and runtime exceptions.
"""


class VigilError(Exception):
    """Base exception for all Vigil domain errors."""


class ConfigurationError(VigilError):
    """Raised when application configuration or environment parameters are invalid or fail security constraints."""
