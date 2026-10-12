#!/usr/bin/env python3
"""
Genera il Passaporto del Camminatore — Sentiero Italia CAI.

Pipeline (design e imposizione separati, come da architettura del progetto):

  1. dati (Excel / PostgreSQL) → contesto Jinja2
  2. Jinja2 → sorgente LaTeX (pagine A6 sequenziali)
  3. XeLaTeX → passaporto A6 con 3 mm di abbondanza (a video si vede l'A6)
  4. pypdf  → imposizione 2x2 su A4 fronte/retro con schema
              duplex corretto (cut & stack): al vivo, e per la
              tipografia con abbondanze + segni di taglio e piega
  5. pypdf  → libretto unico A6 con tutti i gruppi (solo con --all)

Uso:
  python genera_passaporto.py --all           # 9 passaporti + libretto A6 + raccoglitore
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

from esporta_colore import converti_cmyk, converti_rgb
from genera_copertine import prepara_copertina
from genera_mappe import genera_filigrana_tracciato, genera_mappa_gruppo, ref_a_sicai_code
from pypdf import PageObject, PdfReader, PdfWriter, Transformation
from pypdf.generic import ContentStream, DecodedStreamObject, RectangleObject
from reportlab.lib.pagesizes import A4

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
CARTELLE_STAMPA = ("stampa", "stampa_margini", "stampa_cmyk", "stampa_rgb")

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
# versione per la tipografia (cartella stampa_margini), su indicazione della
# copisteria (ottobre 2026): abbondanze e segni di taglio
ABBONDANZA_MM = 3          # abbondanza oltre il rifilo, su ogni lato
AREA_SEGNI_MM = 10         # fascia bianca attorno al rifilo per i segni di taglio
ABB, SEGNI = ABBONDANZA_MM * MM, AREA_SEGNI_MM * MM
MAPPA_CREDIT = "© CAI © OpenStreetMap"

# ----------------------------------------------------------------------
# Raggruppamenti: 9 passaporti, 1 foglio ciascuno (caricati da Excel).
# Capacità per foglio: A4 = copertina + 7 pagine timbri (84 tappe max);
# A5 (solo Val d'Aosta) = copertina + 3 facciate (36 tappe max).
# ----------------------------------------------------------------------

_GRUPPI_CACHE: dict[str, dict] | None = None


def nome_display_gruppo(gruppo_excel: str) -> str:
    """Toglie il prefisso numerico del gruppo Excel: '1-Isole' → 'Isole'."""
    return re.sub(r"^\d+-", "", str(gruppo_excel).strip())


def ordine_gruppo_excel(gruppo_excel: str) -> int:
    """Estrae l'ordine SICAI dal prefisso numerico: '1-Isole' → 1."""
    m = re.match(r"^(\d+)-", str(gruppo_excel).strip())
    if not m:
        raise SystemExit(
            f"Codice gruppo senza prefisso numerico in Excel: {gruppo_excel!r}"
        )
    return int(m.group(1))


