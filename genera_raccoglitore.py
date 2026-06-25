#!/usr/bin/env python3
"""
Genera il Raccoglitore del Camminatore — Sentiero Italia CAI.

Un foglio A5 landscape (210 x 148 mm) fronte/retro che, piegato in due
lungo la piega verticale centrale, diventa un libretto A6 a 4 facciate
(stesso meccanismo del passaporto Valle d'Aosta):

  1. Copertina (esterno, fronte destra) — box bianco per il numero
     identificativo da compilare a mano
  2. Presentazione (interno sinistra) — nome, cognome, foto, firma
  3. Cos'è il SICAI (interno destra) — testo progetto + QR app
  4. Mappa del SICAI (esterno, retro copertina) — mappa dell'intero
     percorso generata a build-time (genera_mappe.py)

Riusa la pipeline del passaporto: Jinja2 → XeLaTeX (A6 sequenziale) →
pypdf (imposizione 2x1 su A5 landscape).

Uso:
  python genera_raccoglitore.py
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import cairosvg

from genera_mappe import genera_mappa_italia
from genera_passaporto import (
    ASSET_DIR,
    DIR_STAMPA,
    DIR_STAMPA_MARGINI,
    FONT_DIR,
    MAPPA_CREDIT,
    MARGINE_STAMPA_MM,
    OUTPUT_DIR,
    compila_xelatex,
    imponi_su_a5,
    pubblica_pdf_stampa,
    renderizza_tex,
)

_QR_SVG = {
    "qr_android_path": ("qr_sicai_app_android.svg", "qr-android.png"),
    "qr_ios_path": ("qr_sicai_app_ios.svg", "qr-ios.png"),
}


def converti_qr_svg_png(build_dir: Path) -> dict[str, str]:
    """Converte i QR SVG in PNG per XeLaTeX (nomi senza underscore per
    compatibilità con l'escaping LaTeX del contesto Jinja)."""
    paths = {}
    for key, (svg_name, png_name) in _QR_SVG.items():
        png_path = build_dir / png_name
        cairosvg.svg2png(
            url=str(ASSET_DIR / svg_name),
            write_to=str(png_path),
            output_width=512,
            output_height=512,
        )
        paths[key] = str(png_path)
    return paths


def genera_raccoglitore(output_dir: Path = OUTPUT_DIR) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    for pdf in output_dir.glob("raccoglitore*.pdf"):
        pdf.unlink()
    for pdf in output_dir.glob("0_raccoglitore*.pdf"):
        pdf.unlink()
    out_a6 = output_dir / "0_raccoglitore_A6.pdf"
    out_stampa = output_dir / "0_raccoglitore_A5_stampa.pdf"
    out_stampa_margini = output_dir / "0_raccoglitore_A5_stampa_margini.pdf"

    # mappa dell'intero percorso SICAI (path senza underscore: il
    # finalize Jinja applica l'escaping LaTeX alle stringhe del contesto)
    mappa_path = genera_mappa_italia(output_dir / "mappe" / "mappa-italia.pdf")

    with tempfile.TemporaryDirectory() as tmp:
        build_dir = Path(tmp)
        context = {
            "font_path": str(FONT_DIR) + "/",
            "asset_path": str(ASSET_DIR) + "/",
            "mappa_path": str(mappa_path),
            "mappa_credit": MAPPA_CREDIT,
            **converti_qr_svg_png(build_dir),
        }
        tex_source = renderizza_tex(context, template="raccoglitore.tex.j2")
        pdf_a6 = compila_xelatex(tex_source, build_dir)
        shutil.copy(pdf_a6, out_a6)

    n_fogli = imponi_su_a5(out_a6, out_stampa)                    # senza margini (al vivo)
    imponi_su_a5(out_a6, out_stampa_margini, margine_mm=MARGINE_STAMPA_MM)

    pubblica_pdf_stampa(out_stampa, DIR_STAMPA)
    pubblica_pdf_stampa(out_stampa_margini, DIR_STAMPA_MARGINI)

    info = {
        "fogli": n_fogli,
        "pdf_a6": out_a6,
        "pdf_stampa": out_stampa,
        "pdf_stampa_margini": out_stampa_margini,
    }
    print(
        f"✔ Raccoglitore del Camminatore: 4 facciate, "
        f"{n_fogli} foglio A5 fronte/retro\n"
        f"  → {out_a6.name}\n  → {out_stampa.name} (senza margini)\n"
        f"  → {out_stampa_margini.name} (margini {MARGINE_STAMPA_MM} mm)"
    )
    return info


if __name__ == "__main__":
    genera_raccoglitore()
