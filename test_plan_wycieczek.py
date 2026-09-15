"""Testy planowania wycieczek po dacie: selektor Trasy Dnia, agenda, zapis z zastąpieniem, migracja.

Warstwa bazy dostaje prawdziwe SQLite w pamięci podstawione za `get_db`, logika wyboru i agendy
to czyste funkcje. Uruchomienie:  pytest test_plan_wycieczek.py
"""

import sqlite3
from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from conftest import wczytaj_funkcje_z_app

FUNKCJE_CZYSTE = [
    "sparsuj_date_iso",
    "sformatuj_date_krotko_pl",
    "opisz_odleglosc_dnia",
    "posortuj_zaplanowane",
    "wybierz_trase_dnia",
    "zbuduj_wiersze_agendy",
    "odmien_wycieczki",
    "opisz_plan_wyjazdu_dla_ai",
]
FUNKCJE_BAZY = [
    "zmigruj_aktywna_wycieczke_na_daty",
    "znajdz_wycieczke_w_dniu",
    "zaplanuj_wycieczke",
    "odplanuj_wycieczke",
    "pobierz_zaplanowane_wycieczki",
    "pobierz_niezaplanowane_wycieczki",
]

DZIS = date(2026, 9, 15)


def _namespace(get_db=None):
    ns = {
        "datetime": datetime,
        "date": date,
        "timedelta": timedelta,
        "pd": pd,
        "DNI_TYGODNIA_SKROT_PL": ["pn", "wt", "śr", "cz", "pt", "so", "nd"],
    }
    if get_db is not None:
        ns["get_db"] = get_db
    for kod in wczytaj_funkcje_z_app(FUNKCJE_CZYSTE + FUNKCJE_BAZY).values():
        exec(kod, ns)
    return ns


F = _namespace()


def w(id_, data, tytul="", odbyta=False):
    return {"id": str(id_), "data": data, "tytul": tytul or f"Wycieczka {id_}", "odbyta": odbyta}


# --- Parsowanie i etykiety ---

def test_sparsuj_date_iso_odrzuca_smieci_i_puste():
    assert F["sparsuj_date_iso"]("2026-09-17") == date(2026, 9, 17)
    for smiec in (None, "", "   ", "nan", "None", "-", "17.09.2026", "2026-13-01"):
        assert F["sparsuj_date_iso"](smiec) is None, smiec


def test_krotka_etykieta_daty_miesci_dzien_tygodnia_i_date():
    assert F["sformatuj_date_krotko_pl"](date(2026, 9, 17)) == "cz 17.09"
    assert F["sformatuj_date_krotko_pl"](date(2026, 9, 6)) == "nd 06.09"


@pytest.mark.parametrize(
    "data, odbyta, oczekiwane",
    [
        (DZIS, False, "dziś"),
        (DZIS + timedelta(days=1), False, "jutro"),
        (DZIS + timedelta(days=3), False, "za 3 dni"),
        (DZIS - timedelta(days=1), False, "wczoraj"),
        (DZIS - timedelta(days=4), False, "minęła 4 dni temu"),
        (DZIS + timedelta(days=3), True, "odbyta ✓"),
    ],
)
def test_chip_odleglosci_dnia(data, odbyta, oczekiwane):
    assert F["opisz_odleglosc_dnia"](data, DZIS, odbyta) == oczekiwane


def test_odmiana_liczby_wycieczek():
    odmien = F["odmien_wycieczki"]
    assert odmien(1) == "wycieczka"
    assert odmien(2) == "wycieczki"
    assert odmien(4) == "wycieczki"
    assert odmien(5) == "wycieczek"
    assert odmien(12) == "wycieczek"
    assert odmien(22) == "wycieczki"


# --- Selektor Trasy Dnia ---

PLAN = [
    w(3, DZIS - timedelta(days=2), "Balos", odbyta=True),
    w(1, DZIS + timedelta(days=1), "Knossos"),
    w(7, DZIS + timedelta(days=4), "Elafonisi"),
]


def test_domyslnie_najblizsza_przyszla_wycieczka():
    assert F["wybierz_trase_dnia"](PLAN, DZIS) == ("1", "3", "7")


def test_dzisiejsza_wycieczka_liczy_sie_jako_najblizsza():
    plan = [w(3, DZIS - timedelta(days=1)), w(5, DZIS), w(6, DZIS + timedelta(days=2))]
    assert F["wybierz_trase_dnia"](plan, DZIS)[0] == "5"