def carica_gruppi_da_excel(excel_path: Path = EXCEL_PATH) -> dict[str, dict]:
    """Ordine gruppi da Riepilogo per Gruppo; regioni e formato da Excel.

    La chiave del dict è il nome display (senza prefisso, es. 'Isole') usato
    nei PDF e per lo slug; `gruppo_excel` conserva il codice grezzo
    ('1-Isole') per filtrare i fogli Tracciati e Riepilogo per Regione. I
    nomi regione sono risolti dal foglio Tracciati (su cui filtra
    `carica_tappe`), nell'ordine delle lettere del foglio Riepilogo per
    Regione."""
    rg = pd.read_excel(excel_path, sheet_name=SHEET_RIEPILOGO_GRUPPO)
    rr = pd.read_excel(excel_path, sheet_name=SHEET_RIEPILOGO_REGIONE)
    tr = pd.read_excel(excel_path, sheet_name=SHEET_TRACCIATI)

    # lettera → nome regione come compare nel foglio Tracciati
    regione_per_lettera = (
        tr.dropna(subset=["lettera", "region"])
        .drop_duplicates("lettera")
        .set_index("lettera")["region"]
        .map(lambda r: str(r).strip())
        .to_dict()
    )

    gruppi: dict[str, dict] = {}
    for _, row in rg.iterrows():
        gruppo_excel = str(row["gruppo"]).strip()
        nome = nome_display_gruppo(gruppo_excel)

        lettere = rr.loc[rr["Gruppo"] == gruppo_excel, "lettera"].tolist()
        regioni: list[str] = []
        for lettera in lettere:
            regione = regione_per_lettera.get(str(lettera).strip())
            if regione and regione not in regioni:
                regioni.append(regione)
        if not regioni:
            raise SystemExit(
                f"Nessuna regione in {SHEET_RIEPILOGO_REGIONE} "
                f"per il gruppo {gruppo_excel!r}."
            )

        gruppi[nome] = {
            "gruppo_excel": gruppo_excel,
            "ordine": ordine_gruppo_excel(gruppo_excel),
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
    gruppo_nome: str, regioni: list[str], gruppo_excel: str | None = None,
    excel_path: Path = EXCEL_PATH,
) -> list[dict]:
    """Carica le tappe dal file Excel per blocco regionale (ordine da
    `regioni`, cioè foglio Riepilogo per Regione) e, dentro ogni regione,
    preserva il senso del Sentiero Italia CAI nel foglio Tracciati.

    Il foglio Tracciati ha la colonna `gruppo` col codice grezzo
    ('1-Isole'): `gruppo_excel` è la chiave di filtro; `gruppo_nome` è il
    nome display usato solo nei messaggi.

    In produzione: stessa struttura via query PostgreSQL con ORDER BY
    esplicito sul percorso del sentiero."""
    gruppo_excel = gruppo_excel or gruppo_nome
    df_full = pd.read_excel(excel_path, sheet_name=SHEET_TRACCIATI)
    df_full["_idx_trail"] = df_full.index

    if "gruppo" not in df_full.columns:
        raise SystemExit(
            f"Colonna 'gruppo' assente in {excel_path.name} "
            f"(foglio {SHEET_TRACCIATI})."
        )

    df = df_full[df_full["gruppo"] == gruppo_excel].copy()
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
    return env.get_template(template).render(abbondanza_mm=ABBONDANZA_MM, **context)


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
    imposta_box_a6(pdf_path)
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


def imposta_box_a6(pdf: Path) -> None:
    """Box di stampa sull'A6 compilato (A6 + abbondanze su ogni lato).

    MediaBox/BleedBox = pagina intera con le abbondanze, TrimBox/CropBox =
    formato rifilato 105x148 mm: a video si vede l'A6, l'imposizione ritaglia
    sul CropBox (pypdf ritaglia la pagina incollata sul suo CropBox).
    """
    writer = PdfWriter(clone_from=PdfReader(str(pdf)))
    for pagina in writer.pages:
        pagina.mediabox = RectangleObject([0, 0, A6_W + 2 * ABB, A6_H + 2 * ABB])
        pagina.bleedbox = RectangleObject([0, 0, A6_W + 2 * ABB, A6_H + 2 * ABB])
        pagina.trimbox = RectangleObject([ABB, ABB, ABB + A6_W, ABB + A6_H])
        pagina.cropbox = RectangleObject([ABB, ABB, ABB + A6_W, ABB + A6_H])
    with open(pdf, "wb") as f:
        writer.write(f)


def _rettangolo_sorgente(t: Transformation, rect: list[float]) -> RectangleObject:
    """Rettangolo del foglio riportato nelle coordinate della pagina A6 (inversa di t)."""
    a, b, c, d, e, f = t.ctm
    det = a * d - b * c
    punti = []
    for x in (rect[0], rect[2]):
        for y in (rect[1], rect[3]):
            x0, y0 = x - e, y - f
            punti.append(((d * x0 - c * y0) / det, (-b * x0 + a * y0) / det))
    xs, ys = zip(*punti)
    return RectangleObject([min(xs), min(ys), max(xs), max(ys)])


