#!/usr/bin/env python3
"""
Verifica consecutività numerica delle tappe per passaporto e regione.

Per ogni passaporto (GRUPPI) e ogni regione, controlla che i numeri
all'interno della stessa serie letterale (es. N01, N02, N06) siano
consecutivi. Segnala anche se un numero mancante esiste in un'altra
regione del dataset o è assente del tutto.

Uso:
  python verifica_tappe.py              # report completo
  python verifica_tappe.py --json       # output JSON
  python verifica_tappe.py --solo-assenti  # solo numeri assenti dal dataset
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict

import pandas as pd

from genera_passaporto import EXCEL_PATH, SHEET_TRACCIATI, get_gruppi, risolvi_ref


def parse_ref(ref: str) -> tuple[str, int | None, str]:
    """Estrae prefisso letterale, numero e codice breve da 'SI N01'."""
    m = re.match(r"^SI\s+(.+)$", ref.strip())
    if not m:
        code = ref.strip().upper()
        return code, None, code
    code = m.group(1).strip().upper()
    m2 = re.match(r"^([A-Za-z]+)(\d+)$", code)
    if m2:
        return m2.group(1).upper(), int(m2.group(2)), code
    return code, None, code


def fmt_code(prefix: str, num: int) -> str:
    return f"{prefix}{num:02d}" if num < 100 else f"{prefix}{num}"


def carica_dataset(excel_path) -> pd.DataFrame:
    df = pd.read_excel(excel_path, sheet_name=SHEET_TRACCIATI)
    df["ref_completo"] = df.apply(risolvi_ref, axis=1)
    return df[df["ref_completo"].notna()].copy()


def indice_globale(df: pd.DataFrame) -> dict[tuple[str, int], str]:
    """Mappa (serie, numero) → regione."""
    index: dict[tuple[str, int], str] = {}
    for _, row in df.iterrows():
        prefix, num, _ = parse_ref(row["ref_completo"])
        if num is not None:
            index[(prefix, num)] = str(row["region"]).strip()
    return index


def analizza_salti(df: pd.DataFrame) -> list[dict]:
    ref_index = indice_globale(df)
    risultati: list[dict] = []

    for passaporto, cfg in get_gruppi().items():
        regioni = cfg["regioni"]
        sub = df[df["region"].isin(regioni)]

        for regione in regioni:
            reg_df = sub[sub["region"] == regione]
            if reg_df.empty:
                continue

            by_prefix: dict[str, list[int]] = defaultdict(list)
            for _, row in reg_df.iterrows():
                prefix, num, _ = parse_ref(row["ref_completo"])
                if num is not None:
                    by_prefix[prefix].append(num)

            for prefix in sorted(by_prefix):
                nums = sorted(set(by_prefix[prefix]))
                for i in range(len(nums) - 1):
                    if nums[i + 1] - nums[i] <= 1:
                        continue
                    missing = list(range(nums[i] + 1, nums[i + 1]))
                    in_altra_regione = []
                    assenti_dataset = []
                    for n in missing:
                        code = fmt_code(prefix, n)
                        loc = ref_index.get((prefix, n))
                        if loc:
                            in_altra_regione.append({
                                "codice": code,
                                "regione": loc,
                            })
                        else:
                            assenti_dataset.append(code)

                    risultati.append({
                        "passaporto": passaporto,
                        "regione": regione,
                        "serie": prefix,
                        "salto": f"{fmt_code(prefix, nums[i])} → {fmt_code(prefix, nums[i + 1])}",
                        "mancanti": [fmt_code(prefix, n) for n in missing],
                        "in_altra_regione": in_altra_regione,
                        "assenti_dataset": assenti_dataset,
                    })

    return risultati


def filtra_solo_assenti(risultati: list[dict]) -> list[dict]:
    filtrati = []
    for r in risultati:
        if not r["assenti_dataset"]:
            continue
        copia = dict(r)
        copia["mancanti"] = list(r["assenti_dataset"])
        filtrati.append(copia)
    return filtrati


def stampa_report(risultati: list[dict]) -> None:
    if not risultati:
        print("Nessun salto di numerazione trovato.")
        return

    passaporto_corrente = None
    for r in risultati:
        if r["passaporto"] != passaporto_corrente:
            passaporto_corrente = r["passaporto"]
            print(f"\n## {passaporto_corrente}")

        print(f"  {r['regione']} (serie {r['serie']}): {r['salto']}")
        print(f"    Mancanti: {', '.join(r['mancanti'])}")
        if r["in_altra_regione"]:
            altrove = ", ".join(
                f"{x['codice']} (in {x['regione']})" for x in r["in_altra_regione"]
            )
            print(f"    Presenti altrove: {altrove}")
        if r["assenti_dataset"]:
            print(f"    Assenti dal dataset: {', '.join(r['assenti_dataset'])}")

    print(f"\nTotale salti: {len(risultati)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verifica consecutività numerica tappe per passaporto/regione.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in formato JSON",
    )
    parser.add_argument(
        "--solo-assenti",
        action="store_true",
        help="Mostra solo salti con numeri assenti dal dataset",
    )
    parser.add_argument(
        "--excel",
        type=str,
        default=str(EXCEL_PATH),
        help=f"Percorso file Excel (default: {EXCEL_PATH})",
    )
    args = parser.parse_args(argv)

    df = carica_dataset(args.excel)
    risultati = analizza_salti(df)
    if args.solo_assenti:
        risultati = filtra_solo_assenti(risultati)

    if args.json:
        print(json.dumps(risultati, indent=2, ensure_ascii=False))
    else:
        stampa_report(risultati)

    return 1 if risultati else 0


if __name__ == "__main__":
    sys.exit(main())
