"""Testy regresyjne kolejności kroków i posiłków w planie wycieczki.

`app.py` jest skryptem Streamlit - import całego modułu uruchomiłby UI, więc testy
wyciągają badane funkcje ze źródła przez AST i uruchamiają je na tymczasowej bazie
SQLite. Testowany jest prawdziwy kod funkcji; podmieniane są tylko zależności
spoza zakresu tych testów (walidacja AuDHD i przeliczanie tras z OSRM).

Uruchomienie:  pytest test_plan_kroki.py
"""

import re
import sqlite3

import pandas as pd
import pytest

from conftest import wczytaj_funkcje_z_app

# Funkcje wyciągane ze źródła aplikacji i uruchamiane w testach bez zmian.
BADANE_FUNKCJE = [
    "_reindex_kroki",
    "_wstaw_krok_do_wycieczki",
    "_usun_krok_z_wycieczki",
    "_usun_pozostale_kolacje",
    "sparsuj_godzine_minuty",
    "znajdz_id_kroku_w_db",
    "szukaj_miejsca_w_bazie",
    "przenies_krok_wycieczki",
    "dodaj_krok_wycieczki",
    "zarzadzaj_posilkiem_kroku",
    "usun_krok_wycieczki",
    "formatuj_posilki_kroku",
]

SCHEMAT = """
CREATE TABLE wycieczka (id TEXT PRIMARY KEY, tytul_wycieczki TEXT);
CREATE TABLE krok_wycieczki (
    id INTEGER PRIMARY KEY AUTOINCREMENT, id_wycieczki TEXT, krok_wycieczki INTEGER,
    numer_miejsca TEXT, nazwa TEXT, wspolrzedne TEXT, okienko_zwiedzania TEXT,
    podsumowanie_taktyki TEXT, opis TEXT);
CREATE TABLE posilki_kroku (
    id INTEGER PRIMARY KEY AUTOINCREMENT, id_kroku INTEGER, rodzaj_posilku TEXT,
    miejsce TEXT, sugerowana_godzina TEXT, opis TEXT);
CREATE TABLE miejsca (
    numer_miejsca TEXT, nazwa TEXT, nazwa_angielska TEXT, adres TEXT, typ TEXT,
    wspolrzedne TEXT, czas_dojazdu TEXT, orientacyjny_czas TEXT, godziny_otwarcia TEXT,
    konieczna_akcja TEXT, ochrona_slonce TEXT, potencjal_meltdownu TEXT,
    strategie_meltdown TEXT, opis TEXT, odwiedzone INTEGER);
CREATE TABLE zakupy (id INTEGER PRIMARY KEY, id_kroku INTEGER);
CREATE TABLE czasy_dojazdu (
    id INTEGER PRIMARY KEY, id_kroku_z INTEGER, id_kroku_do INTEGER,
    czas_przejazdu TEXT, szacowany_czas_postoju INTEGER);
"""

MIEJSCA_TESTOWE = [
    ("6", "Argyroupoli Waterfalls", "Must have"),
    ("8", "Ancient Lappa", "Must have"),
    ("31", "Lappa Avocado", "shop"),
    ("50", "Tawerna Pasiphae", "tawerna"),
    ("51", "Plaza Falasarna", "beach"),
    ("52", "Muzeum Chania", "museum"),
    ("53", "Sklep przy domku w Stavros", "shop"),
]


