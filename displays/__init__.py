"""Custom field displays for admin UI.

Used by the admin interface to render field values.
See displays/example.py for how to create custom displays.

To add displays for a table:
1. Create a file: displays/your_table.py
2. Define display functions and DISPLAYS dict
3. The admin UI will auto-discover them

Example:
    # displays/articles.py
    def render_history(value, record):
        return "<pre>" + json.dumps(value, indent=2) + "</pre>"

    DISPLAYS = {
        "history": render_history,
    }
"""
