"""Testy katalogu ryb do snorklowania: loader CSV, ścieżki zdjęć, klucze odhaczeń.

`app.py` jest skryptem Streamlit - import całego modułu uruchomiłby UI, więc testy
wyciągają badane funkcje ze źródła przez AST i uruchamiają je w kontrolowanym namespace.

Uruchomienie:  pytest test_ryby.py
"""

import io
import os

import pandas as pd
import pytest

from conftest import wczytaj_funkcje_z_app

BADANE_FUNKCJE = [
    "wczytaj_katalog_ryb",
    "sciezka_zdjecia_ryby",
    "klucz_statusu_ryby",
    "klasa_chipa_szansy",
    "etykieta_linku_opisu",
]

KATALOG_REPO = os.path.dirname(os.path.abspath(__file__))
SCIEZKA_CSV = os.path.join(KATALOG_REPO, "ryby.csv")
KATALOG_ZDJEC = os.path.join(KATALOG_REPO, "zdjecia", "ryby")

DOZWOLONE_GRUPY = {"Ryby", "Bezkręgowce", "Żółwie"}
DOZWOLONE_SZANSE = {"Pewniak", "Częsta", "Rzadkość"}

KOLUMNY_KATALOGU_RYB = [
    "numer", "slug", "nazwa_pl", "nazwa_lacinska", "grupa", "szansa", "rozmiar",
    "gdzie_szukac", "opis", "ostrzezenie", "link_opisu", "autor_zdjecia", "licencja_zdjecia",
    "zrodlo_zdjecia",
]


@pytest.fixture(scope="module")
def app_ns():
    ns = {
        "os": os,
        "pd": pd,
        "KATALOG_RYB_CSV": SCIEZKA_CSV,
        "KATALOG_RYB_ZDJECIA": KATALOG_ZDJEC,
        "PREFIKS_KLUCZA_RYBY": "ryba_",
        "KOLUMNY_KATALOGU_RYB": KOLUMNY_KATALOGU_RYB,
    }
    segmenty = wczytaj_funkcje_z_app(BADANE_FUNKCJE)
    for nazwa in BADANE_FUNKCJE:
        exec(segmenty[nazwa], ns)
    return ns


@pytest.fixture(scope="module")
def katalog(app_ns):
    return app_ns["wczytaj_katalog_ryb"](SCIEZKA_CSV)


def test_katalog_ma_gatunki_i_wszystkie_kolumny(katalog):
    assert not katalog.empty
    for kolumna in KOLUMNY_KATALOGU_RYB:
        assert kolumna in katalog.columns


def test_slugi_sa_unikalne_i_bez_spacji(katalog):
    slugi = list(katalog["slug"])
    assert len(slugi) == len(set(slugi))
    for slug in slugi:
        assert slug == slug.strip().lower()
        assert " " not in slug


def test_kazdy_gatunek_ma_nazwe_opis_i_atrybucje(katalog):
    for _, ryba in katalog.iterrows():
        assert ryba["nazwa_pl"].strip(), ryba["slug"]
        assert ryba["nazwa_lacinska"].strip(), ryba["slug"]
        assert len(ryba["opis"].strip()) > 40, ryba["slug"]
        assert ryba["gdzie_szukac"].strip(), ryba["slug"]
        assert ryba["autor_zdjecia"].strip(), ryba["slug"]
        assert ryba["licencja_zdjecia"].strip().startswith("CC"), ryba["slug"]
        assert ryba["zrodlo_zdjecia"].startswith("https://"), ryba["slug"]


def test_kazdy_gatunek_ma_link_do_dluzszego_opisu(katalog):
    linki = []
    for _, ryba in katalog.iterrows():
        link = ryba["link_opisu"].strip()
        assert link.startswith("https://"), ryba["slug"]
        assert ".wikipedia.org/wiki/" in link, ryba["slug"]
        linki.append(link)
    assert len(linki) == len(set(linki))


def test_etykieta_linku_rozpoznaje_jezyk(app_ns):
    etykieta = app_ns["etykieta_linku_opisu"]
    assert etykieta("https://pl.wikipedia.org/wiki/Salpa").endswith("(PL)")
    assert etykieta("https://en.wikipedia.org/wiki/Pterois_miles").endswith("(EN)")


