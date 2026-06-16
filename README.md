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
python verifica_tappe.py --excel path/to/tappe_passaporto.xlsx  # file dati alternativo
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
| **Assenti dal dataset** | il numero base non compare da nessuna parte nel dataset (né come tappa né come lookup dello script) |

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

## Dati tappe (`tappe_passaporto.xlsx`)

Flusso dati:

```
tappe.xlsx  →  estrai_tappe_passaporto.py  →  tappe_passaporto.xlsx  →  genera_passaporto.py
```

- **`tappe.xlsx`** — export completo dal database (sviluppo).
- **`tappe_passaporto.xlsx`** — file operativo per generazione e verifica:
  sole colonne usate dal passaporto, fogli **Tracciati** e **Riepilogo per Regione**.

Colonne foglio **Tracciati**: `id`, `ref` (risolto come sul timbro), `region`,
`gruppo`, `from`, `to`, `distance`, `ascent`, `descent`.

Colonne foglio **Riepilogo per Regione**: `lettera`, `region`, `gruppo`, `num_tappe`, `formato` (A4 / A5).

```bash
python estrai_tappe_passaporto.py   # rigenera tappe_passaporto.xlsx da tappe.xlsx
```

Da eseguire dopo ogni aggiornamento di `tappe.xlsx`, prima di rigenerare i passaporti.

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

Le pagine interne (timbri, note, presentazione ecc.) hanno un **header da 14 mm**
con sfondo blu CAI: tutti i testi sono in **bianco grassetto**. Nel **passaporto**
compare a sinistra il nome del gruppo (9/11 pt), al centro «Sentiero Italia CAI»
(7/9 pt) e a destra «Tappe …» o «Note» (8/10 pt). Nel **raccoglitore** a sinistra
il titolo di sezione (9/11 pt) e a destra «Sentiero Italia CAI» (7/9 pt).

La **copertina** è organizzata in tre fasce:

1. **Alto** — mappa del gruppo (40×50 mm, sinistra) con credito cartografico
   sotto (grassetto bianco ~7 pt, allineato a destra entro i 40 mm: `© CAI © OpenStreetMap`);
   loghi CAI/SICAI (destra); box bianco «PASSAPORTO» e titolo «SENTIERO ITALIA CAI»
   su una riga (stessa larghezza, 50 mm), allineati a destra.
2. **Centro-destra** — blocco testo **uniforme** sotto «SENTIERO ITALIA CAI», in
   bianco grassetto, allineato a destra (49–99 mm). Il blocco **risale** così che
   il suo **fondo si allinei col fondo della mappa** a sinistra (colonna mappa e
   colonna loghi+testo della stessa altezza):
   1. **nome del passaporto** (es. *Centro Sud*) — node a −54 mm;
   2. **elenco delle regioni** del gruppo su **una sola riga** separato da virgola
      (es. *Marche, Lazio, Abruzzo, Molise, Puglia*) a −59,5 mm; nei passaporti
      **monoregione** col nome coincidente col gruppo questa riga è **omessa**;
   3. **recap unico totale** del gruppo — *N tappe · km totali · D+ · D−*. Nei
      **multiregione** è in **riga 3** (−63 mm, fondo ≈ fondo mappa); nei
      **monoregione** prende il **posto dell'elenco regioni** (riga 2, −59,5 mm),
      così sta **subito dopo il nome**.
3. **Basso** — blocco fotografia + crediti tra il blocco testo e l'URL
   (`www.sentieroitalia.cai.it`): foto a tutta larghezza (93 mm), citazione
   CC BY su **esattamente due righe** (attribuzione + fonte/licenza da `Sentiero
   Italia CAI`), con **dimensione adattata** alla larghezza foto (93 mm) per stare
   in due righe — **non** quella del credito mappa: la size si riduce quanto basta
   (più piccola dove l'attribuzione è lunga, es. Nord Est), per massimizzare la
   foto. Crediti appena sopra l'URL. Il **top dell'immagine**
   sale appena sotto il credito cartografico della mappa: la foto è più alta in
   alto ed **identica per tutti i passaporti** (mono e multiregione) — stesso
   top/bottom, stesso crop.

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
├── estrai_tappe_passaporto.py       # tappe.xlsx → tappe_passaporto.xlsx
├── tappe.xlsx                       # export completo DB (sviluppo; in prod: PostgreSQL)
├── tappe_passaporto.xlsx            # fonte dati passaporto (rigenerare dopo tappe.xlsx)
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
| `credits.txt` | citazione completa CC BY; in copertina divisa in due righe (split automatico su `Sentiero Italia CAI`) |
| `cover.jpg` | output generato (ritaglio + ridimensionamento; sovrascritto a ogni build) |

Lo **slot foto** ha larghezza fissa 93 mm e geometria **uniforme** per tutti i
passaporti (mono e multiregione), calcolata in `costruisci_contesto()`. Poiché il
blocco testo è ad altezza costante, `stats_bottom_mm` è una **costante**
(`_STATS_BOTTOM_MM = 68`), quindi `placeholder_top_mm` e `placeholder_image_bottom_mm`
sono fissi e identici per ogni gruppo → **stesso crop** in `genera_copertine.py`
(rapporto `93 / altezza`). Il top immagine è alzato appena sotto il credito
cartografico della mappa. Layout sotto al blocco testo: gap **1 mm** sopra
l'immagine (`_TOP_GAP_MM`), banda crediti **5 mm** (`_CREDIT_BAND_MM`, credito su
2 righe adattate), gap **1 mm** sotto i crediti (`_BOTTOM_GAP_MM`) e margine
footer **1 mm** prima dell'URL (`_FOOTER_MARGIN_MM`); con questi valori
`placeholder_top ≈ 69 mm`, `placeholder_image_bottom ≈ 132,5 mm`, altezza immagine
≈ 63,5 mm.

