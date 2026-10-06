> Ticket: oc:8720

# Libretto unico A6 — piano di implementazione

> **Per chi esegue:** sub-skill richiesta: `superpowers:executing-plans` (o
> `superpowers:subagent-driven-development`). I passi usano le checkbox (`- [ ]`).
> **Nessun commit automatico:** i comandi `git commit` sotto sono istruzioni per il dev, da
> eseguire solo dopo il review-gate di `wm-plan`.

**Obiettivo:** `python genera_passaporto.py --all` produce, oltre ai 9 pieghevoli, il libretto
unico `output/libretto_A6.pdf` (al vivo) e `output/libretto_A6_margini.pdf`.

**Architettura:** il libretto si compone con pypdf dagli A6 dei 9 gruppi già prodotti da
`genera_passaporto()`, senza ricompilare LaTeX. Una funzione pura decide la sequenza delle pagine
(copertina / timbri / Note) a partire dai conteggi per gruppo; un'altra la applica ai PDF; un
controllo finale rilegge il PDF scritto e ne classifica le pagine dal testo.

**Tech stack:** Python 3, pypdf, Jinja2 + XeLaTeX (template esistente), pytest (nuovo, solo per
la funzione pura).

**Spec:** [overview.md](overview.md)

## Vincoli globali

- Repo `passport`, nessun submodule. Tutti i file sotto sono nella root del repo.
- Ordine dei gruppi: quello di `get_gruppi()` (foglio «Riepilogo per Gruppo»).
- Pagina libretto: A6 al vivo, `A6_W, A6_H = 105 * MM, 148 * MM`.
- Margine della versione con margini: `MARGINE_STAMPA_MM` (5 mm), già definito.
- File: `output/libretto_A6.pdf` → copia in `output/stampa/`;
  `output/libretto_A6_margini.pdf` → copia in `output/stampa_margini/`.
- I 9 pieghevoli restano prodotti come oggi; cambia solo l'intestazione (Task 1).

## Punti da tenere d'occhio in review

1. Gruppo con numero pari di pagine e A6 con Note di riempimento (Centro, Lombardia: 6 pagine,
   2 Note): nel libretto le Note **non** vanno copiate → test `test_piano_dati_attuali`.
2. Ultimo gruppo con numero pari di pagine: serve una pagina Note in più in fondo, presa da un
   altro gruppo → test `test_piano_ultimo_gruppo_pari`.
3. Nessun gruppo con pagine Note nei suoi A6 (tutti multipli di 4): non c'è una pagina Note da
   copiare → `ValueError` chiaro → test `test_piano_senza_note_disponibili`.
4. Generazione parziale (`python genera_passaporto.py "Nord Est"`) dopo un `--all`: il libretto
   vecchio deve sparire → verifica manuale al Task 3, passo 4.
5. `--all` che si interrompe su un gruppo: nessun libretto scritto → il libretto si compone
   solo dopo il ciclo sui gruppi (Task 3).

---

### Task 1: intestazioni senza numero di pagina e Note senza nome del gruppo

**File:**
- Modifica: `templates/passaporto.tex.j2:50-64` (macro `\pageheader`), `:158`, `:212-219`
- Modifica: `genera_passaporto.py:367-369` (chiave `pagine_numerate` nel contesto)

**Interfacce:**
- Produce: `\pageheader{<sinistra>}{<destra>}` — #1 testo a sinistra (nome gruppo o vuoto),
  #2 etichetta a destra. Niente più seconda riga «Pag. N di TOT».

- [ ] **Passo 1:** riscrivere `\pageheader` con #1 = testo a sinistra al posto di
  `((( gruppo_nome )))` cablato, #2 = etichetta a destra su una riga sola (via lo `\shortstack`).
  Aggiornare il commento sopra la macro.
- [ ] **Passo 2:** pagine timbri (riga 158):
  `\pageheader{((( gruppo_nome )))}{Tappe ((( pagina.ref_da )))--((( pagina.ref_a )))}`.
- [ ] **Passo 3:** pagine Note: `\pageheader{}{Note}`; togliere il `set pagina_num` ormai inutile.
- [ ] **Passo 4:** togliere `pagine_numerate` dal contesto (`genera_passaporto.py:369`) e
  verificare che nessuno la usi: `grep -rn pagine_numerate templates/ *.py` → nessun risultato.
