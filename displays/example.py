"""Example displays - copy this file for your tables.

Display functions customize how field values appear in the admin detail view.
They receive:
- value: The field value to render
- record: The full record dict (for context-aware rendering)

They return an HTML string.

Usage:
1. Copy this file to displays/your_table.py
2. Create display functions
3. Export them in the DISPLAYS dict
4. The admin UI will auto-discover them
"""
import html
import json
from typing import Any


def render_tags(value: Any, record: dict) -> str:
    """Render a JSON array of tags as styled badges."""
    if not value:
        return '<span class="null">—</span>'

    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return html.escape(value)

    if not isinstance(value, list):
        return html.escape(str(value))

    badges = []
    for tag in value:
        escaped = html.escape(str(tag))
        badges.append(f'<span style="display:inline-block;padding:2px 8px;margin:2px;background:#e5e7eb;border-radius:4px;font-size:0.875rem;">{escaped}</span>')
    return "".join(badges)


def render_status(value: Any, record: dict) -> str:
    """Render a status field with color coding."""
    if value is None:
        return '<span class="null">—</span>'

    status = str(value).lower()
    colors = {
        "active": "#16a34a",
        "pending": "#ca8a04",
        "inactive": "#9ca3af",
        "error": "#dc2626",
        "draft": "#6b7280",
        "published": "#2563eb",
    }
    color = colors.get(status, "#374151")
    escaped = html.escape(str(value))
    return f'<span style="color:{color};font-weight:500;">{escaped}</span>'


def render_url(value: Any, record: dict) -> str:
    """Render a URL as a clickable link."""
    if not value:
        return '<span class="null">—</span>'

    escaped = html.escape(str(value))
    return f'<a href="{escaped}" target="_blank" rel="noopener">{escaped}</a>'


def render_email(value: Any, record: dict) -> str:
    """Render an email as a mailto link."""
    if not value:
        return '<span class="null">—</span>'

    escaped = html.escape(str(value))
    return f'<a href="mailto:{escaped}">{escaped}</a>'


# Register displays for this table
# Uncomment and modify as needed:
DISPLAYS = {
    # "tags": render_tags,
    # "status": render_status,
    # "website": render_url,
    # "email": render_email,
}
