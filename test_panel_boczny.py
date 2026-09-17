"""Testy dostępności panelu bocznego na telefonie.

Panel boczny trzyma szybką nawigację (Domek, Sklep, Market, Rynek). Streamlit zwija go na wąskich
ekranach, a przycisk rozwijający siedzi w pasku narzędzi (`stToolbar`). Aplikacja ukrywała ten pasek
przez `display: none`, żeby pozbyć się przycisku "Deploy" nachodzącego na górną nawigację - i razem
z nim zabierała na telefonie jedyną drogę do panelu. Panel wisiał wtedy za krawędzią ekranu, a jego
przycisk rozwijania miał rozmiar 0 x 0.

Regresja była niewidoczna na komputerze, bo tam panel startuje rozwinięty. Dlatego pilnują jej testy
czytające sam arkusz stylów z `app.py` - reguła CSS nie ma funkcji, którą można by wywołać.

Uruchomienie:  pytest test_panel_boczny.py
"""

import io
import re

import pytest

from conftest import SCIEZKA_APP

with io.open(SCIEZKA_APP, encoding="utf-8") as plik:
    ZRODLO_APP = plik.read()

# Panel boczny Streamlita ma z-index 999991 i przykrywał przycisk rozwijania, dopóki nagłówek
# siedział na domyślnym 999990. Bez wyższej warstwy dotyk nie dochodził do przycisku.
Z_INDEX_PANELU_BOCZNEGO = 999991


def _blok_reguly(selektor_fragment):
    """Treść pierwszej reguły CSS, której selektor zawiera podany fragment."""
    wzor = re.compile(
        r"([^{}]*" + re.escape(selektor_fragment) + r"[^{}]*)\{([^{}]*)\}",
        re.S,
    )
    trafienie = wzor.search(ZRODLO_APP)
    assert trafienie, f"Nie znaleziono reguły CSS dla selektora zawierającego {selektor_fragment!r}"
    return trafienie.group(2)


def _wartosc(blok, wlasciwosc):
    trafienie = re.search(re.escape(wlasciwosc) + r"\s*:\s*([^;]+);", blok)
    return trafienie.group(1).replace("!important", "").strip() if trafienie else None


def test_pasek_narzedzi_nie_jest_ukryty_przez_display_none():
    """`display: none` na pasku zabiera razem z "Deploy" przycisk rozwijający panel boczny."""
    blok = _blok_reguly('[data-testid="stToolbar"]')
    assert _wartosc(blok, "display") != "none", (
        "Pasek narzędzi znowu jest ukryty - na telefonie nie będzie czym otworzyć panelu bocznego. "
        "Zamiast display: none użyj height: 0 z overflow: hidden."
    )


def test_pasek_narzedzi_jest_obciety_i_nie_lapie_dotyku():
    """Zerowa wysokość z overflow ucina "Deploy" i menu, a pointer-events zdejmuje z paska dotyk."""
    blok = _blok_reguly('[data-testid="stToolbar"]')
    assert _wartosc(blok, "height") == "0"
    assert _wartosc(blok, "overflow") == "hidden"
    assert _wartosc(blok, "pointer-events") == "none"


def test_przycisk_rozwijania_jest_wyciagniety_z_paska_i_dotykalny():
    """Przycisk musi wyjść z obciętego paska przez position: fixed i mieć rozmiar pod palec."""
    blok = _blok_reguly('button[data-testid="stExpandSidebarButton"]')
    assert _wartosc(blok, "display") == "flex"
    assert _wartosc(blok, "position") == "fixed"
    assert _wartosc(blok, "pointer-events") == "auto", (
        "Pasek ma pointer-events: none, więc przycisk musi je sobie przywrócić"
    )
    for wlasciwosc in ("width", "height", "min-width", "min-height"):
        wartosc = _wartosc(blok, wlasciwosc)
        assert wartosc and wartosc.endswith("px"), f"{wlasciwosc} musi być podane w pikselach"
        assert int(wartosc.removesuffix("px")) >= 40, (
            f"{wlasciwosc} = {wartosc} to za mało na cel dotykowy - minimum to 40 px"
        )


def test_naglowek_lezy_nad_panelem_bocznym():
    """Bez wyższej warstwy niż panel boczny zwinięty panel przykrywa przycisk rozwijania."""
    bloki = [
        trafienie.group(2)
        for trafienie in re.finditer(
            r'(header\[data-testid="stHeader"\][^{}]*)\{([^{}]*)\}', ZRODLO_APP, re.S
        )
    ]
    z_indexy = [int(z) for z in (_wartosc(blok, "z-index") for blok in bloki) if z]
    assert z_indexy, "Nagłówek nie ma ustawionego z-index"
    assert max(z_indexy) > Z_INDEX_PANELU_BOCZNEGO, (
        f"Nagłówek ma z-index {max(z_indexy)}, a panel boczny {Z_INDEX_PANELU_BOCZNEGO} - "
        "przycisk rozwijania będzie pod panelem i dotyk do niego nie dojdzie"
    )


@pytest.mark.parametrize("etykieta", ["🏠 Domek", "🛒 Sklep", "🏬 Market"])
def test_szybka_nawigacja_zostaje_w_panelu_bocznym(etykieta):
    """Te przyciski to jedyna droga do nawigacji na punkty bazowe - nie mogą zniknąć z panelu."""
    assert f'"{etykieta}"' in ZRODLO_APP, f"Brak przycisku {etykieta} w panelu bocznym"
