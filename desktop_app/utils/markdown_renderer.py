"""markdown_renderer.py — Markdown → HTML for chat bubbles.

Qt rich-text (QLabel) bakes in hard-coded default spacing for <h1>-<h6>
(~19 px) and <p> (~18 px) that inline margin:0 CANNOT override — verified
empirically via sizeHint().  We therefore use <div> for headings, which
has zero default spacing and respects inline styles.
"""

import re
import html as html_mod


def render(text: str) -> str:
    """Convert Markdown text to safe HTML."""

    text = html_mod.escape(text)

    # ── Headings → styled <div> (NO <h1>-<h6> or <p> — Qt ignores margin:0) ──
    text = re.sub(
        r'^### (.+)$',
        r'<div style="font-size:15px; font-weight:600; '
        r'margin:0; padding:0; line-height:1.6; color:#1A202C;">\1</div>',
        text, flags=re.M,
    )
    text = re.sub(
        r'^## (.+)$',
        r'<div style="font-size:17px; font-weight:700; '
        r'margin:0; padding:0; line-height:1.6; color:#1A202C;">\1</div>',
        text, flags=re.M,
    )
    text = re.sub(
        r'^# (.+)$',
        r'<div style="font-size:19px; font-weight:700; '
        r'margin:0; padding:0; line-height:1.6; color:#1A202C;">\1</div>',
        text, flags=re.M,
    )

    # ── Bold / italic ──
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', text)

    # ── Inline code ──
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

    # ── Newlines → <br> ──
    text = text.replace('\n', '<br>')

    # ── Clean up spacing ──

    # Remove the first <br> after a heading <div> (the heading's own
    # line-ending).  The heading <div> already acts as a block break.
    text = re.sub(
        r'(<div style="font-size:1[5-9]px;[^"]*">.+?</div>)<br>',
        r'\1',
        text,
    )

    # Collapse 2+ consecutive <br> into a single one.
    # In markdown a blank line (\\n\\n) means paragraph break — but two
    # full line-heights of gap is too much.  One <br> (~21 px at 14px /
    # 1.5 line-height) is a clean paragraph gap.
    text = re.sub(r'(<br>){2,}', r'<br>', text)

    return (
        '<div style="font-size:14px; line-height:1.5; color:#2D3436;">'
        + text
        + '</div>'
    )


def render_simple(text: str) -> str:
    """Lightweight version: escape + br only."""
    text = html_mod.escape(text)
    text = text.replace('\n', '<br>')
    return f'<span style="font-size:13px; color:#636E72;">{text}</span>'
