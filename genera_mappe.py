#!/usr/bin/env python3
"""
Genera le mappe per passaporti e raccoglitore — Sentiero Italia CAI.

Basemap: tile raster Webmapp (Web Mercator) scaricate e cachate su disco.
Overlay vettoriale (resta vettoriale nel PDF finale):
  - tracciato SICAI da assets/sicai_tappe.geojson
  - confini regionali da assets/limits_IT_regions.geojson

Due prodotti:
  - genera_mappa_italia():  Italia intera + tracciato completo (raccoglitore)
  - genera_mappa_gruppo():  zoom sulla/e regione/i del gruppo, confine
                            evidenziato, tratto SICAI ritagliato, velatura
                            esterna per il focus (copertina passaporto)

Uso stand-alone (mappe di verifica in output/mappe/):
  python genera_mappe.py
"""

from __future__ import annotations

import io
import json
import math
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import requests
from PIL import Image

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath
from shapely.geometry import box, shape
from shapely.geometry.polygon import orient
from shapely.ops import transform as shp_transform
from shapely.ops import unary_union

BASE_DIR = Path(__file__).resolve().parent
ASSET_DIR = BASE_DIR / "assets"
TILE_CACHE_DIR = BASE_DIR / ".tile_cache"

TILE_URL = "https://api.webmapp.it/tiles/{z}/{x}/{y}.png"
TILE_SIZE = 256
ZOOM_MIN, ZOOM_MAX = 4, 14
MAX_TILE = 600                 # guardia: massimo numero di tile per mosaico
DPI_STAMPA = 300               # risoluzione minima alla dimensione di stampa

REGIONI_GEOJSON = ASSET_DIR / "limits_IT_regions.geojson"
TAPPE_GEOJSON = ASSET_DIR / "sicai_tappe.geojson"

R_MERC = 6378137.0             # raggio sferico Web Mercator (EPSG:3857)
LAT_MAX = 85.05112878

# ---- Stile (palette CAI, coerente con i template) ----
COL_TRACCIATO = "#C8102E"      # rosso CAI
COL_ALONE = "#FFFFFF"          # alone bianco sotto il tracciato
COL_CONFINE_FOCUS = "#1B3569"  # caiblu: confine regione/i del passaporto
COL_CONFINE_ALTRI = "#666666"  # confini delle altre regioni
COL_VELATURA = "#FFFFFF"       # velatura fuori dalla zona di interesse

# Mappatura nomi regione del dataset tappe (GRUPPI) → reg_name del geojson
# dei confini. Le voci assenti coincidono (es. "Lombardia").
_REGIONE_GEOJSON = {
    "Friuli Venezia Giulia": ["Friuli-Venezia Giulia"],
    "Trentino-Alto Adige": ["Trentino-Alto Adige/Südtirol"],
    "Trentino - Alto Adige": ["Trentino-Alto Adige/Südtirol"],
    "Valle d'Aosta": ["Valle d'Aosta/Vallée d'Aoste"],
    "Toscana/Emilia Romagna": ["Toscana", "Emilia-Romagna"],
    "Toscana / Emilia-Romagna": ["Toscana", "Emilia-Romagna"],
    "Marche / Umbria": ["Marche", "Umbria"],
}


def nomi_regioni_geojson(regioni: list[str]) -> list[str]:
    """Espande i nomi regione di GRUPPI nei reg_name del geojson confini."""
    nomi = []
    for r in regioni:
        nomi.extend(_REGIONE_GEOJSON.get(r, [r]))
    return nomi


# ----------------------------------------------------------------------
# Proiezione Web Mercator (WGS84 → EPSG:3857), senza pyproj
# ----------------------------------------------------------------------

def _merc_xy(lon, lat, _z=None):
    """Versione vettoriale per shapely.ops.transform (quota ignorata)."""
    lon = np.asarray(lon, dtype=float)
    lat = np.clip(np.asarray(lat, dtype=float), -LAT_MAX, LAT_MAX)
    x = np.radians(lon) * R_MERC
    y = np.log(np.tan(np.pi / 4 + np.radians(lat) / 2)) * R_MERC
    return x, y


def _in_mercator(geom):
    return shp_transform(_merc_xy, geom)


