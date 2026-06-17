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
  python genera_passaporto.py --all           # tutti gli 8 passaporti
  python genera_passaporto.py "Nord Est"      # un gruppo specifico
  python genera_passaporto.py --list          # elenco gruppi disponibili
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

from genera_copertine import prepara_copertina
from genera_mappe import genera_filigrana_tracciato, genera_mappa_gruppo, ref_a_sicai_code
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas

BASE_DIR = Path(__file__).resolve().parent
EXCEL_SOURCE_PATH = BASE_DIR / "tappe.xlsx"
EXCEL_PATH = BASE_DIR / "tappe_passaporto.xlsx"
SHEET_TRACCIATI = "Tracciati"
SHEET_RIEPILOGO_REGIONE = "Riepilogo per Regione"
SHEET_RIEPILOGO_GRUPPO = "Riepilogo per Gruppo"
TEMPLATE_DIR = BASE_DIR / "templates"
ASSET_DIR = BASE_DIR / "assets"
FONT_DIR = BASE_DIR / "fonts"
OUTPUT_DIR = BASE_DIR / "output"
DIR_STAMPA = OUTPUT_DIR / "stampa"
DIR_STAMPA_MARGINI = OUTPUT_DIR / "stampa_margini"

# Dimensioni in punti PostScript (1 mm = 72/25.4 pt)
MM = 72 / 25.4
A6_W, A6_H = 105 * MM, 148 * MM
A4_W, A4_H = A4  # 210 x 297 mm portrait
A5L_W, A5L_H = 210 * MM, 148 * MM  # A5 landscape (formato Val d'Aosta)

TAPPE_PER_PAGINA = 12      # griglia 3x4 di timbri quadrati per pagina A6
PAGINE_PER_FOGLIO_A4 = 8   # 4 slot fronte + 4 slot retro
PAGINE_PER_FOGLIO_A5 = 4   # 2 pannelli fronte + 2 pannelli retro
MAX_TAPPE_A4 = 84          # copertina + 7 pagine timbri × 12
MAX_TAPPE_A5 = 36          # copertina + 3 pagine timbri × 12 (Val d'Aosta)
MARGINE_STAMPA_MM = 5      # margine per la versione "con margini di stampa"
MAPPA_CREDIT = "© CAI © OpenStreetMap"

# ----------------------------------------------------------------------
# Raggruppamenti: 8 passaporti, 1 foglio ciascuno (caricati da Excel).
# Capacità per foglio: A4 = copertina + 7 pagine timbri (84 tappe max);
# A5 (solo Val d'Aosta) = copertina + 3 facciate (36 tappe max).
# ----------------------------------------------------------------------

_GRUPPI_CACHE: dict[str, dict] | None = None


def carica_gruppi_da_excel(excel_path: Path = EXCEL_PATH) -> dict[str, dict]:
    """Ordine gruppi da Riepilogo per Gruppo; regioni e formato da Excel."""
    rg = pd.read_excel(excel_path, sheet_name=SHEET_RIEPILOGO_GRUPPO)
    rr = pd.read_excel(excel_path, sheet_name=SHEET_RIEPILOGO_REGIONE)
    gruppi: dict[str, dict] = {}
    for _, row in rg.iterrows():
        nome = str(row["gruppo"]).strip()
        regioni = rr.loc[rr["gruppo"] == nome, "region"].tolist()
        if not regioni:
            raise SystemExit(
                f"Nessuna regione in {SHEET_RIEPILOGO_REGIONE} "
                f"per il gruppo {nome!r}."
            )
        gruppi[nome] = {
            "regioni": regioni,
            "formato": str(row["formato"]).strip(),
            "num_totale": int(row["num_totale"]),
        }
    return gruppi


def get_gruppi(excel_path: Path = EXCEL_PATH) -> dict[str, dict]:
    """Config gruppi in cache (ordine = foglio Riepilogo per Gruppo)."""
    global _GRUPPI_CACHE
    if _GRUPPI_CACHE is None:
        _GRUPPI_CACHE = carica_gruppi_da_excel(excel_path)
    return _GRUPPI_CACHE


GRUPPI = get_gruppi()


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