class Plan:
    """Tymczasowa baza planu wycieczki wraz z badanymi funkcjami aplikacji."""

    def __init__(self, sciezka_db):
        self.sciezka_db = str(sciezka_db)
        self.conn = sqlite3.connect(self.sciezka_db)
        self.conn.executescript(SCHEMAT)
        for nr, nazwa, typ in MIEJSCA_TESTOWE:
            self.conn.execute(
                "INSERT INTO miejsca (numer_miejsca, nazwa, typ, wspolrzedne, opis, odwiedzone)"
                " VALUES (?, ?, ?, ?, ?, 0)",
                (nr, nazwa, typ, "35.2000, 24.3000", f"opis {nazwa}"),
            )
        self.conn.commit()

        self.ns = {
            "pd": pd,
            "re": re,
            "sqlite3": sqlite3,
            "SKLEP_LAT": 35.586222,
            "SKLEP_LON": 24.091861,
            "GODZINA_GRANICZNA_KOLACJI": 17.0,
            "get_db": lambda: sqlite3.connect(self.sciezka_db, timeout=30.0),
            # Poza zakresem tych testów: walidacja AuDHD i przeliczanie tras (OSRM, sieć).
            "sprawdz_ryzyka_audhd_dla_kroku": lambda *a, **k: (True, ""),
            "przelicz_i_zsynchronizuj_wycieczke": lambda *a, **k: None,
        }
        for nazwa_f, kod in wczytaj_funkcje_z_app(BADANE_FUNKCJE).items():
            exec(kod, self.ns)

    def __getattr__(self, nazwa):
        return self.ns[nazwa]

    def utworz(self, id_wycieczki, nazwy_krokow):
        self.conn.execute(
            "INSERT INTO wycieczka (id, tytul_wycieczki) VALUES (?, ?)",
            (id_wycieczki, f"test {id_wycieczki}"),
        )
        ids = []
        for pozycja, nazwa in enumerate(nazwy_krokow):
            kursor = self.conn.execute(
                "INSERT INTO krok_wycieczki (id_wycieczki, krok_wycieczki, nazwa, wspolrzedne, okienko_zwiedzania)"
                " VALUES (?, ?, ?, ?, ?)",
                (id_wycieczki, pozycja, nazwa, "35.5000, 24.0000", "10:00 - 11:00"),
            )
            ids.append(kursor.lastrowid)
        self.conn.commit()
        return ids

    def dodaj_posilek(self, id_kroku, rodzaj, miejsce, godzina, opis):
        self.conn.execute(
            "INSERT INTO posilki_kroku (id_kroku, rodzaj_posilku, miejsce, sugerowana_godzina, opis)"
            " VALUES (?, ?, ?, ?, ?)",
            (id_kroku, rodzaj, miejsce, godzina, opis),
        )
        self.conn.commit()

    def kolejnosc(self, id_wycieczki):
        return [
            r[0]
            for r in self.conn.execute(
                "SELECT nazwa FROM krok_wycieczki WHERE id_wycieczki = ?"
                " ORDER BY CAST(krok_wycieczki AS INTEGER) ASC, id ASC",
                (id_wycieczki,),
            )
        ]

    def posilki(self, id_wycieczki):
        return list(
            self.conn.execute(
                "SELECT k.nazwa, p.rodzaj_posilku, p.miejsce, p.sugerowana_godzina"
                " FROM posilki_kroku p JOIN krok_wycieczki k ON k.id = p.id_kroku"
                " WHERE k.id_wycieczki = ? ORDER BY CAST(k.krok_wycieczki AS INTEGER) ASC",
                (id_wycieczki,),
            )
        )

    def numer_miejsca_kroku(self, id_kroku):
        return self.conn.execute(
            "SELECT numer_miejsca FROM krok_wycieczki WHERE id = ?", (id_kroku,)
        ).fetchone()[0]


@pytest.fixture
def plan(tmp_path):
    return Plan(tmp_path / "test.db")


# --- Kolejność kroków ---

def test_dodanie_kroku_nie_przestawia_istniejacych(plan):
    """Nowy krok trafia przed powrót do domku, reszta trasy zostaje bez zmian."""
    plan.utworz("1", ["Nasz Domek (Start)", "Plaza Falasarna", "Sklep przy domku w Stavros", "Nasz Domek (Powrot)"])
    plan.dodaj_krok_wycieczki("1", "Muzeum Chania", okienko_zwiedzania="14:00 - 15:00")
    assert plan.kolejnosc("1") == [
        "Nasz Domek (Start)", "Plaza Falasarna", "Sklep przy domku w Stavros",
        "Muzeum Chania", "Nasz Domek (Powrot)",
    ]


def test_pozycja_start_wstawia_za_krokiem_startowym(plan):
    plan.utworz("2", ["Nasz Domek (Start)", "Plaza Falasarna", "Nasz Domek (Powrot)"])
    with sqlite3.connect(plan.sciezka_db) as conn:
        plan._wstaw_krok_do_wycieczki(
            conn.cursor(), "2", "Rynek w Chanii (Laiki)", "35.5118, 24.0239",
            "08:30 - 09:30", "", pozycja="start",
        )
    assert plan.kolejnosc("2") == [
        "Nasz Domek (Start)", "Rynek w Chanii (Laiki)", "Plaza Falasarna", "Nasz Domek (Powrot)",
    ]


def test_jawny_indeks_docelowy_ma_pierwszenstwo(plan):
    plan.utworz("3", ["Nasz Domek (Start)", "Plaza Falasarna", "Nasz Domek (Powrot)"])
    with sqlite3.connect(plan.sciezka_db) as conn:
        plan._wstaw_krok_do_wycieczki(
            conn.cursor(), "3", "Muzeum Chania", "35.5, 24.0",
            "10:00 - 11:00", "", indeks_docelowy=1,
        )
    assert plan.kolejnosc("3") == [
        "Nasz Domek (Start)", "Muzeum Chania", "Plaza Falasarna", "Nasz Domek (Powrot)",
    ]


@pytest.mark.parametrize(
    "kroki_poczatkowe,oczekiwana",
    [
        ([], ["Nowy Krok"]),
        (["Nasz Domek (Start)"], ["Nasz Domek (Start)", "Nowy Krok"]),
    ],
)
def test_krancowe_przypadki_pozycji_koniec(plan, kroki_poczatkowe, oczekiwana):
    """Pusta trasa i trasa z samym krokiem startowym nie mogą wpaść w gałąź 'przed powrotem'."""
    plan.utworz("4", kroki_poczatkowe)
    with sqlite3.connect(plan.sciezka_db) as conn:
        plan._wstaw_krok_do_wycieczki(
            conn.cursor(), "4", "Nowy Krok", "35.5, 24.0", "10:00 - 11:00", "",
        )
    assert plan.kolejnosc("4") == oczekiwana


