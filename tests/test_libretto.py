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
