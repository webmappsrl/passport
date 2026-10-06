> Ticket: oc:8720

# Notes — Libretto unico A6 per la stampa

## Deviazioni dal piano

Nessuna deviazione dai task. Un'aggiunta: `genera_libretto()` in `genera_passaporto.py` mette in
fila composizione, controllo, versione con margini, pubblicazione e stampa della mappa, così
`main()` resta una chiamata sola.

## Bug trovati

- `pytest` non era installato nel `.venv` del repo: aggiunto a `requirements.txt`.

## Decisioni

- Regola guida per ogni scelta di impaginazione, indicata dal dev: seguire l'esempio di Enrico
  (`Pagine_A6.pdf`) e la trascrizione Plaud della call del 2026-10-06.
- «Pag. N di TOT» e il nome del gruppo nelle pagine Note sono tolti da **tutti** gli output,
  pieghevoli compresi (decisione del dev).
- Pagine Note del libretto calcolate da una regola (gruppo con pagine dispari → una Note in coda;
  ultima pagina Note; multiplo di 4), non da una lista fissa: con l'Excel attuale coincide con
  l'esempio di Enrico.
- Il libretto si genera solo con `--all`; ogni generazione lo cancella all'inizio, così non può
  restare un libretto disallineato dopo una rigenerazione parziale (emerso dalla challenge).
- Aggiunta la versione `libretto_A6_margini.pdf` (5 mm), come per i pieghevoli (emerso dalla
  challenge).
- Il controllo finale rilegge il PDF scritto e classifica le pagine dal testo («PASSAPORTO»,
  «Tappe », «Note»), invece di ricontrollare la lista usata per scriverlo.
- Esito del confronto una tantum con `Pagine_A6.pdf`: 60 pagine su 60 uguali per tipo di pagina,
  statistiche di copertina e intervallo di tappe (ignorate le scritte «Pag.» dell'esempio).
- Tag Orchestrator: il dev ha chiesto di non proporne né associarne.

## Follow-up

Domande da girare a Eleonora Berti / Enrico insieme al libretto:
- la copisteria vuole un PDF per facciata invece del file unico?
- la «copertina rigida» è il raccoglitore? In quel caso il totale diventa 64 facciate;
- la copisteria stampa la versione al vivo o quella con margini?

Fuori da questo ticket: `reset_cartelle_stampa` con `--all` svuota anche i PDF del raccoglitore
in `output/stampa/`, che vanno rigenerati con `genera_raccoglitore.py` (comportamento preesistente,
già indicato nel README).