def _segni_overlay(larghezza: float, altezza: float, pieghe: list[tuple[str, float]],
                   segni_taglio: bool) -> "PageObject":
    """Pagina con i segni di piega e, per la tipografia, i segni di taglio.

    pieghe: ("v", x) o ("h", y) nel foglio rifilato.
    Al vivo: tacche di piega tratteggiate ai bordi, dentro il foglio, grigio
    in solo nero. Con segni di taglio: crocini agli angoli e tacche di piega
    nella fascia bianca fuori dal formato, a partire da fine abbondanza
    (niente dentro il rifilo), in colore di registro (CMYK 100/100/100/100).
    Scritta come content stream PDF puro: niente font (reportlab dichiarerebbe
    un Helvetica non incorporato, non ammesso in PDF/X).
    """
    o = SEGNI if segni_taglio else 0
    pw, ph = larghezza + 2 * o, altezza + 2 * o
    continui: list[tuple[float, float, float, float]] = []
    tratteggiati: list[tuple[float, float, float, float]] = []
    if segni_taglio:
        da, a = ABB, SEGNI - 1 * MM  # distanza dal rifilo: inizio e fine del segno
        for cx, sx in ((o, -1), (o + larghezza, 1)):
            for cy, sy in ((o, -1), (o + altezza, 1)):
                continui.append((cx + sx * da, cy, cx + sx * a, cy))
                continui.append((cx, cy + sy * da, cx, cy + sy * a))
        for verso, pos in pieghe:
            if verso == "v":
                tratteggiati.append((o + pos, o - da, o + pos, o - a))
                tratteggiati.append((o + pos, o + altezza + da, o + pos, o + altezza + a))
            else:
                tratteggiati.append((o - da, o + pos, o - a, o + pos))
                tratteggiati.append((o + larghezza + da, o + pos, o + larghezza + a, o + pos))
        stile = "0.25 w 1 1 1 1 K"
    else:
        tick = 4 * MM
        for verso, pos in pieghe:
            if verso == "v":
                tratteggiati.append((pos, altezza, pos, altezza - tick))
                tratteggiati.append((pos, 0, pos, tick))
            else:
                tratteggiati.append((0, pos, tick, pos))
                tratteggiati.append((larghezza - tick, pos, larghezza, pos))
        stile = "0.3 w 0 0 0 0.55 K"

    def tratti(segmenti):
        return " ".join(f"{x0:.3f} {y0:.3f} m {x1:.3f} {y1:.3f} l" for x0, y0, x1, y1 in segmenti)

    ops = [f"q {stile}"]
    if continui:
        ops.append(f"[] 0 d {tratti(continui)} S")
    if tratteggiati:
        ops.append(f"[2 2] 0 d {tratti(tratteggiati)} S")
    ops.append("Q")
    contenuto = DecodedStreamObject()
    contenuto.set_data(" ".join(ops).encode())
    pagina = PdfWriter().add_blank_page(width=pw, height=ph)
    pagina.replace_contents(ContentStream(contenuto, None))
    return pagina


