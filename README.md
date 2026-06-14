# Passaporto del Camminatore — Sentiero Italia CAI

Generatore di passaporti stampabili: pagine A6 (105×148 mm) compilate con
XeLaTeX e imposte a valle con pypdf. Le 19 regioni del Sentiero Italia sono
raggruppate in **8 passaporti**, ciascuno contenuto in **1 solo foglio**:
7 passaporti su A4 fronte/retro (piega a croce) e il passaporto della Val
d'Aosta su A5 landscape fronte/retro (piega unica).

## Uso

```bash
pip install -r requirements.txt
# richiede xelatex (texlive-xetex) installato nel sistema

python genera_passaporto.py --all          # tutti gli 8 passaporti
python genera_passaporto.py "Nord Est"     # un gruppo specifico
python genera_passaporto.py --list         # gruppi disponibili
python verifica_tappe.py                   # controllo salti numerazione tappe
```

Dopo ogni modifica alla copertina (template, layout, crediti foto o mappe,
immagini), rigenerare sempre tutti i passaporti con `--all`, il raccoglitore
con `genera_raccoglitore.py`, e aggiornare il README di conseguenza.

Per ogni gruppo vengono prodotti tre PDF in `output/<slug>/` (es.
`output/nord_est/`, `output/valle_d_aosta/`):

Le mappe di copertina sono in `output/mappe/` (cartella separata).

| File | Contenuto |
|---|---|
| `passaporto_<gruppo>_A6.pdf` | pagine A6 in sequenza logica (per verifica a video) |
| `passaporto_<gruppo>_A4_stampa.pdf` (o `_A5_stampa.pdf` per Valle d'Aosta) | imposizione fronte/retro **senza margini** (al vivo, per tipografia) |
| `passaporto_<gruppo>_A4_stampa_margini.pdf` (o `_A5_...`) | stessa imposizione **con margini di stampa** (5 mm, contenuto scalato e centrato — per stampanti non borderless; costante `MARGINE_STAMPA_MM`) |

## Verifica numerazione tappe

`verifica_tappe.py` controlla la **consecutività numerica** delle tappe
per passaporto e regione: all'interno di ogni serie letterale (es. `N01`,
`N02`, `N06`) segnala i salti rispetto al numero atteso.

```bash
python verifica_tappe.py              # report completo su stdout
python verifica_tappe.py --json       # output strutturato (CI / script)
python verifica_tappe.py --solo-assenti  # solo numeri base assenti dal dataset
python verifica_tappe.py --excel path/to/tappe.xlsx  # file dati alternativo
```

Exit code: `0` se nessun salto, `1` se ne trova (utile in CI opzionale).

Il controllo opera sui **ref base** (`SI N04`, `SI E46`…), non sulle
**varianti** (`SI N04` vs `SI E39A`/`E39B`, `SI Z21A`/`Z21B`, `SI C10N`/`C10S`…).
Le varianti sono incluse nel passaporto come tappe a sé (celle timbro
distinte) ma non “colmano” un salto sul numero base nello script.

Per ogni salto il report indica:

| Esito | Significato |
|---|---|
| **Presenti altrove** | il numero base esiste in un'altra regione (es. `N04` in Umbria mentre in Marche si salta da `N02` a `N06`) |
| **Assenti dal dataset** | il numero base non compare da nessuna parte in `tappe.xlsx` (né come tappa né come lookup dello script) |

Interpretazione tipica dei salti (controllo manuale sul dataset attuale):

- **Cross-regione** — la numerazione CAI è nazionale; le regioni sono
  raggruppamenti editoriali. Esempio: serie `N` spezzata tra Umbria
  (Centro Nord) e Marche (Centro Sud).
- **Varianti** — molti “assenti” segnalati dallo script sono in realtà
  coperti da suffissi nel passaporto (es. `E39A`/`E39B` al posto di `E39`,
  `Z10A`/`Z10B` al posto di `Z10`). Con `--solo-assenti` restano solo i
  buchi reali sul numero base.
- **Assenti davvero** (dataset corrente) — solo **G33** (Liguria) e
  **R04** (Puglia).

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
| 4 | Mappa del SICAI | esterno, retro copertina | testo introduttivo + **mappa dell'intero percorso** generata a build-time + credito cartografico sotto la mappa |

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
| 6 | Centro Sud | Marche, Lazio, Abruzzo, Molise, Puglia | A4 210×297 mm | 76 | 7 | 0 |
| 7 | Sud | Basilicata, Campania, Calabria | A4 210×297 mm | 73 | 7 | 0 |
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
**inizio**, **arrivo**, **km**, **D+** e **D-** (dislivello positivo e
negativo); i campi senza dato non vengono mostrati.

La **copertina** è organizzata in tre fasce:

