> Ticket: oc:8720

# Passaporto SICAI: libretto unico A6 per la stampa

## Cosa cambia

Oggi il generatore produce 9 passaporti separati, ciascuno imposto su un foglio A4 piegato a croce
o su un A5 con una piega sola (Calabria e Valle d'Aosta). Con questo lavoro `--all` produce, **in
aggiunta** ai 9 pieghevoli, un unico libretto A6 da spillare al centro: `output/libretto_A6.pdf`,
una facciata A6 per pagina, senza imposizione. Il riferimento è l'esempio di Enrico
(`Pagine_A6.pdf`, 60 facciate), che è il nostro output del 18 giugno rimontato a mano.

Su tutti gli output, pieghevoli compresi, spariscono la scritta «Pag. N di TOT» e il nome del
gruppo nell'intestazione delle pagine Note.

## Perché

Nella call del 2026-10-06 Eleonora Berti ha chiesto di passare dai pieghevoli a «un librettino in
formato A6, spillabile in mezzo», di circa 60 facciate, da dare alla copisteria «non montati su
A4, proprio ogni singola facciata». Ha chiesto anche di togliere il numero di pagina, perché le
tappe si seguono regione per regione, e di mettere le righe per gli appunti nelle pagine rimaste
bianche e in un'ultima pagina. Rigenerare il libretto dal codice, invece di ritoccare il PDF di
Enrico, lo tiene allineato all'Excel.

La regola di riferimento per ogni scelta di impaginazione è: seguire l'esempio di Enrico e la
trascrizione della call.

## Requisiti

- [ ] `python genera_passaporto.py --all` produce i 9 pieghevoli (A6, stampa, stampa con margini)
      come oggi e in più `output/libretto_A6.pdf`, copiato anche in `output/stampa/`. Con un solo
      gruppo (`python genera_passaporto.py "Nord Est"`) il libretto non viene prodotto.
- [ ] Il libretto non resta mai disallineato dai pieghevoli: `--all` cancella il libretto
      precedente all'inizio e scrive quello nuovo solo dopo che tutti i 9 gruppi sono andati a buon
      fine; una generazione senza `--all` cancella `output/libretto_A6.pdf`, la versione con
      margini e le loro copie in `output/stampa/` e `output/stampa_margini/`, e avvisa di
      rigenerarlo con `--all`.
- [ ] Oltre alla versione al vivo, `output/libretto_A6_margini.pdf`: ogni facciata ridotta per
      lasciare `MARGINE_STAMPA_MM` (5 mm) di bianco su ogni lato, come `_stampa_margini` dei
      pieghevoli, copiata in `output/stampa_margini/`. La copisteria sceglie quale usare.
- [ ] Il libretto contiene i 9 gruppi nell'ordine del foglio «Riepilogo per Gruppo», ciascuno con
      la sua copertina e le sue pagine timbri.
- [ ] Pagine Note nel libretto: un gruppo con un numero dispari di pagine (copertina + timbri)
      riceve in coda una pagina Note, così ogni copertina cade su una pagina dispari (a destra).
      L'ultima pagina del libretto è sempre una pagina Note; se serve si aggiungono pagine Note in
      fondo fino al multiplo di 4. Con l'Excel attuale il risultato coincide con l'esempio di
      Enrico: Note a pagina 8, 34, 46 e 60, totale 60 facciate.
- [ ] La versione principale del libretto è A6 al vivo (105×148 mm), come l'esempio di Enrico.
- [ ] Togliere «Pag. N di TOT» dall'intestazione delle pagine timbri e delle pagine Note, in tutti
      gli output.
- [ ] Intestazione delle pagine Note con «Note» e senza il nome del gruppo, in tutti gli output.
      Le pagine timbri mantengono il nome del gruppo, come nell'esempio.
- [ ] Controllo a fine generazione del libretto: pagine multiplo di 4, ogni copertina su pagina
      dispari, ultima pagina Note. Se un controllo fallisce lo script si ferma con errore. Lo
      script stampa la mappa «gruppo → pagine» (es. `Isole 1-8, Calabria 9-12, …`).
- [ ] Confronto una tantum, pagina per pagina, del testo del libretto generato con
      `Pagine_A6.pdf`: stesse copertine, stessi intervalli di tappe, Note nelle stesse posizioni.
- [ ] README aggiornato con il libretto, il suo file e la regola delle pagine Note.

## Rischi

- Sui PDF non ci sono test automatici. Il controllo a fine generazione e il confronto con
  l'esempio di Enrico coprono numero e posizione delle pagine, non l'aspetto grafico.
- Libretto vecchio mandato in stampa dopo una rigenerazione parziale (es. corretta una tappa del
  Nord Est e rigenerato solo quel gruppo): mitigato cancellando il libretto a ogni generazione
  senza `--all`.
- Griglia timbri e intestazione arrivano al bordo della pagina A6: con una stampante che non
  stampa al bordo, o con il rifilo dopo la spillatura, si perde il bordo delle celle esterne.
  Mitigato con la versione con margini, a scelta della copisteria.
- Le modifiche al template cambiano anche i 9 pieghevoli: è voluto, ma chi rigenera i pieghevoli
  trova le intestazioni diverse da quelle di giugno.

## Out of scope

- Split del libretto in un PDF per facciata: da fare solo se la copisteria lo chiede (la call
  accetta anche «un unico file»). Domanda da girare a Eleonora con l'invio del libretto.
- ~~Raccoglitore come «copertina rigida» del libretto~~: riportato nello scope il 2026-10-07 come
  ipotesi di lavoro (vedi notes.md, «Decisioni»).
- Versione del libretto con abbondanza o crocini di taglio: l'esempio di Enrico è al vivo, e la
  versione con margini copre la stampa senza bordo. Quale delle due usare è una domanda da girare
  alla copisteria.

## Moduli toccati

Tutto nel repo `passport` (nessun submodule).

- `genera_passaporto.py`: composizione del libretto a partire dagli A6 dei 9 gruppi, regola delle
  pagine Note, versione con margini, controllo finale, aggancio a `--all`, cancellazione del
  libretto nelle generazioni parziali; aggiornamento del docstring che dice ancora
  «8 passaporti».
- `templates/passaporto.tex.j2`: intestazione delle pagine timbri senza numero di pagina,
  intestazione delle pagine Note senza numero e senza nome del gruppo.
- `README.md`.
