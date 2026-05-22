"""markdown_renderer.py — Markdown → HTML for chat bubbles."""

import re
import html as html_mod


def render(text: str) -> str:
    """Convert Markdown text to safe HTML."""

    text = html_mod.escape(text)

    # Headings
    text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.M)
    text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.M)
    text = re.sub(r'^# (.+)$', r'<h1>\1</h1>', text, flags=re.M)

    # Bold / italic
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', text)

    # Inline code
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

    # Newlines → <br>
    text = text.replace('\n', '<br>')

    return (
        '<div style="font-size:14px; line-height:1.7; color:#2D3436;">'
        + text +
        '</div>'
    )


def render_simple(text: str) -> str:
    """Lightweight version: escape + br only."""
    text = html_mod.escape(text)
    text = text.replace('\n', '<br>')
    return f'<span style="font-size:13px; color:#636E72;">{text}</span>'