1. **Alto** — mappa del gruppo (40×50 mm, sinistra) con credito cartografico
   sotto (corsivo ~7 pt, allineato a destra entro i 40 mm: `© CAI © OpenStreetMap`);
   loghi CAI/SICAI (destra); box bianco «PASSAPORTO» e titolo «SENTIERO ITALIA CAI»
   su una riga (stessa larghezza, 50 mm), allineati a destra.
2. **Centro-destra** — nome del passaporto e statistiche aggregate per regione
   (tappe, km, D+, D−), in bianco grassetto, vincolate alla colonna destra
   (49–99 mm) su una sola riga ciascuna. Nei passaporti monoregione con nome
   coincidente col gruppo il nome regione non viene ripetuto: il recap compare
   alla stessa altezza del primo nome regione nei gruppi multiregione.
3. **Basso** — blocco fotografia + crediti centrato verticalmente tra fine
   elenco regioni e URL (`www.sentieroitalia.cai.it`): foto a tutta larghezza
   (93 mm, altezza dinamica), citazione CC BY su **due righe** (attribution +
   fonte/licenza da `FotoSICAI`), stessa dimensione tipografica, ~5 mm di aria
   sopra l’URL. Nei gruppi **multiregione** la foto è allargata su entrambi i
   lati: in alto inizia subito sotto il recap dell'ultima regione (il pitch
   `_PER_ROW_MM` conta solo gli intervalli *tra* le righe, n−1, e l'ultima riga
   occupa la sola `stat_tail_mm`); in basso scende di più e i crediti la seguono
   restando appena sopra l'URL (gap inferiore = `_TOP_GAP_MM`, simmetrico con
   quello superiore; `footer_margin` e `bottom_gap` ridotti). I gruppi
   monoregione restano invariati.

