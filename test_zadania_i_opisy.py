"""Testy zadań dla dzieci na trasie, krótkich opisów miejsc i ustawień per profil.

`app.py` jest skryptem Streamlit - import całego modułu uruchomiłby UI, więc testy
wyciągają badane funkcje ze źródła przez AST i uruchamiają je w kontrolowanym
namespace na tymczasowej bazie SQLite.

Uruchomienie:  pytest test_zadania_i_opisy.py
"""

import ast
import io
import json
import re
import sqlite3

import pandas as pd
import pytest

from conftest import SCIEZKA_APP, wczytaj_funkcje_z_app

BADANE_FUNKCJE = [
    "sparsuj_wspolrzedne",
    "_wyczysc_nazwe_miejsca",
    "czy_krok_bazowy",
    "skroc_opis_miejsca",
    "dopasuj_krok_do_bazy_miejsc",
    "sparsuj_liste_zadan",
    "pobierz_grupy_zadan_dla_wycieczki",
    "pobierz_flage_profilu",
    "zapisz_flage_profilu",
]

# Stałe modułowe czytane wprost ze źródła aplikacji, żeby testy nie dublowały ich wartości.
STALE_Z_APP = ["FRAZY_KROKU_BAZOWEGO"]

SCHEMAT_USTAWIEN = """
CREATE TABLE ustawienia_profilu (
    uzytkownik TEXT NOT NULL, klucz TEXT NOT NULL, wartosc TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (uzytkownik, klucz));
"""

# Baza miejsc: plaża przy domku (46) oraz zwykłe miejsca na trasie.
MIEJSCA_TESTOWE = [
    {
        "numer_miejsca": "46",
        "nazwa": "Plaża w Stavros",
        "typ": "plaża",
        "wspolrzedne": "35.59125, 24.09555",
        "opis": "Słynna zatoka o białym piasku u stóp góry Vardies. Znana z filmu Grek Zorba.",
        "zadania_dla_dzieci": "1. Ułóż z patyków swoje imię.\n2. Połóż się na wodzie.",
    },
    {
        "numer_miejsca": "1",
        "nazwa": "Pałac w Knossos",
        "typ": "Must have",
        "wspolrzedne": "35.29788, 25.16313",
        "opis": "Najsłynniejsze stanowisko minojskie na Krecie. Labirynt Minotaura i freski.",
        "zadania_dla_dzieci": "1. Znajdź fresk z delfinami.",
    },
    {
        "numer_miejsca": "2",
        "nazwa": "Cretaquarium",
        "typ": "Must have",
        "wspolrzedne": "35.33256, 25.28254",
        "opis": "Jedno z największych akwariów w Europie.",
        "zadania_dla_dzieci": "",
    },
]


def _stale_z_app():
    zrodlo = io.open(SCIEZKA_APP, encoding="utf-8").read()
    drzewo = ast.parse(zrodlo)
    wartosci = {}
    for wezel in drzewo.body:
        if isinstance(wezel, ast.Assign):
            for cel in wezel.targets:
                if isinstance(cel, ast.Name) and cel.id in STALE_Z_APP:
                    wartosci[cel.id] = ast.literal_eval(wezel.value)
    brakujace = [n for n in STALE_Z_APP if n not in wartosci]
    assert not brakujace, f"Nie znaleziono stałych w app.py: {brakujace}"
    return wartosci


@pytest.fixture
def app_ns(tmp_path):
    sciezka_db = str(tmp_path / "test_ustawienia.db")
    conn = sqlite3.connect(sciezka_db)
    conn.executescript(SCHEMAT_USTAWIEN)
    conn.commit()
    conn.close()

    ns = {
        "pd": pd,
        "re": re,
        "json": json,
        "sqlite3": sqlite3,
        "get_db": lambda: sqlite3.connect(sciezka_db, timeout=30.0),
    }
    ns.update(_stale_z_app())
    for _, kod in wczytaj_funkcje_z_app(BADANE_FUNKCJE).items():
        exec(kod, ns)
    return ns


@pytest.fixture
def df_miejsca():
    return pd.DataFrame(MIEJSCA_TESTOWE)


def _kroki(*wiersze):
    return pd.DataFrame(
        [
            {"id": i + 1, "nazwa": n, "wspolrzedne": w, "numer_miejsca": nr}
            for i, (n, w, nr) in enumerate(wiersze)
        ]
    )


# --- KROKI BAZOWE ---

@pytest.mark.parametrize("nazwa", [
    "Wyjazd z domku",
    "Powrót do domku",
    "Nasz Domek (Start)",
    "Nasz Domek (Powrót)",
    "Sklep przy domku w Stavros",
])
def test_czy_krok_bazowy_wykrywa_kroki_domku(app_ns, nazwa):
    assert app_ns["czy_krok_bazowy"](nazwa) is True