def imponi(a6_pdf: Path, output_pdf: Path, foglio: tuple[float, float],
           layout: list[tuple[int, float, float, bool]],
           pieghe: list[tuple[str, float]], segni_taglio: bool = False) -> int:
    """Monta le pagine A6 (con abbondanze, v. imposta_box_a6) su fogli.

    foglio: formato rifilato (larghezza, altezza) in punti.
    layout: per ogni pagina logica del foglio (lato, x, y, ruota180), con
            x/y angolo in basso a sinistra dello slot nel foglio rifilato;
            lato 0 = fronte, 1 = retro.
    segni_taglio = False → al vivo: pagina = foglio, ogni A6 rifilato al suo slot
    segni_taglio = True  → per la tipografia: foglio + 3 mm di abbondanza sui
                           lati esterni (sulle pieghe interne il taglio resta
                           netto) + fascia bianca con crocini di taglio e di
                           piega; TrimBox/BleedBox impostati.
    """
    reader = PdfReader(str(a6_pdf))
    n = len(reader.pages)
    per_foglio = len(layout)
    n_fogli = math.ceil(n / per_foglio)
    n_lati = max(lato for lato, *_ in layout) + 1
    larghezza, altezza = foglio
    o = SEGNI if segni_taglio else 0
    pw, ph = larghezza + 2 * o, altezza + 2 * o
    segni = _segni_overlay(larghezza, altezza, pieghe, segni_taglio)
    writer = PdfWriter()
    eps = 0.01

    for foglio_idx in range(n_fogli):
        base = foglio_idx * per_foglio
        lati = [writer.add_blank_page(width=pw, height=ph) for _ in range(n_lati)]

        for offset, (lato, x, y, ruota) in enumerate(layout):
            page_idx = base + offset
            if page_idx >= n:
                continue
            # l'A6 ha l'abbondanza attorno: prima si porta il rifilo nell'origine
            t = Transformation().translate(tx=-ABB, ty=-ABB)
            if ruota:
                # rotazione 180° dentro lo slot
                t = t.rotate(180).translate(tx=x + A6_W, ty=y + A6_H)
            else:
                t = t.translate(tx=x, ty=y)
            t = t.translate(tx=o, ty=o)

            # area visibile dello slot: abbondanza solo sui lati esterni del foglio
            ab = ABB if segni_taglio else 0
            clip = [
                o + x - (ab if x < eps else 0),
                o + y - (ab if y < eps else 0),
                o + x + A6_W + (ab if x + A6_W > larghezza - eps else 0),
                o + y + A6_H + (ab if y + A6_H > altezza - eps else 0),
            ]
            pagina = reader.pages[page_idx]
            pagina.cropbox = _rettangolo_sorgente(t, clip)
            lati[lato].merge_transformed_page(pagina, t)

        for dest in lati:
            dest.merge_page(segni)
            dest.mediabox = RectangleObject([0, 0, pw, ph])
            dest.trimbox = RectangleObject([o, o, o + larghezza, o + altezza])
            if segni_taglio:
                dest.bleedbox = RectangleObject(
                    [o - ABB, o - ABB, o + larghezza + ABB, o + altezza + ABB])

    with open(output_pdf, "wb") as f:
        writer.write(f)
    return n_fogli


def imponi_su_a4(a6_pdf: Path, output_pdf: Path, segni_taglio: bool = False) -> int:
    """Imposizione 2x2 fronte/retro per ripiegabile a croce."""
    layout = [(lato, *_slot_origin(slot), ruota) for lato, slot, ruota in _FOLD_LAYOUT]
    pieghe = [("v", A6_W), ("h", A4_H - A6_H)]
    return imponi(a6_pdf, output_pdf, (A4_W, A4_H), layout, pieghe, segni_taglio)


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


def imponi_su_a5(a6_pdf: Path, output_pdf: Path, segni_taglio: bool = False) -> int:
    """Imposizione 2x1 fronte/retro su A5 landscape (libretto a piega unica)."""
    layout = [(lato, col * A6_W, 0, False) for lato, col in _FOLD_LAYOUT_A5]
    return imponi(a6_pdf, output_pdf, (A5L_W, A5L_H), layout, [("v", A6_W)], segni_taglio)


def imponi_su_a6(a6_pdf: Path, output_pdf: Path, segni_taglio: bool = False) -> int:
    """Una facciata A6 per pagina (libretto): rifilata o con abbondanze e crocini."""
    return imponi(a6_pdf, output_pdf, (A6_W, A6_H), [(0, 0, 0, False)], [], segni_taglio)


# ----------------------------------------------------------------------
# 5. Libretto unico A6 — tutti i gruppi in un solo PDF spillato al centro
# ----------------------------------------------------------------------
#
# Il libretto si compone dagli A6 dei 9 gruppi, senza ricompilare LaTeX.
# Ogni gruppo porta copertina + pagine timbri; se le sue pagine sono
# dispari riceve una pagina Note, così la copertina successiva cade
# sempre su una pagina dispari (a destra). L'ultima pagina è sempre una
# Note e il totale è un multiplo di 4 (spillatura al centro).
# Con l'Excel di ottobre 2026 il risultato coincide con l'esempio di
# Enrico: 60 facciate, Note a pagina 8, 34, 46 e 60.

