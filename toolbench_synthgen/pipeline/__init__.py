"""Pipeline package for orchestrating build, generate, validate, and metrics steps."""

from .generate import generate_dataset

__all__ = ["generate_dataset"]