@pytest.mark.parametrize("nazwa", [
    "Pałac w Knossos",
    "Cretaquarium",
    "Plaża Kalathas",
    "Rynek w Chanii",
])
def test_czy_krok_bazowy_przepuszcza_zwykle_miejsca(app_ns, nazwa):
    assert app_ns["czy_krok_bazowy"](nazwa) is False


def test_czy_krok_bazowy_obsluguje_puste_wartosci(app_ns):
    assert app_ns["czy_krok_bazowy"](None) is False
    assert app_ns["czy_krok_bazowy"]("") is False


# --- ZADANIA DLA DZIECI ---

def test_zadania_pomijaja_start_i_powrot_mimo_fk_na_plaze(app_ns, df_miejsca):
    # Krokom "Wyjazd z domku" i "Powrót do domku" baza przypisuje FK 46 (plaża przy domku),
    # przez co zadania z tej plaży dublowały się na początku i końcu trasy.
    kroki = _kroki(
        ("Wyjazd z domku", "35.5914, 24.0918", "46"),
        ("Pałac w Knossos", "35.29788, 25.16313", "1"),
        ("Powrót do domku", "35.5914, 24.0918", "46"),
    )
    grupy = app_ns["pobierz_grupy_zadan_dla_wycieczki"]("7", kroki, df_miejsca)

    tytuly = [t for t, _, _ in grupy]
    assert tytuly == ["📍 1. Pałac w Knossos"]


def test_zadania_z_plazy_przy_domku_gdy_jest_celem_wycieczki(app_ns, df_miejsca):
    kroki = _kroki(
        ("Wyjazd z domku", "35.5914, 24.0918", "46"),
        ("Plaża w Stavros", "35.59125, 24.09555", "46"),
    )
    grupy = app_ns["pobierz_grupy_zadan_dla_wycieczki"]("8", kroki, df_miejsca)

    assert [t for t, _, _ in grupy] == ["📍 46. Plaża w Stavros"]
    assert grupy[0][1] == ["Ułóż z patyków swoje imię.", "Połóż się na wodzie."]


def test_zadania_pomijaja_miejsca_bez_zadan(app_ns, df_miejsca):
    kroki = _kroki(("Cretaquarium", "35.33256, 25.28254", "2"))
    assert app_ns["pobierz_grupy_zadan_dla_wycieczki"]("9", kroki, df_miejsca) == []


# --- KRÓTKI OPIS MIEJSCA ---

def test_skroc_opis_zwraca_pierwsze_zdanie(app_ns):
    opis = "Jedno z największych akwariów w Europie. Rekiny, płaszczki i meduzy w klimatyzowanych salach."
    assert app_ns["skroc_opis_miejsca"](opis) == "Jedno z największych akwariów w Europie."


def test_skroc_opis_normalizuje_biale_znaki(app_ns):
    assert app_ns["skroc_opis_miejsca"]("Spokojna\n  zatoczka   blisko Stavros.") == "Spokojna zatoczka blisko Stavros."


def test_skroc_opis_przycina_dlugie_zdanie_bez_kropki(app_ns):
    opis = "Imponujące stanowisko archeologiczne na płaskowyżu nad Zatoką Souda z rzymskimi cysternami o niesamowitej akustyce oraz osmańskim fortem"
    wynik = app_ns["skroc_opis_miejsca"](opis, max_znakow=60)

    assert len(wynik) <= 61  # 60 znaków + wielokropek
    assert wynik.endswith("…")
    assert opis.startswith(wynik[:-1].rstrip())


@pytest.mark.parametrize("pusty", [None, "", "   ", "None", "nan", "Brak", float("nan")])
def test_skroc_opis_dla_pustych_wartosci(app_ns, pusty):
    assert app_ns["skroc_opis_miejsca"](pusty) == ""


# --- USTAWIENIA PER PROFIL ---

def test_flaga_profilu_domyslna_gdy_brak_wpisu(app_ns):
    assert app_ns["pobierz_flage_profilu"]("Magda", "krotki_opis_miejsc", False) is False
    assert app_ns["pobierz_flage_profilu"]("Magda", "krotki_opis_miejsc", True) is True


def test_flaga_profilu_zapisuje_sie_per_uzytkownik(app_ns):
    app_ns["zapisz_flage_profilu"]("Magda", "krotki_opis_miejsc", True)
    app_ns["zapisz_flage_profilu"]("Jerzy", "krotki_opis_miejsc", False)

    assert app_ns["pobierz_flage_profilu"]("Magda", "krotki_opis_miejsc", False) is True
    assert app_ns["pobierz_flage_profilu"]("Jerzy", "krotki_opis_miejsc", True) is False


def test_flaga_profilu_nadpisuje_poprzednia_wartosc(app_ns):
    app_ns["zapisz_flage_profilu"]("Magda", "krotki_opis_miejsc", True)
    app_ns["zapisz_flage_profilu"]("Magda", "krotki_opis_miejsc", False)

    assert app_ns["pobierz_flage_profilu"]("Magda", "krotki_opis_miejsc", True) is False
