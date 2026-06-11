#!/usr/bin/env python3
"""
Genera il Passaporto del Camminatore — Sentiero Italia CAI.

Pipeline (design e imposizione separati, come da architettura del progetto):

  1. dati (Excel / PostgreSQL) → contesto Jinja2
  2. Jinja2 → sorgente LaTeX (pagine A6 sequenziali)
  3. XeLaTeX → passaporto A6 (PDF leggibile/verificabile)
  4. pypdf  → imposizione 2x2 su A4 fronte/retro con schema
              duplex corretto (cut & stack) + crocini di taglio

Uso:
  python genera_passaporto.py Sardegna
  python genera_passaporto.py Molise Basilicata
  python genera_passaporto.py --list          # elenco regioni disponibili
"""

from __future__ import annotations

import argparse
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import jinja2
import pandas as pd
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas

BASE_DIR = Path(__file__).resolve().parent
EXCEL_PATH = BASE_DIR / "tappe.xlsx"
TEMPLATE_DIR = BASE_DIR / "templates"
ASSET_DIR = BASE_DIR / "assets"
FONT_DIR = BASE_DIR / "fonts"
OUTPUT_DIR = BASE_DIR / "output"

# Dimensioni in punti PostScript (1 mm = 72/25.4 pt)
MM = 72 / 25.4
A6_W, A6_H = 105 * MM, 148 * MM
A4_W, A4_H = A4  # 210 x 297 mm portrait

TAPPE_PER_PAGINA = 6
PAGINE_PER_FOGLIO_A4 = 8  # 4 slot fronte + 4 slot retro
MARGINE_STAMPA_MM = 5      # margine per la versione "con margini di stampa"


# ----------------------------------------------------------------------
# 1. Dati
# ----------------------------------------------------------------------