# --- Rodzaj posiłku: obiad vs kolacja ---

def test_wieczorna_tawerna_zapisuje_sie_jako_kolacja(plan):
    ids = plan.utworz("5", ["Nasz Domek (Start)", "Plaza Falasarna", "Nasz Domek (Powrot)"])
    plan.dodaj_posilek(ids[-1], "kolacja", "w domku", "18:00", "Kolacja")

    plan.dodaj_krok_wycieczki("5", "Tawerna Pasiphae", okienko_zwiedzania="19:00 - 20:30")

    assert plan.kolejnosc("5") == [
        "Nasz Domek (Start)", "Plaza Falasarna", "Tawerna Pasiphae", "Nasz Domek (Powrot)",
    ]
    # Kolacja w tawernie zastępuje domyślną kolację w domku - jedna kolacja na wycieczkę.
    assert plan.posilki("5") == [("Tawerna Pasiphae", "kolacja", "restauracja", "19:00")]


def test_tawerna_w_srodku_dnia_zostaje_obiadem(plan):
    plan.utworz("6", ["Nasz Domek (Start)", "Nasz Domek (Powrot)"])
    plan.dodaj_krok_wycieczki("6", "Tawerna Pasiphae", okienko_zwiedzania="12:30 - 14:00")
    assert plan.posilki("6") == [("Tawerna Pasiphae", "obiad", "restauracja", "12:30")]


def test_kolacja_w_kroku_kasuje_pozostale_kolacje(plan):
    ids = plan.utworz("7", ["Nasz Domek (Start)", "Tawerna Pasiphae", "Nasz Domek (Powrot)"])
    plan.dodaj_posilek(ids[-1], "kolacja", "w domku", "18:00", "Kolacja")

    plan.zarzadzaj_posilkiem_kroku(
        "7", ids[1], "kolacja", miejsce="restauracja",
        sugerowana_godzina="19:30", opis="Kolacja w tawernie",
    )

    assert plan.posilki("7") == [("Tawerna Pasiphae", "kolacja", "restauracja", "19:30")]
    # Bez kolacji w domku Hangry Guard nie blokuje już usunięcia kroku powrotnego.
    assert plan.usun_krok_wycieczki("7", ids[-1]).get("success") is True


# --- Rozpoznawanie nazwy miejsca ---

def test_sklejona_nazwa_dwoch_miejsc_jest_odrzucana(plan):
    """Regresja: 'Ancient Lappa & Lappa Avocado' tworzyło krok-widmo pod współrzędnymi sklepu."""
    plan.utworz("8", ["Nasz Domek (Start)", "Nasz Domek (Powrot)"])

    wynik = plan.dodaj_krok_wycieczki("8", "Ancient Lappa & Lappa Avocado", okienko_zwiedzania="09:45 - 11:15")

    assert wynik.get("success") is False
    assert plan.kolejnosc("8") == ["Nasz Domek (Start)", "Nasz Domek (Powrot)"]


def test_kazde_miejsce_dodane_osobno_jest_wlasnym_krokiem(plan):
    plan.utworz("9", ["Nasz Domek (Start)", "Nasz Domek (Powrot)"])

    wynik = plan.dodaj_krok_wycieczki("9", "Ancient Lappa", okienko_zwiedzania="09:45 - 11:15")

    assert wynik.get("success") is True
    assert plan.kolejnosc("9") == ["Nasz Domek (Start)", "Ancient Lappa", "Nasz Domek (Powrot)"]
    assert plan.numer_miejsca_kroku(wynik["id_kroku"]) == "8"


# --- Prezentacja posiłków ---

def test_obiad_w_tawernie_nie_ukrywa_kolacji(plan):
    df = pd.DataFrame([
        {"rodzaj_posilku": "obiad", "miejsce": "restauracja", "sugerowana_godzina": "12:30", "opis": "Tawerna"},
        {"rodzaj_posilku": "kolacja", "miejsce": "restauracja", "sugerowana_godzina": "19:00", "opis": "Kolacja"},
    ])
    wynik = plan.formatuj_posilki_kroku(df)
    assert "Obiad" in wynik and "Kolacja" in wynik


def test_obiad_w_domku_nadal_zastepuje_kolacje(plan):
    df = pd.DataFrame([
        {"rodzaj_posilku": "obiad", "miejsce": "w domku", "sugerowana_godzina": "15:00", "opis": "Obiad"},
        {"rodzaj_posilku": "kolacja", "miejsce": "w domku", "sugerowana_godzina": "18:00", "opis": "Kolacja"},
    ])
    wynik = plan.formatuj_posilki_kroku(df)
    assert "Obiad" in wynik and "Kolacja" not in wynik
