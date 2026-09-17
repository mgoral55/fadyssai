"""Testy zadań dla dzieci na trasie, krótkich opisów miejsc i ustawień per profil.

`app.py` jest skryptem Streamlit - import całego modułu uruchomiłby UI, więc testy
wyciągają badane funkcje ze źródła przez AST i uruchamiają je w kontrolowanym
namespace na tymczasowej bazie SQLite.

Uruchomienie:  pytest test_zadania_i_opisy.py
"""

import ast
import csv
import io
import json
import os
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
    "zsynchronizuj_miejsca_z_csv",
]

# Stałe modułowe czytane wprost ze źródła aplikacji, żeby testy nie dublowały ich wartości.
STALE_Z_APP = ["FRAZY_KROKU_BAZOWEGO",
    "KOLUMNY_MIEJSC_Z_CSV",
]

SCHEMAT_USTAWIEN = """
CREATE TABLE ustawienia_profilu (
    uzytkownik TEXT NOT NULL, klucz TEXT NOT NULL, wartosc TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (uzytkownik, klucz));
CREATE TABLE miejsca (
    numer_miejsca TEXT PRIMARY KEY, nazwa TEXT, opis TEXT);
"""

# Baza miejsc: plaża przy domku (46) oraz zwykłe miejsca na trasie z opisem 1-2 słowa w nawiasie.
MIEJSCA_TESTOWE = [
    {
        "numer_miejsca": "46",
        "nazwa": "Plaża w Stavros (piaszczysta zatoka)",
        "typ": "plaża",
        "wspolrzedne": "35.59125, 24.09555",
        "opis": "Słynna zatoka o białym piasku u stóp góry Vardies. Znana z filmu Grek Zorba.",
        "zadania_dla_dzieci": "1. Ułóż z patyków swoje imię.\n2. Połóż się na wodzie.",
    },
    {
        "numer_miejsca": "1",
        "nazwa": "Pałac w Knossos (ruiny pałacu)",
        "typ": "Must have",
        "wspolrzedne": "35.29788, 25.16313",
        "opis": "Najsłynniejsze stanowisko minojskie na Krecie. Labirynt Minotaura i freski.",
        "zadania_dla_dzieci": "1. Znajdź fresk z delfinami.",
    },
    {
        "numer_miejsca": "2",
        "nazwa": "Cretaquarium (akwarium)",
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
        "os": os,
        "json": json,
        "sqlite3": sqlite3,
        "get_db": lambda: sqlite3.connect(sciezka_db, timeout=30.0),
    }
    ns.update(_stale_z_app())
    for _, kod in wczytaj_funkcje_z_app(BADANE_FUNKCJE).items():
        exec(kod, ns)
    ns["_sciezka_db"] = sciezka_db
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
    assert tytuly == ["📍 1. Pałac w Knossos (ruiny pałacu)"]


def test_zadania_z_plazy_przy_domku_gdy_jest_celem_wycieczki(app_ns, df_miejsca):
    kroki = _kroki(
        ("Wyjazd z domku", "35.5914, 24.0918", "46"),
        ("Plaża w Stavros", "35.59125, 24.09555", "46"),
    )
    grupy = app_ns["pobierz_grupy_zadan_dla_wycieczki"]("8", kroki, df_miejsca)

    assert [t for t, _, _ in grupy] == ["📍 46. Plaża w Stavros (piaszczysta zatoka)"]
    assert grupy[0][1] == ["Ułóż z patyków swoje imię.", "Połóż się na wodzie."]


def test_zadania_pomijaja_miejsca_bez_zadan(app_ns, df_miejsca):
    kroki = _kroki(("Cretaquarium", "35.33256, 25.28254", "2"))
    assert app_ns["pobierz_grupy_zadan_dla_wycieczki"]("9", kroki, df_miejsca) == []


# --- USTAWIENIA PER PROFIL ---

def test_flaga_profilu_domyslna_gdy_brak_wpisu(app_ns):
    assert app_ns["pobierz_flage_profilu"]("Magda", "test_klucz", False) is False
    assert app_ns["pobierz_flage_profilu"]("Magda", "test_klucz", True) is True


def test_flaga_profilu_zapisuje_sie_per_uzytkownik(app_ns):
    app_ns["zapisz_flage_profilu"]("Magda", "test_klucz", True)
    app_ns["zapisz_flage_profilu"]("Jerzy", "test_klucz", False)

    assert app_ns["pobierz_flage_profilu"]("Magda", "test_klucz", False) is True
    assert app_ns["pobierz_flage_profilu"]("Jerzy", "test_klucz", True) is False


def test_flaga_profilu_nadpisuje_poprzednia_wartosc(app_ns):
    app_ns["zapisz_flage_profilu"]("Magda", "test_klucz", True)
    app_ns["zapisz_flage_profilu"]("Magda", "test_klucz", False)

    assert app_ns["pobierz_flage_profilu"]("Magda", "test_klucz", True) is False


# --- SYNCHRONIZACJA NAZW MIEJSC Z CSV ---

def _csv_miejsc(sciezka, wiersze):
    with io.open(sciezka, "w", encoding="utf-8", newline="") as f:
        pisarz = csv.DictWriter(f, fieldnames=["numer miejsca", "nazwa", "Opis"])
        pisarz.writeheader()
        for w in wiersze:
            pisarz.writerow(w)
    return str(sciezka)


def _wstaw_miejsca(app_ns, wiersze):
    conn = sqlite3.connect(app_ns["_sciezka_db"])
    conn.executemany(
        "INSERT INTO miejsca (numer_miejsca, nazwa, opis) VALUES (?, ?, ?)", wiersze
    )
    conn.commit()
    conn.close()


def _nazwy_w_bazie(app_ns):
    conn = sqlite3.connect(app_ns["_sciezka_db"])
    wynik = dict(conn.execute("SELECT numer_miejsca, nazwa FROM miejsca"))
    conn.close()
    return wynik


def test_synchronizacja_aktualizuje_nazwy_w_bazie(app_ns, tmp_path):
    _wstaw_miejsca(app_ns, [("1", "Knossos", "Pałac minojski."), ("2", "Cretaquarium", "Akwarium.")])
    plik = _csv_miejsc(tmp_path / "miejsca.csv", [
        {"numer miejsca": "1", "nazwa": "Pałac w Knossos (ruiny pałacu)", "Opis": "Pałac minojski."},
        {"numer miejsca": "2", "nazwa": "Cretaquarium (akwarium)", "Opis": "Akwarium."},
    ])

    assert app_ns["zsynchronizuj_miejsca_z_csv"](plik) == 2
    assert _nazwy_w_bazie(app_ns) == {
        "1": "Pałac w Knossos (ruiny pałacu)",
        "2": "Cretaquarium (akwarium)",
    }


def test_synchronizacja_nie_rusza_zgodnych_nazw(app_ns, tmp_path):
    _wstaw_miejsca(app_ns, [("1", "Pałac w Knossos (ruiny pałacu)", "Pałac minojski.")])
    plik = _csv_miejsc(tmp_path / "miejsca.csv", [
        {"numer miejsca": "1", "nazwa": "Pałac w Knossos (ruiny pałacu)", "Opis": "Pałac minojski."},
    ])

    assert app_ns["zsynchronizuj_miejsca_z_csv"](plik) == 0
    assert _nazwy_w_bazie(app_ns) == {"1": "Pałac w Knossos (ruiny pałacu)"}


def test_synchronizacja_bez_pliku_csv_nic_nie_robi(app_ns, tmp_path):
    _wstaw_miejsca(app_ns, [("1", "Knossos", "Pałac minojski.")])
    assert app_ns["zsynchronizuj_miejsca_z_csv"](str(tmp_path / "nie_ma.csv")) == 0


# --- OPISY MIEJSC W NAWIASIE PRZY NAZWIE W miejsca.csv ---

def _miejsca_z_repo():
    sciezka = os.path.join(os.path.dirname(SCIEZKA_APP), "miejsca.csv")
    with io.open(sciezka, encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if str(r.get("numer miejsca", "")).strip()]


def test_miejsca_csv_nie_ma_oddzielnego_pola_krotki_opis():
    sciezka = os.path.join(os.path.dirname(SCIEZKA_APP), "miejsca.csv")
    with io.open(sciezka, encoding="utf-8", newline="") as f:
        naglowki = [c.lower() for c in csv.DictReader(f).fieldnames]
    assert "krótki opis" not in naglowki
    assert "krotki_opis" not in naglowki


def test_kazde_miejsce_ma_opis_w_nawiasie_na_koncu_nazwy():
    bez_nawiasu = []
    for r in _miejsca_z_repo():
        nazwa = str(r.get("nazwa", "")).strip()
        if not re.search(r'\s*\([^)]+\)$', nazwa):
            bez_nawiasu.append((r["numer miejsca"], nazwa))
    assert bez_nawiasu == [], f"Miejsca bez opisu w nawiasie: {bez_nawiasu}"


def test_opis_w_nawiasie_ma_maksymalnie_dwa_slowa():
    za_dlugie = []
    for r in _miejsca_z_repo():
        nazwa = str(r.get("nazwa", "")).strip()
        m = re.search(r'\(([^)]+)\)$', nazwa)
        if m:
            slowa = m.group(1).split()
            if len(slowa) < 1 or len(slowa) > 2:
                za_dlugie.append((r["numer miejsca"], nazwa, len(slowa)))
    assert za_dlugie == [], f"Opisy o innej liczbie słów niż 1-2: {za_dlugie}"


def test_wyczysc_nazwe_miejsca_usuwa_opis_w_nawiasie(app_ns):
    czysta = app_ns["_wyczysc_nazwe_miejsca"]("Pałac Minojski w Knossos (ruiny pałacu)")
    assert czysta == "pałac minojski w knossos"
    czysta_akw = app_ns["_wyczysc_nazwe_miejsca"]("Cretaquarium (akwarium)")
    assert czysta_akw == "cretaquarium"