- [ ] **Passo 5:** `python genera_passaporto.py "Isole"` e controllare il testo:
  `pdftotext -f 2 -l 8 -layout output/1_isole/1_passaporto_isole_A6.pdf - | grep -c "Pag\."` → `0`;
  pagina 8 contiene «Note» e non «Isole». A pagina 2 c'è ancora «Isole» a sinistra.
- [ ] **Passo 6 (istruzione per il dev):**
  `git commit -m "feat(oc:8720): remove page numbers and group name from Note pages header"`

### Task 2: sequenza delle pagine del libretto (funzione pura, con test)

**File:**
- Modifica: `genera_passaporto.py` (nuova sezione «5. Libretto unico A6» prima di «Entry point»)
- Crea: `tests/test_libretto.py`
- Modifica: `requirements.txt` (aggiungere `pytest`)

**Interfacce:**
- Produce: `piano_libretto(gruppi: list[tuple[str, int, int]]) -> list[tuple[int, int, str]]`
  - input: per ogni gruppo in ordine `(nome, pagine_timbri, pagine_note_nell_A6)`;
  - output: una voce per pagina del libretto, `(indice_gruppo, indice_pagina_nell_A6, tipo)`,
    con `tipo` in `{"copertina", "timbri", "note"}`.
- Regola (dall'overview): per ogni gruppo copertina (pag. 0) + timbri (pag. 1..n); se `1 + n` è
  dispari aggiunge la prima Note del suo A6 (pag. `1 + n`). Poi, se l'ultima pagina non è una
  Note, aggiunge una Note; poi Note fino al multiplo di 4. Le Note aggiunte in fondo sono la
  prima pagina Note disponibile di qualunque gruppo; se non ce n'è nessuna → `ValueError`.

- [ ] **Passo 1: scrivere i test**

```python
from genera_passaporto import piano_libretto

ATTUALI = [("Isole", 6, 1), ("Calabria", 3, 0), ("Sud", 7, 0), ("Centro", 5, 2),
           ("Centro Nord", 6, 1), ("Piemonte", 7, 0), ("Valle d'Aosta", 2, 1),
           ("Lombardia", 5, 2), ("Nord Est", 6, 1)]

def test_piano_dati_attuali():
    piano = piano_libretto(ATTUALI)
    assert len(piano) == 60
    note = [i + 1 for i, (_, _, t) in enumerate(piano) if t == "note"]
    assert note == [8, 34, 46, 60]
    copertine = [i + 1 for i, (_, _, t) in enumerate(piano) if t == "copertina"]
    assert copertine == [1, 9, 13, 21, 27, 35, 43, 47, 53]

def test_piano_ultimo_gruppo_pari():
    piano = piano_libretto([("A", 6, 1), ("B", 5, 2)])   # 7+1, poi 6 → serve Note finale
    assert [t for _, _, t in piano][-1] == "note"
    assert len(piano) % 4 == 0 and len(piano) == 16

def test_piano_senza_note_disponibili():
    import pytest
    with pytest.raises(ValueError):
        piano_libretto([("A", 3, 0), ("B", 7, 0)])
```

- [ ] **Passo 2:** `python -m pytest tests/test_libretto.py -v` → FAIL (`ImportError`).
- [ ] **Passo 3:** implementare `piano_libretto` in `genera_passaporto.py`.
- [ ] **Passo 4:** `python -m pytest tests/test_libretto.py -v` → 3 passed.
- [ ] **Passo 5 (istruzione per il dev):**
  `git commit -m "feat(oc:8720): add booklet page plan with Note page rule"`

### Task 3: composizione, versione con margini, controllo e aggancio a `--all`

**File:**
- Modifica: `genera_passaporto.py` (sezione «5. Libretto unico A6», `main()` alle righe 767-796,
  docstring in testa e help di `--all`: «8 passaporti» → «9 passaporti»)

**Interfacce:**
- Consuma: `piano_libretto` (Task 2); da `genera_passaporto()` il dict `info` con `pdf_a6`,
  `pagine_timbri`, `pagine_note`.
- Produce:
  - `LIBRETTO_A6 = OUTPUT_DIR / "libretto_A6.pdf"`,
    `LIBRETTO_A6_MARGINI = OUTPUT_DIR / "libretto_A6_margini.pdf"`;
  - `componi_libretto(infos: list[dict], output_pdf: Path) -> list[tuple[str, int, int]]` —
    scrive il PDF e restituisce la mappa `(gruppo, prima_pagina, ultima_pagina)`, 1-based;
  - `riduci_con_margini(a6_pdf: Path, output_pdf: Path, margine_mm: float) -> None` — ogni pagina
    scalata e centrata su un A6 bianco, stessa formula di `scala` in `imponi_su_a5`;
  - `verifica_libretto(pdf: Path, attesi: list[str]) -> None` — rilegge il PDF scritto, classifica
    ogni pagina dal testo (`"PASSAPORTO"` → copertina, `"Tappe "` → timbri, altrimenti `"Note"`
    → note) e solleva `SystemExit` se: pagine non multiplo di 4, una copertina su pagina pari
    (1-based), ultima pagina non Note, o classificazione ≠ `attesi` (i tipi di `piano_libretto`);
  - `rimuovi_libretto(output_dir: Path = OUTPUT_DIR) -> bool` — cancella i due PDF del libretto e
    le copie in `stampa/` e `stampa_margini/`; `True` se ne ha cancellato almeno uno.

- [ ] **Passo 1:** implementare le quattro funzioni. La verifica legge il PDF dal disco, non la
  lista usata per scriverlo: è questo che la rende un controllo e non una ripetizione del calcolo.
- [ ] **Passo 2:** in `main()`: `rimuovi_libretto()` sempre, prima di generare. Con `--all`:
  raccogliere gli `info` restituiti da `genera_passaporto()`, poi — solo dopo il ciclo —
  `componi_libretto` → `verifica_libretto` → `riduci_con_margini` → `pubblica_pdf_stampa` dei due
  file nelle rispettive cartelle, e stampare la mappa (`Isole 1-8, Calabria 9-12, …`). Senza
  `--all`, se `rimuovi_libretto()` ha cancellato qualcosa, stampare
  `⚠ libretto rimosso perché non più allineato: rigeneralo con --all`.
- [ ] **Passo 3:** `python genera_passaporto.py --all` → termina senza errori; stampa
  `Isole 1-8, Calabria 9-12, Sud 13-20, Centro 21-26, Centro Nord 27-34, Piemonte 35-42,
  Valle d'Aosta 43-46, Lombardia 47-52, Nord Est 53-60`; `pdfinfo output/libretto_A6.pdf` →
  `Pages: 60`, `Page size: 297.64 x 419.53 pts`; esistono `output/stampa/libretto_A6.pdf` e
  `output/stampa_margini/libretto_A6_margini.pdf`; i 9 pieghevoli ci sono ancora in
  `output/stampa/`.
- [ ] **Passo 4:** `python genera_passaporto.py "Nord Est"` → stampa l'avviso; i due libretti e le
  copie non esistono più. Rilanciare `--all` per ripristinarli.
- [ ] **Passo 5 (confronto una tantum, non versionato):** script nello scratchpad che, per ogni
  pagina di `output/libretto_A6.pdf` e di `/Volumes/Crucial X6/CAI/SICAI/Passaporto/Revisione_enrico/Pagine_A6.pdf`,
  estrae con `pdftotext` tipo di pagina, nome del gruppo in copertina e intervallo «Tappe X–Y»,
  ignorando le scritte «Pag.». Atteso: 60 righe identiche. Ogni differenza va in `notes.md`.
- [ ] **Passo 6:** aprire `output/libretto_A6_margini.pdf` e controllare a vista una copertina e
  una pagina timbri: contenuto ridotto e centrato, bordo bianco di 5 mm.
- [ ] **Passo 7 (istruzione per il dev):**
  `git commit -m "feat(oc:8720): generate single A6 booklet with --all"`

### Task 4: README

**File:**
- Modifica: `README.md` (comandi, sezione output e cartelle di stampa, nuova sezione «Libretto
  unico A6», intestazioni senza numero di pagina; tabella dei test con `python -m pytest`)

- [ ] **Passo 1:** documentare: cosa produce `--all` in più, i due file e dove vengono copiati,
  la regola delle pagine Note, il fatto che una generazione parziale cancella il libretto.
- [ ] **Passo 2:** verificare che i nomi file e gli intervalli di pagina citati coincidano con
  l'output del Task 3, passo 3.
- [ ] **Passo 3 (istruzione per il dev):**
  `git commit -m "docs(oc:8720): document single A6 booklet"`
