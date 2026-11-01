#!/usr/bin/env python3
"""Draw figures/ghost-exchange.drawio.svg for the writeup.

draw.io saves a diagram as an SVG with its editable model in the `content`
attribute. This script builds one list of shapes and writes both from it, so
the file renders in the PDF as it is and opens in draw.io for editing.

The bars show the order of one step and are not to scale.
"""
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "figures" / "ghost-exchange.drawio.svg"

RANKS, SIZE = 6, 100
WIDTH, HEIGHT = 900, 290
FONT = "Helvetica"
INK, MUTED, RULE = "#1f2937", "#6b7280", "#d1d5db"
RANK_FILL, EDGE_FILL = "#dbeafe", "#93c5fd"
TO_HIGHER, TO_LOWER = "#1d4ed8", "#c2410c"
WAIT_FILL = "#fed7aa"


class Diagram:
    """Collects shapes as SVG elements and draw.io cells at the same time."""

    def __init__(self):
        self.svg, self.cells = [], []

    def _cell(self, attrs, geometry):
        cell_id = f"c{len(self.cells) + 2}"
        self.cells.append(f'<mxCell id="{cell_id}" {attrs} parent="1">{geometry}</mxCell>')

    def box(self, x, y, w, h, fill="none", stroke="none", dashed=False, label=""):
        dash = ' stroke-dasharray="3 2"' if dashed else ""
        self.svg.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                        f'fill="{fill}" stroke="{stroke}"{dash}/>')
        style = (f"rounded=0;whiteSpace=wrap;html=0;fillColor={fill};strokeColor={stroke};"
                 f"dashed={int(dashed)};fontFamily={FONT};fontSize=14;fontColor={INK};")
        geometry = f'<mxGeometry x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" as="geometry"/>'
        self._cell(f'value={quoteattr(label)} style="{style}" vertex="1"', geometry)
        if label:
            for i, line in enumerate(label.split("\n")):
                self._svg_text(x + w / 2, y + h / 2 + 4 + (i - label.count("\n") / 2) * 16, line, 14, INK, "middle", False)

    def _svg_text(self, x, y, text, size, color, anchor, bold):
        weight = ' font-weight="bold"' if bold else ""
        self.svg.append(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" fill="{color}" '
                        f'text-anchor="{anchor}"{weight}>{escape(text)}</text>')

    def text(self, x, y, text, size=13, color=INK, anchor="start", bold=False):
        self._svg_text(x, y, text, size, color, anchor, bold)
        w, h = len(text) * size * 0.56, size + 4
        left = {"start": x, "middle": x - w / 2, "end": x - w}[anchor]
        align = {"start": "left", "middle": "center", "end": "right"}[anchor]
        style = (f"text;html=0;align={align};verticalAlign=middle;spacing=0;fontFamily={FONT};fontSize={size};"
                 f"fontColor={color};fontStyle={int(bold)};")
        geometry = f'<mxGeometry x="{left:.1f}" y="{y - size:.1f}" width="{w:.1f}" height="{h}" as="geometry"/>'
        self._cell(f'value={quoteattr(text)} style="{style}" vertex="1"', geometry)

    def line(self, x1, y1, x2, y2, color=RULE, arrow=False, width=1.0):
        mark = f' marker-end="url(#head-{color[1:]})"' if arrow else ""
        self.svg.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" '
                        f'stroke-width="{width}"{mark}/>')
        style = (f"endArrow={'block' if arrow else 'none'};html=0;strokeColor={color};strokeWidth={width};"
                 "endSize=4;")
        geometry = (f'<mxGeometry relative="1" as="geometry"><mxPoint x="{x1:.1f}" y="{y1:.1f}" as="sourcePoint"/>'
                    f'<mxPoint x="{x2:.1f}" y="{y2:.1f}" as="targetPoint"/></mxGeometry>')
        self._cell(f'value="" style="{style}" edge="1"', geometry)

    def write(self, path):
        model = ('<mxGraphModel dx="900" dy="400" grid="0" gridSize="10" guides="1" tooltips="1" connect="1" '
                 f'arrows="1" fold="1" page="0" pageScale="1" pageWidth="{WIDTH}" pageHeight="{HEIGHT}" '
                 'background="#ffffff" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
                 + "".join(self.cells) + "</root></mxGraphModel>")
        mxfile = f'<mxfile><diagram name="Page-1" id="ghost-exchange">{model}</diagram></mxfile>'
        heads = "".join(
            f'<marker id="head-{c[1:]}" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" '
            f'orient="auto"><path d="M0 0 L8 4 L0 8 z" fill="{c}"/></marker>' for c in (TO_HIGHER, TO_LOWER))
        path.parent.mkdir(exist_ok=True)
        path.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{WIDTH}px" height="{HEIGHT}px" '
            f'viewBox="0 0 {WIDTH} {HEIGHT}" content={quoteattr(mxfile)}><defs>{heads}</defs>'
            f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>' + "".join(self.svg) + "</svg>\n")


