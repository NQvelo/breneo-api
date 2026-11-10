"""Column and sidebar detection from line coordinates."""

from __future__ import annotations

from app.ats.pipeline.model import Block


def order_blocks(blocks: list[Block], page_width: float) -> list[Block]:
    """Read a narrow sidebar on its own, and keep same-row lines together otherwise."""
    if not blocks:
        return []
    pages: dict[int, list[Block]] = {}
    for block in blocks:
        pages.setdefault(block.page, []).append(block)
    ordered: list[Block] = []
    for page in sorted(pages):
        ordered.extend(_order_page(pages[page], page_width))
    return ordered


def _order_page(blocks: list[Block], page_width: float) -> list[Block]:
    columns = _columns(blocks, page_width)
    if len(columns) <= 1:
        for block in blocks:
            block.region = 0
            block.column = 0
        return sorted(blocks, key=lambda block: (block.y0, block.x0))

    widths = [_span(column) for column in columns]
    sidebar = [index for index, width in enumerate(widths) if page_width and width < page_width * 0.38]
    main = [index for index in range(len(columns)) if index not in sidebar]
    if sidebar and main and page_width and max(widths) > page_width * 0.45:
        for index in sidebar:
            for block in columns[index]:
                block.region = 0
                block.column = index
        for index in main:
            for block in columns[index]:
                block.region = 1
                block.column = index
        return sorted(blocks, key=lambda block: (block.region, block.y0, block.x0))

    for block in blocks:
        block.region = 0
    return sorted(blocks, key=lambda block: (round(block.y0, 1), block.x0))


def _columns(blocks: list[Block], page_width: float) -> list[list[Block]]:
    if len(blocks) < 4 or not page_width:
        return [blocks]
    bins = 40
    width = page_width / bins
    coverage = [0] * bins
    for block in blocks:
        start = max(0, min(bins - 1, int(block.x0 / width)))
        end = max(start, min(bins - 1, int(max(block.x1 - 0.01, block.x0) / width)))
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
            if end - index >= 2 and sum(coverage[:index]) > 0 and sum(coverage[end:]) > 0:
                gutters.append(((index + end) / 2) * width)
            index = end
        else:
            index += 1
    if not gutters:
        return [blocks]
    bounds = [0.0, *gutters, page_width + 1]
    columns: list[list[Block]] = [[] for _ in range(len(bounds) - 1)]
    for block in blocks:
        center = max(0.0, (block.x0 + block.x1) / 2)
        for column_index in range(len(bounds) - 1):
            if bounds[column_index] <= center < bounds[column_index + 1]:
                columns[column_index].append(block)
                break
    populated = [column for column in columns if column]
    populated.sort(key=lambda column: min(block.x0 for block in column))
    return populated or [blocks]


def _span(column: list[Block]) -> float:
    return max(block.x1 for block in column) - min(block.x0 for block in column)