LIBRETTO_A6 = OUTPUT_DIR / "libretto_A6.pdf"
LIBRETTO_A6_MARGINI = OUTPUT_DIR / "libretto_A6_margini.pdf"


def piano_libretto(gruppi: list[tuple[str, int, int]]) -> list[tuple[int, int, str]]:
    """Sequenza delle pagine del libretto.

    gruppi: per ogni gruppo, in ordine, (nome, pagine_timbri, pagine_note
    presenti nel suo A6). Restituisce una voce per pagina del libretto:
    (indice_gruppo, indice_pagina_nell_A6, tipo), tipo in
    {"copertina", "timbri", "note"}.
    """
    piano: list[tuple[int, int, str]] = []
    for g, (_, n_timbri, _) in enumerate(gruppi):
        piano.append((g, 0, "copertina"))
        piano.extend((g, 1 + i, "timbri") for i in range(n_timbri))
        if (1 + n_timbri) % 2:
            # pagine dispari → l'A6 del gruppo ha almeno una Note di riempimento
            piano.append((g, 1 + n_timbri, "note"))

    # le Note aggiunte in fondo sono tutte uguali: si copia la prima disponibile
    sorgente_note = next(
        ((g, 1 + n_timbri) for g, (_, n_timbri, n_note) in enumerate(gruppi) if n_note),
        None,
    )
    while piano[-1][2] != "note" or len(piano) % 4:
        if sorgente_note is None:
            raise ValueError(
                "Nessun gruppo ha una pagina Note nel suo A6: impossibile "
                "aggiungere le pagine Note in fondo al libretto."
            )
        piano.append((*sorgente_note, "note"))
    return piano


def componi_libretto(infos: list[dict], output_pdf: Path) -> list[tuple[str, int, int]]:
    """Scrive il libretto A6 dagli A6 dei gruppi (dict info di genera_passaporto).

    Restituisce la mappa (gruppo, prima_pagina, ultima_pagina), 1-based.
    """
    piano = piano_libretto(
        [(i["gruppo"], i["pagine_timbri"], i["pagine_note"]) for i in infos]
    )
    readers = [PdfReader(str(i["pdf_a6"])) for i in infos]
    writer = PdfWriter()
    for g, pagina, _ in piano:
        writer.add_page(readers[g].pages[pagina])
    with open(output_pdf, "wb") as f:
        writer.write(f)

    # ogni gruppo va dalla sua copertina alla pagina prima della copertina
    # successiva; l'ultimo arriva in fondo (Note finali comprese)
    copertine = [n + 1 for n, (_, _, tipo) in enumerate(piano) if tipo == "copertina"]
    fine = [c - 1 for c in copertine[1:]] + [len(piano)]
    return [(i["gruppo"], da, a) for i, da, a in zip(infos, copertine, fine)]


def _tipo_pagina(testo: str) -> str:
    if "PASSAPORTO" in testo:
        return "copertina"
    if "Tappe " in testo:
        return "timbri"
    if "Note" in testo:
        return "note"
    return "sconosciuta"


def verifica_libretto(pdf: Path, attesi: list[str]) -> None:
    """Rilegge il libretto scritto e ne controlla la struttura dal testo delle pagine.

    Legge il PDF dal disco, non il piano usato per scriverlo: è un controllo
    sul file prodotto, non una ripetizione del calcolo.
    """
    tipi = [_tipo_pagina(p.extract_text() or "") for p in PdfReader(str(pdf)).pages]
    errori = []
    if len(tipi) % 4:
        errori.append(f"{len(tipi)} pagine, non multiplo di 4")
    pari = [n + 1 for n, t in enumerate(tipi) if t == "copertina" and (n + 1) % 2 == 0]
    if pari:
        errori.append(f"copertine su pagina pari (a sinistra): {pari}")
    if not tipi or tipi[-1] != "note":
        errori.append("l'ultima pagina non è una pagina Note")
    if tipi != attesi:
        diverse = [n + 1 for n, (a, b) in enumerate(zip(tipi, attesi)) if a != b]
        errori.append(
            f"struttura diversa dal piano ({len(tipi)} pagine lette, "
            f"{len(attesi)} attese; pagine diverse: {diverse})"
        )
    if errori:
        raise SystemExit(f"Libretto {pdf.name} non valido:\n  - " + "\n  - ".join(errori))