# ----------------------------------------------------------------------
# Caricamento dati (cachato: stessi geojson per tutte le mappe)
# ----------------------------------------------------------------------

@lru_cache(maxsize=1)
def _carica_regioni() -> dict:
    """reg_name → geometria (Web Mercator)."""
    with open(REGIONI_GEOJSON, encoding="utf-8") as f:
        data = json.load(f)
    return {
        feat["properties"]["reg_name"]: _in_mercator(shape(feat["geometry"]))
        for feat in data["features"]
    }


@lru_cache(maxsize=1)
def _carica_tracciato():
    """Unione di tutte le tappe SICAI (Web Mercator)."""
    with open(TAPPE_GEOJSON, encoding="utf-8") as f:
        data = json.load(f)
    linee = [_in_mercator(shape(feat["geometry"])) for feat in data["features"]]
    return unary_union(linee)


@lru_cache(maxsize=1)
def _indice_tappe_geojson() -> dict:
    """sicai_ref → geometria della singola tappa (Web Mercator)."""
    with open(TAPPE_GEOJSON, encoding="utf-8") as f:
        data = json.load(f)
    indice = {}
    for feat in data["features"]:
        ref = feat["properties"].get("sicai_ref")
        if ref:
            indice[str(ref).strip()] = _in_mercator(shape(feat["geometry"]))
    return indice


def ref_a_sicai_code(ref: str) -> str:
    """Estrae il codice SICAI da un ref passaporto: 'SI V20' → 'V20'."""
    return str(ref).strip().removeprefix("SI").strip()


# ----------------------------------------------------------------------
# Tile: zoom, download con cache, mosaico
# ----------------------------------------------------------------------

_WORLD = 2 * math.pi * R_MERC  # estensione del mondo in metri mercator


@lru_cache(maxsize=1)
def _sessione() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "passaporto-sicai/1.0"
    return s


def _zoom_per_bbox(bbox: tuple, w_mm: float, dpi: int = DPI_STAMPA) -> int:
    """Zoom minimo che garantisce ~dpi alla larghezza di stampa target."""
    px_target = w_mm / 25.4 * dpi
    ris_richiesta = (bbox[2] - bbox[0]) / px_target      # m/px richiesti
    ris_z0 = _WORLD / TILE_SIZE                          # m/px a zoom 0
    z = math.ceil(math.log2(ris_z0 / ris_richiesta))
    return max(ZOOM_MIN, min(ZOOM_MAX, z))


def _scarica_tile(z: int, x: int, y: int) -> Image.Image:
    cache = TILE_CACHE_DIR / str(z) / f"{x}_{y}.png"
    if cache.exists():
        return Image.open(cache).convert("RGB")
    url = TILE_URL.format(z=z, x=x, y=y)
    try:
        resp = _sessione().get(url, timeout=30)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(resp.content)
        return img
    except Exception as exc:  # tile mancante (es. mare aperto) o rete
        print(f"⚠ tile {z}/{x}/{y} non disponibile ({exc})", file=sys.stderr)
        return Image.new("RGB", (TILE_SIZE, TILE_SIZE), "#EAF0F6")


def _mosaico(bbox: tuple, z: int) -> tuple[Image.Image, tuple]:
    """Mosaico di tile che copre la bbox mercator. Ritorna (immagine,
    extent mercator (xmin, xmax, ymin, ymax)) per imshow."""
    n = 2 ** z

    def merc2tile(xm, ym):
        tx = (xm + _WORLD / 2) / _WORLD * n
        ty = (_WORLD / 2 - ym) / _WORLD * n
        return tx, ty

    tx0, ty0 = merc2tile(bbox[0], bbox[3])   # angolo NW
    tx1, ty1 = merc2tile(bbox[2], bbox[1])   # angolo SE
    x_min, x_max = int(math.floor(tx0)), int(math.floor(tx1))
    y_min, y_max = int(math.floor(ty0)), int(math.floor(ty1))
    x_min, y_min = max(x_min, 0), max(y_min, 0)
    x_max, y_max = min(x_max, n - 1), min(y_max, n - 1)

    n_tile = (x_max - x_min + 1) * (y_max - y_min + 1)
    if n_tile > MAX_TILE:
        raise RuntimeError(f"Troppi tile richiesti ({n_tile} > {MAX_TILE}) a zoom {z}")

    mosaico = Image.new(
        "RGB",
        ((x_max - x_min + 1) * TILE_SIZE, (y_max - y_min + 1) * TILE_SIZE),
    )
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            mosaico.paste(
                _scarica_tile(z, x, y),
                ((x - x_min) * TILE_SIZE, (y - y_min) * TILE_SIZE),
            )

    lato_tile = _WORLD / n                   # metri per tile
    extent = (
        x_min * lato_tile - _WORLD / 2,          # xmin
        (x_max + 1) * lato_tile - _WORLD / 2,    # xmax
        _WORLD / 2 - (y_max + 1) * lato_tile,    # ymin
        _WORLD / 2 - y_min * lato_tile,          # ymax
    )
    return mosaico, extent