Ogni pagina timbri ospita **12 timbri quadrati** (griglia 3 colonne × 4
righe sotto l'header da 14 mm). Capacità di un foglio A4: copertina +
7 pagine timbri = **84 tappe max**. La pagina mappa (vecchio retro
copertina) è stata rimossa per liberare uno slot timbri nel foglio.

## Struttura

```
progetto/
├── genera_passaporto.py             # pipeline completa + GRUPPI
├── genera_raccoglitore.py           # raccoglitore A5→A6 (riusa la pipeline)
├── genera_mappe.py                  # mappe basemap Webmapp + overlay SICAI
├── genera_copertine.py              # ritaglio foto copertina + lettura credits
├── verifica_tappe.py                # controllo salti numerazione per passaporto/regione
├── tappe.xlsx    # fonte dati (sviluppo; in prod: PostgreSQL)
├── templates/passaporto.tex.j2      # template LaTeX (delimitatori ((( ))) / ((* *)))
├── templates/raccoglitore.tex.j2    # template LaTeX del raccoglitore
├── assets/logo_cai.png              # ritagliato e con sfondo trasparente
├── assets/logo_sicai.png            # logo Sentiero Italia / SICAI
├── assets/copertine/<slug>/         # foto copertina per ogni passaporto (vedi sotto)
├── assets/sicai_tappe.geojson       # tracciato SICAI (525 tappe, overlay mappe)
├── assets/limits_IT_regions.geojson # confini delle 20 regioni (overlay mappe)
├── .tile_cache/                     # cache tile basemap (gitignorata)
└── fonts/Montserrat-*.ttf
```

## Mappe dinamiche

Le mappe di copertina (passaporto) e del retro (raccoglitore) sono
generate a build-time da `genera_mappe.py`:

- **basemap**: tile raster Webmapp (`https://api.webmapp.it/tiles/{z}/{x}/{y}.png`,
  Web Mercator), scaricate al volo e cachate in `.tile_cache/`; lo zoom è
  scelto in automatico per garantire ≥300 dpi alla dimensione di stampa;
- **overlay vettoriale** (resta vettoriale nel PDF): tracciato SICAI da
  `assets/sicai_tappe.geojson` (rosso CAI con alone bianco) e confini
  regionali da `assets/limits_IT_regions.geojson`;
- **raccoglitore** (89×70 mm): Italia intera + tracciato completo, velatura
  leggera fuori dai confini nazionali;
- **passaporto** (40×50 mm): zoom sulla/e regione/i del gruppo, confine
  esterno evidenziato (blu CAI con alone), confini interni sottili nei
  gruppi multiregione, tratto SICAI ritagliato sulle regioni
  (intersezione geometrica con buffer 2 km — robusta rispetto alle
  differenze di codifica `ref`/`sicai_ref`), velatura fuori dal gruppo;
- **attribuzione cartografica**: sotto ogni mappa (passaporto e raccoglitore)
  compare il credito fisso `© CAI © OpenStreetMap` (costante `MAPPA_CREDIT`
  in `genera_passaporto.py`), distinto dai crediti foto CC BY per regione
  (da `assets/copertine/<slug>/credits.txt`).

Le mappe di copertina sono salvate in `output/mappe/` (rigenerate a ogni
build insieme ai passaporti; grazie alla cache tile l'operazione è rapida).
Per generarle/verificarle senza compilare i PDF:

```bash
python genera_mappe.py
```

## Foto di copertina

Le fotografie in basso sulla copertina sono preparate a build-time da
`genera_copertine.py` (Pillow). Per ogni passaporto serve una cartella in
`assets/copertine/<slug>/`, dove `<slug>` coincide con quello del gruppo
(es. `nord_est`, `valle_d_aosta`, `centro_sud`):

| File | Descrizione |
|---|---|
| `original.jpg` (o `.jpeg`/`.png`) | immagine sorgente ad alta risoluzione |
| `credits.txt` | citazione completa CC BY; in copertina divisa in due righe (split automatico su `FotoSICAI`) |
| `cover.jpg` | output generato (ritaglio + ridimensionamento; sovrascritto a ogni build) |

Lo **slot foto** ha larghezza fissa 93 mm; altezza e posizione verticale sono
calcolate in `costruisci_contesto()` con layout **asimmetrico** tra statistiche
regione e URL: gap **1 mm** sopra l'immagine (vicino alle statistiche), banda
crediti **6 mm**, gap sotto i crediti e margine footer prima dell'URL
(`_TOP_GAP_MM`, `_BOTTOM_GAP_MM`, `_CREDIT_BAND_MM`, `_FOOTER_MARGIN_MM`).
Altezza immagine = `placeholder_image_bottom − placeholder_top` mm.

Nei gruppi **multiregione** la foto è ingrandita su entrambi i lati e i gruppi
monoregione restano invariati:

- **in alto** `placeholder_top` usa `(n_regioni − 1) * _PER_ROW_MM + stat_tail_mm`
  (non `n_regioni * _PER_ROW_MM`): l'ultima riga del recap non riserva un pitch
  intero, quindi la foto inizia più vicino al testo;
- **in basso** lo spazio sotto i crediti è compresso (`bottom_gap = _TOP_GAP_MM`,
  `footer_margin = 1 mm`): l'immagine scende di più e i crediti la seguono
  restando appena sopra l'URL, con gap inferiore simmetrico a quello superiore.

Il ritaglio rispetta l'aspect ratio dello slot:

- immagini **verticali** (portrait): crop ancorato in **alto**;
- immagini **orizzontali o quadrate**: crop **centrato**.

Il **credito fotografico** compare subito sotto la linea separatrice
(coordinate dinamiche), in corsivo ~7 pt su **esattamente due righe** con
**stessa dimensione**: larghezza **93 mm** (allineata alla foto), un unico
`\resizebox{93mm}{!}` sul blocco, `\shortstack` + `\mbox` su ciascuna riga
(niente a capo interno); `\fontsize{7}{8.5}\selectfont` applicato
**esplicitamente a ogni riga** (evita reset del font interno a `\shortstack`);
split automatico su `FotoSICAI`. Margine ~3 mm tra fine crediti e URL.

Per testare il ritaglio senza compilare i PDF:

```bash
python genera_copertine.py nord_est 72 118   # slug + top_mm + bottom_mm
```

In assenza di sorgente o `credits.txt` la generazione del passaporto
termina con errore esplicito.

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

7. **Titolo copertina**: «SENTIERO ITALIA CAI» su una riga con
   `\resizebox{50mm}{!}` per allinearlo al box bianco «PASSAPORTO»; le
   statistiche regione usano `\resizebox` nella colonna destra (50 mm) per
   restare su una sola riga senza sconfinare sotto la mappa.

8. **Loghi pre-processati**: separazione delle due metà di
   `logghi_sicai_cai.png`, sfondo nero esterno reso trasparente con
   flood-fill dai bordi (i tratti neri interni dei disegni restano),
   rimozione delle strisce bianche residue di bordo.

9. **Foto copertina dinamiche**: `costruisci_contesto()` calcola top/bottom
   del blocco immagine+crediti (centrato tra statistiche e URL);
   `genera_copertine.py` ritaglia l'originale al rapporto dello slot,
   divide `credits.txt` in due righe al marker `FotoSICAI`; il template
   applica un unico `\resizebox` per entrambe le righe credito.

10. **Crediti mappe**: costante `MAPPA_CREDIT` (`© CAI © OpenStreetMap`)
    passata al template via Jinja; sotto ogni mappa (40×50 mm in copertina
    passaporto, 89×70 mm nel raccoglitore) linea separatrice + testo corsivo
    7 pt allineato a destra, stesso stile dei crediti fotografici.

## Migrazione a PostgreSQL

In `carica_tappe()` sostituire la lettura Excel con:

```sql
SELECT ref, "from", "to", distance, ascent, descent, cai_scale
FROM ec_tracks
WHERE region = ANY(%(regioni)s)
```

(la struttura del dizionario per il template resta identica).
