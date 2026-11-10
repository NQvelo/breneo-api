"""Positioned resume content. Fields are read from these blocks, not from a flat dump."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Block:
    text: str
    page: int = 1
    x0: float = 0
    y0: float = 0
    x1: float = 0
    y1: float = 0
    column: int = 0
    region: int = 0

    def __post_init__(self) -> None:
        self.text = (self.text or "").strip()


@dataclass
class ResumeDocument:
    blocks: list[Block] = field(default_factory=list)
    page_count: int = 1
    method: str = "text"
    kind: str = "text"
    warnings: list[str] = field(default_factory=list)
    filename: str = ""

    def ordered_text(self) -> str:
        """Logical reading order, with a blank line between columns and pages."""
        lines: list[str] = []
        previous: tuple[int, int] | None = None
        for block in self.blocks:
            if not block.text:
                continue
            marker = (block.page, block.region)
            if previous is not None and marker != previous:
                lines.append("")
            lines.append(block.text)
            previous = marker
        return "\n".join(lines).strip()