def stripes(d):
    d.text(30, 16, "Stripes and ghost rows: 6 ranks over 100 rows, split along the i axis", 15, bold=True)
    gap, top, height, strip = 40, 28, 54, 7
    unit = (WIDTH - 60 - gap * (RANKS - 1)) / SIZE
    x, spans = 30.0, []
    base, extra = SIZE // RANKS, SIZE % RANKS
    begin = 0
    for r in range(RANKS):
        rows = base + (1 if r < extra else 0)
        w = rows * unit
        d.box(x, top, w, height, RANK_FILL, "#60a5fa",
              label=f"rank {r}\nrows {begin} ~ {begin + rows - 1}")
        if r > 0:
            d.box(x, top, strip, height, EDGE_FILL, "#60a5fa")
        if r < RANKS - 1:
            d.box(x + w - strip, top, strip, height, EDGE_FILL, "#60a5fa")
        spans.append((x, w))
        x += w + gap
        begin += rows
    for r in range(RANKS - 1):
        right_edge = spans[r][0] + spans[r][1]
        left_edge = spans[r + 1][0]
        d.box(right_edge + 1, top, strip, height, "#ffffff", MUTED, dashed=True)
        d.box(left_edge - strip - 1, top, strip, height, "#ffffff", MUTED, dashed=True)
        d.line(right_edge - strip / 2, top + 17, left_edge - 3, top + 17, TO_HIGHER, arrow=True, width=1.5)
        d.line(left_edge + strip / 2, top + 37, right_edge + 3, top + 37, TO_LOWER, arrow=True, width=1.5)
    d.text(30, top + height + 13, "row 0 = 0.0", 13, MUTED)
    d.text(WIDTH - 30, top + height + 13, "row 99 = 0.0", 13, MUTED, "end")


def step(d, x0, title, parts, send_at, arrive_at):
    """One time step on ranks 1 and 2, with the rows crossing between them."""
    top, lane = 146, 64
    d.text(x0 - 30, top - 14, title, 15, bold=True)
    for r, y in ((1, top), (2, top + lane)):
        d.text(x0 - 6, y + 18, f"R{r}", 13, MUTED, "end")
        x = x0
        for width, fill, label in parts:
            d.box(x, y, width, 28, fill, "#60a5fa" if fill != WAIT_FILL else "#fb923c", label=label)
            x += width
    d.line(x0 + send_at, top + 28, x0 + arrive_at, top + lane, TO_HIGHER, arrow=True, width=1.5)
    d.line(x0 + send_at + 12, top + lane, x0 + arrive_at + 12, top + 28, TO_LOWER, arrow=True, width=1.5)


def main():
    d = Diagram()
    stripes(d)
    step(d, 70, "Blocking: compute, then exchange",
         [(170, RANK_FILL, "compute all rows"), (170, WAIT_FILL, "blocked")], 180, 300)
    step(d, 500, "Overlap: exchange during the interior",
         [(40, EDGE_FILL, ""), (200, RANK_FILL, "compute interior rows"), (70, WAIT_FILL, "wait")], 44, 216)
    d.line(30, HEIGHT - 22, 60, HEIGHT - 22, TO_HIGHER, arrow=True, width=1.5)
    d.text(66, HEIGHT - 18, "row to the higher rank", 13, MUTED)
    d.line(240, HEIGHT - 22, 270, HEIGHT - 22, TO_LOWER, arrow=True, width=1.5)
    d.text(276, HEIGHT - 18, "row to the lower rank", 13, MUTED)
    d.box(446, HEIGHT - 28, 7, 12, EDGE_FILL, "#60a5fa")
    d.text(458, HEIGHT - 18, "boundary row", 13, MUTED)
    d.box(566, HEIGHT - 28, 7, 12, "#ffffff", MUTED, dashed=True)
    d.text(578, HEIGHT - 18, "ghost row, a copy of the neighbor's boundary", 13, MUTED)
    d.write(OUT)
    print(f"wrote {OUT.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