def carica_tappe(
    gruppo_nome: str, regioni: list[str], excel_path: Path = EXCEL_PATH
) -> list[dict]:
    """Carica le tappe dal file Excel per blocco regionale (ordine da
    `regioni`, cioè foglio Riepilogo per Regione) e, dentro ogni regione,
    preserva il senso del Sentiero Italia CAI nel foglio Tracciati.

    In produzione: stessa struttura via query PostgreSQL con ORDER BY
    esplicito sul percorso del sentiero."""
    df_full = pd.read_excel(excel_path, sheet_name=SHEET_TRACCIATI)
    df_full["_idx_trail"] = df_full.index

    if "gruppo" not in df_full.columns:
        raise SystemExit(
            f"Colonna 'gruppo' assente in {excel_path.name} "
            f"(foglio {SHEET_TRACCIATI})."
        )

    df = df_full[df_full["gruppo"] == gruppo_nome].copy()
    if df.empty:
        raise SystemExit(
            f"Nessuna tappa per il gruppo {gruppo_nome!r} in {excel_path.name}."
        )

    regioni_presenti = set(df["region"].dropna().unique())
    regioni_attese = set(regioni)
    if regioni_presenti != regioni_attese:
        raise SystemExit(
            f"Regioni del gruppo {gruppo_nome!r} non coerenti con la config Excel.\n"
            f"  Attese: {', '.join(sorted(regioni_attese))}\n"
            f"  Nel file: {', '.join(sorted(regioni_presenti))}"
        )

    ordine_regione = {r: i for i, r in enumerate(regioni)}
    df["_ord_regione"] = df["region"].map(ordine_regione)
    df = df.sort_values(["_ord_regione", "_idx_trail"]).drop(
        columns=["_ord_regione", "_idx_trail"]
    )

    df["ref_completo"] = df.apply(risolvi_ref, axis=1)
    scartate = df[df["ref_completo"].isna()]
    for _, row in scartate.iterrows():
        print(
            f"⚠ tappa scartata (ref irrecuperabile): "
            f"ref={row['ref']!r} from={row['from']!r} to={row['to']!r}",
            file=sys.stderr,
        )
    df = df[df["ref_completo"].notna()]

    tappe = []
    for _, row in df.iterrows():
        tappe.append({
            "ref": row["ref_completo"],
            "regione": str(row["region"]).strip(),
            # campi opzionali: None = non mostrare la riga sul passaporto
            "da": str(row["from"]).strip() if pd.notna(row["from"]) else None,
            "a": str(row["to"]).strip() if pd.notna(row["to"]) else None,
            "km": (
                str(round(float(row["distance"])))
                if pd.notna(row["distance"])
                else "n.d."
            ),
            "dislivello": str(int(row["ascent"])) if pd.notna(row["ascent"]) else None,
            "discesa": str(int(row["descent"])) if pd.notna(row["descent"]) else None,
            "difficolta": (
                str(row["cai_scale"]).strip()
                if "cai_scale" in row.index and pd.notna(row["cai_scale"])
                else "n.d."
            ),
            # valori numerici grezzi per gli aggregati di copertina
            "km_val": float(row["distance"]) if pd.notna(row["distance"]) else 0.0,
            "ascent_val": int(row["ascent"]) if pd.notna(row["ascent"]) else 0,
            "descent_val": int(row["descent"]) if pd.notna(row["descent"]) else 0,
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


def costruisci_contesto(gruppo_nome: str, regioni: list[str], tappe: list[dict]) -> dict:
    pagine_timbri = []
    for i in range(0, len(tappe), TAPPE_PER_PAGINA):
        gruppo = tappe[i:i + TAPPE_PER_PAGINA]
        celle = [
            {"numero": i + j + 1, "tappa": t}
            for j, t in enumerate(gruppo)
        ]
        # caselle vuote nell'ultima pagina (numerazione casella 1..12)
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

    # 1 sola pagina fissa (copertina): la pagina mappa è stata rimossa
    pagine_logiche = 1 + len(pagine_timbri)
    pagine_totali = math.ceil(pagine_logiche / 4) * 4
    pagine_note = pagine_totali - pagine_logiche

    # elenco regioni su riga unica, ordine Riepilogo per Regione
    regioni_lista = ""
    if not (len(regioni) == 1 and gruppo_nome == regioni[0]):
        regioni_lista = ", ".join(regioni)

    # recap UNICO aggregato su tutte le regioni del gruppo (riga 3 copertina)
    def _fmt_int(n: int) -> str:
        return f"{n:,}".replace(",", ".")

    statistiche_totali = {
        "tappe": len(tappe),
        "km": _fmt_int(round(sum(t["km_val"] for t in tappe))),
        "dislivello": _fmt_int(sum(t["ascent_val"] for t in tappe)),
        "discesa": _fmt_int(sum(t["descent_val"] for t in tappe)),
    }

    # blocco immagine + crediti — geometria UNIFORME per tutti i gruppi (mono e
    # multi): stats_bottom_mm è COSTANTE => slot foto identico => stesso crop in
    # genera_copertine.py. Il blocco testo è sempre 3 righe a Y fisse (nome -56,
    # elenco regioni -66, recap -72, vedi template); nei monoregione la riga 2
    # non viene emessa ma il recap (riga 3) resta alla stessa Y, quindi nulla si
    # sposta. Gap inferiore e margine footer unificati (era diverso mono/multi).
    _STATS_BOTTOM_MM = 68        # fine blocco testo, costante per tutti i gruppi
    _CREDIT_BAND_MM = 5          # credito foto 2 righe (size adattata a 93mm)
    _URL_ANCHOR_MM = 143
    _URL_HEIGHT_MM = 3.5
    _FOOTER_MARGIN_MM = 1
    _TOP_GAP_MM = 1
    _BOTTOM_GAP_MM = _TOP_GAP_MM

    stats_bottom_mm = _STATS_BOTTOM_MM
    url_zone_top_mm = _URL_ANCHOR_MM - _URL_HEIGHT_MM - _FOOTER_MARGIN_MM
    available_mm = url_zone_top_mm - stats_bottom_mm
    image_height_mm = max(
        8,
        available_mm - _CREDIT_BAND_MM - _TOP_GAP_MM - _BOTTOM_GAP_MM,
    )
    placeholder_top_mm = stats_bottom_mm + _TOP_GAP_MM
    placeholder_image_bottom_mm = placeholder_top_mm + image_height_mm
    copertina_credit_line_mm = placeholder_image_bottom_mm + _TOP_GAP_MM
    copertina_credit_text_mm = copertina_credit_line_mm + 0.5

    return {
        "gruppo_nome": gruppo_nome,
        "regioni_lista": regioni_lista,
        "statistiche_totali": statistiche_totali,
        "pagine_timbri": pagine_timbri,
        "totale_tappe": len(tappe),
        "pagine_note": pagine_note,
        "pagine_totali": pagine_totali,
        "pagine_numerate": pagine_totali - 1,
        "placeholder_top_mm": placeholder_top_mm,
        "placeholder_image_bottom_mm": placeholder_image_bottom_mm,
        "placeholder_image_height_mm": image_height_mm,
        "copertina_credit_line_mm": copertina_credit_line_mm,
        "copertina_credit_text_mm": copertina_credit_text_mm,
        "mappa_credit": MAPPA_CREDIT,
        "font_path": str(FONT_DIR) + "/",
        "asset_path": str(ASSET_DIR) + "/",
    }


def renderizza_tex(context: dict, template: str = "passaporto.tex.j2") -> str:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
        block_start_string="((*", block_end_string="*))",
        variable_start_string="(((", variable_end_string=")))",
        comment_start_string="((#", comment_end_string="#))",
        autoescape=False,
        undefined=jinja2.StrictUndefined,
        finalize=lambda v: latex_escape(v) if isinstance(v, str) else v,
    )
    return env.get_template(template).render(**context)


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
#   │  3 ↓    │   2 ↓   │         │    4    │    5    │
#   │ (capov.)│ (capov.)│         │         │         │
#   ├─────────┼─────────┤         ├─────────┼─────────┤
#   │  8      │    1    │         │    6    │    7    │
#   │ (Note)  │ (coper- │         │         │         │
#   │         │  tina)  │         │         │         │
#   └─────────┴─────────┘         └─────────┴─────────┘
#
# Il PDF sequenziale ha solo copertina + timbri + Note (niente retro
# copertina). Le tappe INIZIANO a pag. 2 nel fronte alto-dx (slot
# capovolto); proseguono 3→4→5→6→7; le eventuali Note cadono a pag. 8
# (basso-sx fronte, slot ex retro copertina).
#
# Chiuso: copertina davanti (fronte basso-dx). Aperto completamente:
# l'interno A4 si legge come quattro sezioni A6 dritte (2→3→4→5);
# ripiegando si trovano le sezioni 6 e 7; la pag. 8 (Note) resta sul
# retro esterno in basso-sx.

# slot: (colonna, riga) con riga 0 = in alto
_SLOT_TL, _SLOT_TR, _SLOT_BL, _SLOT_BR = (0, 0), (1, 0), (0, 1), (1, 1)

# ordine delle pagine logiche del foglio: (lato, slot, ruota180)
# lato 0 = fronte A4, lato 1 = retro A4
_FOLD_LAYOUT = [
    (0, _SLOT_BR, False),  # 1: copertina
    (0, _SLOT_TR, True),   # 2: prime tappe (alto-dx, capovolta)
    (0, _SLOT_TL, True),   # 3
    (1, _SLOT_TL, False),  # 4
    (1, _SLOT_TR, False),  # 5
    (1, _SLOT_BL, False),  # 6
    (1, _SLOT_BR, False),  # 7: ultime tappe del foglio
    (0, _SLOT_BL, False),  # 8: Note (basso-sx fronte, ex retro copertina)
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
# 4-bis. Imposizione 2x1 su A5 landscape — formato dedicato Val d'Aosta
# ----------------------------------------------------------------------
#
# Il foglio A5 landscape (210 x 148 mm), piegato in due lungo la piega
# verticale centrale, diventa un libretto A6. Layout a 4 facciate:
#
#   FRONTE (esterno)              RETRO (interno)
#   ┌─────────┬─────────┐         ┌─────────┬─────────┐
#   │    4    │    1    │         │    2    │    3    │
#   │ (retro  │ (coper- │         │         │         │
#   │  cop.)  │  tina)  │         │         │         │
#   └─────────┴─────────┘         └─────────┴─────────┘
#
# Chiuso: copertina davanti (fronte destra), retro copertina dietro
# (fronte sinistra). Aperto: l'interno si legge come doppia pagina 2-3.
# Stampa duplex con ribaltamento sul lato corto (le colonne del retro
# sono speculari rispetto al fronte).

# ordine delle pagine logiche del foglio A5: (lato, colonna)
# lato 0 = fronte, lato 1 = retro; colonna 0 = sinistra, 1 = destra
_FOLD_LAYOUT_A5 = [
    (0, 1),  # 1: copertina (fronte destra)
    (1, 0),  # 2: interno sinistra
    (1, 1),  # 3: interno destra
    (0, 0),  # 4: retro copertina (fronte sinistra)
]


def _crocini_overlay_a5() -> "PdfReader":
    """Pagina A5 landscape con segni di piega ai bordi (piega verticale)."""
    import io
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(A5L_W, A5L_H))
    c.setLineWidth(0.3)
    c.setStrokeColorRGB(0.45, 0.45, 0.45)
    c.setDash(2, 2)
    tick = 4 * MM
    x_fold = A6_W  # piega verticale centrale
    c.line(x_fold, A5L_H, x_fold, A5L_H - tick)
    c.line(x_fold, 0, x_fold, tick)
    c.showPage()
    c.save()
    buf.seek(0)
    return PdfReader(buf)


def imponi_su_a5(a6_pdf: Path, output_pdf: Path, crocini: bool = True,
                 margine_mm: float = 0.0) -> int:
    """Imposizione 2x1 fronte/retro su A5 landscape (libretto a piega unica).

    margine_mm = 0  → senza margini (al vivo, per stampa tipografica)
    margine_mm > 0  → montaggio scalato e centrato dentro l'area utile
    """
    reader = PdfReader(str(a6_pdf))
    n = len(reader.pages)
    n_fogli = math.ceil(n / PAGINE_PER_FOGLIO_A5)
    writer = PdfWriter()
    marks = _crocini_overlay_a5().pages[0] if crocini else None

    m = margine_mm * MM
    scala = min((A5L_W - 2 * m) / A5L_W, (A5L_H - 2 * m) / A5L_H)
    off_x = (A5L_W - A5L_W * scala) / 2
    off_y = (A5L_H - A5L_H * scala) / 2
    riduzione = Transformation().scale(scala).translate(tx=off_x, ty=off_y)

    for foglio in range(n_fogli):
        base = foglio * PAGINE_PER_FOGLIO_A5
        fronte = writer.add_blank_page(width=A5L_W, height=A5L_H)
        retro = writer.add_blank_page(width=A5L_W, height=A5L_H)
        lati = (fronte, retro)

        for offset, (lato, col) in enumerate(_FOLD_LAYOUT_A5):
            page_idx = base + offset
            if page_idx >= n:
                continue
            t = Transformation().translate(tx=col * A6_W, ty=0)
            if margine_mm > 0:
                t = Transformation(t.ctm).scale(scala).translate(tx=off_x, ty=off_y)
            lati[lato].merge_transformed_page(reader.pages[page_idx], t)

        for dest in lati:
            if marks is not None:
                if margine_mm > 0:
                    dest.merge_transformed_page(marks, riduzione)
                else:
                    dest.merge_page(marks)
            dest.mediabox = RectangleObject([0, 0, A5L_W, A5L_H])

    with open(output_pdf, "wb") as f:
        writer.write(f)
    return n_fogli


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------

def reset_cartelle_stampa(output_dir: Path = OUTPUT_DIR) -> None:
    """Svuota le cartelle di export piatto prima di una rigenerazione --all."""
    for nome in ("stampa", "stampa_margini"):
        cartella = output_dir / nome
        if not cartella.exists():
            continue
        for pdf in cartella.glob("*.pdf"):
            pdf.unlink()


def pubblica_pdf_stampa(src: Path, dest_dir: Path) -> Path:
    """Copia un PDF di stampa nella cartella piatta di export."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(src, dest)
    return dest


def genera_passaporto(gruppo_nome: str, output_dir: Path = OUTPUT_DIR) -> dict:
    gruppi = get_gruppi()
    if gruppo_nome not in gruppi:
        raise SystemExit(
            f"Gruppo non trovato: {gruppo_nome!r}.\n"
            f"Disponibili: {', '.join(gruppi)}"
        )
    cfg = gruppi[gruppo_nome]
    regioni = cfg["regioni"]
    formato = cfg["formato"]

    tappe = carica_tappe(gruppo_nome, regioni)
    if not tappe:
        raise SystemExit("Nessuna tappa trovata per le regioni richieste.")

    if len(tappe) != cfg["num_totale"]:
        raise SystemExit(
            f"Gruppo {gruppo_nome!r}: {len(tappe)} tappe caricate, "
            f"attese {cfg['num_totale']} (Riepilogo per Gruppo)."
        )

    max_tappe = MAX_TAPPE_A5 if formato == "A5" else MAX_TAPPE_A4
    if len(tappe) > max_tappe:
        raise SystemExit(
            f"Il gruppo {gruppo_nome!r} ha {len(tappe)} tappe: supera il limite "
            f"di {max_tappe} tappe per un foglio {formato}."
        )

    slug = re.sub(r"[^a-z0-9]+", "_", gruppo_nome.lower()).strip("_")
    gruppo_dir = output_dir / slug
    gruppo_dir.mkdir(parents=True, exist_ok=True)

    # mappa di copertina in output/mappe/ (path senza underscore: il finalize
    # Jinja applica l'escaping LaTeX a tutte le stringhe del contesto)
    mappe_dir = output_dir / "mappe"
    mappe_dir.mkdir(parents=True, exist_ok=True)
    mappa_path = genera_mappa_gruppo(
        regioni, mappe_dir / f"mappa-{slug.replace('_', '-')}.pdf"
    )

    # filigrana del tracciato per ogni tappa (sfondo del riquadro timbro)
    filigrane_dir = mappe_dir / "filigrane"
    for t in tappe:
        code = ref_a_sicai_code(t["ref"])
        path = genera_filigrana_tracciato(code, filigrane_dir / f"{code}.png")
        t["tracciato_path"] = str(path) if path else None

    context = costruisci_contesto(gruppo_nome, regioni, tappe)
    context["mappa_path"] = str(mappa_path)
    copertina_path, credit_line1, credit_line2 = prepara_copertina(
        slug,
        context["placeholder_top_mm"],
        context["placeholder_image_bottom_mm"],
    )
    context["copertina_path"] = str(copertina_path)
    context["copertina_credit_line1"] = credit_line1
    context["copertina_credit_line2"] = credit_line2
    tex_source = renderizza_tex(context)

    out_a6 = gruppo_dir / f"passaporto_{slug}_A6.pdf"
    out_stampa = gruppo_dir / f"passaporto_{slug}_{formato}_stampa.pdf"
    out_stampa_margini = gruppo_dir / f"passaporto_{slug}_{formato}_stampa_margini.pdf"

    with tempfile.TemporaryDirectory() as tmp:
        pdf_a6 = compila_xelatex(tex_source, Path(tmp))
        shutil.copy(pdf_a6, out_a6)

    imponi = imponi_su_a5 if formato == "A5" else imponi_su_a4
    n_fogli = imponi(out_a6, out_stampa)                          # senza margini (al vivo)
    imponi(out_a6, out_stampa_margini, margine_mm=MARGINE_STAMPA_MM)

    pubblica_pdf_stampa(out_stampa, DIR_STAMPA)
    pubblica_pdf_stampa(out_stampa_margini, DIR_STAMPA_MARGINI)

    info = {
        "gruppo": gruppo_nome,
        "regioni": regioni,
        "formato": formato,
        "tappe": len(tappe),
        "pagine_timbri": len(context["pagine_timbri"]),
        "pagine_note": context["pagine_note"],
        "pagine_logiche_totali": 1 + len(context["pagine_timbri"]) + context["pagine_note"],
        "fogli": n_fogli,
        "pdf_a6": out_a6,
        "pdf_stampa": out_stampa,
        "pdf_stampa_margini": out_stampa_margini,
    }
    print(
        f"✔ {gruppo_nome} ({' · '.join(regioni)}): {info['tappe']} tappe, "
        f"{info['pagine_timbri']} pagine timbri, {info['pagine_note']} pagine note, "
        f"{info['fogli']} fogli {formato} fronte/retro\n"
        f"  → {out_a6.name}\n  → {out_stampa.name} (senza margini)\n"
        f"  → {out_stampa_margini.name} (margini {MARGINE_STAMPA_MM} mm)"
    )
    return info


def main():
    parser = argparse.ArgumentParser(description="Genera il Passaporto del Camminatore")
    parser.add_argument("gruppi", nargs="*",
                        help="Uno o più gruppi (es. \"Nord Est\", Piemonte)")
    parser.add_argument("--all", action="store_true",
                        help="Genera tutti gli 8 passaporti")
    parser.add_argument("--list", action="store_true",
                        help="Elenca i gruppi disponibili")
    args = parser.parse_args()

    if args.list or (not args.gruppi and not args.all):
        df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_TRACCIATI)
        counts = df["region"].value_counts()
        gruppi = get_gruppi()
        print("Gruppi disponibili (tappe):")
        for nome, cfg in gruppi.items():
            n = sum(int(counts.get(r, 0)) for r in cfg["regioni"])
            print(f"  {nome} [{cfg['formato']}]: {n} — {', '.join(cfg['regioni'])}")
        if not args.gruppi and not args.all:
            sys.exit(0)

    gruppi = get_gruppi()
    da_generare = list(gruppi) if args.all else args.gruppi
    if args.all:
        reset_cartelle_stampa(OUTPUT_DIR)
    for gruppo in da_generare:
        genera_passaporto(gruppo)


if __name__ == "__main__":
    main()
