"""Formatting helpers shared by every handler module."""
from __future__ import annotations
import html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

NL = chr(10)
DIV = "───────────────"


def esc(text) -> str:
    return html.escape(str(text), quote=False)


def bar(value: int, maximum: int, width: int = 10, filled: str = "█", empty: str = "░") -> str:
    maximum = max(1, int(maximum))
    ratio = max(0.0, min(1.0, value / maximum))
    return filled * int(round(ratio * width)) + empty * (width - int(round(ratio * width)))


def hp_line(label: str, hp: int, maximum: int) -> str:
    maximum = max(1, int(maximum))
    return f"{label} {bar(hp, maximum, 10, '❤', '·')} {max(0, hp)}/{maximum}"


def mp_line(value: int, maximum: int) -> str:
    return f"MP {bar(value, maximum, 8, '▰', '▱')} {value}/{maximum}"


def num(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def kb(rows) -> InlineKeyboardMarkup | None:
    cleaned = []
    for row in rows:
        if not row:
            continue
        buttons = [(t, d) for t, d in row if t and d]
        if buttons:
            cleaned.append(buttons)
    return InlineKeyboardMarkup(cleaned) if cleaned else None


def chunk(seq, size):
    seq = list(seq)
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def paginate(items, page: int, per_page: int):
    items = list(items)
    total = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(int(page), total - 1))
    return items[page * per_page:(page + 1) * per_page], page, total


def stars(n: int) -> str:
    return "★" * max(1, min(6, int(n)))


def rank_tag(rank: str) -> str:
    return {"Z": "🔴 Z", "S": "🟡 S", "A": "🟣 A", "B": "🔵 B", "E": "⚪ E"}.get(rank, f"⚪ {rank}")


def short(text: str, limit: int = 28) -> str:
    text = str(text)
    return text if len(text) <= limit else text[:limit - 1] + "…"