def natural_ref_key(ref: str):
    """Ordina i ref in modo naturale: 'SI Z2' < 'SI Z10'."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(ref))]


def _ref_valido(valore) -> str | None:
    """Restituisce il ref normalizzato se è completo ('SI' + codice),
    altrimenti None. Un valore pari al solo prefisso 'SI' è incompleto."""
    if pd.isna(valore):
        return None
    s = str(valore).strip()
    if re.match(r"^SI\s+\S+", s):
        return s
    return None


def risolvi_ref(row) -> str | None:
    """Catena di fallback per il codice tappa: ref → name (e varianti
    lingua) → description (estrazione 'Tappa X##'). Il dataset contiene
    righe con ref troncato a 'SI': il codice completo non deve mai
    mancare sul passaporto. Restituisce None se irrecuperabile."""
    for col in ("ref", "name", "name_it", "name_en", "name_fr"):
        if col in row.index:
            ref = _ref_valido(row[col])
            if ref:
                return ref
    # ultima risorsa: "Sentiero Italia - Tappa E46" → "SI E46"
    for col in ("description", "description_it", "description_en", "description_fr"):
        if col in row.index and pd.notna(row[col]):
            m = re.search(r"Tappa\s+(\S+)", str(row[col]))
            if m:
                return f"SI {m.group(1)}"
    return None


def carica_tappe(regioni: list[str], excel_path: Path = EXCEL_PATH) -> list[dict]:
    """Carica le tappe dal file Excel (in produzione: stessa struttura via
    query PostgreSQL su ec_tracks: ref, "from", "to", distance, ascent,
    cai_scale WHERE region = ANY(%(regioni)s))."""
    df = pd.read_excel(excel_path)

    disponibili = set(df["region"].dropna().unique())
    mancanti = [r for r in regioni if r not in disponibili]
    if mancanti:
        raise SystemExit(
            f"Regione/i non trovata/e: {', '.join(mancanti)}.\n"
            f"Disponibili: {', '.join(sorted(disponibili))}"
        )

    df = df[df["region"].isin(regioni)].copy()

    # risoluzione del ref PRIMA dell'ordinamento: con il ref completo la
    # tappa finisce nella posizione giusta (es. 'SI E46' tra E45 ed E47,
    # non in testa) e l'header "Tappe X–Y" risulta corretto
    df["ref_completo"] = df.apply(risolvi_ref, axis=1)
    scartate = df[df["ref_completo"].isna()]
    for _, row in scartate.iterrows():
        print(
            f"⚠ tappa scartata (ref irrecuperabile): "
            f"ref={row['ref']!r} from={row['from']!r} to={row['to']!r}",
            file=sys.stderr,
        )
    df = df[df["ref_completo"].notna()]
    df = df.sort_values("ref_completo", key=lambda s: s.map(natural_ref_key))

    tappe = []
    for _, row in df.iterrows():
        tappe.append({
            "ref": row["ref_completo"],
            # il dataset contiene valori mancanti in from/to/cai_scale:
            # vanno gestiti, mai stampare 'nan' sul passaporto
            "da": str(row["from"]).strip() if pd.notna(row["from"]) else "—",
            "a": str(row["to"]).strip() if pd.notna(row["to"]) else "—",
            "km": f"{float(row['distance']):.1f}",
            "dislivello": str(int(row["ascent"])) if pd.notna(row["ascent"]) else "—",
            "difficolta": str(row["cai_scale"]).strip() if pd.notna(row["cai_scale"]) else "n.d.",
        })
    return tappe


# ----------------------------------------------------------------------
# 2. Contesto e rendering Jinja2
# ----------------------------------------------------------------------

_LATEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}


def latex_escape(value) -> str:
    """Filtro Jinja2: rende sicuri i dati liberi (toponimi ecc.) per LaTeX."""
    s = str(value)
    return "".join(_LATEX_SPECIALS.get(ch, ch) for ch in s)


def costruisci_contesto(regioni: list[str], tappe: list[dict]) -> dict:
    pagine_timbri = []
    for i in range(0, len(tappe), TAPPE_PER_PAGINA):
        gruppo = tappe[i:i + TAPPE_PER_PAGINA]
        celle = [
            {"numero": i + j + 1, "tappa": t}
            for j, t in enumerate(gruppo)
        ]
        # caselle vuote nell'ultima pagina (numerazione casella 1..6)
        while len(celle) < TAPPE_PER_PAGINA:
            celle.append({"numero": len(celle) + 1, "tappa": None})
        def _ref_breve(ref: str) -> str:
            # toglie il prefisso comune "SI " per compattezza nell'header
            return ref[3:] if ref.startswith("SI ") else ref

        pagine_timbri.append({
            "n_da": i + 1,
            "n_a": min(i + TAPPE_PER_PAGINA, len(tappe)),
            "ref_da": _ref_breve(gruppo[0]["ref"]),
            "ref_a": _ref_breve(gruppo[-1]["ref"]),
            "celle": celle,
        })

    pagine_logiche = 2 + len(pagine_timbri)
    pagine_totali = math.ceil(pagine_logiche / 4) * 4
    pagine_note = pagine_totali - pagine_logiche

    return {
        "regione_nome": " · ".join(regioni),
        "pagine_timbri": pagine_timbri,
        "totale_tappe": len(tappe),
        "pagine_note": pagine_note,
        "font_path": str(FONT_DIR) + "/",
        "asset_path": str(ASSET_DIR) + "/",
    }


def renderizza_tex(context: dict) -> str:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
        block_start_string="((*", block_end_string="*))",
        variable_start_string="(((", variable_end_string=")))",
        comment_start_string="((#", comment_end_string="#))",
        autoescape=False,
        undefined=jinja2.StrictUndefined,
        finalize=lambda v: latex_escape(v) if isinstance(v, str) else v,
    )
    return env.get_template("passaporto.tex.j2").render(**context)


# ----------------------------------------------------------------------
# 3. Compilazione XeLaTeX → PDF A6 sequenziale
# ----------------------------------------------------------------------

def compila_xelatex(tex_source: str, build_dir: Path) -> Path:
    tex_path = build_dir / "passaporto.tex"
    tex_path.write_text(tex_source, encoding="utf-8")
    # due passate: i nodi TikZ "remember picture" leggono le coordinate
    # di pagina dal .aux della passata precedente
    for _ in range(2):
        result = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", "-halt-on-error",
             f"-output-directory={build_dir}", str(tex_path)],
            capture_output=True, text=True,
        )
    pdf_path = build_dir / "passaporto.pdf"
    if result.returncode != 0 or not pdf_path.exists():
        log = (build_dir / "passaporto.log")
        tail = log.read_text(errors="ignore")[-3000:] if log.exists() else result.stdout[-3000:]
        raise RuntimeError(f"Compilazione XeLaTeX fallita:\n{tail}")
    return pdf_path


# ----------------------------------------------------------------------
# 4. Imposizione 2x2 su A4 fronte/retro — RIPIEGABILE (piega a croce)
# ----------------------------------------------------------------------
#
# Il foglio A4, piegato in 4 (piega orizzontale + piega verticale),
# diventa un passaporto A6. Schema come il modello SICAI di riferimento:
#
#   FRONTE (esterno)              RETRO (interno, tutto dritto)
#   ┌─────────┬─────────┐         ┌─────────┬─────────┐
#   │  4 ↓    │   3 ↓   │         │    5    │    6    │
#   │ (capov.)│ (capov.)│         │         │         │
#   ├─────────┼─────────┤         ├─────────┼─────────┤
#   │    2    │    1    │         │    7    │    8    │
#   │ (retro  │ (coper- │         │         │ (Note)  │
#   │  cop.)  │  tina)  │         │         │         │
#   └─────────┴─────────┘         └─────────┴─────────┘
#
# Le tappe INIZIANO nel primo A4 (fronte alto = pagine 3 e 4, cioè le
# prime pagine timbri, partendo dallo slot in alto a DESTRA); le
# eventuali pagine Note cadono alla fine della sequenza, quindi negli
# ultimi slot dell'ultimo foglio.
#
# Chiuso: copertina davanti (fronte basso-dx), retro copertina dietro
# (fronte basso-sx). Aperto completamente: l'interno A4 si legge come
# quattro sezioni A6 dritte (3→4→5→6); ripiegando si trovano le due
# sezioni esterne superiori (7, 8), stampate capovolte perché risultino
# dritte dopo la piega orizzontale.

# slot: (colonna, riga) con riga 0 = in alto
_SLOT_TL, _SLOT_TR, _SLOT_BL, _SLOT_BR = (0, 0), (1, 0), (0, 1), (1, 1)

# ordine delle pagine logiche del foglio: (lato, slot, ruota180)
# lato 0 = fronte A4, lato 1 = retro A4
_FOLD_LAYOUT = [
    (0, _SLOT_BR, False),  # 1: copertina
    (0, _SLOT_BL, False),  # 2: retro copertina
    (0, _SLOT_TR, True),   # 3: prime tappe (fronte alto-dx, capovolta)
    (0, _SLOT_TL, True),   # 4: (fronte alto-sx, capovolta)
    (1, _SLOT_TL, False),  # 5: interno
    (1, _SLOT_TR, False),  # 6
    (1, _SLOT_BL, False),  # 7
    (1, _SLOT_BR, False),  # 8: ultima pagina del foglio (es. Note)
]


def _slot_origin(slot: tuple[int, int]) -> tuple[float, float]:
    col, row = slot
    x = col * A6_W
    # le due righe sono adiacenti e allineate in alto (piega unica al centro)
    y = A4_H - (row + 1) * A6_H
    return x, y


def _crocini_overlay() -> "PdfReader":
    """Pagina A4 con segni di piega ai bordi (croce 2x2)."""
    import io
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(A4_W, A4_H))
    c.setLineWidth(0.3)
    c.setStrokeColorRGB(0.45, 0.45, 0.45)
    c.setDash(2, 2)
    tick = 4 * MM
    x_fold = A6_W                          # piega verticale centrale
    y_fold = A4_H - A6_H                   # piega orizzontale
    c.line(x_fold, A4_H, x_fold, A4_H - tick)
    c.line(x_fold, 0, x_fold, tick)
    c.line(0, y_fold, tick, y_fold)
    c.line(A4_W - tick, y_fold, A4_W, y_fold)
    c.showPage()
    c.save()
    buf.seek(0)
    return PdfReader(buf)


def imponi_su_a4(a6_pdf: Path, output_pdf: Path, crocini: bool = True,
                 margine_mm: float = 0.0) -> int:
    """Imposizione 2x2 fronte/retro per ripiegabile a croce.

    margine_mm = 0  → senza margini (al vivo, per stampa tipografica)
    margine_mm > 0  → montaggio scalato e centrato dentro l'area utile
                      A4 meno il margine (stampanti non borderless)
    """
    reader = PdfReader(str(a6_pdf))
    n = len(reader.pages)
    n_fogli = math.ceil(n / PAGINE_PER_FOGLIO_A4)
    writer = PdfWriter()
    marks = _crocini_overlay().pages[0] if crocini else None

    m = margine_mm * MM
    scala = min((A4_W - 2 * m) / A4_W, (A4_H - 2 * m) / A4_H)
    off_x = (A4_W - A4_W * scala) / 2
    off_y = (A4_H - A4_H * scala) / 2
    riduzione = Transformation().scale(scala).translate(tx=off_x, ty=off_y)

    for foglio in range(n_fogli):
        base = foglio * PAGINE_PER_FOGLIO_A4
        fronte = writer.add_blank_page(width=A4_W, height=A4_H)
        retro = writer.add_blank_page(width=A4_W, height=A4_H)
        lati = (fronte, retro)

        for offset, (lato, slot, ruota) in enumerate(_FOLD_LAYOUT):
            page_idx = base + offset
            if page_idx >= n:
                continue
            x, y = _slot_origin(slot)
            t = Transformation()
            if ruota:
                # rotazione 180° dentro lo slot
                t = t.rotate(180).translate(tx=x + A6_W, ty=y + A6_H)
            else:
                t = t.translate(tx=x, ty=y)
            if margine_mm > 0:
                t = Transformation(t.ctm).scale(scala).translate(tx=off_x, ty=off_y)
            lati[lato].merge_transformed_page(reader.pages[page_idx], t)

        for dest in lati:
            if marks is not None:
                if margine_mm > 0:
                    dest.merge_transformed_page(marks, riduzione)
                else:
                    dest.merge_page(marks)
            dest.mediabox = RectangleObject([0, 0, A4_W, A4_H])

    with open(output_pdf, "wb") as f:
        writer.write(f)
    return n_fogli


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------

def genera_passaporto(regioni: list[str], output_dir: Path = OUTPUT_DIR) -> dict:
    tappe = carica_tappe(regioni)
    if not tappe:
        raise SystemExit("Nessuna tappa trovata per le regioni richieste.")

    context = costruisci_contesto(regioni, tappe)
    tex_source = renderizza_tex(context)

    slug = "_".join(
        re.sub(r"[^a-z0-9]+", "_", r.lower()).strip("_") for r in regioni
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    out_a6 = output_dir / f"passaporto_{slug}_A6.pdf"
    out_a4 = output_dir / f"passaporto_{slug}_A4_stampa.pdf"
    out_a4_margini = output_dir / f"passaporto_{slug}_A4_stampa_margini.pdf"

    with tempfile.TemporaryDirectory() as tmp:
        pdf_a6 = compila_xelatex(tex_source, Path(tmp))
        shutil.copy(pdf_a6, out_a6)

    n_fogli = imponi_su_a4(out_a6, out_a4)                       # senza margini (al vivo)
    imponi_su_a4(out_a6, out_a4_margini, margine_mm=MARGINE_STAMPA_MM)

    info = {
        "regioni": regioni,
        "tappe": len(tappe),
        "pagine_timbri": len(context["pagine_timbri"]),
        "pagine_note": context["pagine_note"],
        "pagine_logiche_totali": 2 + len(context["pagine_timbri"]) + context["pagine_note"],
        "fogli_a4": n_fogli,
        "pdf_a6": out_a6,
        "pdf_a4": out_a4,
        "pdf_a4_margini": out_a4_margini,
    }
    print(
        f"✔ {context['regione_nome']}: {info['tappe']} tappe, "
        f"{info['pagine_timbri']} pagine timbri, {info['pagine_note']} pagine note, "
        f"{info['fogli_a4']} fogli A4 fronte/retro\n"
        f"  → {out_a6.name}\n  → {out_a4.name} (senza margini)\n"
        f"  → {out_a4_margini.name} (margini {MARGINE_STAMPA_MM} mm)"
    )
    return info


def main():
    parser = argparse.ArgumentParser(description="Genera il Passaporto del Camminatore")
    parser.add_argument("regioni", nargs="*", help="Una o più regioni (es. Sardegna, oppure Molise Basilicata)")
    parser.add_argument("--list", action="store_true", help="Elenca le regioni disponibili")
    args = parser.parse_args()

    if args.list or not args.regioni:
        df = pd.read_excel(EXCEL_PATH)
        counts = df["region"].value_counts()
        print("Regioni disponibili (tappe):")
        for reg, n in counts.items():
            print(f"  {reg}: {n}")
        if not args.regioni:
            sys.exit(0)

    genera_passaporto(args.regioni)


if __name__ == "__main__":
    main()
