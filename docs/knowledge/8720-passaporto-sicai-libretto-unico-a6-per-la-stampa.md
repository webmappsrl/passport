# Libretto unico A6 del passaporto SICAI

## Come funziona oggi

Meccanismo, file prodotti e regola delle pagine Note sono nel README, sezione
[Libretto unico A6](../../README.md#libretto-unico-a6). Vale in più: togliere il numero di pagina
e il nome del gruppo dalle Note ha cambiato anche le intestazioni dei 9 pieghevoli rispetto alla
versione di giugno 2026.

## Perché così

- **Regola invece di posizioni fisse per le Note** (oc:8720): l'esempio di Enrico
  (`Pagine_A6.pdf`) mette le Note in coda ai gruppi con pagine dispari. La regola lo riproduce
  con l'Excel attuale e tiene ogni copertina su pagina dispari (a destra) anche quando l'Excel
  cambia; copiare le posizioni dell'esempio no.
- **Composizione dagli A6 già prodotti** (oc:8720): pieghevoli e libretto escono dalla stessa
  run e dagli stessi dati, senza una seconda compilazione XeLaTeX (un `--all` misurato a ottobre
  2026 dura circa 1 minuto).
- **Libretto cancellato a ogni generazione** (oc:8720): rigenerando un solo gruppo il libretto
  resterebbe con i dati vecchi e potrebbe finire in copisteria.
- **Controllo sul PDF scritto** (oc:8720): la verifica rilegge il file e classifica le pagine dal
  testo, così non ripete il calcolo che l'ha prodotto.
- **Il raccoglitore è la copertina** (oc:8720, ipotesi di lavoro da confermare): avvolge le 60
  facciate interne, 64 in tutto; per questo `--all` lo rigenera insieme al libretto.
- **Niente numero di pagina** (oc:8720): richiesto da Eleonora Berti nella call del 2026-10-06,
  perché le tappe si seguono regione per regione.

## Come ci siamo arrivati

- **Pieghevoli separati come unico prodotto di stampa** (giugno 2026, superato da oc:8720): il
  cliente ha chiesto un solo librettino A6 spillato; `Pagine_A6.pdf` è l'output del 18 giugno
  rimontato a mano da Enrico il 5 ottobre. I pieghevoli restano prodotti.
