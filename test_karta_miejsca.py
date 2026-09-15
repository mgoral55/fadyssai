"""Testy chipów stanu i ikon akcji na karcie jednego miejsca.

`app.py` jest skryptem Streamlit - import całego modułu uruchomiłby UI, więc testy
wyciągają badane funkcje ze źródła przez AST i uruchamiają je w kontrolowanym namespace.

Uruchomienie:  pytest test_karta_miejsca.py
"""

import re
import urllib.parse

import pytest

from conftest import wczytaj_funkcje_z_app

BADANE_FUNKCJE = [
    "sparsuj_wspolrzedne",
    "rozbij_stan_i_opis",
    "_svg_slupki_trudnosci",
    "ikona_trudnosci",
    "ikona_slonca",
    "ikona_meltdownu",
    "_chip_stanu",
    "render_chipy_stanu",
    "zbuduj_linki_miejsca",
    "render_place_icon_actions",
]

DOMEK_LAT, DOMEK_LON = 35.5827, 24.1258


@pytest.fixture(scope="module")
def app_ns():
    ns = {
        "re": re,
        "urllib": urllib,
        "DOMEK_LAT": DOMEK_LAT,
        "DOMEK_LON": DOMEK_LON,
        "pd": type("PdStub", (), {"isna": staticmethod(lambda v: v is None)}),
    }
    segmenty = wczytaj_funkcje_z_app(BADANE_FUNKCJE)
    for nazwa in BADANE_FUNKCJE:
        exec(segmenty[nazwa], ns)
    return ns


# --- rozbicie "stan - uzasadnienie" ---

@pytest.mark.parametrize("wejscie, stan, poczatek_opisu", [
    ("Średnie - Rozległy, otwarty teren archeologiczny.", "Średnie", "Rozległy"),
    ("Wysoki do Ekstremalny - Dzieci: Ponad 2-godzinna podróż.", "Wysoki do Ekstremalny", "Dzieci:"),
    ("Pełne słońce. Rozległy, otwarty teren miasta.", "Pełne słońce", "Rozległy"),
    ("Cień (Wewnątrz) / Półcień. Warsztaty w chłodnym budynku.", "Cień (Wewnątrz) / Półcień", "Warsztaty"),
    ("Niski - Dojazd (25 min). Dzieci: Szybka wizyta.", "Niski", "Dojazd"),
])
def test_rozbij_stan_i_opis_wyciaga_prefiks_stanu(app_ns, wejscie, stan, poczatek_opisu):
    got_stan, got_opis = app_ns["rozbij_stan_i_opis"](wejscie)
    assert got_stan == stan
    assert got_opis.startswith(poczatek_opisu)


def test_rozbij_stan_i_opis_nie_lamie_liczb_z_myslnikiem(app_ns):
    # "2-godzinna" nie jest separatorem - myslnik musi miec odstepy z obu stron
    stan, _ = app_ns["rozbij_stan_i_opis"]("Wysoki - 2-godzinna podróż w jedną stronę.")
    assert stan == "Wysoki"


@pytest.mark.parametrize("puste", ["", None, "nan", "None", "Brak", "-", "   "])
def test_rozbij_stan_i_opis_traktuje_puste_jako_brak(app_ns, puste):
    assert app_ns["rozbij_stan_i_opis"](puste) == ("", "")


def test_rozbij_stan_i_opis_bez_separatora_zwraca_calosc_jako_stan(app_ns):
    assert app_ns["rozbij_stan_i_opis"]("Półcień") == ("Półcień", "")


# --- ikony trudnosci: slupki SVG ---

def _liczba_wypelnionych_slupkow(svg):
    return svg.count("#8C5338")


@pytest.mark.parametrize("stan, slupki, etykieta", [
    ("Łatwe", 1, "Trudność łatwa"),
    ("Latwe", 1, "Trudność łatwa"),
    ("Średnie", 2, "Trudność średnia"),
    ("Srednie", 2, "Trudność średnia"),
    ("Trudne", 3, "Trudność trudna"),
])
def test_ikona_trudnosci_mapuje_stan_na_slupki(app_ns, stan, slupki, etykieta):
    svg, opis = app_ns["ikona_trudnosci"](stan)
    assert _liczba_wypelnionych_slupkow(svg) == slupki
    assert opis == etykieta
    assert svg.startswith("<svg") and svg.endswith("</svg>")


def test_ikona_trudnosci_bez_danych_oznacza_todo(app_ns):
    svg, opis = app_ns["ikona_trudnosci"]("")
    assert _liczba_wypelnionych_slupkow(svg) == 0
    assert opis == "Trudność: {TODO}"


def test_svg_slupkow_ma_zawsze_trzy_prostokaty(app_ns):
    for poziom in range(4):
        assert app_ns["_svg_slupki_trudnosci"](poziom).count("<rect") == 3


# --- ikony slonca ---