# ----------------------------------------------------------------------
# Helper geometrici / disegno
# ----------------------------------------------------------------------

def _espandi_bbox(bounds: tuple, ratio_wh: float, padding: float = 0.06) -> tuple:
    """Aggiunge un padding relativo e poi espande la bbox (centrata) fino
    a raggiungere esattamente il rapporto larghezza/altezza richiesto."""
    xmin, ymin, xmax, ymax = bounds
    w, h = xmax - xmin, ymax - ymin
    pad = max(w, h) * padding
    xmin, ymin, xmax, ymax = xmin - pad, ymin - pad, xmax + pad, ymax + pad
    w, h = xmax - xmin, ymax - ymin
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    if w / h < ratio_wh:
        w = h * ratio_wh
    else:
        h = w / ratio_wh
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def _poligoni(geom) -> list:
    """Lista dei poligoni componenti (gestisce Polygon e MultiPolygon)."""
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type in ("MultiPolygon", "GeometryCollection"):
        out = []
        for g in geom.geoms:
            out.extend(_poligoni(g))
        return out
    return []


def _patch_poligono(geom, **kwargs) -> PathPatch:
    """PathPatch composto da esterni + buchi (orientazioni opposte, così
    il riempimento funziona sia nonzero che even-odd)."""
    vertici, codici = [], []
    for poly in _poligoni(geom):
        poly = orient(poly, sign=1.0)  # esterno CCW, buchi CW
        for ring in [poly.exterior, *poly.interiors]:
            pts = np.asarray(ring.coords)
            vertici.append(pts)
            codici.append(
                np.concatenate((
                    [MplPath.MOVETO],
                    np.full(len(pts) - 2, MplPath.LINETO),
                    [MplPath.CLOSEPOLY],
                ))
            )
    path = MplPath(np.concatenate(vertici), np.concatenate(codici).astype(np.uint8))
    return PathPatch(path, **kwargs)


def _segmenti(geom) -> list:
    """Lista di array Nx2 dalle (Multi)LineString per LineCollection."""
    if geom.is_empty:
        return []
    if geom.geom_type == "LineString":
        return [np.asarray(geom.coords)]
    if geom.geom_type in ("MultiLineString", "GeometryCollection"):
        out = []
        for g in geom.geoms:
            out.extend(_segmenti(g))
        return out
    return []


def _anelli(geom) -> list:
    """Anelli (esterni + buchi) dei poligoni, come array Nx2."""
    out = []
    for poly in _poligoni(geom):
        for ring in [poly.exterior, *poly.interiors]:
            out.append(np.asarray(ring.coords))
    return out


def _disegna_tracciato(ax, geom, tolleranza: float,
                       lw_alone: float = 1.8, lw_linea: float = 1.0) -> None:
    """Tracciato SICAI: alone bianco sotto, rosso CAI sopra (vettoriale)."""
    segs = _segmenti(geom.simplify(tolleranza))
    ax.add_collection(LineCollection(
        segs, colors=COL_ALONE, linewidths=lw_alone,
        capstyle="round", joinstyle="round", zorder=8))
    ax.add_collection(LineCollection(
        segs, colors=COL_TRACCIATO, linewidths=lw_linea,
        capstyle="round", joinstyle="round", zorder=9))


