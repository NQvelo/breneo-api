"""Reading-order reconstruction for multi-column resume pages."""

from __future__ import annotations


def words_to_text(words: list[dict], page_width: float) -> str:
    """Sort word boxes into columns, then top-to-bottom within each column.

    ``words`` items need ``text``, ``x0``, ``x1``, ``top``, and ``bottom``.
    Coordinates may come from pdfplumber or from Tesseract ``image_to_data``.
    """
    usable = []
    for word in words:
        text = str(word.get("text") or "").strip()
        if not text:
            continue
        usable.append(
            {
                "text": text,
                "x0": float(word.get("x0") or 0),
                "x1": float(word.get("x1") or 0),
                "top": float(word.get("top") or 0),
                "bottom": float(word.get("bottom") or 0),
            }
        )
    if not usable:
        return ""
    width = page_width if page_width and page_width > 0 else max(word["x1"] for word in usable)
    columns = _split_columns(usable, width)
    lines: list[str] = []
    for column in columns:
        lines.extend(_lines_in_column(column))
    return "\n".join(line for line in lines if line.strip())


def _split_columns(words: list[dict], page_width: float) -> list[list[dict]]:
    bins = 40
    bin_width = page_width / bins if page_width else 1
    coverage = [0] * bins
    for word in words:
        start = max(0, min(bins - 1, int(word["x0"] / bin_width)))
        end = max(start, min(bins - 1, int(max(word["x1"] - 0.01, word["x0"]) / bin_width)))
        for index in range(start, end + 1):
            coverage[index] += 1

    margin = max(1, int(bins * 0.08))
    gutters: list[float] = []
    index = margin
    while index < bins - margin:
        if coverage[index] == 0:
            end = index
            while end < bins - margin and coverage[end] == 0:
                end += 1
            left_has_text = sum(coverage[:index]) > 0
            right_has_text = sum(coverage[end:]) > 0
            if end - index >= 2 and left_has_text and right_has_text:
                gutters.append(((index + end) / 2) * bin_width)
            index = end
        else:
            index += 1

    if not gutters:
        return [words]

    boundaries = [0.0, *gutters, page_width + 1]
    columns: list[list[dict]] = [[] for _ in range(len(boundaries) - 1)]
    for word in words:
        center = max(0.0, (word["x0"] + word["x1"]) / 2)
        placed = False
        for column_index in range(len(boundaries) - 1):
            if boundaries[column_index] <= center < boundaries[column_index + 1]:
                columns[column_index].append(word)
                placed = True
                break
        if not placed:
            columns[-1].append(word)
    populated = [column for column in columns if column]
    populated.sort(key=lambda column: min(word["x0"] for word in column))
    return populated or [words]


def _lines_in_column(words: list[dict]) -> list[str]:
    heights = [max(1.0, word["bottom"] - word["top"]) for word in words]
    median = sorted(heights)[len(heights) // 2]
    tolerance = max(2.0, median * 0.6)
    ordered = sorted(words, key=lambda word: (word["top"], word["x0"]))
    lines: list[str] = []
    current: list[dict] = []
    current_top: float | None = None
    for word in ordered:
        if current_top is None or abs(word["top"] - current_top) <= tolerance:
            current.append(word)
            if current_top is None:
                current_top = word["top"]
            continue
        lines.append(_join_line(current))
        current = [word]
        current_top = word["top"]
    if current:
        lines.append(_join_line(current))
    return lines


def _join_line(words: list[dict]) -> str:
    ordered = sorted(words, key=lambda word: word["x0"])
    return " ".join(word["text"] for word in ordered).strip()
