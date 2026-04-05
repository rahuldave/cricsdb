"""Example validators - copy this file for your tables.

Validators are plain functions that:
- Receive a field value
- Return the (possibly transformed) value
- Raise ValueError with message on invalid input

These validators are used by BOTH:
- CLI: deebase data insert/update
- API: create_crud_router(validators=...)
- Admin: Web forms
"""
import re


def validate_email(value: str) -> str:
    """Validate and normalize email format."""
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", value):
        raise ValueError("Invalid email format")
    return value.lower()  # Normalize


def validate_non_empty(value: str) -> str:
    """Ensure string is not empty or whitespace."""
    if not value or not value.strip():
        raise ValueError("Cannot be empty")
    return value.strip()


def validate_positive(value: int) -> int:
    """Ensure integer is positive."""
    if value <= 0:
        raise ValueError("Must be positive")
    return value


def validate_length(min_len: int = 0, max_len: int = None):
    """Create a length validator.

    Args:
        min_len: Minimum length (default: 0)
        max_len: Maximum length (default: None = unlimited)

    Returns:
        Validator function

    Example:
        >>> validators = {
        ...     "username": validate_length(3, 20),
        ...     "bio": validate_length(max_len=500),
        ... }
    """
    def validator(value: str) -> str:
        if len(value) < min_len:
            raise ValueError(f"Must be at least {min_len} characters")
        if max_len is not None and len(value) > max_len:
            raise ValueError(f"Must be at most {max_len} characters")
        return value
    return validator


# Register validators for this table
# Uncomment and modify as needed:
VALIDATORS = {
    # "email": validate_email,
    # "name": validate_non_empty,
}