def _nuova_figura(bbox: tuple, w_mm: float, h_mm: float):
    fig = plt.figure(figsize=(w_mm / 25.4, h_mm / 25.4))
    ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
    ax.set_axis_off()
    ax.set_xlim(bbox[0], bbox[2])
    ax.set_ylim(bbox[1], bbox[3])
    ax.set_aspect("auto")  # la bbox ha già il rapporto esatto della figura
    return fig, ax


def _salva(fig, z: int, bbox: tuple, w_mm: float, out_path: Path) -> None:
    """Salva il PDF con dpi sufficiente a non degradare la basemap."""
    ris = _WORLD / (TILE_SIZE * 2 ** z)                   # m/px allo zoom z
    px_bbox = (bbox[2] - bbox[0]) / ris                   # px reali della bbox
    dpi = int(min(max(DPI_STAMPA, px_bbox / (w_mm / 25.4)), 600))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)


# ----------------------------------------------------------------------
# API pubblica
# ----------------------------------------------------------------------

def genera_mappa_italia(out_path: Path, w_mm: float = 89, h_mm: float = 70) -> Path:
    """Mappa dell'Italia intera con il tracciato SICAI completo
    (retro copertina del raccoglitore)."""
    out_path = Path(out_path)
    regioni = _carica_regioni()
    italia = unary_union(list(regioni.values()))
    bbox = _espandi_bbox(italia.bounds, w_mm / h_mm, padding=0.03)
    tol = (bbox[2] - bbox[0]) / 3000

    z = _zoom_per_bbox(bbox, w_mm)
    mosaico, extent = _mosaico(bbox, z)

    fig, ax = _nuova_figura(bbox, w_mm, h_mm)
    ax.imshow(np.asarray(mosaico), extent=extent, origin="upper",
              interpolation="bilinear", zorder=1)

    # leggera velatura fuori dall'Italia per dare focus al Paese
    velo = box(*bbox).difference(italia.simplify(tol))
    ax.add_patch(_patch_poligono(
        velo, facecolor=COL_VELATURA, alpha=0.45, edgecolor="none", zorder=3))

    # confini regionali sottili
    anelli = []
    for geom in regioni.values():
        anelli.extend(_anelli(geom.simplify(tol)))
    ax.add_collection(LineCollection(
        anelli, colors=COL_CONFINE_ALTRI, linewidths=0.3, alpha=0.7, zorder=5))

    _disegna_tracciato(ax, _carica_tracciato(), tol, lw_alone=1.4, lw_linea=0.8)

    _salva(fig, z, bbox, w_mm, out_path)
    return out_path


def genera_mappa_gruppo(regioni_gruppo: list[str], out_path: Path,
                        w_mm: float = 40, h_mm: float = 55) -> Path:
    """Mappa con zoom sulla/e regione/i del gruppo: confine evidenziato,
    tratto SICAI che le attraversa, velatura esterna (copertina passaporto)."""
    out_path = Path(out_path)
    regioni = _carica_regioni()
    nomi = nomi_regioni_geojson(regioni_gruppo)
    mancanti = [n for n in nomi if n not in regioni]
    if mancanti:
        raise SystemExit(f"Regione/i non nel geojson confini: {', '.join(mancanti)}")

    focus = unary_union([regioni[n] for n in nomi])
    bbox = _espandi_bbox(focus.bounds, w_mm / h_mm, padding=0.06)
    tol = (bbox[2] - bbox[0]) / 2000

    z = _zoom_per_bbox(bbox, w_mm)
    mosaico, extent = _mosaico(bbox, z)

    fig, ax = _nuova_figura(bbox, w_mm, h_mm)
    ax.imshow(np.asarray(mosaico), extent=extent, origin="upper",
              interpolation="bilinear", zorder=1)

    focus_semplificato = focus.simplify(tol)

    # velatura fuori dalla/e regione/i del gruppo
    velo = box(*bbox).difference(focus_semplificato)
    ax.add_patch(_patch_poligono(
        velo, facecolor=COL_VELATURA, alpha=0.55, edgecolor="none", zorder=3))

    # confini delle altre regioni visibili nella bbox (sottili)
    finestra = box(*bbox)
    anelli_altri = []
    for nome, geom in regioni.items():
        if nome in nomi or not geom.intersects(finestra):
            continue
        anelli_altri.extend(_anelli(geom.simplify(tol)))
    if anelli_altri:
        ax.add_collection(LineCollection(
            anelli_altri, colors=COL_CONFINE_ALTRI, linewidths=0.3,
            alpha=0.6, zorder=4))

    # confini interni tra le regioni del gruppo (l'unione li elimina)
    if len(nomi) > 1:
        anelli_interni = []
        for n in nomi:
            anelli_interni.extend(_anelli(regioni[n].simplify(tol)))
        ax.add_collection(LineCollection(
            anelli_interni, colors=COL_CONFINE_FOCUS, linewidths=0.4,
            alpha=0.65, zorder=5))

    # confine della/e regione/i in evidenza (alone bianco + caiblu)
    anelli_focus = _anelli(focus_semplificato)
    ax.add_collection(LineCollection(
        anelli_focus, colors=COL_ALONE, linewidths=2.0,
        capstyle="round", joinstyle="round", zorder=6))
    ax.add_collection(LineCollection(
        anelli_focus, colors=COL_CONFINE_FOCUS, linewidths=1.1,
        capstyle="round", joinstyle="round", zorder=7))

    # tratto SICAI ritagliato sulla/e regione/i (buffer minimo: il
    # tracciato OSM può uscire di poco dal confine amministrativo)
    tratto = _carica_tracciato().intersection(focus.buffer(2000))
    _disegna_tracciato(ax, tratto, tol)

    _salva(fig, z, bbox, w_mm, out_path)
    return out_path


