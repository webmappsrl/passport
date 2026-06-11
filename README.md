# Passaporto del Camminatore — Sentiero Italia CAI

Generatore di passaporti stampabili: pagine A6 (105×148 mm) compilate con
XeLaTeX e imposte 2×2 su A4 fronte/retro.

## Uso

```bash
pip install jinja2 pandas openpyxl pypdf reportlab
# richiede xelatex (texlive-xetex) installato nel sistema

python genera_passaporto.py Sardegna
python genera_passaporto.py Molise Basilicata
python genera_passaporto.py --list        # regioni disponibili
```

Per ogni esecuzione vengono prodotti due PDF in `output/`:

| File | Contenuto |
|---|---|
| `passaporto_<regione>_A6.pdf` | pagine A6 in sequenza logica (per verifica a video) |
| `passaporto_<regione>_A4_stampa.pdf` | imposizione 2×2 fronte/retro **senza margini** (al vivo, per tipografia) |
| `passaporto_<regione>_A4_stampa_margini.pdf` | stessa imposizione **con margini di stampa** (5 mm, contenuto scalato e centrato — per stampanti che non stampano borderless; costante `MARGINE_STAMPA_MM`) |

Le caselle tappa mostrano solo il **numero progressivo**, il **ref** della
tappa e la **zona timbro** (ampliata a 29×52 mm).

## Struttura

```
progetto/
├── genera_passaporto.py             # pipeline completa
├── tappe.xlsx    # fonte dati (sviluppo; in prod: PostgreSQL)
├── templates/passaporto.tex.j2      # template LaTeX (delimitatori ((( ))) / ((* *)))
├── assets/logo_cai.png              # ritagliato e con sfondo trasparente
├── assets/logo_sicai.png              # logo Sentiero Italia / SICAI
└── fonts/Montserrat-*.ttf
```

## Miglioramenti rispetto al prompt originale

1. **Imposizione separata dal design (pgfpages rimosso).** Il LaTeX
   genera solo il documento A6 sequenziale; l'imposizione è fatta a
   valle con pypdf secondo lo schema **ripiegabile a croce** (come il
   modello SICAI di riferimento): il foglio A4 piegato in 4 diventa il
   passaporto A6.

   ```
   FRONTE (esterno)            RETRO (interno, tutto dritto)
   ┌────────┬────────┐         ┌────────┬────────┐
   │  4 ↓   │  3 ↓   │         │   5    │   6    │
   │ capov. │ capov. │         │        │        │
   ├────────┼────────┤         ├────────┼────────┤
   │   2    │   1    │         │   7    │   8    │
   │ retro  │ coper- │         │        │ (Note) │
   │ cop.   │ tina   │         │        │        │
   └────────┴────────┘         └────────┴────────┘
   ```

   Le tappe **iniziano nel primo A4** (fronte alto = prime due pagine
   timbri); le eventuali pagine **Note cadono alla fine**, negli ultimi
   slot dell'ultimo foglio.

   Chiuso: copertina davanti, retro copertina dietro. Aperto: l'interno
   A4 si legge come 4 sezioni A6 dritte; le due sezioni esterne
   superiori sono capovolte perché risultino dritte dopo la piega
   orizzontale. Segni di piega tratteggiati ai bordi. Un foglio A4
   fronte/retro ospita 8 pagine logiche.

2. **Escaping LaTeX dei dati.** I toponimi possono contenere `&`, `%`,
   `#`, `_` ecc.: un filtro `finalize` di Jinja2 li rende sicuri
   automaticamente su tutte le variabili stringa.

3. **Gestione valori mancanti.** Il dataset contiene 26 `from`, 28 `to`
   e 66 `cai_scale` nulli: lo script stampa `—` / `n.d.` invece di `nan`.

4. **Ordinamento naturale dei ref** (`SI Z2` < `SI Z10`), robusto a
   formati di numerazione diversi tra regioni.

5. **Segni di piega** sul PDF A4 (overlay reportlab) lungo le due
   linee di piega.

6. **Doppia passata XeLaTeX** (necessaria per i nodi TikZ
   `remember picture`) e `--halt-on-error` con log diagnostico.

7. **Titolo copertina via `font=` del nodo TikZ**: con `\fontsize`
   inline il corpo non sopravvive al `\\` nei nodi multilinea.

8. **Loghi pre-processati**: separazione delle due metà di
   `logghi_sicai_cai.png`, sfondo nero esterno reso trasparente con
   flood-fill dai bordi (i tratti neri interni dei disegni restano),
   rimozione delle strisce bianche residue di bordo.

## Migrazione a PostgreSQL

In `carica_tappe()` sostituire la lettura Excel con:

```sql
SELECT ref, "from", "to", distance, ascent, cai_scale
FROM ec_tracks
WHERE region = ANY(%(regioni)s)
```

(la struttura del dizionario per il template resta identica).
