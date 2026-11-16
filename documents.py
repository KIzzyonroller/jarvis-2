"""
Real documents, not just text files: Word (.docx), Excel (.xlsx), PowerPoint (.pptx) and PDF, made from a simple
outline he writes, plus reading them back (and PDFs). Plain text, Markdown, CSV, code and the rest still go through
files write.

The outline he sends (all optional except what the kind needs):
  docx / pdf: {"title": "...", "blocks": [{"h": "Heading"}, {"h2": "Sub"}, {"p": "Paragraph"},
               {"bullets": ["a", "b"]}, {"numbers": ["a", "b"]}, {"table": [["Head", "Head"], ["a", "b"]]},
               {"quote": "..."}, {"pagebreak": true}]}
  xlsx:       {"sheets": [{"name": "Budget", "rows": [["Item", "Cost"], ["Rent", 900], ["Total", "=SUM(B2:B2)"]],
               "widths": [24, 12]}]}            (the first row is the header; formulas start with =)
  pptx:       {"title": "Deck title", "subtitle": "...", "slides": [{"title": "...", "bullets": ["..."],
               "notes": "speaker notes"}]}
"""
from pathlib import Path

KINDS = ("docx", "xlsx", "pptx", "pdf")


def _txt(v):
    return "" if v is None else str(v)


# ------------------------------------------------------------------ making
def make(kind, path, spec):
    kind = (kind or Path(path).suffix.lstrip(".")).lower()
    if kind not in KINDS:
        raise ValueError(f"I can make {', '.join(KINDS)}; use files write for {kind or 'that'}.")
    p = Path(path)
    if p.suffix.lower() != "." + kind:
        p = p.with_suffix("." + kind)
    p.parent.mkdir(parents=True, exist_ok=True)
    {"docx": _docx, "xlsx": _xlsx, "pptx": _pptx, "pdf": _pdf}[kind](p, spec or {})
    return p


def _docx(p, spec):
    from docx import Document
    from docx.shared import Pt
    d = Document()
    d.styles["Normal"].font.name = "Calibri"
    d.styles["Normal"].font.size = Pt(11)
    if spec.get("title"):
        d.add_heading(_txt(spec["title"]), 0)
    for b in spec.get("blocks") or []:
        if not isinstance(b, dict):
            d.add_paragraph(_txt(b))
        elif "h" in b:
            d.add_heading(_txt(b["h"]), 1)
        elif "h2" in b:
            d.add_heading(_txt(b["h2"]), 2)
        elif "p" in b:
            d.add_paragraph(_txt(b["p"]))
        elif "bullets" in b:
            for x in b["bullets"]:
                d.add_paragraph(_txt(x), style="List Bullet")
        elif "numbers" in b:
            for x in b["numbers"]:
                d.add_paragraph(_txt(x), style="List Number")
        elif "quote" in b:
            d.add_paragraph(_txt(b["quote"]), style="Intense Quote")
        elif "table" in b and b["table"]:
            rows = b["table"]
            t = d.add_table(rows=len(rows), cols=max(len(r) for r in rows))
            t.style = "Light Grid Accent 1"
            for i, r in enumerate(rows):
                for j, v in enumerate(r):
                    t.cell(i, j).text = _txt(v)
                    if i == 0:
                        for run in t.cell(i, j).paragraphs[0].runs:
                            run.bold = True
        elif b.get("pagebreak"):
            d.add_page_break()
    d.save(p)


def _xlsx(p, spec):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    sheets = spec.get("sheets") or [{"name": "Sheet1", "rows": spec.get("rows") or []}]
    for n, sh in enumerate(sheets):
        ws = wb.active if n == 0 else wb.create_sheet()
        ws.title = _txt(sh.get("name") or f"Sheet{n + 1}")[:31]
        rows = sh.get("rows") or []
        for r in rows:
            ws.append([_cell(v) for v in r])
        if rows:
            for c in ws[1]:
                c.font = Font(bold=True)
                c.fill = PatternFill("solid", fgColor="DDE7F0")
            ws.freeze_panes = "A2"
        widths = sh.get("widths") or []
        cols = max((len(r) for r in rows), default=0)
        for j in range(cols):
            w = widths[j] if j < len(widths) else min(48, max(8, max(len(_txt(r[j])) if j < len(r) else 0 for r in rows) + 2))
            ws.column_dimensions[get_column_letter(j + 1)].width = w
    wb.save(p)


def _cell(v):
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("="):
            return s
        try:
            return int(s) if s.lstrip("-").isdigit() else float(s.replace(",", "")) if s.replace(",", "").replace(".", "", 1).lstrip("-").isdigit() else v
        except ValueError:
            return v
    return v