Il ritaglio rispetta l'aspect ratio dello slot:

- immagini **verticali** (portrait): crop ancorato in **alto**;
- immagini **orizzontali o quadrate**: crop **centrato**.

Il **credito fotografico** compare subito sotto la linea separatrice, su
**esattamente due righe** in grassetto bianco con **stessa dimensione** per entrambe,
**adattata** alla larghezza foto: un unico `\resizebox{93mm}{!}` su uno
`\shortstack[r]` di due righe in `\mbox` (niente a capo), scalato perché la riga
più larga (riga 1, attribuzione) misuri 93 mm. Lo split avviene su
**`Sentiero Italia CAI`** (riga 2 = fonte + licenza CC BY). La dimensione
risultante **non** è quella del credito mappa: varia per gruppo (più piccola dove
l'attribuzione è lunga) così da restare su due righe e massimizzare la foto.

Per testare il ritaglio senza compilare i PDF:

```bash
python genera_copertine.py nord_est 69 132.5   # slug + top_mm + bottom_mm
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
│  3 ↓   │  2 ↓   │         │   4    │   5    │
│ capov. │ capov. │         │        │        │
├────────┼────────┤         ├────────┼────────┤
│  8     │   1    │         │   6    │   7    │
│ (Note) │ coper- │         │        │        │
│        │ tina   │         │        │        │
└────────┴────────┘         └────────┴────────┘
```

Il PDF sequenziale ha solo copertina + timbri + Note (niente retro
copertina). Le tappe **iniziano a pag. 2** nel fronte alto-dx (capovolto
per la piega); proseguono in ordine 3→4→5→6→7; le eventuali **Note**
cadono a pag. 8 (basso-sx fronte). Chiuso: copertina davanti. Aperto:
l'interno A4 si legge come 4 sezioni A6 dritte (2→3→4→5); le sezioni
superiori del fronte (2, 3) sono capovolte perché risultino dritte dopo
la piega orizzontale. Segni di piega tratteggiati ai bordi.

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

3. **Gestione valori mancanti.** Il dataset può avere `from`, `to`,
   `ascent` o `descent` nulli: le righe corrispondenti non vengono
   mostrate sul passaporto.

4. **Ordinamento naturale dei ref** (`SI Z2` < `SI Z10`), robusto a
   formati di numerazione diversi tra regioni.

5. **Segni di piega** sul PDF di stampa (overlay reportlab): croce 2×2
   per i fogli A4, piega verticale singola per l'A5 della Valle d'Aosta.

6. **Doppia passata XeLaTeX** (necessaria per i nodi TikZ
   `remember picture`) e `--halt-on-error` con log diagnostico.

7. **Titolo e blocco regioni in copertina**: «SENTIERO ITALIA CAI» su una riga
   con `\resizebox{50mm}{!}` per allinearlo al box bianco «PASSAPORTO». L'elenco
   regioni e il recap totale usano invece la macro `\fitwidth{50mm}` (definita in
   preambolo, basata solo su `graphicx`: niente `adjustbox`, non garantito in
   TinyTeX): rimpicciolisce alla larghezza solo i testi che la eccedono e lascia
   alla dimensione naturale quelli più corti (es. *Sicilia, Sardegna* non viene
   ingrandito come farebbe `\resizebox` puro), garantendo comunque la riga unica.

8. **Loghi pre-processati**: separazione delle due metà di
   `logghi_sicai_cai.png`, sfondo nero esterno reso trasparente con
   flood-fill dai bordi (i tratti neri interni dei disegni restano),
   rimozione delle strisce bianche residue di bordo.

9. **Foto copertina uniformi**: `costruisci_contesto()` fissa top/bottom del
   blocco immagine+crediti a valori **costanti** (slot identico per tutti i
   gruppi); `genera_copertine.py` ritaglia l'originale al rapporto dello slot,
   divide `credits.txt` al marker `Sentiero Italia CAI`; il template rende il
   credito su **2 righe** con un unico `\resizebox{93mm}{!}` su uno `\shortstack`
   di due righe in `\mbox` (stessa dimensione, adattata alla larghezza foto).

10. **Crediti mappe**: costante `MAPPA_CREDIT` (`© CAI © OpenStreetMap`)
    passata al template via Jinja; sotto ogni mappa (40×50 mm in copertina
    passaporto, 89×70 mm nel raccoglitore) linea separatrice + testo grassetto bianco
    7 pt allineato a destra, stesso stile dei crediti fotografici e dell'URL
    `www.sentieroitalia.cai.it` in fondo copertina.

## Migrazione a PostgreSQL

In `carica_tappe()` sostituire la lettura Excel con:

```sql
SELECT ref, "from", "to", distance, ascent, descent, region
FROM ec_tracks
WHERE region = ANY(%(regioni)s)
```

(la struttura del dizionario per il template resta identica).