def test_gdy_wszystkie_minely_pokazuje_ostatnia():
    plan = [w(3, DZIS - timedelta(days=9)), w(4, DZIS - timedelta(days=2))]
    assert F["wybierz_trase_dnia"](plan, DZIS) == ("4", "3", None)


def test_pusta_lista_daje_same_none():
    assert F["wybierz_trase_dnia"]([], DZIS) == (None, None, None)


def test_wybor_strzalkami_wygrywa_nad_domyslna():
    assert F["wybierz_trase_dnia"](PLAN, DZIS, wybrane_id="7") == ("7", "1", None)
    assert F["wybierz_trase_dnia"](PLAN, DZIS, wybrane_id=3) == ("3", None, "1")


def test_niewazny_wybor_po_odplanowaniu_wraca_do_domyslnej():
    assert F["wybierz_trase_dnia"](PLAN, DZIS, wybrane_id="99")[0] == "1"


def test_sortowanie_po_dacie_potem_po_id():
    plan = [w(9, DZIS + timedelta(days=2)), w(2, DZIS), w(10, DZIS)]
    assert [x["id"] for x in F["posortuj_zaplanowane"](plan)] == ["2", "10", "9"]


# --- Agenda ---

def test_agenda_pokazuje_dziury_i_zwija_dlugie_przerwy():
    plan = [
        w(1, date(2026, 9, 14)),
        w(2, date(2026, 9, 16)),
        w(3, date(2026, 9, 25)),
    ]
    wiersze = F["zbuduj_wiersze_agendy"](plan, DZIS)
    typy = [(r["typ"], r.get("data") or r.get("od")) for r in wiersze]
    assert typy == [
        ("wycieczka", date(2026, 9, 14)),
        ("wolny", date(2026, 9, 15)),
        ("wycieczka", date(2026, 9, 16)),
        ("wolne", date(2026, 9, 17)),
        ("wycieczka", date(2026, 9, 25)),
    ]
    zwinieta = wiersze[3]
    assert zwinieta["do"] == date(2026, 9, 24) and zwinieta["dni"] == 8
    assert wiersze[1]["dzis"] is True and zwinieta["dzis"] is False


def test_agenda_krotka_przerwa_zostaje_dzien_po_dniu():
    plan = [w(1, date(2026, 9, 14)), w(2, date(2026, 9, 18))]
    wiersze = F["zbuduj_wiersze_agendy"](plan, DZIS)
    assert [r["typ"] for r in wiersze] == ["wycieczka", "wolny", "wolny", "wolny", "wycieczka"]


def test_agenda_pusta_bez_wycieczek():
    assert F["zbuduj_wiersze_agendy"]([], DZIS) == []


def test_opis_planu_dla_ai_wymienia_daty_i_wycieczki_bez_daty():
    opis = F["opisz_plan_wyjazdu_dla_ai"](PLAN, [{"id": "5", "tytul": "Spinalonga"}], DZIS)
    assert "2026-09-16 (śr) #1 Knossos" in opis
    assert "#3 Balos [odbyta]" in opis
    assert "Bez daty: #5 Spinalonga." in opis


# --- Warstwa bazy ---

@pytest.fixture
def baza():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE wycieczka (id TEXT PRIMARY KEY, tytul_wycieczki TEXT, planowana_data TEXT, odbyta INTEGER DEFAULT 0)"
    )
    conn.executemany(
        "INSERT INTO wycieczka (id, tytul_wycieczki, planowana_data, odbyta) VALUES (?, ?, ?, ?)",
        [
            ("1", "Knossos", "2026-09-17", 0),
            ("2", "Elafonisi", None, 0),
            ("3", "Balos", "2026-09-13", 1),
            ("4", "Spinalonga", "", 0),
        ],
    )
    conn.commit()

    class _Polaczenie:
        """`with get_db() as conn` nie może zamknąć wspólnego połączenia w pamięci."""

        def __enter__(self):
            return conn

        def __exit__(self, typ, wartosc, tb):
            if typ is None:
                conn.commit()
            return False

    ns = _namespace(get_db=lambda: _Polaczenie())
    yield ns, conn
    conn.close()


def _daty(conn):
    return dict(conn.execute("SELECT id, planowana_data FROM wycieczka ORDER BY CAST(id AS INTEGER)").fetchall())


def test_zaplanowanie_wolnego_dnia_zapisuje_date(baza):
    ns, conn = baza
    wynik = ns["zaplanuj_wycieczke"]("2", "2026-09-20")
    assert wynik["success"] is True and wynik["zastapiono"] is None
    assert _daty(conn)["2"] == "2026-09-20"


