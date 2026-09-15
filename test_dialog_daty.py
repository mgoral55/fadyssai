"""Testy regresyjne dialogu planowania wycieczki (`edit_date_dialog`).

Historia: wycieczka, której `planowana_data` minęła, wywracała cały widok:
`StreamlitValueBelowMinError: The value 2026-09-11 is less than the min_value 2026-09-12`.
Do tego doszło planowanie po dacie: jeden dzień = jedna wycieczka, zajęty dzień pokazuje
ostrzeżenie i przycisk "Zastąp", zaplanowana wycieczka ma przycisk "Usuń z planu".
Testy uruchamiają prawdziwy kod dialogu na atrapie Streamlita, która odtwarza wyłącznie
walidację zakresu daty, przyciski, ostrzeżenia i session_state.

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
    """Minimalny Streamlit: walidacja zakresu daty, przyciski, ostrzeżenia i session_state."""

    def __init__(self, klikniety=None, zwracana_data=None):
        self.klikniety = klikniety
        self.zwracana_data = zwracana_data
        self.wywolania_date_input = []
        self.ostrzezenia = []
        self.bledy = []
        self.przyciski = []
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
        self.przyciski.append(label)
        return label == self.klikniety

    def warning(self, tekst, **kwargs):
        self.ostrzezenia.append(tekst)

    def error(self, tekst, **kwargs):
        self.bledy.append(tekst)

    def markdown(self, *a, **k):
        pass

    def rerun(self):
        raise Rerun()


class Szpieg:
    def __init__(self, wynik=None):
        self.wywolania = []
        self.wynik = wynik if wynik is not None else {"success": True}

    def __call__(self, *args, **kwargs):
        self.wywolania.append((args, kwargs))
        return self.wynik


def uruchom_dialog(aktualna_data, klikniety=None, zwracana_data=None, czy_zaplanowana=False, zajeta_przez=None, wynik_zaplanuj=None):
    """Wykonuje edit_date_dialog z app.py; zwraca (atrapa st, szpieg zaplanuj, szpieg odplanuj)."""
    st = AtrapaStreamlit(klikniety=klikniety, zwracana_data=zwracana_data)
    if wynik_zaplanuj is None:
        wynik_zaplanuj = {"success": True, "zastapiono": zajeta_przez}
    zaplanuj, odplanuj = Szpieg(wynik_zaplanuj), Szpieg()
    ns = {
        "st": st,
        "date": date,
        "zaplanuj_wycieczke": zaplanuj,
        "odplanuj_wycieczke": odplanuj,
        "znajdz_wycieczke_w_dniu": lambda data_str, poza_id=None, cursor=None: zajeta_przez,
    }
    for kod in wczytaj_funkcje_z_app(BADANE_FUNKCJE).values():
        exec(kod, ns)
    try:
        ns["edit_date_dialog"]("7", aktualna_data, czy_zaplanowana=czy_zaplanowana)
    except Rerun:
        pass
    return st, zaplanuj, odplanuj


# --- Zakres date_input (regresja StreamlitValueBelowMinError) ---

def test_przeszla_data_wycieczki_nie_wywala_dialogu():
    wczoraj = date.today() - timedelta(days=1)
    st, _, _ = uruchom_dialog(wczoraj)
    (wywolanie,) = st.wywolania_date_input
    assert wywolanie["value"] == wczoraj
    assert wywolanie["min_value"] <= wywolanie["value"]


def test_przyszla_wycieczka_nadal_blokuje_przeszlosc():
    za_piec_dni = date.today() + timedelta(days=5)
    st, _, _ = uruchom_dialog(za_piec_dni)
    (wywolanie,) = st.wywolania_date_input
    assert wywolanie["min_value"] == date.today()


def test_dzisiejsza_wycieczka_ma_granice_na_dzis():
    st, _, _ = uruchom_dialog(date.today())
    (wywolanie,) = st.wywolania_date_input
    assert wywolanie["min_value"] == date.today()
    assert wywolanie["value"] == date.today()


# --- Zapis i zastąpienie ---

def test_zapis_wolnego_dnia_planuje_wycieczke():
    nowa = date.today() + timedelta(days=2)
    st, zaplanuj, odplanuj = uruchom_dialog(date.today(), klikniety="💾 Zapisz", zwracana_data=nowa)
    assert zaplanuj.wywolania == [(("7", nowa.strftime("%Y-%m-%d")), {"zastap": True})]
    assert odplanuj.wywolania == []
    assert st.ostrzezenia == []
    assert st.session_state["flash_toast"] == f"📅 Zaplanowano na {nowa.strftime('%Y-%m-%d')}"


def test_zajety_dzien_pokazuje_ostrzezenie_i_przycisk_zastap():
    nowa = date.today() + timedelta(days=2)
    zajeta = {"id": "3", "tytul": "Knossos"}
    st, zaplanuj, _ = uruchom_dialog(date.today(), zwracana_data=nowa, zajeta_przez=zajeta)
    (ostrzezenie,) = st.ostrzezenia
    assert "#3 Knossos" in ostrzezenie
    assert "straci datę" in ostrzezenie
    assert "🔁 Zastąp #3" in st.przyciski
    assert "💾 Zapisz" not in st.przyciski
    assert zaplanuj.wywolania == []


def test_klik_zastap_planuje_z_flaga_i_mowi_kogo_wyrzucil():
    nowa = date.today() + timedelta(days=2)
    zajeta = {"id": "3", "tytul": "Knossos"}
    st, zaplanuj, _ = uruchom_dialog(date.today(), klikniety="🔁 Zastąp #3", zwracana_data=nowa, zajeta_przez=zajeta)
    assert zaplanuj.wywolania == [(("7", nowa.strftime("%Y-%m-%d")), {"zastap": True})]
    assert "#3 straciła ten dzień" in st.session_state["flash_toast"]


def test_nieudany_zapis_pokazuje_blad_zamiast_toastu_sukcesu():
    nowa = date.today() + timedelta(days=2)
    st, zaplanuj, _ = uruchom_dialog(
        date.today(), klikniety="💾 Zapisz", zwracana_data=nowa,
        wynik_zaplanuj={"success": False, "error": "Nieprawidłowa data"},
    )
    assert len(zaplanuj.wywolania) == 1
    (blad,) = st.bledy
    assert "Nieprawidłowa data" in blad
    assert "flash_toast" not in st.session_state


# --- Usunięcie z planu ---

def test_niezaplanowana_wycieczka_nie_ma_przycisku_usun_z_planu():
    st, _, _ = uruchom_dialog(date.today(), czy_zaplanowana=False)
    assert not any("Usuń z planu" in p for p in st.przyciski)


def test_zaplanowana_wycieczka_ma_przycisk_usun_z_planu_ktory_czysci_date():
    st, zaplanuj, odplanuj = uruchom_dialog(
        date.today() + timedelta(days=1), klikniety="🗑️ Usuń z planu wyjazdu", czy_zaplanowana=True
    )
    assert odplanuj.wywolania == [(("7",), {})]
    assert zaplanuj.wywolania == []
    assert st.session_state["flash_toast"] == "📅 Wycieczka #7 nie ma już daty"


def test_anuluj_nic_nie_zapisuje():
    _, zaplanuj, odplanuj = uruchom_dialog(date.today(), klikniety="Anuluj")
    assert zaplanuj.wywolania == [] and odplanuj.wywolania == []
