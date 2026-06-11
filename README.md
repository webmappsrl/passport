# Passaporto del Camminatore — Sentiero Italia CAI

Generatore di passaporti stampabili: pagine A6 (105×148 mm) compilate con
XeLaTeX e imposte a valle con pypdf. Le 19 regioni del Sentiero Italia sono
raggruppate in **8 passaporti**, ciascuno contenuto in **1 solo foglio**:
7 passaporti su A4 fronte/retro (piega a croce) e il passaporto della Val
d'Aosta su A5 landscape fronte/retro (piega unica).

## Uso

```bash
pip install jinja2 pandas openpyxl pypdf reportlab
# richiede xelatex (texlive-xetex) installato nel sistema

python genera_passaporto.py --all          # tutti gli 8 passaporti
python genera_passaporto.py "Nord Est"     # un gruppo specifico
python genera_passaporto.py --list         # gruppi disponibili
```

Per ogni gruppo vengono prodotti tre PDF in `output/`:

| File | Contenuto |
|---|---|
| `passaporto_<gruppo>_A6.pdf` | pagine A6 in sequenza logica (per verifica a video) |
| `passaporto_<gruppo>_A4_stampa.pdf` (o `_A5_stampa.pdf` per Valle d'Aosta) | imposizione fronte/retro **senza margini** (al vivo, per tipografia) |
| `passaporto_<gruppo>_A4_stampa_margini.pdf` (o `_A5_...`) | stessa imposizione **con margini di stampa** (5 mm, contenuto scalato e centrato — per stampanti non borderless; costante `MARGINE_STAMPA_MM`) |

## Raccoglitore del Camminatore

Oltre ai passaporti è disponibile un **raccoglitore** che ogni
camminatore conserva insieme ai singoli passaporti: un foglio
**A5 landscape (210×148 mm) fronte/retro** che, piegato in due lungo la
piega verticale centrale, diventa un libretto **A6** a 4 facciate
(stesso meccanismo del passaporto Valle d'Aosta).

```bash
pip install cairosvg   # conversione QR SVG → PNG per XeLaTeX
python genera_raccoglitore.py
```

Produce in `output/`: `raccoglitore_A6.pdf`,
`raccoglitore_A5_stampa.pdf` (al vivo) e
`raccoglitore_A5_stampa_margini.pdf` (margini 5 mm).

Le 4 facciate logiche (ordine sequenziale A6, imposte con
`imponi_su_a5`):

| # | Facciata | Posizione | Contenuto |
|---|---|---|---|
| 1 | Copertina | esterno, fronte destra | stile copertina passaporto; box bianco centrale per il **numero identificativo** compilato a mano |
| 2 | Presentazione | interno sinistra | campi **Nome** e **Cognome**, riquadro 35×45 mm per la **foto tessera**, linea per la **firma** |
| 3 | Cos'è il SICAI | interno destra | testo descrittivo del progetto + badge store e **QR code** app Android/iOS |
| 4 | Mappa del SICAI | esterno, retro copertina | testo introduttivo + placeholder **mappa dell'intero percorso** |

Template:
`templates/raccoglitore.tex.j2`. I QR code sono convertiti da SVG a PNG
a build-time (`cairosvg`) perché XeLaTeX non include direttamente gli SVG.

## Raggruppamenti (costante `GRUPPI`)

| # | Gruppo | Regioni | Formato foglio | Tappe | Pag. timbri | Note |
|---|---|---|---|---:|---:|---:|
| 1 | Nord Est | Friuli Venezia Giulia, Veneto, Trentino | A4 210×297 mm | 69 | 6 | 1 |
| 2 | Lombardia | Lombardia | A4 210×297 mm | 60 | 5 | 2 |
| 3 | Piemonte | Piemonte | A4 210×297 mm | 83 | 7 | 0 |
| 4 | Valle d'Aosta | Valle d'Aosta | **A5 210×148 mm** | 20 | 2 | 1 |
| 5 | Centro Nord | Liguria, Toscana/Emilia Romagna, Umbria | A4 210×297 mm | 77 | 7 | 0 |
| 6 | Centro Sud | Marche, Lazio, Abruzzo, Molise, Basilicata | A4 210×297 mm | 70 | 6 | 1 |
| 7 | Sud | Puglia, Campania, Calabria | A4 210×297 mm | 79 | 7 | 0 |
| 8 | Isole | Sicilia, Sardegna | A4 210×297 mm | 67 | 6 | 1 |

Totale: **525 tappe, 8 fogli** (7 A4 + 1 A5).

## Dimensioni

| Elemento | Dimensioni |
|---|---|
| Foglio di stampa A4 (gruppi 1–3, 5–8) | 210 × 297 mm |
| Foglio di stampa A5 landscape (Valle d'Aosta) | 210 × 148 mm |
| Pagina / passaporto chiuso (tutti) | 105 × 148 mm (A6) |
| Casella timbro (griglia 3×4, 12 per pagina) | cella 35 × 33,5 mm, zona timbro quadrata 26 × 26 mm |

Ogni casella mostra il **ref** della tappa in alto a sinistra e il **nome
regione** in alto a destra (font più piccolo, stessa riga); dentro il
riquadro tratteggiato (testo centrato, a capo automatico) compaiono
**inizio**, **arrivo**, **km**, **dislivello positivo** e **dislivello negativo**;
i campi senza dato non vengono mostrati.

La **copertina** riporta, sotto il nome del passaporto, le statistiche
aggregate per ogni regione del gruppo: numero di tappe, chilometri
totali, dislivello positivo e negativo totali (es.
`20 tappe · 236,7 km · +17.656 m / −18.632 m`). Nei passaporti
monoregione con nome coincidente col gruppo il nome regione non viene
ripetuto sopra la riga statistiche.

Ogni pagina timbri ospita **12 timbri quadrati** (griglia 3 colonne × 4
righe sotto l'header da 14 mm). Capacità di un foglio A4: copertina +
7 pagine timbri = **84 tappe max**. La pagina mappa (vecchio retro
copertina) è stata rimossa per liberare uno slot timbri nel foglio.

## Struttura

```
progetto/
├── genera_passaporto.py             # pipeline completa + GRUPPI
├── genera_raccoglitore.py           # raccoglitore A5→A6 (riusa la pipeline)
├── tappe.xlsx    # fonte dati (sviluppo; in prod: PostgreSQL)
├── templates/passaporto.tex.j2      # template LaTeX (delimitatori ((( ))) / ((* *)))
├── templates/raccoglitore.tex.j2    # template LaTeX del raccoglitore
├── assets/logo_cai.png              # ritagliato e con sfondo trasparente
├── assets/logo_sicai.png            # logo Sentiero Italia / SICAI
└── fonts/Montserrat-*.ttf
```

## Imposizione

L'imposizione è separata dal design (il LaTeX genera solo il documento A6
sequenziale, pypdf monta i fogli a valle).

### Gruppi A4 — ripiegabile a croce (2×2)

Il foglio A4 piegato in 4 diventa il passaporto A6 (come il modello SICAI
di riferimento). Un foglio A4 fronte/retro ospita 8 pagine logiche.

```
FRONTE (esterno)            RETRO (interno, tutto dritto)
┌────────┬────────┐         ┌────────┬────────┐
│  4 ↓   │  3 ↓   │         │   5    │   6    │
│ capov. │ capov. │         │        │        │
├────────┼────────┤         ├────────┼────────┤
│   2    │   1    │         │   7    │   8    │
│        │ coper- │         │        │ (Note) │
│        │ tina   │         │        │        │
└────────┴────────┘         └────────┴────────┘
```

Le tappe **iniziano nel primo slot dopo la copertina**; le eventuali
pagine **Note cadono alla fine**, negli ultimi slot del foglio. Chiuso:
copertina davanti. Aperto: l'interno A4 si legge come 4 sezioni A6
dritte; le due sezioni esterne superiori sono capovolte perché risultino
dritte dopo la piega orizzontale. Segni di piega tratteggiati ai bordi.

### Valle d'Aosta — A5 landscape, piega unica (2×1)

Il foglio A5 landscape (210×148 mm), piegato lungo la piega verticale
centrale, diventa un libretto A6 a 4 facciate. Un foglio A5 fronte/retro
ospita 4 pagine logiche (copertina + 2 pagine timbri + 1 pagina Note).

```
FRONTE (esterno)            RETRO (interno)
┌────────┬────────┐         ┌────────┬────────┐
│   4    │   1    │         │   2    │   3    │
│ (retro │ (coper-│         │        │        │
│  cop.) │  tina) │         │        │        │
└────────┴────────┘         └────────┴────────┘
```

Stampa duplex con **ribaltamento sul lato corto** (le colonne del retro
sono speculari rispetto al fronte). Chiuso il passaporto misura
105×148 mm, identico agli altri.

## Note implementative

1. **Imposizione separata dal design (pgfpages rimosso).** Il LaTeX
   genera solo il documento A6 sequenziale; l'imposizione è fatta a
   valle con pypdf (`imponi_su_a4` per la croce 2×2, `imponi_su_a5`
   per il libretto Valle d'Aosta).

2. **Escaping LaTeX dei dati.** I toponimi possono contenere `&`, `%`,
   `#`, `_` ecc.: un filtro `finalize` di Jinja2 li rende sicuri
   automaticamente su tutte le variabili stringa.

3. **Gestione valori mancanti.** Il dataset contiene `from`, `to` e
   `cai_scale` nulli: lo script stampa `—` / `n.d.` invece di `nan`.

4. **Ordinamento naturale dei ref** (`SI Z2` < `SI Z10`), robusto a
   formati di numerazione diversi tra regioni.

5. **Segni di piega** sul PDF di stampa (overlay reportlab): croce 2×2
   per i fogli A4, piega verticale singola per l'A5 della Valle d'Aosta.

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
SELECT ref, "from", "to", distance, ascent, descent, cai_scale
FROM ec_tracks
WHERE region = ANY(%(regioni)s)
```

(la struttura del dizionario per il template resta identica).
