"""Testy regresyjne dialogu zmiany daty wycieczki.

Wycieczka, której `planowana_data` minęła, wywracała cały widok:
`StreamlitValueBelowMinError: The value 2026-09-11 is less than the min_value 2026-09-12`.
Testy uruchamiają prawdziwy kod `edit_date_dialog` na atrapie Streamlita, która
odtwarza wyłącznie tę walidację zakresu, przez którą leciał wyjątek.

Uruchomienie:  pytest test_dialog_daty.py
"""

from datetime import date, timedelta

import pytest

from conftest import wczytaj_funkcje_z_app

BADANE_FUNKCJE = ["edit_date_dialog"]


class BladWartosciPonizejMinimum(Exception):
    """Odpowiednik streamlit.errors.StreamlitValueBelowMinError."""


class Rerun(Exception):
    """Odpowiednik streamlit.runtime.scriptrunner.RerunException."""


class _PustyKontekst:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class AtrapaStreamlit:
    """Minimalny Streamlit: walidacja zakresu daty, przyciski i session_state."""

    def __init__(self, klikniety=None, zwracana_data=None):
        self.klikniety = klikniety
        self.zwracana_data = zwracana_data
        self.wywolania_date_input = []
        self.session_state = {}

    def date_input(self, label, value=None, min_value=None, max_value=None, **kwargs):
        self.wywolania_date_input.append({"value": value, "min_value": min_value, "max_value": max_value})
        if min_value is not None and value < min_value:
            raise BladWartosciPonizejMinimum(
                f"The `value` {value} is less than the `min_value` {min_value}."
            )
        if max_value is not None and value > max_value:
            raise AssertionError(f"value {value} > max_value {max_value}")
        return self.zwracana_data or value

    def columns(self, n, **kwargs):
        return [_PustyKontekst() for _ in range(n)]

    def button(self, label, **kwargs):
        return label == self.klikniety

    def markdown(self, *a, **k):
        pass

    def rerun(self):
        raise Rerun()


class SzpiegZapisu:
    def __init__(self):
        self.wywolania = []

    def __call__(self, id_wycieczki, **kwargs):
        self.wywolania.append((id_wycieczki, kwargs))


def uruchom_dialog(aktualna_data, klikniety=None, zwracana_data=None):
    """Wykonuje edit_date_dialog z app.py; zwraca (atrapa st, szpieg edytuj_wycieczke)."""
    st = AtrapaStreamlit(klikniety=klikniety, zwracana_data=zwracana_data)
    zapis = SzpiegZapisu()
    ns = {"st": st, "date": date, "edytuj_wycieczke": zapis}
    for kod in wczytaj_funkcje_z_app(BADANE_FUNKCJE).values():
        exec(kod, ns)
    try:
        ns["edit_date_dialog"]("7", aktualna_data)
    except Rerun:
        pass
    return st, zapis


def test_przeszla_data_wycieczki_nie_wywala_dialogu():
    wczoraj = date.today() - timedelta(days=1)
    st, _ = uruchom_dialog(wczoraj)
    (wywolanie,) = st.wywolania_date_input
    assert wywolanie["value"] == wczoraj
    assert wywolanie["min_value"] <= wywolanie["value"]


def test_przyszla_wycieczka_nadal_blokuje_przeszlosc():
    za_piec_dni = date.today() + timedelta(days=5)
    st, _ = uruchom_dialog(za_piec_dni)
    (wywolanie,) = st.wywolania_date_input
    assert wywolanie["min_value"] == date.today()


def test_dzisiejsza_wycieczka_ma_granice_na_dzis():
    st, _ = uruchom_dialog(date.today())
    (wywolanie,) = st.wywolania_date_input
    assert wywolanie["min_value"] == date.today()
    assert wywolanie["value"] == date.today()


def test_zapis_przekazuje_wybrana_date_do_bazy():
    wczoraj = date.today() - timedelta(days=1)
    nowa = date.today() + timedelta(days=2)
    st, zapis = uruchom_dialog(wczoraj, klikniety="💾 Zapisz", zwracana_data=nowa)
    assert zapis.wywolania == [("7", {"planowana_data": nowa.strftime("%Y-%m-%d")})]
    assert st.session_state["flash_toast"] == f"📅 Zmieniono datę: {nowa.strftime('%Y-%m-%d')}"