def test_grupy_i_szanse_sa_ze_slownika(katalog):
    assert set(katalog["grupa"]) <= DOZWOLONE_GRUPY
    assert set(katalog["szansa"]) <= DOZWOLONE_SZANSE


def test_gatunki_id_sortuja_sie_rosnaco(katalog):
    numery = [int(n) for n in katalog["numer"]]
    assert numery == sorted(numery)
    assert len(numery) == len(set(numery))


def test_kazdy_gatunek_ma_plik_zdjecia(app_ns, katalog):
    for slug in katalog["slug"]:
        sciezka = app_ns["sciezka_zdjecia_ryby"](slug, KATALOG_ZDJEC)
        assert sciezka is not None, f"brak zdjęcia dla {slug}"
        assert os.path.getsize(sciezka) > 5000, f"podejrzanie małe zdjęcie {slug}"


def test_gatunki_z_kolcami_maja_ostrzezenie(katalog):
    # Jadowite i inwazyjne gatunki muszą nieść ostrzeżenie - to sekcja dla dzieci.
    wymagane = ["scorpaena_porcus", "pterois_miles", "trachinus_draco",
                "lagocephalus_sceleratus", "paracentrotus_lividus", "pelagia_noctiluca",
                "muraena_helena", "siganus_luridus"]
    z_ostrzezeniem = {r["slug"] for _, r in katalog.iterrows() if r["ostrzezenie"].strip()}
    assert set(wymagane) <= z_ostrzezeniem


def test_brak_pliku_csv_daje_pusty_katalog(app_ns, tmp_path):
    pusty = app_ns["wczytaj_katalog_ryb"](str(tmp_path / "nie_ma.csv"))
    assert pusty.empty
    assert list(pusty.columns) == KOLUMNY_KATALOGU_RYB


def test_brakujace_kolumny_sa_dopelniane(app_ns, tmp_path):
    sciezka = tmp_path / "ryby_ubogie.csv"
    sciezka.write_text("numer,slug,nazwa_pl\n2,b,Druga\n1,a,Pierwsza\n", encoding="utf-8")
    df = app_ns["wczytaj_katalog_ryb"](str(sciezka))
    assert list(df["slug"]) == ["a", "b"]
    for kolumna in KOLUMNY_KATALOGU_RYB:
        assert kolumna in df.columns
    assert df.iloc[0]["ostrzezenie"] == ""


def test_wiersze_bez_sluga_wypadaja(app_ns, tmp_path):
    sciezka = tmp_path / "ryby_dziury.csv"
    sciezka.write_text("numer,slug,nazwa_pl\n1,a,Pierwsza\n2,,Bez sluga\n", encoding="utf-8")
    df = app_ns["wczytaj_katalog_ryb"](str(sciezka))
    assert list(df["slug"]) == ["a"]


def test_sciezka_zdjecia_zwraca_none_gdy_brak_pliku(app_ns, tmp_path):
    assert app_ns["sciezka_zdjecia_ryby"]("nie_ma_takiej_ryby", str(tmp_path)) is None


def test_klucz_statusu_ma_prefiks_ryby(app_ns):
    assert app_ns["klucz_statusu_ryby"]("thalassoma_pavo") == "ryba_thalassoma_pavo"


def test_klasa_chipa_szansy(app_ns):
    assert app_ns["klasa_chipa_szansy"]("Pewniak") == "szansa-pewniak"
    assert app_ns["klasa_chipa_szansy"]("Rzadkość") == "szansa-rzadkosc"
    assert app_ns["klasa_chipa_szansy"]("cokolwiek") == ""


def test_zakladka_ryb_jest_podpieta_w_nawigacji():
    zrodlo = io.open(os.path.join(KATALOG_REPO, "app.py"), encoding="utf-8").read()
    assert '("ryby", "Ryby")' in zrodlo
    assert 'active_tab == "ryby"' in zrodlo
    assert "renderuj_katalog_ryb()" in zrodlo


def test_mostek_powiekszania_zdjec_jest_wstrzykiwany():
    # Klik w zdjęcie ma odpalać pełny ekran Streamlita, a nie otwierać nowej strony.
    zrodlo = io.open(os.path.join(KATALOG_REPO, "app.py"), encoding="utf-8").read()
    assert "zainstaluj_mostek_powiekszania_zdjec()" in zrodlo
    assert '__cretaiMostekZdjecRyb' in zrodlo
    assert 'data-testid="stElementToolbar"' in zrodlo
