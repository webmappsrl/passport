#!/usr/bin/env python3
"""
Varianti colore dei PDF per la tipografia (PDF/X-4, condizione di stampa FOGRA39).

Partono dai PDF con abbondanze e segni di taglio (`*_stampa_margini.pdf`,
`libretto_A6_margini.pdf`) e producono due versioni, da scegliere in base a
cosa chiede la copisteria:

- CMYK (`output/stampa_cmyk/*_cmyk.pdf`): Ghostscript converte tutto il
  colore RGB (foto, mappe, loghi, azzurro) in CMYK con il profilo FOGRA39,
  in un unico passaggio sul PDF finale. Il colore già CMYK (blu CAI 100/72/0/19,
  grigi in solo nero, segni di registro) resta invariato.
- RGB (`output/stampa_rgb/*_rgb.pdf`): il colore non viene toccato, l'RGB
  viene dichiarato sRGB (profilo sRGB2014 associato) e la conversione in
  CMYK la fa la tipografia, verso FOGRA39 indicato come OutputIntent.

Entrambe sono rese PDF/X-4 (OutputIntent FOGRA39 incorporato, metadati XMP,
Trapped) e verificate con `verifica_pdfx4` prima di essere pubblicate.

Richiede Ghostscript (`brew install ghostscript`).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    ByteStringObject,
    DecodedStreamObject,
    DictionaryObject,
    IndirectObject,
    NameObject,
    NumberObject,
    StreamObject,
    TextStringObject,
)

ICC_DIR = Path(__file__).resolve().parent / "assets" / "icc"
ICC_FOGRA39 = ICC_DIR / "Coated_Fogra39L_VIGC_300.icc"  # registro ICC, caratterizzazione FOGRA39
ICC_SRGB = ICC_DIR / "sRGB2014.icc"                      # registro ICC, sRGB v2

OUTPUT_CONDITION_ID = "FOGRA39"
OUTPUT_CONDITION = "Coated FOGRA39 (ISO 12647-2:2004)"
PDF_HEADER = b"%PDF-1.6"  # PDF/X-4 si basa su PDF 1.6

_RGB = NameObject("/DeviceRGB")


# ----------------------------------------------------------------------
# Conversioni
# ----------------------------------------------------------------------

def _gs() -> str:
    gs = shutil.which("gs")
    if gs is None:
        raise SystemExit(
            "Ghostscript non trovato: serve per la versione CMYK "
            "(macOS: brew install ghostscript)."
        )
    return gs


def converti_cmyk(src: Path, dest: Path, titolo: str) -> Path:
    """PDF/X-4 CMYK FOGRA39: conversione Ghostscript + finalizzazione PDF/X-4."""
    with tempfile.TemporaryDirectory() as tmp:
        convertito = Path(tmp) / "cmyk.pdf"
        risultato = subprocess.run(
            [
                _gs(), "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER",
                f"--permit-file-read={ICC_FOGRA39}",
                "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.6",
                # mai ruotare le pagine: i fogli imposti hanno metà facciate
                # capovolte e l'auto-rotazione girerebbe il fronte di 180°
                "-dAutoRotatePages=/None",
                "-sColorConversionStrategy=CMYK",
                f"-sOutputICCProfile={ICC_FOGRA39}",
                # colorimetrico relativo + compensazione del punto nero
                "-dRenderIntent=1", "-dBlackPtComp=1",
                # niente ricampionamento; JPEG ad alta qualità per le immagini convertite
                "-dDownsampleColorImages=false", "-dDownsampleGrayImages=false",
                "-dDownsampleMonoImages=false",
                "-dAutoFilterColorImages=false", "-dColorImageFilter=/DCTEncode",
                "-dJPEGQ=95",
                f"-sOutputFile={convertito}", str(src),
            ],
            capture_output=True, text=True,
        )
        if risultato.returncode != 0 or not convertito.exists():
            raise RuntimeError(
                f"Conversione CMYK di {src.name} fallita:\n"
                f"{risultato.stderr[-2000:] or risultato.stdout[-2000:]}"
            )
        _finalizza_pdfx4(convertito, dest, titolo, dichiara_srgb=False)
    errori = verifica_pdfx4(dest, cmyk=True)
    if errori:
        raise SystemExit(f"{dest.name} non è un PDF/X-4 valido:\n  - " + "\n  - ".join(errori))
    return dest


def converti_rgb(src: Path, dest: Path, titolo: str) -> Path:
    """PDF/X-4 con RGB dichiarato sRGB: il colore non cambia, converte la tipografia."""
    _finalizza_pdfx4(src, dest, titolo, dichiara_srgb=True)
    errori = verifica_pdfx4(dest, cmyk=False)
    if errori:
        raise SystemExit(f"{dest.name} non è un PDF/X-4 valido:\n  - " + "\n  - ".join(errori))
    return dest


# ----------------------------------------------------------------------
# Finalizzazione PDF/X-4
# ----------------------------------------------------------------------

def _stream_icc(writer: PdfWriter, profilo: Path, componenti: int) -> IndirectObject:
    stream = DecodedStreamObject()
    stream.set_data(profilo.read_bytes())
    stream[NameObject("/N")] = NumberObject(componenti)
    return writer._add_object(stream.flate_encode())


def _dichiara_srgb(writer: PdfWriter, srgb: IndirectObject) -> None:
    """Associa sRGB a tutto l'RGB del documento.

    - ogni dizionario /Resources riceve /ColorSpace /DefaultRGB = sRGB, che
      rimappa anche i colori impostati con gli operatori rg/RG;
    - immagini, gruppi di trasparenza, shading e spazi Indexed/Separation/
      DeviceN con base DeviceRGB puntano direttamente al profilo sRGB.
    """
    icc = ArrayObject([NameObject("/ICCBased"), srgb])
    icc_ref = writer._add_object(icc)
    visitati: set[int] = set()

    def sostituisci_cs(valore):
        if valore == _RGB:
            return icc_ref
        if isinstance(valore, ArrayObject) and valore:
            if valore[0] == "/Indexed" and len(valore) > 1 and valore[1] == _RGB:
                valore[1] = icc_ref
            elif valore[0] in ("/Separation", "/DeviceN") and len(valore) > 2 and valore[2] == _RGB:
                valore[2] = icc_ref
        return valore

    def visita(obj):
        if isinstance(obj, IndirectObject):
            if obj.idnum in visitati:
                return
            visitati.add(obj.idnum)
            obj = obj.get_object()
        if isinstance(obj, (DictionaryObject, StreamObject)):
            for chiave in list(obj.keys()):
                valore = obj[chiave]
                risolto = valore.get_object() if isinstance(valore, IndirectObject) else valore
                if chiave in ("/ColorSpace", "/CS"):
                    if isinstance(risolto, DictionaryObject) and chiave == "/ColorSpace" and not isinstance(obj.get("/Subtype"), NameObject):
                        # dizionario di spazi colore nominati di una /Resources
                        for nome in list(risolto.keys()):
                            sotto = risolto[nome]
                            sotto_r = sotto.get_object() if isinstance(sotto, IndirectObject) else sotto
                            nuovo = sostituisci_cs(sotto_r)
                            if nuovo is icc_ref:
                                risolto[nome] = icc_ref
                    else:
                        nuovo = sostituisci_cs(risolto)
                        if nuovo is icc_ref:
                            obj[NameObject(chiave)] = icc_ref
                if chiave == "/Resources" and isinstance(risolto, DictionaryObject):
                    spazi = risolto.get("/ColorSpace")
                    if spazi is None:
                        spazi = DictionaryObject()
                        risolto[NameObject("/ColorSpace")] = spazi
                    spazi = spazi.get_object()
                    spazi[NameObject("/DefaultRGB")] = icc_ref
                visita(valore)
        elif isinstance(obj, ArrayObject):
            for elemento in obj:
                visita(elemento)

    for pagina in writer.pages:
        visita(pagina.indirect_reference)


def _xmp(titolo: str, adesso: datetime, producer: str) -> bytes:
    data = adesso.isoformat(timespec="seconds")
    doc_id, inst_id = uuid.uuid4(), uuid.uuid4()
    titolo_xml = (titolo.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return f"""<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:pdf="http://ns.adobe.com/pdf/1.3/"
    xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/"
    xmlns:pdfxid="http://www.npes.org/pdfx/ns/id/">
   <dc:format>application/pdf</dc:format>
   <dc:title><rdf:Alt><rdf:li xml:lang="x-default">{titolo_xml}</rdf:li></rdf:Alt></dc:title>
   <xmp:CreateDate>{data}</xmp:CreateDate>
   <xmp:ModifyDate>{data}</xmp:ModifyDate>
   <xmp:MetadataDate>{data}</xmp:MetadataDate>
   <xmp:CreatorTool>genera_passaporto.py</xmp:CreatorTool>
   <pdf:Producer>{producer}</pdf:Producer>
   <pdf:Trapped>False</pdf:Trapped>
   <pdfxid:GTS_PDFXVersion>PDF/X-4</pdfxid:GTS_PDFXVersion>
   <xmpMM:DocumentID>uuid:{doc_id}</xmpMM:DocumentID>
   <xmpMM:InstanceID>uuid:{inst_id}</xmpMM:InstanceID>
   <xmpMM:VersionID>1</xmpMM:VersionID>
   <xmpMM:RenditionClass>default</xmpMM:RenditionClass>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>""".encode("utf-8")


def _data_pdf(adesso: datetime) -> str:
    off = adesso.strftime("%z")  # +0200
    return adesso.strftime("D:%Y%m%d%H%M%S") + f"{off[:3]}'{off[3:]}'"


def _finalizza_pdfx4(src: Path, dest: Path, titolo: str, dichiara_srgb: bool) -> None:
    writer = PdfWriter(clone_from=PdfReader(str(src)))
    writer.pdf_header = PDF_HEADER
    # PDF/X richiede l'identificatore del file nel trailer
    identificativo = ByteStringObject(uuid.uuid4().bytes)
    writer._ID = ArrayObject([identificativo, identificativo])

    if dichiara_srgb:
        _dichiara_srgb(writer, _stream_icc(writer, ICC_SRGB, 3))

    intent = DictionaryObject({
        NameObject("/Type"): NameObject("/OutputIntent"),
        NameObject("/S"): NameObject("/GTS_PDFX"),
        NameObject("/OutputConditionIdentifier"): TextStringObject(OUTPUT_CONDITION_ID),
        NameObject("/OutputCondition"): TextStringObject(OUTPUT_CONDITION),
        NameObject("/Info"): TextStringObject(OUTPUT_CONDITION),
        NameObject("/RegistryName"): TextStringObject("http://www.color.org"),
        NameObject("/DestOutputProfile"): _stream_icc(writer, ICC_FOGRA39, 4),
    })
    writer.root_object[NameObject("/OutputIntents")] = ArrayObject([writer._add_object(intent)])

    adesso = datetime.now().astimezone().replace(microsecond=0)
    producer = "pypdf + Ghostscript" if not dichiara_srgb else "pypdf"
    info = DictionaryObject({
        NameObject("/Title"): TextStringObject(titolo),
        NameObject("/Creator"): TextStringObject("genera_passaporto.py"),
        NameObject("/Producer"): TextStringObject(producer),
        NameObject("/CreationDate"): TextStringObject(_data_pdf(adesso)),
        NameObject("/ModDate"): TextStringObject(_data_pdf(adesso)),
        NameObject("/Trapped"): NameObject("/False"),
        NameObject("/GTS_PDFXVersion"): TextStringObject("PDF/X-4"),
    })
    writer._info = writer._add_object(info)

    metadati = DecodedStreamObject()
    metadati.set_data(_xmp(titolo, adesso, producer))
    metadati[NameObject("/Type")] = NameObject("/Metadata")
    metadati[NameObject("/Subtype")] = NameObject("/XML")
    writer.root_object[NameObject("/Metadata")] = writer._add_object(metadati)

    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        writer.write(f)


# ----------------------------------------------------------------------
# Verifica (requisiti PDF/X-4 controllabili senza validatore commerciale)
# ----------------------------------------------------------------------

def _operatori_rgb(contenuto: bytes) -> bool:
    """True se il content stream imposta colori RGB (operatori rg/RG)."""
    from pypdf.generic import ContentStream
    stream = DecodedStreamObject()
    stream.set_data(contenuto)
    return any(op in (b"rg", b"RG") for _, op in ContentStream(stream, None).operations)


def verifica_pdfx4(pdf: Path, cmyk: bool) -> list[str]:
    """Rilegge il PDF scritto e restituisce le non conformità trovate.

    cmyk=True: nessun colore RGB ammesso (né DeviceRGB, né ICC a 3 componenti,
    né operatori rg/RG). cmyk=False: l'RGB è ammesso solo dichiarato sRGB
    (DefaultRGB in ogni /Resources che lo usa, nessun DeviceRGB esplicito).
    """
    errori: list[str] = []
    with open(pdf, "rb") as f:
        intestazione = f.read(8)
    if intestazione > PDF_HEADER:
        errori.append(f"versione PDF {intestazione.decode()} oltre 1.6")
    reader = PdfReader(str(pdf))
    if reader.is_encrypted:
        errori.append("PDF cifrato")
    root = reader.trailer["/Root"]
    if "/ID" not in reader.trailer:
        errori.append("manca /ID nel trailer")

    # OutputIntent
    intents = root.get("/OutputIntents")
    pdfx = [i.get_object() for i in (intents or []) if i.get_object().get("/S") == "/GTS_PDFX"]
    if len(pdfx) != 1:
        errori.append("serve esattamente un OutputIntent /GTS_PDFX")
    else:
        profilo = pdfx[0].get("/DestOutputProfile")
        if profilo is None:
            errori.append("OutputIntent senza profilo incorporato")
        else:
            dati = profilo.get_object().get_data()
            if dati[16:20] != b"CMYK" or profilo.get_object().get("/N") != 4:
                errori.append("profilo di output non CMYK")
        if not pdfx[0].get("/OutputConditionIdentifier"):
            errori.append("OutputConditionIdentifier mancante")

    # Info + XMP
    info = reader.trailer.get("/Info")
    info = info.get_object() if info else {}
    if info.get("/Trapped") not in ("/True", "/False"):
        errori.append("/Trapped deve essere /True o /False")
    if not info.get("/Title"):
        errori.append("titolo mancante")
    xmp = root.get("/Metadata")
    xmp = xmp.get_object().get_data() if xmp else b""
    for richiesto in (b"<pdfxid:GTS_PDFXVersion>PDF/X-4<", b"<pdf:Trapped>False<",
                      b"<xmpMM:DocumentID>", b"<xmpMM:VersionID>", b"<xmpMM:RenditionClass>",
                      b"<xmp:CreateDate>", b"<xmp:ModifyDate>", b"<dc:title>"):
        if richiesto not in xmp:
            errori.append(f"XMP: manca {richiesto.decode().strip('<')}")

    # box, font, colore, stati grafici
    visitati: set[int] = set()
    problemi_colore: set[str] = set()
    font_non_incorporati: set[str] = set()
    trasferimenti = False

    def risolvi(o):
        return o.get_object() if isinstance(o, IndirectObject) else o

    def controlla_resources(res, contesto: str, contenuto=None):
        res = risolvi(res) or {}
        spazi = risolvi(res.get("/ColorSpace")) or {}
        ha_default = "/DefaultRGB" in spazi
        if contenuto is not None and _operatori_rgb(contenuto):
            if cmyk:
                problemi_colore.add(f"operatori RGB rg/RG in {contesto}")
            elif not ha_default:
                problemi_colore.add(f"RGB senza DefaultRGB in {contesto}")
        for nome, cs in spazi.items():
            if nome != "/DefaultRGB":
                controlla_cs(risolvi(cs), contesto)
            elif cmyk:
                problemi_colore.add(f"DefaultRGB nella versione CMYK ({contesto})")
        for gs_ in (risolvi(res.get("/ExtGState")) or {}).values():
            gs_ = risolvi(gs_)
            if any(k in gs_ for k in ("/TR", "/HTP")) or gs_.get("/TR2", "/Default") != "/Default":
                nonlocal trasferimenti
                trasferimenti = True
            smask = risolvi(gs_.get("/SMask"))
            if isinstance(smask, DictionaryObject) and "/G" in smask:
                controlla_xobject(smask.raw_get("/G"), contesto)
        for font in (risolvi(res.get("/Font")) or {}).values():
            controlla_font(risolvi(font))
        for xo in (risolvi(res.get("/XObject")) or {}).values():
            controlla_xobject(xo, contesto)
        for sh in (risolvi(res.get("/Shading")) or {}).values():
            controlla_cs(risolvi(risolvi(sh).get("/ColorSpace")), contesto)
        for pat in (risolvi(res.get("/Pattern")) or {}).values():
            pat = risolvi(pat)
            if "/Resources" in pat:
                controlla_resources(pat["/Resources"], contesto, pat.get_data() if hasattr(pat, "get_data") else None)
            if "/Shading" in pat:
                controlla_cs(risolvi(risolvi(pat["/Shading"]).get("/ColorSpace")), contesto)

    def controlla_cs(cs, contesto):
        if cs is None:
            return
        if cs == "/DeviceRGB":
            problemi_colore.add(f"DeviceRGB esplicito in {contesto}")
        elif isinstance(cs, ArrayObject) and cs:
            if cs[0] == "/ICCBased":
                if cmyk and risolvi(cs[1]).get("/N") == 3:
                    problemi_colore.add(f"ICC RGB nella versione CMYK ({contesto})")
            elif cs[0] == "/Indexed":
                controlla_cs(risolvi(cs[1]), contesto)
            elif cs[0] in ("/Separation", "/DeviceN"):
                controlla_cs(risolvi(cs[2]), contesto)

    def controlla_xobject(ref, contesto):
        if isinstance(ref, IndirectObject):
            if ref.idnum in visitati:
                return
            visitati.add(ref.idnum)
        xo = risolvi(ref)
        if xo.get("/Subtype") == "/Image":
            if not xo.get("/ImageMask"):
                controlla_cs(risolvi(xo.get("/ColorSpace")), f"{contesto} (immagine)")
            if "/Alternates" in xo or "/OPI" in xo:
                problemi_colore.add("immagini alternative/OPI non ammesse")
        elif xo.get("/Subtype") == "/Form":
            gruppo = risolvi(xo.get("/Group"))
            if gruppo:
                controlla_cs(risolvi(gruppo.get("/CS")), f"{contesto} (gruppo trasparenza)")
            if "/Resources" in xo:
                controlla_resources(xo["/Resources"], f"{contesto} (form)", xo.get_data())
        elif xo.get("/Subtype") == "/PS":
            problemi_colore.add("PostScript XObject non ammesso")

    def controlla_font(font):
        if font.get("/Subtype") == "/Type3":
            if "/Resources" in font:
                controlla_resources(font["/Resources"], "font Type3")
            return
        discendenti = font.get("/DescendantFonts")
        if discendenti:
            for d in risolvi(discendenti):
                controlla_font(risolvi(d))
            return
        desc = risolvi(font.get("/FontDescriptor"))
        if not desc or not any(k in desc for k in ("/FontFile", "/FontFile2", "/FontFile3")):
            font_non_incorporati.add(str(font.get("/BaseFont")))

    for n, pagina in enumerate(reader.pages, start=1):
        media, trim, bleed = pagina.mediabox, pagina.get("/TrimBox"), pagina.get("/BleedBox")
        if trim is None:
            errori.append(f"pagina {n}: manca TrimBox")
        else:
            t, b = pagina.trimbox, pagina.bleedbox
            if not (b.left <= t.left and b.bottom <= t.bottom and b.right >= t.right and b.top >= t.top):
                errori.append(f"pagina {n}: TrimBox fuori dal BleedBox")
            if bleed is not None and not (media.left <= b.left and media.bottom <= b.bottom
                                          and media.right >= b.right and media.top >= b.top):
                errori.append(f"pagina {n}: BleedBox fuori dal MediaBox")
        if int(pagina.get("/Rotate", 0)) % 360:
            errori.append(f"pagina {n}: ruotata di {pagina.get('/Rotate')}°")
        if "/Annots" in pagina:
            errori.append(f"pagina {n}: annotazioni presenti")
        gruppo = risolvi(pagina.get("/Group"))
        if gruppo:
            controlla_cs(risolvi(gruppo.get("/CS")), f"pagina {n} (gruppo trasparenza)")
        contenuto = pagina.get_contents()
        controlla_resources(pagina.get("/Resources"), f"pagina {n}",
                            contenuto.get_data() if contenuto is not None else None)

    if trasferimenti:
        errori.append("funzioni di trasferimento/halftone negli stati grafici")
    if font_non_incorporati:
        errori.append(f"font non incorporati: {sorted(font_non_incorporati)}")
    errori.extend(sorted(problemi_colore))
    return errori
