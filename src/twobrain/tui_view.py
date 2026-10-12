"""Responsive terminal layout using the same brand tokens as the CLI."""

from .appearance import fit, wrap


def document(value, width):
    rows = []
    if "error" in value or "empty" in value:
        return [(line, "muted") for line in wrap(value.get("error", value.get("empty")), width)]
    # Project context comes first; its general defaults remain accessible below.
    groups = []
    if "context" in value:
        groups.append((value.get("tool", value.get("project")), value["context"]))
    if "general" in value:
        groups.append((value["general"].get("person", "General"), value["general"]))
    for title, record in groups:
        rows.extend((line, "accent") for line in wrap(title, width))
        rows.append(("", "text"))
        for guidance in record["guidance"]:
            lines = wrap(guidance, max(1, width - 2))
            rows.extend((("· " if i == 0 else "  ") + line, "text") for i, line in enumerate(lines))
            rows.append(("", "text"))
        for pointer in record["pointers"]:
            rows.extend((line, "accent") for line in wrap(pointer["label"], width))
            rows.extend((line, "muted") for line in wrap(pointer["target"], width))
            rows.append(("", "text"))
        if not record["guidance"] and not record["pointers"]:
            rows.append(("No guidance saved yet.", "muted"))
    for warning in value.get("warnings", []):
        rows.extend((line, "accent") for line in wrap("Warning: " + warning, width))
    rows.extend((line, "muted") for line in wrap(value["policy"], width))
    return rows


def frame(model, columns, height, theme):
    width = max(1, columns - 1)
    height = max(1, height)

    def line(text="", role="text", bold=False):
        return theme.paint(fit(text, width), role, "background", bold)

    if columns < 32 or height < 10:
        text = ["2brain", "A little more room, please.", "Resize, or q to quit."]
        return [line(text[i] if i < len(text) else "") for i in range(height)]
    entries = model.visible
    count = len(entries)
    heading = "  2brain   /   your context, close at hand" if columns >= 78 else "  2brain / local context"
    rows = [line(heading, "accent", True), line("  LOCAL CONTEXT / READ ONLY", "muted")]
    search = f"  / {model.search}" + ("_" if model.searching else "") if model.search or model.searching else "  / search records"
    rows += [line(search, "accent" if model.searching else "muted"), line("─" * width, "line")]
    body_height = height - 7
    wide = columns >= 78
    sidebar = min(32, max(24, width // 3)) if wide else width
    content_width = width - sidebar - 4 if wide else width - 4
    content = document(model.content(), content_width)
    model.offset = min(model.offset, max(0, len(content) - body_height))
    first = max(0, model.selected - body_height + 1)
    for i in range(body_height):
        index = first + i
        label = ""
        role = "text"
        if index < count:
            entry = entries[index]
            label = f" {'>' if index == model.selected else ' '} {entry.label}"
            if entry.kind != "general":
                label += " / " + entry.kind
            role = "selected" if index == model.selected else "muted"
        if not wide and model.detail:
            text, content_role = content[model.offset + i] if model.offset + i < len(content) else ("", "text")
            rows.append(line("  " + text, content_role))
            continue
        left = theme.paint(fit(label, sidebar), role,
                           "selection" if index == model.selected and index < count else "background")
        if wide:
            text, content_role = content[model.offset + i] if model.offset + i < len(content) else ("", "text")
            divider = theme.paint(" │  ", "line", "background")
            right = theme.paint(fit(text, content_width), content_role, "background")
            rows.append(left + divider + right)
        else:
            rows.append(left)
    start = min(len(content), model.offset + 1)
    end = min(len(content), model.offset + body_height)
    position = f"{model.selected + 1 if count else 0}/{count} records"
    if wide or model.detail:
        position += f"   ·   lines {start}–{end}/{len(content)}"
    rows += [line("─" * width, "line"), line("  " + position, "muted")]
    help_text = "  ↑↓ browse · Tab read · / search · PgUp/PgDn scroll · r refresh · q quit"
    if wide and model.detail:
        help_text = "  ↑↓ scroll · Tab browse · / search · PgUp/PgDn scroll · r refresh · q quit"
    if not wide:
        help_text = "  ↑↓ move · Enter read · / find · q quit"
        if model.detail:
            help_text = "  ↑↓ scroll · Esc back · q quit"
        if model.searching:
            help_text = "  Enter apply · Esc clear · Ctrl+C quit"
    rows.append(line(help_text, "muted"))
    return rows
