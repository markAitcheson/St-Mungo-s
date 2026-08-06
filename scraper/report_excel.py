"""Builds the .xlsx report: a 'Latest comp set' sheet (side-by-side
comparison with colour-coded deltas) and a 'History' sheet (every run ever
recorded, for trend analysis in Excel / the Claude Excel add-in)."""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill("solid", fgColor="1F2937")
HEADER_FONT = Font(color="FFFFFF", bold=True)
RED_FONT = Font(color="B91C1C")    # negative % - red
GREEN_FONT = Font(color="0B7A3B")  # positive % - green


def _pct(v):
    return "" if v is None else f"{v:+.1f}%"


def _money(v):
    return "" if v is None else f"£{v:.2f}"


def _style_header(ws, row=1):
    for cell in ws[row]:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")


def build_excel(comparison: list[dict], history: list[dict], path) -> None:
    wb = Workbook()

    ws = wb.active
    ws.title = "Latest comp set"
    headers = [
        "Property", "Room type", "Category", "Price (pw)", "Current offer",
        "vs last report", "vs baseline", "Equivalent St Mungo's room", "vs St Mungo's",
    ]
    ws.append(headers)
    _style_header(ws)

    ordered = sorted(comparison, key=lambda r: (not r["is_own"], r["property_name"], r["room_type"]))
    for r in ordered:
        ws.append([
            r["property_name"],
            r["room_type"],
            r["category"],
            _money(r["price_pw"]),
            r["offer_text"],
            _pct(r["pct_vs_prev"]),
            _pct(r["pct_vs_baseline"]),
            "-" if r["is_own"] else (r.get("equivalent_room") or ""),
            "-" if r["is_own"] else _pct(r["vs_own_pct"]),
        ])
        excel_row = ws.max_row
        for col, key in ((6, "pct_vs_prev"), (7, "pct_vs_baseline")):
            val = r.get(key)
            if val:
                ws.cell(row=excel_row, column=col).font = RED_FONT if val < 0 else GREEN_FONT

        # Same negative-red/positive-green convention as the trend columns
        # above - red = priced below us (bad for us), green = priced above
        # us (good for us).
        vs_own = r.get("vs_own_pct")
        if vs_own:
            ws.cell(row=excel_row, column=9).font = RED_FONT if vs_own < 0 else GREEN_FONT

    widths = [30, 32, 12, 12, 42, 16, 16, 30, 16]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"

    ws2 = wb.create_sheet("History")
    if history:
        cols = list(history[0].keys())
        ws2.append(cols)
        _style_header(ws2)
        for r in history:
            ws2.append([r.get(c, "") for c in cols])
        for i in range(1, len(cols) + 1):
            ws2.column_dimensions[get_column_letter(i)].width = 20
        ws2.freeze_panes = "A2"

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