def _pptx(p, spec):
    from pptx import Presentation
    from pptx.util import Pt
    pr = Presentation()
    pr.slide_width, pr.slide_height = 12192000, 6858000          # 16:9
    if spec.get("title"):
        s = pr.slides.add_slide(pr.slide_layouts[0])
        s.shapes.title.text = _txt(spec["title"])
        if spec.get("subtitle") and len(s.placeholders) > 1:
            s.placeholders[1].text = _txt(spec["subtitle"])
    for sl in spec.get("slides") or []:
        s = pr.slides.add_slide(pr.slide_layouts[1])
        s.shapes.title.text = _txt(sl.get("title"))
        body = s.placeholders[1].text_frame
        body.clear()
        for i, x in enumerate(sl.get("bullets") or []):
            para = body.paragraphs[0] if i == 0 else body.add_paragraph()
            para.text = _txt(x)
            para.font.size = Pt(22)
        if sl.get("notes"):
            s.notes_slide.notes_text_frame.text = _txt(sl["notes"])
    pr.save(p)


def _pdf(p, spec):
    from fpdf import FPDF
    pdf = FPDF()
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()
    font = "Helvetica"
    try:                                         # a Windows font so accents and symbols print
        import os
        ttf = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        if (ttf / "segoeui.ttf").exists():
            pdf.add_font("Segoe", "", str(ttf / "segoeui.ttf"))
            pdf.add_font("Segoe", "B", str(ttf / "segoeuib.ttf"))
            font = "Segoe"
    except Exception:
        pass

    def safe(s):
        s = _txt(s)
        return s if font != "Helvetica" else s.encode("latin-1", "replace").decode("latin-1")
    w = pdf.w - pdf.l_margin - pdf.r_margin
    if spec.get("title"):
        pdf.set_font(font, "B", 22)
        pdf.multi_cell(w, 11, safe(spec["title"]), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
    for b in spec.get("blocks") or []:
        if not isinstance(b, dict):
            b = {"p": b}
        if "h" in b or "h2" in b:
            pdf.ln(2)
            pdf.set_font(font, "B", 16 if "h" in b else 13)
            pdf.multi_cell(w, 8, safe(b.get("h", b.get("h2"))), new_x="LMARGIN", new_y="NEXT")
        elif "p" in b or "quote" in b:
            pdf.set_font(font, "", 11)
            pdf.multi_cell(w, 6, safe(b.get("p", b.get("quote"))), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        elif "bullets" in b or "numbers" in b:
            pdf.set_font(font, "", 11)
            for i, x in enumerate(b.get("bullets") or b.get("numbers")):
                mark = f"{i + 1}." if "numbers" in b else "-"
                pdf.multi_cell(w, 6, safe(f"  {mark} {x}"), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        elif "table" in b and b["table"]:
            pdf.set_font(font, "", 10)
            with pdf.table() as t:
                for i, r in enumerate(b["table"]):
                    row = t.row()
                    for v in r:
                        row.cell(safe(v))
            pdf.ln(3)
        elif b.get("pagebreak"):
            pdf.add_page()
    pdf.output(str(p))


# ------------------------------------------------------------------ reading
def read(p, limit=12000):
    p = Path(p)
    ext = p.suffix.lower()
    out = []
    if ext == ".docx":
        from docx import Document
        d = Document(p)
        for para in d.paragraphs:
            if para.text.strip():
                st = para.style.name.lower() if para.style is not None else ""
                out.append(("# " if st.startswith("heading") or st == "title" else "") + para.text)
        for t in d.tables:
            for r in t.rows:
                out.append(" | ".join(c.text for c in r.cells))
    elif ext in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        vals = load_workbook(p, data_only=True, read_only=True)
        forms = load_workbook(p, read_only=True)          # formulas, for cells Excel hasn't calculated yet
        for ws, wf in zip(vals.worksheets, forms.worksheets):
            out.append(f"## sheet {ws.title}")
            for i, (r, rf) in enumerate(zip(ws.iter_rows(values_only=True), wf.iter_rows(values_only=True))):
                if i >= 400:
                    out.append("[more rows]")
                    break
                r = [v if v is not None else f for v, f in zip(r, rf)]
                if any(v is not None for v in r):
                    out.append(", ".join("" if v is None else str(v) for v in r))
    elif ext == ".pptx":
        from pptx import Presentation
        for i, s in enumerate(Presentation(p).slides, 1):
            out.append(f"## slide {i}")
            for sh in s.shapes:
                if sh.has_text_frame and sh.text_frame.text.strip():
                    out.append(sh.text_frame.text)
            if s.has_notes_slide and s.notes_slide.notes_text_frame.text.strip():
                out.append("notes: " + s.notes_slide.notes_text_frame.text)
    elif ext == ".pdf":
        from pypdf import PdfReader
        r = PdfReader(str(p))
        for i, pg in enumerate(r.pages[:60], 1):
            t = (pg.extract_text() or "").strip()
            if t:
                out.append(f"## page {i}\n{t}")
        if not out:
            return f"{p.name} has no text layer (probably scanned). I can look at it on screen instead."
    else:
        return None
    text = "\n".join(out)
    return text[:limit] + (f"\n\n[truncated, it's longer than {limit} characters]" if len(text) > limit else "")
