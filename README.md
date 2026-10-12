# Passaporto del Camminatore — Sentiero Italia CAI

Generatore di passaporti stampabili: pagine A6 (105×148 mm) compilate con
XeLaTeX e imposte a valle con pypdf. Le 19 regioni del Sentiero Italia sono
raggruppate in **9 passaporti**, ciascuno contenuto in **1 solo foglio**:
7 passaporti su A4 fronte/retro (piega a croce) e 2 passaporti (Calabria e
Valle d'Aosta) su A5 landscape fronte/retro (piega unica). Con `--all` viene
prodotto in più il **libretto unico A6**: tutti i 9 passaporti in un solo PDF,
una facciata A6 per pagina, da stampare e spillare al centro (vedi
[Libretto unico A6](#libretto-unico-a6)).

## Uso

```bash
pip install -r requirements.txt
# richiede xelatex (texlive-xetex) installato nel sistema
# e Ghostscript per la variante CMYK (macOS: brew install ghostscript)

python genera_passaporto.py --all          # 9 passaporti + libretto unico A6 + raccoglitore
python genera_passaporto.py "Nord Est"     # un gruppo specifico
python genera_passaporto.py --list         # gruppi disponibili
python genera_passaporto.py --all --filigrana-mappa  # filigrana timbro con basemap
python verifica_tappe.py                   # controllo salti numerazione tappe
python -m pytest                           # test libretto, box di stampa, PDF/X-4
```

Dopo ogni modifica alla copertina (template, layout, crediti foto o mappe,
immagini), rigenerare sempre tutto con `--all` (passaporti, libretto e
raccoglitore, che popola anche le cartelle di export piatte), e aggiornare il
README di conseguenza. `genera_raccoglitore.py` rigenera il solo raccoglitore.

Per ogni gruppo vengono prodotti tre PDF in `output/<N>_<slug>/`, dove `<N>`
è l'ordine SICAI (es. `output/1_isole/`, `output/9_nord_est/`):

Le mappe di copertina sono in `output/mappe/` (cartella separata).

Per la **stampa** sono disponibili due cartelle piatte in `output/` (tutti i
file in root, senza sottocartelle per gruppo, **senza** PDF A6):

| Cartella | Contenuto |
|---|---|
| `output/stampa/` | 9 passaporti + raccoglitore, versione **al vivo** (`*_stampa.pdf`), + `libretto_A6.pdf` |
| `output/stampa_margini/` | 9 passaporti + raccoglitore, versione **per la tipografia** con abbondanze e segni di taglio (`*_stampa_margini.pdf`), + `libretto_A6_margini.pdf` |
| `output/stampa_cmyk/` | gli stessi file per la tipografia in **PDF/X-4 CMYK FOGRA39** (`*_cmyk.pdf`, `libretto_A6_cmyk.pdf`) — vedi [Varianti colore](#varianti-colore-pdfx-4) |
| `output/stampa_rgb/` | gli stessi file per la tipografia in **PDF/X-4 RGB sRGB** (`*_rgb.pdf`, `libretto_A6_rgb.pdf`) |
| `output/libretto_A6/` | **cartelle pronte da zippare** con solo il libretto A6 e la sua copertina (raccoglitore su pagine A6 singole e montato fronte/retro su A5), una per versione — vedi sotto |

`output/libretto_A6/` contiene una sottocartella per versione di stampa, ognuna
con i soli file da mandare per il libretto: l'interno e la copertina (raccoglitore)
in due forme, su pagine A6 singole e montata fronte/retro sul foglio A5 da piegare
in A6 (la copisteria usa quella che le serve). Nelle cartelle i file prendono il
nome della versione: in `libretto_A6_<versione>/` ci sono `libretto_A6_<versione>.pdf`,
`raccoglitore_A6_<versione>.pdf` e `raccoglitore_A5_<versione>.pdf`:

| Cartella | Contenuto | Copiata da |
|---|---|---|
| `libretto_A6_stampa_margini/` | **PDF/X-4 CMYK** FOGRA39, abbondanze + crocini — **la versione da mandare in stampa** | `stampa_cmyk/` |
| `libretto_A6_stampa_margini_rgb/` | abbondanze + crocini, RGB senza profilo | `stampa_margini/` |
| `libretto_A6_stampa_srgb/` | PDF/X-4 con RGB dichiarato sRGB, abbondanze + crocini | `stampa_rgb/` |
| `libretto_A6_stampa/` | al vivo, senza abbondanze né crocini | `stampa/` |

Esempio: `libretto_A6_stampa_margini/` contiene `libretto_A6_stampa_margini.pdf`
(interno, 60 pagine), `raccoglitore_A6_stampa_margini.pdf` (copertina, 4 pagine A6)
e `raccoglitore_A5_stampa_margini.pdf` (copertina montata, foglio A5 fronte/retro).

Le cartelle sono copie dei file delle cartelle piatte, ricomposte da zero a ogni
generazione del raccoglitore (quindi con `--all`), e cancellate insieme al
libretto quando questo non è più allineato.

I PDF per gruppo in `output/<N>_<slug>/` (inclusi gli A6 per verifica a video)
restano disponibili come prima. I nomi file hanno un **prefisso numerico**
nell'ordine SICAI (`0` = raccoglitore, `1`–`9` = passaporti come nel foglio
**Riepilogo per Gruppo**). Fanno eccezione i file del libretto unico e della sua
copertina su pagine A6 singole (`libretto_A6*.pdf`, `raccoglitore_A6_stampa*.pdf`),
senza prefisso.

| File | Contenuto |
|---|---|
| `<N>_passaporto_<gruppo>_A6.pdf` | pagine A6 in sequenza logica (per verifica a video) |
| `<N>_passaporto_<gruppo>_A4_stampa.pdf` (o `_A5_stampa.pdf` per Calabria/Valle d'Aosta) | imposizione fronte/retro **al vivo** (formato rifilato, per stampanti da ufficio) |
| `<N>_passaporto_<gruppo>_A4_stampa_margini.pdf` (o `_A5_...`) | stessa imposizione **per la tipografia**: abbondanze e segni di taglio e di piega (vedi [Stampa in tipografia](#stampa-in-tipografia)) |

Nelle cartelle piatte `output/stampa/` e `output/stampa_margini/` i PDF
seguono lo stesso schema (es. `0_raccoglitore_A5_stampa.pdf`,
`1_passaporto_isole_A4_stampa.pdf`, …).

## Libretto unico A6

`python genera_passaporto.py --all`, dopo i 9 passaporti, compone un **unico
libretto A6** da spillare al centro, unendo con pypdf gli A6 dei gruppi (senza
ricompilare LaTeX):

| File | Contenuto |
|---|---|
| `output/libretto_A6.pdf` | facciate A6 105×148 mm in sequenza, **al vivo**, non imposte su A4 (copiato in `output/stampa/`) |
| `output/libretto_A6_margini.pdf` | stesse facciate **per la tipografia**: ognuna con 3 mm di abbondanza e segni di taglio (copiato in `output/stampa_margini/`) |

Composizione, nell'ordine del foglio **Riepilogo per Gruppo**:

- ogni gruppo porta la sua **copertina** (che nel libretto fa da separatore) e
  le sue **pagine timbri**;
- un gruppo con un numero **dispari** di pagine riceve in coda una pagina
  **Note**, così ogni copertina cade su una pagina dispari (a destra);
- l'**ultima pagina** è sempre una pagina Note, e il totale è un **multiplo di 4**
  (se serve si aggiungono pagine Note in fondo).

Con i dati attuali il libretto ha **60 facciate**, come l'esempio di Enrico
(ottobre 2026): Isole 1-8, Calabria 9-12, Sud 13-20, Centro 21-26, Centro Nord
27-34, Piemonte 35-42, Valle d'Aosta 43-46, Lombardia 47-52, Nord Est 53-60;
pagine Note a pagina 8, 34, 46 e 60. La mappa «gruppo → pagine» è stampata a
fine generazione.

Prima di pubblicarlo lo script **rilegge il PDF scritto** e si ferma con errore
se le pagine non sono un multiplo di 4, se una copertina cade su una pagina
pari, se l'ultima pagina non è una Note o se la struttura non è quella attesa.

**Copertina.** La «copertina rigida» del libretto è il [raccoglitore](#raccoglitore-del-camminatore)
(ipotesi di lavoro, ottobre 2026, da confermare con il committente): il foglio A5
piegato avvolge le 60 facciate interne e viene spillato con loro, per **64 facciate
in tutto** (4 di copertina + 60 interne). Alla copisteria vanno quindi due file,
entrambi da `output/stampa_margini/`: l'interno (`libretto_A6_margini.pdf`) e la
copertina (`0_raccoglitore_A5_stampa_margini.pdf`: foglio A5 aperto, fronte = retro
e prima di copertina, retro = interno, con segno della piega di dorso; in alternativa
`raccoglitore_A6_stampa_margini.pdf`, le stesse 4 facciate su pagine A6 singole in
ordine di lettura), oppure gli
stessi due file da `output/stampa_cmyk/` o `output/stampa_rgb/` se la copisteria
chiede PDF/X-4 in CMYK o in RGB. Per questo `--all` rigenera anche il raccoglitore.

Il libretto esiste solo se allineato ai passaporti: ogni generazione **lo
cancella all'inizio** (con le copie di stampa) e solo `--all`, a fine run
riuscita, lo riscrive. Rigenerando un singolo gruppo lo script avvisa
«libretto rimosso perché non più allineato: rigeneralo con --all».

## Stampa in tipografia

Su indicazione della copisteria (ottobre 2026) i PDF per la tipografia devono
avere **abbondanze** e **segni di taglio**, e testi e cornici tratteggiate devono
stare ad almeno **3–4 mm** dal taglio, perché in confezionamento non si taglino.

- **Abbondanze** — le pagine A6 sono compilate a 111 × 154 mm: A6 più **3 mm**
  per lato (`ABBONDANZA_MM`), dove escono gli sfondi blu (copertina, header,
  facciate piene del raccoglitore). L'A6 porta TrimBox/CropBox sul formato
  rifilato, così a video e nelle versioni al vivo si vede solo l'A6.
- **Versione per la tipografia** (`*_stampa_margini.pdf`, `libretto_A6_margini.pdf`)
  — il foglio rifilato (A4, A5 o A6) è circondato dall'abbondanza e da una fascia
  bianca di 10 mm (`AREA_SEGNI_MM`) con i **crocini di taglio** agli angoli e i
  **segni di piega** tratteggiati, in colore di registro e fuori dal formato.
  Sui fogli piegati l'abbondanza c'è solo sui lati esterni: sulle pieghe interne
  ogni facciata resta rifilata al suo slot. TrimBox e BleedBox sono impostati.
- **Area sicura** — tutti i testi stanno ad almeno 4,5 mm dal taglio; la griglia
  timbri occupa x 4–101 mm e y 14–144 mm, quindi i bordi delle celle stanno a
  4 mm dal taglio e i riquadri tratteggiati a 5 mm o più.

Le versioni al vivo (`*_stampa.pdf`, `libretto_A6.pdf`) restano senza abbondanze
né crocini, con le sole tacche di piega dentro il foglio.

I grigi di linee e testi secondari (`grigiolinea` K 20%, `grigiochiarotesto`
K 58%) sono definiti in **solo nero**: in quadricromia le linee sottili
(riquadri tratteggiati, bordi celle) restano nitide anche con un registro
imperfetto. Il blu CAI è già CMYK (100/72/0/19, FOGRA39, dal brandbook).

### Varianti colore (PDF/X-4)

Foto, mappe, filigrane, loghi e azzurro sono RGB. Dai PDF per la tipografia
(`stampa_margini/`) `esporta_colore.py` ricava due varianti, entrambe **PDF/X-4**
con condizione di stampa **FOGRA39** (OutputIntent con profilo incorporato,
metadati XMP, Trapped), da scegliere in base a cosa chiede la copisteria:

| Cartella | Colore | Quando usarla |
|---|---|---|
| `output/stampa_cmyk/` | tutto **CMYK**: Ghostscript converte l'RGB verso FOGRA39 in un solo passaggio sul PDF finale (colorimetrico relativo + compensazione del punto nero, senza ricampionare le immagini); il colore già CMYK resta invariato | la copisteria vuole file CMYK |
| `output/stampa_rgb/` | colore **invariato**, l'RGB è dichiarato **sRGB** (profilo sRGB2014 su immagini, gruppi di trasparenza e `DefaultRGB` per i colori vettoriali) | la copisteria accetta RGB e converte con il suo profilo |

Profili in `assets/icc/`, dal registro ICC (color.org): `Coated_Fogra39L_VIGC_300.icc`
(FOGRA39) e `sRGB2014.icc`. Il profilo FOGRA39 incorporato pesa circa 8,6 MB per file.

Ogni file è **riletto e verificato** prima della pubblicazione (`verifica_pdfx4`):
versione PDF ≤ 1.6, `/ID`, un solo OutputIntent con profilo CMYK, Trapped, XMP
PDF/X-4, TrimBox dentro BleedBox dentro MediaBox, nessuna pagina ruotata, nessuna
annotazione, font tutti incorporati, niente funzioni di trasferimento, e per il
colore: nessun RGB nella variante CMYK, nessun RGB non dichiarato nella variante
RGB. In caso di errore la generazione si ferma. Ghostscript va lanciato con
`-dAutoRotatePages=/None`: altrimenti ruota di 180° i fronti A4, dove prevale il
testo capovolto.

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
  raggruppamenti editoriali. Una stessa serie letterale può attraversare il
  confine tra due passaporti (es. la serie `Q/R` tra Sud e Centro).
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
  fogli **Tracciati**, **Riepilogo per Regione** e **Riepilogo per Gruppo**.

Colonne foglio **Tracciati**: `id`, `ref` (risolto come sul timbro), `region`,
`gruppo`, `from`, `to`, `distance`, `ascent`, `descent`.

L'**ordine delle righe** nel foglio Tracciati segue il **senso del Sentiero
Italia CAI** (da Sardegna verso Friuli). Nel PDF, `carica_tappe()` ordina le
tappe per **blocco regionale** secondo l'ordine del foglio **Riepilogo per
Regione** e, dentro ogni regione, preserva il senso di percorrenza del foglio
Tracciati (evitando riordinamenti alfabetici per ref).

Colonne foglio **Riepilogo per Regione**: `lettera`, `region`, `Gruppo`
(codice col prefisso, es. `4-Centro`), `num_tappe`, `formato` (A4 / A5) —
ordine regioni in copertina e percorrenza dentro ogni passaporto. L'ordine
delle regioni di un gruppo segue le `lettera` di questo foglio; i nomi regione
sono poi risolti dal foglio Tracciati.

Colonne foglio **Riepilogo per Gruppo**: `lettera`, `gruppo` (col prefisso
numerico, es. `1-Isole`), `num_totale`, `formato` — ordine dei passaporti,
conteggio tappe atteso e formato foglio. `get_gruppi()` carica gruppi, regioni
e formato da questi fogli e rimuove il prefisso numerico per il nome display.

```bash
python estrai_tappe_passaporto.py   # rigenera tappe_passaporto.xlsx da tappe.xlsx
```

Da eseguire dopo ogni aggiornamento di `tappe.xlsx`, prima di rigenerare i
passaporti. Se si aggiorna `tappe_passaporto.xlsx` a mano, verificare che i
tre fogli restino coerenti (in particolare `num_totale` nel Riepilogo per Gruppo).

## Raccoglitore del Camminatore

Oltre ai passaporti è disponibile un **raccoglitore**, che fa da
**copertina del libretto unico A6** (vedi [Libretto unico A6](#libretto-unico-a6))
e che con i pieghevoli il camminatore conserva insieme ai singoli passaporti: un foglio
**A5 landscape (210×148 mm) fronte/retro** che, piegato in due lungo la
piega verticale centrale, diventa un libretto **A6** a 4 facciate
(stesso meccanismo del passaporto Valle d'Aosta).

```bash
pip install cairosvg   # conversione QR SVG → PNG per XeLaTeX
python genera_raccoglitore.py   # solo il raccoglitore (--all lo genera già)
```

Produce in `output/`: `0_raccoglitore_A6.pdf` e, per la stampa, il raccoglitore
in due formati, ciascuno al vivo e per la tipografia (abbondanze e segni di taglio),
più le varianti PDF/X-4 CMYK e RGB:

| Formato | Al vivo | Per la tipografia |
|---|---|---|
| foglio **A5** aperto, imposto per la piega | `0_raccoglitore_A5_stampa.pdf` | `0_raccoglitore_A5_stampa_margini.pdf` (+ `_cmyk`, `_rgb`) |
| **A6 su pagine singole**, 4 facciate in ordine di lettura | `raccoglitore_A6_stampa.pdf` | `raccoglitore_A6_stampa_margini.pdf` (+ `_cmyk`, `_rgb`) |

Le 4 facciate logiche (ordine sequenziale A6, imposte con
`imponi_su_a5`):

| # | Facciata | Posizione | Contenuto |
|---|---|---|---|
| 1 | Copertina | esterno, fronte destra | stile copertina passaporto; etichetta **«N. identificativo passaporto»** in bianco grassetto 7/8,5 pt sopra il box bianco centrale per il numero compilato a mano |
| 2 | Presentazione | interno sinistra | campi **Nome** e **Cognome**, riquadro 35×45 mm per la **foto tessera**, linea per la **firma** |
| 3 | Cos'è il SICAI | interno destra | testo descrittivo del progetto + badge store e **QR code** app Android/iOS |
| 4 | Mappa del SICAI | esterno, retro copertina | testo introduttivo + **mappa dell'intero percorso** generata a build-time + credito cartografico sotto la mappa |

Template:
`templates/raccoglitore.tex.j2`. I QR code sono convertiti da SVG a PNG
a build-time (`cairosvg`) perché XeLaTeX non include direttamente gli SVG.

## Raggruppamenti (`get_gruppi()` da Excel)

Ordine passaporti, regioni per gruppo, formato e `num_totale` sono letti da
`tappe_passaporto.xlsx` (fogli **Riepilogo per Gruppo** e **Riepilogo per Regione**).

Il nome del gruppo nei fogli Excel ha un **prefisso numerico** che fissa
l'ordine dei passaporti (`1-Isole`, `2-Calabria`, …); `get_gruppi()` lo
rimuove (`nome_display_gruppo()`) e nei PDF e negli slug compare solo il nome
(`Isole`, `Calabria`, …).

| # | Gruppo | Regioni (ordine percorrenza) | Formato foglio | Tappe | Pag. timbri | Note |
|---|---|---|---|---:|---:|---:|
| 1 | Isole | Sardegna, Sicilia | A4 210×297 mm | 67 | 6 | 1 |
| 2 | Calabria | Calabria | **A5 210×148 mm** | 33 | 3 | 0 |
| 3 | Sud | Basilicata, Campania, Puglia, Molise | A4 210×297 mm | 79 | 7 | 0 |
| 4 | Centro | Abruzzo, Lazio, Marche/Umbria | A4 210×297 mm | 56 | 5 | 2 |
| 5 | Centro Nord | Toscana/Emilia Romagna, Liguria | A4 210×297 mm | 69 | 6 | 1 |
| 6 | Piemonte | Piemonte | A4 210×297 mm | 83 | 7 | 0 |
| 7 | Valle d'Aosta | Valle d'Aosta | **A5 210×148 mm** | 20 | 2 | 1 |
| 8 | Lombardia | Lombardia | A4 210×297 mm | 60 | 5 | 2 |
| 9 | Nord Est | Veneto, Trentino-Alto Adige, Friuli Venezia Giulia | A4 210×297 mm | 68 | 6 | 1 |

Totale: **535 tappe, 9 fogli** (7 A4 + 2 A5). Il **Piemonte** è al limite
A4 (**83 tappe** = 7 pagine timbri).

## Dimensioni

| Elemento | Dimensioni |
|---|---|
| Foglio di stampa A4 (gruppi 1–3, 5–8) | 210 × 297 mm |
| Foglio di stampa A5 landscape (Valle d'Aosta) | 210 × 148 mm |
| Pagina / passaporto chiuso (tutti) | 105 × 148 mm (A6) |
| Casella timbro (griglia 3×4, 12 per pagina) | cella ≈32,3 × 32,5 mm (griglia 97 × 130 mm, a 4 mm dal taglio), zona timbro quadrata 26 × 26 mm |

Ogni casella mostra il **ref** della tappa in alto a sinistra e il **nome
regione** in alto a destra (font più piccolo, **grassetto**, stessa riga); dentro il
riquadro tratteggiato (26×26 mm, testo centrato con a capo automatico)
compaiono **Da**, **a**, **Km**, **D+** e **D-** con etichette brevi e
**stessa dimensione** in tutta la cella: il corpo del testo scala in modo
adattivo (5–8 pt) in base alla lunghezza dei nomi, per riempire il riquadro
e massimizzare la leggibilità in stampa. Km, D+ e D- stanno **ciascuno su una
riga propria** con interlinea uniforme (l'unità `m` non si separa mai dal
valore); i campi senza dato non vengono mostrati. Dietro al testo, **centrata
nel riquadro**, c'è in **filigrana** (opacità 20%) la silhouette del **tracciato
della tappa** (rosso CAI, generata da `sicai_tappe.geojson`); le poche tappe
senza geometria nel dataset non hanno filigrana. Con il flag
`--filigrana-mappa` la filigrana include anche la **basemap** sotto il tracciato
(stessa tappa, stesso riquadro); **senza il flag** (default) resta la sola
silhouette su sfondo trasparente.

Le pagine interne (timbri, note, presentazione ecc.) hanno un **header da 14 mm**
con sfondo blu CAI: tutti i testi sono in **bianco grassetto**. Nel **passaporto**
compare a sinistra il nome del gruppo (9/11 pt), al centro «Sentiero Italia CAI»
(7/9 pt) e a destra «Tappe …» o «Note» (8/10 pt). Le pagine **non sono
numerate** (le tappe si seguono regione per regione) e le pagine **Note** non
riportano il nome del gruppo (sono identiche in tutti i passaporti). Nel **raccoglitore** a sinistra
il titolo di sezione (9/11 pt) e a destra «Sentiero Italia CAI» (7/9 pt); sulla **copertina** l'etichetta
«N. identificativo passaporto» sopra il box bianco è in bianco grassetto **7/8,5 pt**.

Le pagine **Note** del passaporto (dove presenti) e la pagina **Presentazione**
del raccoglitore hanno in filigrana il **logo CAI** centrato sul foglio A6
(48 mm di altezza, opacità 20%), dietro header e contenuto — più grande dei
loghi in copertina (16 mm, pieni) e non invasivo per la scrittura a mano.

La **copertina** è organizzata in tre fasce:

1. **Alto** — mappa del gruppo (40×50 mm, sinistra) con **bordi arrotondati 2 mm**
   (come la foto di copertina) e credito cartografico sotto (grassetto bianco ~7 pt,
   allineato a destra entro i 40 mm: `© CAI © OpenStreetMap`);
   loghi CAI/SICAI (destra); box bianco «PASSAPORTO» e titolo «SENTIERO ITALIA CAI»
   su una riga (stessa larghezza, 50 mm), allineati a destra.
2. **Centro-destra** — blocco testo **uniforme** sotto «SENTIERO ITALIA CAI», in
   bianco grassetto, allineato a destra (49–99 mm). Il blocco **risale** così che
   il suo **fondo si allinei col fondo della mappa** a sinistra (colonna mappa e
   colonna loghi+testo della stessa altezza):
   1. **nome del passaporto** (es. *Centro*) — node a −54 mm;
   2. **elenco delle regioni** del gruppo su **una sola riga** separato da virgola
      (es. *Abruzzo, Lazio, Marche/Umbria*) a −59,5 mm; nei passaporti
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
├── genera_passaporto.py             # pipeline completa + get_gruppi()
├── genera_raccoglitore.py           # raccoglitore A5→A6 (riusa la pipeline)
├── genera_mappe.py                  # mappe basemap Webmapp + overlay SICAI
├── genera_copertine.py              # ritaglio foto copertina + lettura credits
├── esporta_colore.py                # varianti PDF/X-4 CMYK e RGB + verifica PDF/X-4
├── verifica_tappe.py                # controllo salti numerazione per passaporto/regione
├── tests/test_libretto.py           # sequenza pagine del libretto unico A6 (pytest)
├── tests/test_imposizione.py        # box di stampa: abbondanze e segni di taglio (pytest)
├── tests/test_esporta_colore.py     # varianti PDF/X-4 e verificatore (pytest)
├── estrai_tappe_passaporto.py       # tappe.xlsx → tappe_passaporto.xlsx
├── tappe.xlsx                       # export completo DB (sviluppo; in prod: PostgreSQL)
├── tappe_passaporto.xlsx            # fonte dati passaporto (rigenerare dopo tappe.xlsx)
├── templates/passaporto.tex.j2      # template LaTeX (delimitatori ((( ))) / ((* *)))
├── templates/raccoglitore.tex.j2    # template LaTeX del raccoglitore
├── assets/logo_cai.png              # ritagliato e con sfondo trasparente
├── assets/logo_sicai.png            # logo Sentiero Italia / SICAI
├── assets/icc/                       # profili ICC: FOGRA39 (output) e sRGB2014
├── assets/copertine/<slug>/         # foto copertina per ogni passaporto (vedi sotto)
├── assets/sicai_tappe.geojson       # tracciato SICAI (overlay mappe)
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
  leggera fuori dai confini nazionali; bordi arrotondati **2 mm** come la foto
  di copertina;
- **passaporto** (40×50 mm): zoom sulla/e regione/i del gruppo, confine
  esterno evidenziato (blu CAI con alone), confini interni sottili nei
  gruppi multiregione, tratto SICAI ritagliato sulle regioni
  (intersezione geometrica con buffer 2 km — robusta rispetto alle
  differenze di codifica `ref`/`sicai_ref`), velatura fuori dal gruppo;
  bordi arrotondati **2 mm**;
- **filigrane timbro** (26×26 mm): una per tappa, silhouette del solo
  tracciato della tappa (rosso CAI con alone, **sfondo trasparente**, niente
  basemap), salvate come PNG in `output/mappe/filigrane/<sicai_ref>.png` e
  cachate su disco (rigenerate solo se `sicai_tappe.geojson` cambia); inserite
  in filigrana (opacità 20%) dietro il testo di ogni casella timbro. Con il
  flag `--filigrana-mappa` viene invece usata la variante con **basemap
  Webmapp** sotto il tracciato, salvata in `output/mappe/filigrane_mappa/`
  (PNG opaco; la prima build scarica i tile della singola tappa, poi la cache
  `.tile_cache/` accelera le esecuzioni successive);
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
(es. `nord_est`, `valle_d_aosta`, `centro`):

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

4. **Ordine tappe nel passaporto**: raggruppate per **regione** nell'ordine
   del foglio **Riepilogo per Regione**; dentro ogni regione seguono il senso
   del Sentiero Italia CAI nel foglio Tracciati. Gruppi/regioni/formato da
   `get_gruppi()` (fogli Riepilogo). `natural_ref_key` resta in `verifica_tappe.py`
   e `estrai_tappe_passaporto.py`.

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
    `www.sentieroitalia.cai.it` in fondo copertina. Le mappe usano `\clip[rounded
    corners=2mm]` e bordo con lo stesso raggio della foto di copertina.

## Migrazione a PostgreSQL

In `carica_tappe()` sostituire la lettura Excel con:

```sql
SELECT ref, "from", "to", distance, ascent, descent, region
FROM ec_tracks
WHERE region = ANY(%(regioni)s)
```

(la struttura del dizionario per il template resta identica).
