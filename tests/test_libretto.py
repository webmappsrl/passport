"""Sequenza delle pagine del libretto unico A6 (oc:8720)."""

import pytest

from genera_passaporto import piano_libretto

# (gruppo, pagine timbri, pagine Note nell'A6 del gruppo) con l'Excel di ottobre 2026
ATTUALI = [("Isole", 6, 1), ("Calabria", 3, 0), ("Sud", 7, 0), ("Centro", 5, 2),
           ("Centro Nord", 6, 1), ("Piemonte", 7, 0), ("Valle d'Aosta", 2, 1),
           ("Lombardia", 5, 2), ("Nord Est", 6, 1)]


def _pagine(piano, tipo):
    return [i + 1 for i, (_, _, t) in enumerate(piano) if t == tipo]


def test_piano_dati_attuali():
    # stessa struttura dell'esempio di Enrico (Pagine_A6.pdf)
    piano = piano_libretto(ATTUALI)
    assert len(piano) == 60
    assert _pagine(piano, "note") == [8, 34, 46, 60]
    assert _pagine(piano, "copertina") == [1, 9, 13, 21, 27, 35, 43, 47, 53]


def test_piano_ultimo_gruppo_pari():
    # A: 7 pagine + 1 Note; B: 6 pagine → serve una Note finale, poi multiplo di 4
    piano = piano_libretto([("A", 6, 1), ("B", 5, 2)])
    assert piano[-1][2] == "note"
    assert len(piano) == 16


def test_piano_senza_note_disponibili():
    with pytest.raises(ValueError):
        piano_libretto([("A", 3, 0), ("B", 7, 0)])


def test_cartelle_libretto(tmp_path):
    from genera_passaporto import (LIBRETTO_KIT, componi_cartelle_libretto,
                                   nomi_cartella_libretto)
    for sorgente, *pdf in LIBRETTO_KIT.values():
        (tmp_path / sorgente).mkdir(exist_ok=True)
        for f in pdf:
            # contenuto distinto per file: verifica che ogni copia venga dalla sorgente giusta
            (tmp_path / sorgente / f).write_bytes(f"{sorgente}/{f}".encode())
    # un file vecchio nella cartella non deve sopravvivere alla ricomposizione
    vecchio = tmp_path / "libretto_A6" / "libretto_A6_stampa" / "vecchio.pdf"
    vecchio.parent.mkdir(parents=True)
    vecchio.write_bytes(b"%PDF")

    cartelle = componi_cartelle_libretto(tmp_path)
    assert [c.name for c in cartelle] == list(LIBRETTO_KIT)
    for c in cartelle:
        sorgente, *pdf = LIBRETTO_KIT[c.name]
        nomi = nomi_cartella_libretto(c.name)
        assert sorted(f.name for f in c.iterdir()) == sorted(nomi)
        for f, dest in zip(pdf, nomi):
            assert (c / dest).read_bytes() == f"{sorgente}/{f}".encode()


def test_nomi_cartella_cmyk():
    from genera_passaporto import LIBRETTO_KIT, nomi_cartella_libretto
    assert LIBRETTO_KIT["libretto_A6_stampa_margini"][0] == "stampa_cmyk"
    assert nomi_cartella_libretto("libretto_A6_stampa_margini") == (
        "libretto_A6_stampa_margini.pdf", "raccoglitore_A6_stampa_margini.pdf",
        "raccoglitore_A5_stampa_margini.pdf")


def test_cartelle_libretto_senza_libretto(tmp_path):
    from genera_passaporto import componi_cartelle_libretto
    (tmp_path / "libretto_A6" / "libretto_A6_stampa").mkdir(parents=True)
    assert componi_cartelle_libretto(tmp_path) == []
    assert not (tmp_path / "libretto_A6").exists()