@pytest.mark.parametrize("stan, opis_bazy, ikona, etykieta", [
    ("Pełne słońce", "Brak cienia na ruinach.", "☀️", "Pełne słońce"),
    ("Półcień", "Spacer pod koronami drzew.", "⛅", "Półcień"),
    ("Cień / Półcień", "Głęboki cień platanów.", "🌳", "Cień naturalny"),
    ("Cień (Wewnątrz)", "Sklepik w zacienionym wnętrzu kamienicy.", "🏛️", "Wnętrze"),
    ("Cień (Wewnątrz)", "Klimatyzowane sale muzeum.", "❄️", "Klimatyzacja"),
])
def test_ikona_slonca_czyta_pierwszy_stan(app_ns, stan, opis_bazy, ikona, etykieta):
    assert app_ns["ikona_slonca"](stan, opis_bazy) == (ikona, etykieta)


def test_ikona_slonca_kombinacji_bierze_stan_wiodacy(app_ns):
    # "Pełne słońce / Półcień" - liczy sie pierwszy, autorsko dominujacy stan
    assert app_ns["ikona_slonca"]("Pełne słońce / Półcień", "")[1] == "Pełne słońce"
    assert app_ns["ikona_slonca"]("Półcień / Pełne słońce", "")[1] == "Półcień"


def test_ikona_slonca_bez_danych_oznacza_todo(app_ns):
    assert app_ns["ikona_slonca"]("", "")[1] == "Słońce: {TODO}"


# --- ikony meltdownu ---

@pytest.mark.parametrize("stan, ikona, etykieta", [
    ("Niski", "💚", "Meltdown niski"),
    ("Niski do Średni", "💛", "Meltdown niski–średni"),
    ("Średni", "🧡", "Meltdown średni"),
    ("Średni do Wysoki", "❤️", "Meltdown średni–wysoki"),
    ("Wysoki", "🖤", "Meltdown wysoki"),
    ("Ekstremalny", "💀", "Meltdown ekstremalny"),
    ("Wysoki do Ekstremalny", "💀", "Meltdown ekstremalny"),
])
def test_ikona_meltdownu_pokrywa_wszystkie_stany_bazy(app_ns, stan, ikona, etykieta):
    assert app_ns["ikona_meltdownu"](stan) == (ikona, etykieta)


def test_ikona_meltdownu_bez_danych_oznacza_todo(app_ns):
    assert app_ns["ikona_meltdownu"]("")[1] == "Meltdown: {TODO}"


# --- HTML chipow ---

MIEJSCE = {
    "trudnosc_adhd": "Średnie - Rozległy, otwarty teren archeologiczny.",
    "ochrona_slonce": "Pełne słońce. Teren pozbawiony drzew i cienia.",
    "potencjal_meltdownu": "Średni - Dzieci: Krótki dojazd (35 min) zapobiega zmęczeniu.",
    "strategie_meltdown": "Zwiedzajcie wyłącznie rano.",
}


def test_render_chipy_stanu_daje_trzy_wykluczajace_sie_chipy(app_ns):
    html = app_ns["render_chipy_stanu"](MIEJSCE, "chipy_miejsca_7")
    assert html.count('<details class="state-chip"') == 3
    # wspolny `name` to natywna wylacznosc <details> - jeden rozwiniety naraz
    assert html.count('name="chipy_miejsca_7"') == 3
    assert html.count("<summary>") == 3
    assert html.count('class="state-chip-panel"') == 3


def test_render_chipy_stanu_trzyma_kolejnosc_wymagana_przez_css(app_ns):
    # CSS wylamuje panel z kolumny ujemnym marginesem dobranym przez :nth-child,
    # wiec kolejnosc chipow jest kontraktem: trudnosc, slonce, meltdown
    html = app_ns["render_chipy_stanu"](MIEJSCE, "g")
    pozycje = [html.index(t) for t in ("Poziom trudno\u015bci ADHD", "Ochrona przed s\u0142o\u0144cem", "Specyfika AuDHD")]
    assert pozycje == sorted(pozycje)


def test_render_chipy_stanu_panel_jest_wewnatrz_swojego_chipa(app_ns):
    html = app_ns["render_chipy_stanu"](MIEJSCE, "g")
    # kazdy <details> domyka sie po swoim panelu
    assert html.count("</details>") == 3
    for fragment in html.split('<details class="state-chip"')[1:]:
        assert fragment.index('class="state-chip-panel"') < fragment.index("</details>")


def test_render_chipy_stanu_niesie_pelna_tresc_starych_sekcji(app_ns):
    html = app_ns["render_chipy_stanu"](MIEJSCE, "g")
    assert "Rozległy, otwarty teren archeologiczny." in html
    assert "Teren pozbawiony drzew i cienia." in html
    assert "Krótki dojazd (35 min) zapobiega zmęczeniu." in html
    assert "Zwiedzajcie wyłącznie rano." in html
    assert "Strategia zaradcza" in html


def test_render_chipy_stanu_pokazuje_todo_zamiast_pustki(app_ns):
    html = app_ns["render_chipy_stanu"]({}, "g")
    assert html.count("{TODO}") >= 4  # trudnosc, slonce, meltdown i strategia


def test_render_chipy_stanu_pokazuje_etykiety_na_guzikach(app_ns):
    html = app_ns["render_chipy_stanu"](MIEJSCE, "g")
    for etykieta in ("Trudność średnia", "Pełne słońce", "Meltdown średni"):
        assert f'<span class="state-chip-tx">{etykieta}</span>' in html