def rimuovi_libretto(output_dir: Path = OUTPUT_DIR) -> bool:
    """Cancella i PDF del libretto e le loro copie di stampa. True se ne c'erano."""
    nomi = (LIBRETTO_A6.name, LIBRETTO_A6_MARGINI.name,
            "libretto_A6_cmyk.pdf", "libretto_A6_rgb.pdf")
    candidati = [output_dir / n for n in nomi]
    candidati += [output_dir / cartella / n
                  for cartella in CARTELLE_STAMPA for n in nomi]
    rimossi = False
    for pdf in candidati:
        if pdf.exists():
            pdf.unlink()
            rimossi = True
    if (output_dir / DIR_LIBRETTO_KIT).exists():
        shutil.rmtree(output_dir / DIR_LIBRETTO_KIT)
        rimossi = True
    return rimossi


# Cartelle pronte da zippare: per ogni versione di stampa, solo l'interno del
# libretto e la sua copertina (raccoglitore), sia su pagine A6 singole sia
# montata fronte/retro sul foglio A5 da piegare.
# La versione consigliata per la stampa (PDF/X-4 CMYK FOGRA39) è
# libretto_stampa_margini; *_margini_rgb è la stessa senza conversione né profili,
# *_srgb la PDF/X-4 con RGB dichiarato sRGB.
DIR_LIBRETTO_KIT = "libretto_A6"
LIBRETTO_KIT = {
    # cartella: (cartella sorgente, interno, copertina A6 singole, copertina A5 montata)
    "libretto_A6_stampa": ("stampa", "libretto_A6.pdf", "raccoglitore_A6_stampa.pdf",
                           "0_raccoglitore_A5_stampa.pdf"),
    "libretto_A6_stampa_margini_rgb": ("stampa_margini", "libretto_A6_margini.pdf",
                                   "raccoglitore_A6_stampa_margini.pdf",
                                   "0_raccoglitore_A5_stampa_margini.pdf"),
    "libretto_stampa_margini": ("stampa_cmyk", "libretto_A6_cmyk.pdf",
                                "raccoglitore_A6_stampa_cmyk.pdf",
                                "0_raccoglitore_A5_stampa_cmyk.pdf"),
    "libretto_A6_stampa_srgb": ("stampa_rgb", "libretto_A6_rgb.pdf",
                               "raccoglitore_A6_stampa_rgb.pdf",
                               "0_raccoglitore_A5_stampa_rgb.pdf"),
}


def componi_cartelle_libretto(output_dir: Path = OUTPUT_DIR) -> list[Path]:
    """Ricrea output/libretto_A6/<versione>/ con interno + copertina (A6 e A5).

    Le cartelle si ricompongono da zero dalle cartelle di stampa piatte, così
    non restano file vecchi; se il libretto non c'è (rimosso perché non più
    allineato) non vengono create. Nelle cartelle i file perdono il prefisso
    numerico "0_" (serve solo a ordinare le cartelle piatte), come il libretto.
    Restituisce le cartelle scritte.
    """
    radice = output_dir / DIR_LIBRETTO_KIT
    if radice.exists():
        shutil.rmtree(radice)
    if not (output_dir / "stampa" / LIBRETTO_A6.name).exists():
        return []
    scritte = []
    for nome, (sorgente, *pdf) in LIBRETTO_KIT.items():
        mancanti = [f for f in pdf if not (output_dir / sorgente / f).exists()]
        if mancanti:
            raise SystemExit(f"Cartella {nome}: mancano {mancanti} in output/{sorgente}/")
        cartella = radice / nome
        cartella.mkdir(parents=True)
        for f in pdf:
            shutil.copy2(output_dir / sorgente / f, cartella / f.removeprefix("0_"))
        scritte.append(cartella)
    return scritte


