"""Testy regresyjne pustych komórek bazy w widokach.

Kolumny TEXT z NULL-ami wracały z pandas 2 jako `None`, a od pandas 3 jako `nan`
(`StringDtype(na_value=nan)`). Widoki sprawdzały pustkę własnymi listami zaślepek
(`not in ["None", "Brak"]`), więc po podbiciu wersji napis "nan" pojawił się rodzicowi
na karcie wycieczki - w godzinie ewakuacji, ostrzeżeniu czerwonej strefy i taktyce kroku.

Pierwszy test przybija zachowanie pandas (żeby kolejna zmiana wersji nie przeszła po cichu),
reszta pilnuje jednego wspólnego filtra `tekst_z_bazy` i tego, że karta wycieczki faktycznie
przez niego przepuszcza kolumny, które potrafią być puste.

Uruchomienie:  pytest test_puste_pola_bazy.py
"""

import ast
import io
import sqlite3

import pandas as pd
import pytest

from conftest import SCIEZKA_APP, wczytaj_funkcje_z_app, wczytaj_stale_z_app

# Kolumny kroku, które w bazie bywają puste (AI tworzy krok bez nich) i trafiają wprost do HTML.
KOLUMNY_KROKU_BYWAJA_PUSTE = {
    "godzina_ewakuacji",
    "czerwona_strefa_ostrzezenie",
    "strefa_luzu_i_regeneracji",
    "podsumowanie_taktyki",
    "opis",
    "okienko_zwiedzania",
}


@pytest.fixture(scope="module")
def tekst_z_bazy():
    ns = {"pd": pd, **wczytaj_stale_z_app(["ZASLEPKI_BAZY"])}
    exec(wczytaj_funkcje_z_app(["tekst_z_bazy"])["tekst_z_bazy"], ns)
    return ns["tekst_z_bazy"]


@pytest.fixture(scope="module")
def zrodlo_app():
    return io.open(SCIEZKA_APP, encoding="utf-8").read()


def test_pusta_komorka_text_wraca_z_pandas_jako_nan():
    """Źródło błędu: NULL w kolumnie TEXT to dziś `nan`, a `str(nan)` to napis "nan"."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE krok (godzina_ewakuacji TEXT)")
    conn.execute("INSERT INTO krok VALUES ('17:30')")
    conn.execute("INSERT INTO krok VALUES (NULL)")

    df = pd.read_sql("SELECT * FROM krok", conn)
    pusta = df.iloc[1]["godzina_ewakuacji"]

    assert pd.isna(pusta)
    assert str(pusta) == "nan", "Gdyby pandas wrócił do None, komentarz przy tekst_z_bazy jest do poprawy"


@pytest.mark.parametrize("pusta", [None, float("nan"), pd.NA, "", "   ", "-", "—", "nan", "NaN", "None", "Brak", "brak"])
def test_pustka_i_zaslepki_schodza_do_wartosci_domyslnej(tekst_z_bazy, pusta):
    """Każda forma pustki daje to samo, niezależnie od tego, czy przyszła z pandas, czy z CSV."""
    assert tekst_z_bazy(pusta) == ""
    assert tekst_z_bazy(pusta, "{TODO}") == "{TODO}"


@pytest.mark.parametrize("wejscie, oczekiwane", [
    ("17:30", "17:30"),
    ("  Unikaj plaży po 11:00  ", "Unikaj plaży po 11:00"),
    ("Brak cienia na trasie", "Brak cienia na trasie"),
    (0, "0"),
    (12, "12"),
])
def test_prawdziwa_wartosc_przechodzi_bez_zmian(tekst_z_bazy, wejscie, oczekiwane):
    """Filtr obcina białe znaki i nic poza tym - "Brak cienia" to treść, nie zaślepka."""
    assert tekst_z_bazy(wejscie) == oczekiwane


def test_wartosc_nieskalarna_nie_wysypuje_filtra(tekst_z_bazy):
    """`pd.isna` na liście rzuca - taka wartość ma przejść jako tekst, nie wywalić renderu."""
    assert tekst_z_bazy(["a", "b"]) == "['a', 'b']"


def _wezel_funkcji(zrodlo, nazwa):
    for wezel in ast.parse(zrodlo).body:
        if isinstance(wezel, ast.FunctionDef) and wezel.name == nazwa:
            return wezel
    raise AssertionError(f"Nie znaleziono funkcji w app.py: {nazwa}")


def _odczyty_kolumn(wezel, kolumny):
    """Zwraca {(nazwa_kolumny, id_wezla)} dla wywołań `cos.get("kolumna")` w tej funkcji."""
    znalezione = set()
    for w in ast.walk(wezel):
        if not isinstance(w, ast.Call) or not isinstance(w.func, ast.Attribute) or w.func.attr != "get":
            continue
        if w.args and isinstance(w.args[0], ast.Constant) and w.args[0].value in kolumny:
            znalezione.add((w.args[0].value, id(w)))
    return znalezione


def _odczyty_pod_filtrem(wezel, kolumny):
    """To samo, ale wyłącznie dla odczytów będących argumentem `tekst_z_bazy(...)`."""
    znalezione = set()
    for w in ast.walk(wezel):
        if isinstance(w, ast.Call) and isinstance(w.func, ast.Name) and w.func.id == "tekst_z_bazy":
            for arg in w.args:
                znalezione |= _odczyty_kolumn(arg, kolumny)
    return znalezione


@pytest.mark.parametrize("nazwa_funkcji", ["renderuj_karte_wycieczki", "generuj_autonomiczny_pakiet_offline_html"])
def test_widok_czyta_puste_kolumny_tylko_przez_filtr(zrodlo_app, nazwa_funkcji):
    """Kolumna, która bywa pusta, nie może iść do HTML z pominięciem `tekst_z_bazy`."""
    wezel = _wezel_funkcji(zrodlo_app, nazwa_funkcji)
    wszystkie = _odczyty_kolumn(wezel, KOLUMNY_KROKU_BYWAJA_PUSTE)
    przefiltrowane = _odczyty_pod_filtrem(wezel, KOLUMNY_KROKU_BYWAJA_PUSTE)

    bez_filtra = sorted({nazwa for nazwa, _ in wszystkie - przefiltrowane})
    assert not bez_filtra, f"{nazwa_funkcji}: kolumny czytane z pominięciem tekst_z_bazy: {bez_filtra}"
