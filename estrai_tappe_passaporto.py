#!/usr/bin/env python3
"""
Estrae da tappe.xlsx un file ridotto con sole colonne usate dal passaporto.

Fogli prodotti:
  - Tracciati: id, ref (risolto), region, gruppo, from, to, distance, ascent, descent
  - Riepilogo per Regione: lettera, region, gruppo, num_tappe, formato

Uso:
  python estrai_tappe_passaporto.py
  python estrai_tappe_passaporto.py -o altro.xlsx
  python estrai_tappe_passaporto.py --excel path/to/tappe.xlsx
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from genera_passaporto import EXCEL_SOURCE_PATH, GRUPPI, natural_ref_key, risolvi_ref

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = BASE_DIR / "tappe_passaporto.xlsx"
SHEET_TRACCIATI = "Tracciati"
SHEET_RIEPILOGO = "Riepilogo per Regione"

COLONNE_TRACCIATI = [
    "id", "ref", "region", "gruppo", "from", "to", "distance", "ascent", "descent"
]
COLONNE_RIEPILOGO = ["lettera", "region", "gruppo", "num_tappe", "formato"]


def mappa_regione_gruppo() -> dict[str, str]:
    """Mappa ogni regione al nome del passaporto (GRUPPI)."""
    out: dict[str, str] = {}
    for gruppo, cfg in GRUPPI.items():
        for regione in cfg["regioni"]:
            out[regione] = gruppo
    return out


def mappa_regione_formato() -> dict[str, str]:
    """Mappa ogni regione al formato di stampa del passaporto (A4 / A5)."""
    out: dict[str, str] = {}
    for cfg in GRUPPI.values():
        for regione in cfg["regioni"]:
            out[regione] = cfg["formato"]
    return out


def estrai_tracciati(df: pd.DataFrame, regione_gruppo: dict[str, str]) -> pd.DataFrame:
    df = df.copy()
    df["ref"] = df.apply(risolvi_ref, axis=1)
    df = df[df["ref"].notna()]
    df["gruppo"] = df["region"].map(regione_gruppo)

    ordine_gruppi = {nome: i for i, nome in enumerate(GRUPPI)}
    df["_ord_gruppo"] = df["gruppo"].map(ordine_gruppi)
    df["_ref_key"] = df["ref"].map(lambda r: tuple(natural_ref_key(r)))
    df = df.sort_values(
        ["_ord_gruppo", "region", "_ref_key"]
    ).drop(columns=["_ord_gruppo", "_ref_key"])

    return df[COLONNE_TRACCIATI].reset_index(drop=True)


def estrai_riepilogo(
    df: pd.DataFrame,
    regione_gruppo: dict[str, str],
    regione_formato: dict[str, str],
) -> pd.DataFrame:
    df = df.copy()
    df["gruppo"] = df["region"].map(regione_gruppo)
    df["formato"] = df["region"].map(regione_formato)
    ordine_gruppi = {nome: i for i, nome in enumerate(GRUPPI)}
    df["_ord_gruppo"] = df["gruppo"].map(ordine_gruppi)
    df = df.sort_values(["_ord_gruppo", "region"]).drop(columns="_ord_gruppo")
    return df[COLONNE_RIEPILOGO].reset_index(drop=True)


def estrai_tappe_passaporto(
    excel_path: Path = EXCEL_SOURCE_PATH,
    output_path: Path = OUTPUT_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    regione_gruppo = mappa_regione_gruppo()
    regione_formato = mappa_regione_formato()

    tracciati = pd.read_excel(excel_path, sheet_name=SHEET_TRACCIATI)
    riepilogo = pd.read_excel(excel_path, sheet_name=SHEET_RIEPILOGO)

    out_tracciati = estrai_tracciati(tracciati, regione_gruppo)
    out_riepilogo = estrai_riepilogo(riepilogo, regione_gruppo, regione_formato)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        out_tracciati.to_excel(writer, sheet_name=SHEET_TRACCIATI, index=False)
        out_riepilogo.to_excel(writer, sheet_name=SHEET_RIEPILOGO, index=False)

    return out_tracciati, out_riepilogo


def main():
    parser = argparse.ArgumentParser(
        description="Estrae tappe_passaporto.xlsx da tappe.xlsx"
    )
    parser.add_argument(
        "--excel",
        type=Path,
        default=EXCEL_SOURCE_PATH,
        help=f"File sorgente (default: {EXCEL_SOURCE_PATH.name})",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=OUTPUT_PATH,
        help=f"File destinazione (default: {OUTPUT_PATH.name})",
    )
    args = parser.parse_args()

    tracciati, riepilogo = estrai_tappe_passaporto(args.excel, args.output)
    print(
        f"✔ {args.output.name}: {len(tracciati)} tappe, "
        f"{len(riepilogo)} regioni"
    )


if __name__ == "__main__":
    main()