def genera_libretto(infos: list[dict], output_dir: Path = OUTPUT_DIR) -> None:
    """Libretto al vivo + versione per la tipografia, verificati e pubblicati per la stampa."""
    out = output_dir / LIBRETTO_A6.name
    out_margini = output_dir / LIBRETTO_A6_MARGINI.name
    with tempfile.TemporaryDirectory() as tmp:
        composto = Path(tmp) / out.name  # A6 con abbondanze, da rifilare o segnare
        mappa = componi_libretto(infos, composto)
        imponi_su_a6(composto, out)
        imponi_su_a6(composto, out_margini, segni_taglio=True)
    attesi = [tipo for _, _, tipo in piano_libretto(
        [(i["gruppo"], i["pagine_timbri"], i["pagine_note"]) for i in infos]
    )]
    verifica_libretto(out, attesi)
    verifica_libretto(out_margini, attesi)
    pubblica_pdf_stampa(out, output_dir / "stampa")
    pubblica_pdf_stampa(out_margini, output_dir / "stampa_margini")
    pubblica_varianti_colore(out_margini, "Passaporto del Camminatore — libretto unico A6",
                             output_dir)
    print(
        f"✔ Libretto unico A6: {len(attesi)} facciate\n  "
        + ", ".join(f"{g} {da}-{a}" for g, da, a in mappa)
        + f"\n  → {out.name} (al vivo)\n  → {out_margini.name} "
        f"(abbondanze {ABBONDANZA_MM} mm + segni di taglio)\n"
        f"  → libretto_A6_cmyk.pdf / libretto_A6_rgb.pdf (PDF/X-4)\n"
    )


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------

def reset_cartelle_stampa(output_dir: Path = OUTPUT_DIR) -> None:
    """Svuota le cartelle di export piatto prima di una rigenerazione --all."""
    for nome in CARTELLE_STAMPA:
        cartella = output_dir / nome
        if not cartella.exists():
            continue
        for pdf in cartella.glob("*.pdf"):
            pdf.unlink()


def pubblica_varianti_colore(pdf_margini: Path, titolo: str,
                             output_dir: Path = OUTPUT_DIR) -> tuple[Path, Path]:
    """Dal PDF per la tipografia, le due varianti PDF/X-4 (FOGRA39).

    stampa_cmyk/<nome>_cmyk.pdf: tutto convertito in CMYK da noi;
    stampa_rgb/<nome>_rgb.pdf: RGB dichiarato sRGB, converte la tipografia.
    """
    base = pdf_margini.stem.removesuffix("_margini")
    return (
        converti_cmyk(pdf_margini, output_dir / "stampa_cmyk" / f"{base}_cmyk.pdf", titolo),
        converti_rgb(pdf_margini, output_dir / "stampa_rgb" / f"{base}_rgb.pdf", titolo),
    )