def genera_filigrana_tracciato(
    sicai_ref: str, out_path: Path, w_mm: float = 26, h_mm: float = 26,
    con_mappa: bool = False,
) -> Path | None:
    """Filigrana della singola tappa per il riquadro timbro. Ritorna None se
    la tappa non ha geometria in sicai_tappe.geojson. PNG cachato su disco:
    rigenerato solo se manca o se il geojson sorgente è più recente.

    con_mappa=False (default): solo silhouette del tracciato (rosso CAI) su
        sfondo trasparente.
    con_mappa=True: basemap Webmapp sotto il tracciato, PNG opaco; stessa
        bbox quadrata centrata sulla tappa."""
    code = str(sicai_ref).strip()
    geom = _indice_tappe_geojson().get(code)
    if geom is None or geom.is_empty:
        return None

    out_path = Path(out_path)
    if out_path.exists() and out_path.stat().st_mtime >= TAPPE_GEOJSON.stat().st_mtime:
        return out_path

    bbox = _espandi_bbox(geom.bounds, w_mm / h_mm, padding=0.12)
    tol = (bbox[2] - bbox[0]) / 1500

    if con_mappa:
        z = _zoom_per_bbox(bbox, w_mm)
        mosaico, extent = _mosaico(bbox, z)
        fig, ax = _nuova_figura(bbox, w_mm, h_mm)
        ax.imshow(np.asarray(mosaico), extent=extent, origin="upper",
                  interpolation="bilinear", zorder=1)
        _disegna_tracciato(ax, geom, tol, lw_alone=1.6, lw_linea=1.0)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=DPI_STAMPA)
        plt.close(fig)
        return out_path

    fig, ax = _nuova_figura(bbox, w_mm, h_mm)
    fig.patch.set_alpha(0.0)
    ax.patch.set_alpha(0.0)
    _disegna_tracciato(ax, geom, tol, lw_alone=2.2, lw_linea=1.4)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=DPI_STAMPA, transparent=True)
    plt.close(fig)
    return out_path


# ----------------------------------------------------------------------
# Stand-alone: mappe di verifica in output/mappe/
# ----------------------------------------------------------------------

def main():
    from genera_passaporto import OUTPUT_DIR, get_gruppi  # import locale: evita ciclo

    out_dir = OUTPUT_DIR / "mappe"
    print("Mappa Italia (raccoglitore)…")
    p = genera_mappa_italia(out_dir / "mappa-italia.pdf")
    print(f"  → {p}")
    for nome, cfg in get_gruppi().items():
        slug = nome.lower().replace(" ", "-").replace("'", "")
        print(f"Mappa gruppo {nome} ({' · '.join(cfg['regioni'])})…")
        p = genera_mappa_gruppo(cfg["regioni"], out_dir / f"mappa-{slug}.pdf")
        print(f"  → {p}")


if __name__ == "__main__":
    main()
