"""Varianti PDF/X-4 per la tipografia: CMYK convertito e RGB dichiarato sRGB."""

import shutil

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, DecodedStreamObject, NameObject, NumberObject

from esporta_colore import converti_cmyk, converti_rgb, verifica_pdfx4
from genera_passaporto import A6_W, A6_H, ABB, imponi_su_a4, imposta_box_a6


@pytest.fixture
def foglio(tmp_path):
    """Foglio A4 per la tipografia da 8 facciate A6 con un riempimento RGB rosso."""
    a6 = tmp_path / "a6.pdf"
    writer = PdfWriter()
    for _ in range(8):
        pagina = writer.add_blank_page(width=A6_W + 2 * ABB, height=A6_H + 2 * ABB)
        contenuto = DecodedStreamObject()
        contenuto.set_data(b"1 0 0 rg 20 20 100 100 re f 0 0 0 1 k 150 150 50 50 re f")
        pagina.replace_contents(ContentStream(contenuto, None))
    with open(a6, "wb") as f:
        writer.write(f)
    imposta_box_a6(a6)
    out = tmp_path / "foglio_stampa_margini.pdf"
    imponi_su_a4(a6, out, segni_taglio=True)
    return out


def test_sorgente_non_conforme(foglio):
    errori = verifica_pdfx4(foglio, cmyk=False)
    assert any("OutputIntent" in e for e in errori)
    assert any("DefaultRGB" in e for e in errori)


def test_segni_senza_font(foglio):
    # i segni di taglio non devono portare font non incorporati (vietati in PDF/X)
    for pagina in PdfReader(str(foglio)).pages:
        assert "/Font" not in pagina["/Resources"]


def test_rgb_pdfx4(foglio, tmp_path):
    out = converti_rgb(foglio, tmp_path / "rgb.pdf", "prova")
    assert verifica_pdfx4(out, cmyk=False) == []
    reader = PdfReader(str(out))
    intent = reader.trailer["/Root"]["/OutputIntents"][0].get_object()
    assert intent["/OutputConditionIdentifier"] == "FOGRA39"
    assert intent["/DestOutputProfile"].get_object()["/N"] == 4
    for pagina in reader.pages:
        spazi = pagina["/Resources"]["/ColorSpace"]
        assert spazi["/DefaultRGB"][0] == "/ICCBased"
    # il colore non cambia: stessi box del sorgente
    sorgente = PdfReader(str(foglio)).pages[0]
    assert reader.pages[0].trimbox == sorgente.trimbox
    assert reader.pages[0].bleedbox == sorgente.bleedbox


def test_rgb_ruotato_non_conforme(foglio, tmp_path):
    out = converti_rgb(foglio, tmp_path / "rgb.pdf", "prova")
    writer = PdfWriter(clone_from=PdfReader(str(out)))
    writer.pages[0][NameObject("/Rotate")] = NumberObject(180)
    ruotato = tmp_path / "ruotato.pdf"
    with open(ruotato, "wb") as f:
        writer.write(f)
    assert any("ruotata" in e for e in verifica_pdfx4(ruotato, cmyk=False))


@pytest.mark.skipif(shutil.which("gs") is None, reason="Ghostscript non installato")
def test_cmyk_pdfx4(foglio, tmp_path):
    out = converti_cmyk(foglio, tmp_path / "cmyk.pdf", "prova")
    assert verifica_pdfx4(out, cmyk=True) == []
    reader = PdfReader(str(out))
    sorgente = PdfReader(str(foglio)).pages[0]
    # Ghostscript arrotonda i box a 4 decimali di punto
    assert list(reader.pages[0].trimbox) == pytest.approx(list(sorgente.trimbox), abs=1e-3)
    assert list(reader.pages[0].bleedbox) == pytest.approx(list(sorgente.bleedbox), abs=1e-3)
    operazioni = [
        (op, [float(x) for x in args])
        for p in reader.pages
        for args, op in ContentStream(p.get_contents(), reader).operations
        if op in (b"k", b"rg")
    ]
    assert not any(op == b"rg" for op, _ in operazioni)
    # il nero CMYK puro resta tale: niente riconversione del colore già CMYK
    assert (b"k", [0.0, 0.0, 0.0, 1.0]) in operazioni