def test_zajety_dzien_blokuje_bez_flagi_i_nic_nie_zmienia(baza):
    ns, conn = baza
    wynik = ns["zaplanuj_wycieczke"]("2", "2026-09-17")
    assert wynik["success"] is False
    assert wynik["zajete_przez"] == {"id": "1", "tytul": "Knossos"}
    assert "#1" in wynik["error"] and "zastap_wycieczke_w_tym_dniu=True" in wynik["error"]
    assert _daty(conn) == {"1": "2026-09-17", "2": None, "3": "2026-09-13", "4": ""}


def test_zastapienie_zabiera_date_poprzedniej_wycieczce(baza):
    ns, conn = baza
    wynik = ns["zaplanuj_wycieczke"]("2", "2026-09-17", zastap=True)
    assert wynik["success"] is True
    assert wynik["zastapiono"] == {"id": "1", "tytul": "Knossos"}
    assert "#1" in wynik["message"]
    daty = _daty(conn)
    assert daty["2"] == "2026-09-17" and daty["1"] is None


def test_ta_sama_wycieczka_moze_zostac_w_swoim_dniu(baza):
    ns, conn = baza
    assert ns["znajdz_wycieczke_w_dniu"]("2026-09-17", poza_id="1") is None
    wynik = ns["zaplanuj_wycieczke"]("1", "2026-09-17")
    assert wynik["success"] is True and wynik["zastapiono"] is None


def test_zla_data_jest_odrzucana_przed_dotknieciem_bazy(baza):
    ns, conn = baza
    wynik = ns["zaplanuj_wycieczke"]("2", "17.09.2026")
    assert wynik["success"] is False and "RRRR-MM-DD" in wynik["error"]
    assert _daty(conn)["2"] is None


def test_odplanowanie_czysci_date(baza):
    ns, conn = baza
    ns["odplanuj_wycieczke"]("1")
    assert _daty(conn)["1"] is None


def test_lista_zaplanowanych_pomija_puste_i_sortuje_po_dacie(baza):
    ns, _ = baza
    zaplanowane = ns["pobierz_zaplanowane_wycieczki"]()
    assert [(x["id"], x["data"], x["odbyta"]) for x in zaplanowane] == [
        ("3", date(2026, 9, 13), True),
        ("1", date(2026, 9, 17), False),
    ]


def test_lista_niezaplanowanych_obejmuje_pusty_napis_i_pomija_odbyte(baza):
    ns, conn = baza
    conn.execute("UPDATE wycieczka SET planowana_data = NULL, odbyta = 1 WHERE id = '3'")
    conn.commit()
    assert [x["id"] for x in ns["pobierz_niezaplanowane_wycieczki"]()] == ["2", "4"]


def test_migracja_zostawia_date_tylko_aktywnej_i_kasuje_tabele(baza):
    ns, conn = baza
    conn.execute("CREATE TABLE aktywna_wycieczka (id INTEGER PRIMARY KEY, aktualne_id_wycieczki TEXT)")
    conn.execute("INSERT INTO aktywna_wycieczka VALUES (1, '3')")
    conn.execute("UPDATE wycieczka SET planowana_data = '2026-09-12'")
    conn.commit()
    cursor = conn.cursor()
    assert ns["zmigruj_aktywna_wycieczke_na_daty"](cursor) == "3"
    conn.commit()
    assert _daty(conn) == {"1": None, "2": None, "3": "2026-09-12", "4": None}
    tabele = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    assert "aktywna_wycieczka" not in tabele


@pytest.mark.parametrize("aktywna", ["", "   ", None])
def test_migracja_z_pustym_wskaznikiem_zeruje_wszystkie_daty(baza, aktywna):
    ns, conn = baza
    conn.execute("CREATE TABLE aktywna_wycieczka (id INTEGER PRIMARY KEY, aktualne_id_wycieczki TEXT)")
    conn.execute("INSERT INTO aktywna_wycieczka VALUES (1, ?)", (aktywna,))
    conn.commit()
    assert ns["zmigruj_aktywna_wycieczke_na_daty"](conn.cursor()) is None
    conn.commit()
    assert all(d is None for d in _daty(conn).values())


def test_migracja_jest_idempotentna_bez_starej_tabeli(baza):
    ns, conn = baza
    assert ns["zmigruj_aktywna_wycieczke_na_daty"](conn.cursor()) is None
    assert _daty(conn)["1"] == "2026-09-17"
