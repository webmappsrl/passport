#!/usr/bin/env python3
"""
Prepara le immagini di copertina dei passaporti — Sentiero Italia CAI.

Ritaglia l'originale allo aspect ratio dello slot placeholder (dinamico
per ogni gruppo) e salva cover.jpg nella cartella del passaporto.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
COPERTINE_DIR = BASE_DIR / "assets" / "copertine"

PLACEHOLDER_WIDTH_MM = 93
COVER_OUTPUT_NAME = "cover.jpg"
COVER_WIDTH_PX = 1100
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
PORTRAIT_THRESHOLD = 1.05
CREDIT_SPLIT_MARKER = " Sentiero Italia CAI"


def _split_credit(credit: str) -> tuple[str, str]:
    """Divide la citazione: riga 1 = attribution (autore/titolo/luogo),
    riga 2 = da 'Sentiero Italia CAI' in poi (fonte + licenza CC BY)."""
    idx = credit.find(CREDIT_SPLIT_MARKER)
    if idx == -1:
        return credit, ""
    return credit[:idx].rstrip(), credit[idx + 1 :].lstrip()


def _trova_originale(cartella: Path) -> Path:
    """Restituisce l'immagine sorgente (preferisce nomi original*)."""
    candidates = [
        p for p in sorted(cartella.iterdir())
        if p.is_file()
        and p.suffix.lower() in IMAGE_EXTENSIONS
        and p.name.lower() != COVER_OUTPUT_NAME
    ]
    for p in candidates:
        if p.stem.lower().startswith("original"):
            return p
    if candidates:
        return candidates[0]
    raise FileNotFoundError(f"nessuna immagine sorgente in {cartella}")


def _crop_to_aspect(img: Image.Image, target_ratio: float, *, anchor_top: bool) -> Image.Image:
    """Ritaglia l'immagine al rapporto w/h target.

    Portrait: ancorato in alto (y=0). Landscape/quadrato: centrato.
    """
    w, h = img.size
    current_ratio = w / h

    if current_ratio > target_ratio:
        new_h = h
        new_w = int(h * target_ratio)
        x = (w - new_w) // 2
        y = 0
    else:
        new_w = w
        new_h = int(w / target_ratio)
        x = 0
        y = 0 if anchor_top else (h - new_h) // 2

    return img.crop((x, y, x + new_w, y + new_h))


def prepara_copertina(
    slug: str, placeholder_top_mm: float, placeholder_image_bottom_mm: float
) -> tuple[Path, str, str]:
    """Ritaglia e salva cover.jpg; restituisce (path, citazione riga 1, riga 2)."""
    cartella = COPERTINE_DIR / slug
    if not cartella.is_dir():
        raise SystemExit(f"Cartella copertina non trovata: {cartella}")

    try:
        originale = _trova_originale(cartella)
    except FileNotFoundError:
        raise SystemExit(
            f"Immagine sorgente non trovata in {cartella} "
            f"(atteso original.jpg o simile)."
        ) from None

    credits_path = cartella / "credits.txt"
    if not credits_path.is_file():
        raise SystemExit(f"credits.txt non trovato in {cartella}")
    credit = credits_path.read_text(encoding="utf-8").strip()
    if not credit:
        raise SystemExit(f"credits.txt vuoto in {cartella}")

    height_mm = placeholder_image_bottom_mm - placeholder_top_mm
    if height_mm <= 0:
        raise SystemExit(
            f"Slot immagine non valido per {slug}: "
            f"top={placeholder_top_mm}mm, bottom={placeholder_image_bottom_mm}mm"
        )

    target_ratio = PLACEHOLDER_WIDTH_MM / height_mm

    with Image.open(originale) as img:
        img = img.convert("RGB")
        portrait = img.height > img.width * PORTRAIT_THRESHOLD
        cropped = _crop_to_aspect(img, target_ratio, anchor_top=portrait)

        target_h_px = max(1, int(COVER_WIDTH_PX / target_ratio))
        cropped = cropped.resize(
            (COVER_WIDTH_PX, target_h_px), Image.Resampling.LANCZOS
        )

        out_path = cartella / COVER_OUTPUT_NAME
        cropped.save(out_path, "JPEG", quality=90, optimize=True)

    return out_path.resolve(), *_split_credit(credit)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(
            f"Uso: {Path(sys.argv[0]).name} "
            f"<slug> <placeholder_top_mm> <placeholder_image_bottom_mm>"
        )
        sys.exit(1)
    path, line1, line2 = prepara_copertina(
        sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    )
    print(path)
    print(line1)
    if line2:
        print(line2)
