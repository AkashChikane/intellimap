from __future__ import annotations

from html import escape

THEMES = {
    "navy": {
        "bg": "#1F2F57",
        "card": "#27406f",
        "text": "#FDFAF9",
        "muted": "#A8A8A8",
        "accent": "#6091C3",
        "edge": "#8fb4d8",
        "warn": "#e2b15a",
        "danger": "#e07a7a",
        "paper": "#FDFAF9",
    },
    "paper": {
        "bg": "#FDFAF9",
        "card": "#ffffff",
        "text": "#1F2F57",
        "muted": "#5c6570",
        "accent": "#6091C3",
        "edge": "#1F2F57",
        "warn": "#b8860b",
        "danger": "#a33b3b",
        "paper": "#1F2F57",
    },
    "gray": {
        "bg": "#f3f3f3",
        "card": "#ffffff",
        "text": "#333333",
        "muted": "#A8A8A8",
        "accent": "#6e6e6e",
        "edge": "#666666",
        "warn": "#8a6d3b",
        "danger": "#7a3b3b",
        "paper": "#1F2F57",
    },
}


def render_svg(graph: dict, theme: str = "navy") -> str:
    t = THEMES.get(theme, THEMES["navy"])
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    width = 160
    height = 160
    for n in nodes:
        x = int(n.get("position", {}).get("x") or 0)
        y = int(n.get("position", {}).get("y") or 0)
        width = max(width, x + 340)
        height = max(height, y + 220)
    frame = graph.get("frame") or {}
    title = f"IntelliMap · {frame.get('type') or 'frame'} · {frame.get('id') or ''}"
    view = graph.get("view") or "deterministic"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="100%" height="100%" fill="{t["bg"]}"/>',
        f'<text x="32" y="36" fill="{t["text"]}" font-family="IBM Plex Sans, Helvetica, Arial, sans-serif" font-size="18" font-weight="700">{escape(title)}</text>',
        f'<text x="32" y="56" fill="{t["muted"]}" font-family="IBM Plex Sans, Helvetica, Arial, sans-serif" font-size="11">view={escape(view)} · source facts + deterministic findings · AI is labeled when used</text>',
        '<defs>',
        f'<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{t["edge"]}"/></marker>',
        "</defs>",
    ]

    centers = {}
    for n in nodes:
        x = int(n.get("position", {}).get("x") or 0)
        y = int(n.get("position", {}).get("y") or 0)
        w, h = 220, 86
        centers[n["id"]] = (x + w / 2, y + h / 2)

    for e in edges:
        a = centers.get(e.get("source"))
        b = centers.get(e.get("target"))
        if not a or not b:
            continue
        kind = e.get("kind")
        dash = "0"
        color = t["edge"]
        if kind == "interface":
            dash = "6 4"
        elif kind == "flow":
            dash = "2 4"
            if (e.get("data") or {}).get("sensitive"):
                color = t["danger"]
        elif kind == "supports":
            dash = "1 6"
            color = t["muted"]
        label = escape(e.get("label") or "")
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 6
        parts.append(
            f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" '
            f'stroke="{color}" stroke-width="1.6" stroke-dasharray="{dash}" marker-end="url(#arrow)"/>'
        )
        if label:
            parts.append(
                f'<text x="{mx:.1f}" y="{my:.1f}" fill="{t["muted"]}" font-size="9" '
                f'text-anchor="middle" font-family="IBM Plex Sans, Helvetica, Arial, sans-serif">{label}</text>'
            )

    for n in nodes:
        x = int(n.get("position", {}).get("x") or 0)
        y = int(n.get("position", {}).get("y") or 0)
        data = n.get("data") or {}
        kind = data.get("kind")
        w, h = 220, 86
        stroke = t["accent"]
        if data.get("unresolved"):
            stroke = t["danger"]
        elif data.get("sensitive"):
            stroke = t["warn"]
        elif data.get("seed"):
            stroke = t["paper"] if t["bg"] == "#1F2F57" else t["accent"]
        dash = "5 4" if data.get("unresolved") else "0"
        rx = 18 if kind == "process" else 10
        if kind == "information_object":
            rx = 40
        parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{t["card"]}" '
            f'stroke="{stroke}" stroke-width="2" stroke-dasharray="{dash}"/>'
        )
        label = escape((data.get("label") or n["id"])[:42])
        sub = escape((data.get("domain") or data.get("classification") or data.get("kind") or "")[:40])
        nid = escape(str(data.get("id") or n["id"]))
        parts.append(
            f'<text x="{x + 14}" y="{y + 24}" fill="{t["muted"]}" font-size="10" '
            f'font-family="IBM Plex Sans, Helvetica, Arial, sans-serif">{nid}</text>'
        )
        parts.append(
            f'<text x="{x + 14}" y="{y + 44}" fill="{t["text"]}" font-size="13" font-weight="700" '
            f'font-family="IBM Plex Sans, Helvetica, Arial, sans-serif">{label}</text>'
        )
        parts.append(
            f'<text x="{x + 14}" y="{y + 64}" fill="{t["muted"]}" font-size="10" '
            f'font-family="IBM Plex Sans, Helvetica, Arial, sans-serif">{sub}</text>'
        )
        if data.get("source_row"):
            src = f"{data.get('source_sheet')}!{data.get('source_row')}"
            parts.append(
                f'<text x="{x + 14}" y="{y + 78}" fill="{t["accent"]}" font-size="9" '
                f'font-family="IBM Plex Sans, Helvetica, Arial, sans-serif">{escape(src)}</text>'
            )

    parts.append("</svg>")
    return "\n".join(parts)


def available_themes() -> list[str]:
    return list(THEMES.keys())