def pubblica_pdf_stampa(src: Path, dest_dir: Path) -> Path:
    """Copia un PDF di stampa nella cartella piatta di export."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(src, dest)
    return dest


def genera_passaporto(
    gruppo_nome: str, output_dir: Path = OUTPUT_DIR, filigrana_mappa: bool = False
) -> dict:
    gruppi = get_gruppi()
    if gruppo_nome not in gruppi:
        raise SystemExit(
            f"Gruppo non trovato: {gruppo_nome!r}.\n"
            f"Disponibili: {', '.join(gruppi)}"
        )
    cfg = gruppi[gruppo_nome]
    regioni = cfg["regioni"]
    formato = cfg["formato"]

    tappe = carica_tappe(gruppo_nome, regioni, cfg["gruppo_excel"])
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
    prefisso = f"{cfg['ordine']}_"
    gruppo_dir = output_dir / f"{cfg['ordine']}_{slug}"
    gruppo_dir.mkdir(parents=True, exist_ok=True)
    for pdf in gruppo_dir.glob("*.pdf"):
        pdf.unlink()

    # mappa di copertina in output/mappe/ (path senza underscore: il finalize
    # Jinja applica l'escaping LaTeX a tutte le stringhe del contesto)
    mappe_dir = output_dir / "mappe"
    mappe_dir.mkdir(parents=True, exist_ok=True)
    mappa_path = genera_mappa_gruppo(
        regioni, mappe_dir / f"mappa-{slug.replace('_', '-')}.pdf"
    )

    # filigrana del tracciato per ogni tappa (sfondo del riquadro timbro);
    # con filigrana_mappa la silhouette ha sotto la basemap Webmapp
    filigrane_dir = mappe_dir / ("filigrane_mappa" if filigrana_mappa else "filigrane")
    for t in tappe:
        code = ref_a_sicai_code(t["ref"])
        path = genera_filigrana_tracciato(
            code, filigrane_dir / f"{code}.png", con_mappa=filigrana_mappa
        )
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

    out_a6 = gruppo_dir / f"{prefisso}passaporto_{slug}_A6.pdf"
    out_stampa = gruppo_dir / f"{prefisso}passaporto_{slug}_{formato}_stampa.pdf"
    out_stampa_margini = (
        gruppo_dir / f"{prefisso}passaporto_{slug}_{formato}_stampa_margini.pdf"
    )

    with tempfile.TemporaryDirectory() as tmp:
        pdf_a6 = compila_xelatex(tex_source, Path(tmp))
        shutil.copy(pdf_a6, out_a6)

    imponi_foglio = imponi_su_a5 if formato == "A5" else imponi_su_a4
    n_fogli = imponi_foglio(out_a6, out_stampa)                   # al vivo
    imponi_foglio(out_a6, out_stampa_margini, segni_taglio=True)  # per la tipografia

    pubblica_pdf_stampa(out_stampa, DIR_STAMPA)
    pubblica_pdf_stampa(out_stampa_margini, DIR_STAMPA_MARGINI)
    pubblica_varianti_colore(
        out_stampa_margini, f"Passaporto del Camminatore — {gruppo_nome} (Sentiero Italia CAI)"
    )

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
        f"  → {out_a6.name}\n  → {out_stampa.name} (al vivo)\n"
        f"  → {out_stampa_margini.name} (abbondanze {ABBONDANZA_MM} mm + segni di taglio)\n"
        f"  → varianti PDF/X-4 in stampa_cmyk/ e stampa_rgb/"
    )
    return info


def main():
    parser = argparse.ArgumentParser(description="Genera il Passaporto del Camminatore")
    parser.add_argument("gruppi", nargs="*",
                        help="Uno o più gruppi (es. \"Nord Est\", Piemonte)")
    parser.add_argument("--all", action="store_true",
                        help="Genera i 9 passaporti, il libretto unico A6 e il raccoglitore (copertina)")
    parser.add_argument("--list", action="store_true",
                        help="Elenca i gruppi disponibili")
    parser.add_argument("--filigrana-mappa", action="store_true",
                        help="Filigrana timbro con basemap + tracciato "
                             "(default: solo tracciato)")
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
    # il libretto vecchio non deve sopravvivere a una rigenerazione: con --all
    # viene riscritto solo se tutti i gruppi vanno a buon fine, altrimenti resta
    # assente finché non si rilancia --all
    libretto_rimosso = rimuovi_libretto(OUTPUT_DIR)
    if args.all:
        reset_cartelle_stampa(OUTPUT_DIR)
    infos = [
        genera_passaporto(gruppo, filigrana_mappa=args.filigrana_mappa)
        for gruppo in da_generare
    ]
    if args.all:
        genera_libretto(infos, OUTPUT_DIR)
        # il raccoglitore è la copertina del libretto: reset_cartelle_stampa ha
        # svuotato anche i suoi PDF di stampa, quindi va rigenerato insieme.
        # Import locale: genera_raccoglitore importa da questo modulo.
        from genera_raccoglitore import genera_raccoglitore
        genera_raccoglitore(OUTPUT_DIR)
    elif libretto_rimosso:
        print("⚠ libretto rimosso perché non più allineato: rigeneralo con --all")


if __name__ == "__main__":
    main()
