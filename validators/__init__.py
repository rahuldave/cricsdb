"""Validator registry for all tables.

Used by both CLI (deebase data) and API routes.
See validators/example.py for how to create validators.

To add validators for a table:
1. Create a file: validators/your_table.py
2. Define validator functions and VALIDATORS dict
3. Import and register here

Example:
    from . import users

    VALIDATORS = {
        "users": users.VALIDATORS,
    }
"""

# Table name -> validators dict
VALIDATORS: dict[str, dict] = {}


def get_validators(table_name: str) -> dict:
    """Get validators for a table.

    Args:
        table_name: Name of the table

    Returns:
        Dict of field_name -> validator_function
    """
    return VALIDATORS.get(table_name, {})