# --- linki i ikony akcji ---

def test_zbuduj_linki_miejsca_woli_nazwe_angielska_i_dokleja_crete(app_ns):
    linki = app_ns["zbuduj_linki_miejsca"]("35.46271,24.14175", "7. Ancient Aptera (ruiny)", "Ancient Aptera", "Aptera, Chania")
    assert "Ancient+Aptera" in linki["nav_url"] or "Ancient%20Aptera" in linki["nav_url"]
    assert "Crete" in urllib.parse.unquote(linki["nav_url"])
    assert "(ruiny)" not in urllib.parse.unquote(linki["nav_url"])
    assert linki["google_url"].startswith("https://www.google.com/search?q=")


def test_zbuduj_linki_miejsca_bez_nazwy_kotwiczy_na_krecie(app_ns):
    # Bez nazwy i adresu zostaje samo "Crete" - fraza nigdy nie jest pusta, wiec link
    # tekstowy ma pierwszenstwo nad wspolrzednymi (zachowanie paska akcji na trasie).
    linki = app_ns["zbuduj_linki_miejsca"]("35.46271,24.14175", "", "", "")
    assert urllib.parse.unquote(linki["nav_url"]).endswith("query=Crete")
    assert linki["google_url"].endswith("q=Crete")


def test_render_place_icon_actions_daje_trzy_ikony(app_ns):
    html = app_ns["render_place_icon_actions"](
        coords_clean="35.46271,24.14175",
        search_name="Ancient Aptera",
        search_name_en="Ancient Aptera",
        address="Aptera, Chania",
        czy_odwiedzone=False,
        url_visit="?tab=zabytek&place=7&user=Jurek&visit=1",
    )
    assert html.count("place-icon-btn") == 3
    assert "🧭" in html and "🔍" in html and "✓" in html
    assert 'href="?tab=zabytek&place=7&user=Jurek&visit=1"' in html
    assert "done" not in html


def test_render_place_icon_actions_zaznacza_odwiedzone(app_ns):
    html = app_ns["render_place_icon_actions"](
        coords_clean="35.46271,24.14175", search_name="Ancient Aptera",
        czy_odwiedzone=True, url_visit="?visit=1",
    )
    assert 'class="place-icon-btn done"' in html


def test_render_place_icon_actions_zawsze_ma_trzy_ikony(app_ns):
    # Fraza szukania nigdy nie jest pusta (kotwica "Crete"), wiec ikona Google zostaje
    html = app_ns["render_place_icon_actions"](
        coords_clean="35.46271,24.14175", search_name="", search_name_en="", address="",
        czy_odwiedzone=False, url_visit="?visit=1",
    )
    assert html.count("place-icon-btn") == 3
    assert "🔍" in html


# --- slonce: plaze i tawerny opisano skala OCHRONY, nie ekspozycji ---

@pytest.mark.parametrize("stan, opis_bazy, ikona, etykieta", [
    ("Brak ochrony", "Plaża jest całkowicie odsłonięta.", "☀️", "Pełne słońce"),
    ("Częściowa", "Plaża w pełnym słońcu, ale gaj palmowy daje cień.", "⛅", "Półcień"),
    ("Dobra", "Parasole i leżaki do wynajęcia, tamaryszki dają cień.", "🌳", "Cień naturalny"),
    ("Bardzo dobra – naturalny, głęboki cień", "Drzewa tamaryszkowe.", "🌳", "Cień naturalny"),
    ("Pełna ochrona", "Stoliki zacienione parasolami i koronami drzew.", "🌳", "Cień naturalny"),
    ("Dobra", "Klimatyzowana sala i zacieniony taras.", "❄️", "Klimatyzacja"),
])
def test_ikona_slonca_rozumie_skale_ochrony(app_ns, stan, opis_bazy, ikona, etykieta):
    assert app_ns["ikona_slonca"](stan, opis_bazy) == (ikona, etykieta)


def test_kazde_miejsce_z_csv_ma_ikone_slonca(app_ns):
    """Zaden wiersz miejsca.csv nie moze wpadac na {TODO} - inaczej chip klamie o braku danych."""
    import csv
    import os

    sciezka = os.path.join(os.path.dirname(os.path.abspath(__file__)), "miejsca.csv")
    bez_dopasowania = []
    for wiersz in csv.DictReader(open(sciezka, encoding="utf-8")):
        for kolumna, funkcja in (
            ("Ochrona przed słońcem", "ikona_slonca"),
            ("Poziom trudności ADHD", "ikona_trudnosci"),
            ("Potencjał meltdownu", "ikona_meltdownu"),
        ):
            stan, opis = app_ns["rozbij_stan_i_opis"](wiersz.get(kolumna))
            etykieta = (app_ns[funkcja](stan, opis) if funkcja == "ikona_slonca" else app_ns[funkcja](stan))[1]
            if "{TODO}" in etykieta:
                bez_dopasowania.append((wiersz["numer miejsca"], kolumna, stan))
    assert not bez_dopasowania, bez_dopasowania
