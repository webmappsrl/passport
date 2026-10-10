"""Box di stampa delle versioni per la tipografia: abbondanze e segni di taglio."""

import pytest
from pypdf import PdfReader
from reportlab.pdfgen import canvas as rl_canvas

from genera_passaporto import (
    A4_W, A4_H, A6_W, A6_H, ABB, MM, SEGNI,
    imponi_su_a4, imponi_su_a6, imposta_box_a6,
)


@pytest.fixture
def a6(tmp_path):
    """8 pagine A6 con abbondanze, come le produce compila_xelatex."""
    pdf = tmp_path / "a6.pdf"
    c = rl_canvas.Canvas(str(pdf), pagesize=(A6_W + 2 * ABB, A6_H + 2 * ABB))
    for _ in range(8):
        c.showPage()
    c.save()
    imposta_box_a6(pdf)
    return pdf


def _mm(box):
    return [round(float(v) / MM, 1) for v in box]


def test_a6_rifilato_a_video(a6):
    pagina = PdfReader(str(a6)).pages[0]
    assert _mm(pagina.mediabox) == [0, 0, 111, 154]
    assert _mm(pagina.cropbox) == _mm(pagina.trimbox) == [3, 3, 108, 151]


def test_a4_al_vivo(a6, tmp_path):
    out = tmp_path / "vivo.pdf"
    imponi_su_a4(a6, out)
    pagina = PdfReader(str(out)).pages[0]
    assert _mm(pagina.mediabox) == _mm([0, 0, A4_W, A4_H])


def test_a4_per_tipografia(a6, tmp_path):
    out = tmp_path / "tipografia.pdf"
    imponi_su_a4(a6, out, segni_taglio=True)
    pagine = PdfReader(str(out)).pages
    assert len(pagine) == 2  # fronte e retro
    s = SEGNI / MM
    for pagina in pagine:
        assert _mm(pagina.trimbox) == [s, s, s + 210, s + 297]
        assert _mm(pagina.bleedbox) == [s - 3, s - 3, s + 213, s + 300]
        assert _mm(pagina.mediabox) == [0, 0, 210 + 2 * s, 297 + 2 * s]


def test_libretto_per_tipografia(a6, tmp_path):
    out = tmp_path / "libretto.pdf"
    imponi_su_a6(a6, out, segni_taglio=True)
    pagine = PdfReader(str(out)).pages
    assert len(pagine) == 8  # una facciata per pagina
    s = SEGNI / MM
    assert _mm(pagine[0].trimbox) == [s, s, s + 105, s + 148]
    assert _mm(pagine[0].bleedbox) == [s - 3, s - 3, s + 108, s + 151]
