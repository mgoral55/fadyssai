"""Testy regresyjne cache zewnętrznych API (OSRM, wttr.in).

Cache `@st.cache_data` trzyma teraz wyłącznie udane odpowiedzi, a awaria trafia do rejestru
awarii (`AWARIA_API_PONOW_PO_S`) żyjącego w `@st.cache_resource`, a nie do cache na 24 h / 8 h.
Testy pilnują, że wartości zastępcze są bajt w bajt takie jak przed zmianą, że udana odpowiedź
formatuje się identycznie jak dotąd, że rejestr awarii tłumi powtarzane timeouty, ale sam wygasa,
i że sam rejestr nadal jest trzymany tak, by przetrwał rerun skryptu Streamlita.

`app.py` jest skryptem Streamlit - import całego modułu uruchomiłby UI, więc testy wyciągają
badane funkcje ze źródła przez AST. Dekoratory nie wchodzą w segment źródła, więc funkcje
`@st.cache_data` jadą tu bez cache; sieć i zegar monotoniczny podstawiane są atrapami, a za
`@st.cache_resource` robi domknięcie oddające jedną parę (rejestr, blokada) na test. Tego, czego
wykonanie kodu nie pokaże - że dekoratory w app.py są dokładnie te, a modułowych zmiennych
rejestru już nie ma - pilnują osobne testy czytające drzewo AST.

Uruchomienie:  pytest test_api_zewnetrzne.py
"""

import ast
import io
import json
import math
import threading
import types

import pytest

from conftest import SCIEZKA_APP, wczytaj_funkcje_z_app

BADANE_FUNKCJE = [
    "_awaria_api_niedawna",
    "_zanotuj_awarie_api",
    "zaokraglij_do_5_minut",
    "_sformatuj_czas_przejazdu",
    "oblicz_czas_przejazdu_osrm",
    "_osrm_czas_przejazdu",
    "_szacunek_czasu_przejazdu",
    "pobierz_geometrie_trasy_osrm",
    "_osrm_geometria_trasy",
    "pobierz_prognoze_pogody",
    "_prognoza_wttr",
]

STALE_MODULU = ["AWARIA_API_PONOW_PO_S", "AWARIA_API_PROG_SPRZATANIA"]

# Opakowania widoczne dla reszty app.py - muszą być bez cache, żeby wartość zastępcza nie wpadła do cache.
NAZWY_PUBLICZNE = {
    "oblicz_czas_przejazdu_osrm",
    "pobierz_geometrie_trasy_osrm",
    "pobierz_prognoze_pogody",
}

# Funkcje sięgające do sieci - tylko one mają @st.cache_data, bo wracają wyłącznie z sukcesem.
# Wartością jest komunikat spinnera spisany z wersji sprzed rozdzielenia: st.cache_data przy zimnym
# trafieniu rysuje go w UI, więc musi zostać przy nazwie publicznej, a nie prywatnego pomocnika.
NAZWY_Z_CACHE_DATA = {
    "_osrm_czas_przejazdu": "Running `oblicz_czas_przejazdu_osrm(...)`.",
    "_osrm_geometria_trasy": "Running `pobierz_geometrie_trasy_osrm(...)`.",
    "_prognoza_wttr": "Running `pobierz_prognoze_pogody(...)`.",
}

# Zmienne modułowe zerowałyby się przy każdym rerunie skryptu Streamlita - rejestr ma ich nie używać.
NIEDOZWOLONE_GLOBALNE = ["_AWARIE_API", "_AWARIE_API_BLOKADA"]

with io.open(SCIEZKA_APP, encoding="utf-8") as plik:
    ZRODLO_APP = plik.read()
DRZEWO_APP = ast.parse(ZRODLO_APP)

DOMEK = (35.5914, 24.0918)
KNOSSOS = (35.2980, 25.1631)
CHANIA = (35.5138, 24.0180)

# Wartości zastępcze spisane z wersji sprzed zmiany - nie wolno ich ruszyć, bo widzi je rodzic w UI.
ZASTEPCZY_CZAS = {KNOSSOS: ("~1h 40m", 100), CHANIA: ("~20 min", 20)}
ZASTEPCZA_GEOMETRIA = {
    KNOSSOS: [[35.5914, 24.0918], [35.2980, 25.1631]],
    CHANIA: [[35.5914, 24.0918], [35.5138, 24.0180]],
}

NAGLOWEK = {"User-Agent": "CretAiApp/1.0"}


# --- Atrapy zależności zewnętrznych ---

class OdpowiedzHTTP:
    """Atrapa odpowiedzi `urlopen` - menedżer kontekstu z `read()` zwracającym JSON w bajtach."""

    def __init__(self, ladunek):
        self._bajty = json.dumps(ladunek).encode("utf-8")

    def read(self):
        return self._bajty

    def __enter__(self):
        return self

    def __exit__(self, *wyjatek):
        return False


class Zapytanie:
    """Atrapa `urllib.request.Request` - zapamiętuje URL i nagłówki."""

    def __init__(self, url, headers=None):
        self.url = url
        self.headers = headers or {}


class SiecAtrapa:
    """Sterowalny `urlopen`: n-te wywołanie obsługuje n-ta reakcja, ostatnia obowiązuje dalej.

    Reakcją jest ładunek JSON (sukces) albo instancja wyjątku (awaria sieci).
    """

    def __init__(self, reakcje):
        self.reakcje = list(reakcje)
        self.zapytania = []

    def __call__(self, req, timeout=None):
        self.zapytania.append((req.url, req.headers, timeout))
        reakcja = self.reakcje[min(len(self.zapytania) - 1, len(self.reakcje) - 1)]
        if isinstance(reakcja, Exception):
            raise reakcja
        return OdpowiedzHTTP(reakcja)

    @property
    def liczba_wywolan(self):
        return len(self.zapytania)


class ZegarAtrapa:
    """Sterowalny zegar monotoniczny podstawiany pod `zegar` z app.py."""

    def __init__(self):
        self.teraz = 1000.0

    def monotonic(self):
        return self.teraz

    def przesun(self, sekundy):
        self.teraz += sekundy


def _atrapa_urllib(siec):
    return types.SimpleNamespace(request=types.SimpleNamespace(Request=Zapytanie, urlopen=siec))


# --- Ładowanie kodu z app.py ---

def _segmenty_stalych(nazwy):
    """Zwraca źródła modułowych przypisań z app.py (stałe rejestru awarii)."""
    znalezione = {}
    for wezel in DRZEWO_APP.body:
        if isinstance(wezel, ast.Assign):
            for cel in wezel.targets:
                if getattr(cel, "id", None) in nazwy:
                    znalezione[cel.id] = ast.get_source_segment(ZRODLO_APP, wezel)
    brakujace = [n for n in nazwy if n not in znalezione]
    assert not brakujace, f"Nie znaleziono przypisań w app.py: {brakujace}"
    return [znalezione[n] for n in nazwy]


SEGMENTY_STALYCH = _segmenty_stalych(STALE_MODULU)
SEGMENTY_FUNKCJI = wczytaj_funkcje_z_app(BADANE_FUNKCJE)


def _wezel_funkcji(nazwa):
    """Węzeł AST funkcji najwyższego poziomu z app.py - razem z dekoratorami."""
    for wezel in DRZEWO_APP.body:
        if isinstance(wezel, ast.FunctionDef) and wezel.name == nazwa:
            return wezel
    raise AssertionError(f"Nie znaleziono funkcji w app.py: {nazwa}")


def _nazwa_dekoratora(wezel):
    """'st.cache_data' zarówno dla @st.cache_data, jak i @st.cache_data(ttl=...)."""
    cel = wezel.func if isinstance(wezel, ast.Call) else wezel
    if isinstance(cel, ast.Attribute) and isinstance(cel.value, ast.Name):
        return f"{cel.value.id}.{cel.attr}"
    return ast.dump(cel)


class Srodowisko:
    """Świeży namespace app.py z atrapą sieci i zegara - rejestr awarii startuje pusty."""

    def __init__(self, reakcje):
        self.siec = SiecAtrapa(reakcje)
        self.zegar = ZegarAtrapa()
        # Dekoratory nie wchodzą w segment źródła, więc `_rejestr_awarii_api` wyciągnięty z app.py oddawałby
        # nowy słownik przy każdym wywołaniu i backoff nie miałby czego pamiętać. Podstawiamy domknięcie z jedną
        # parą (rejestr, blokada) na test - dokładnie tak, jak @st.cache_resource trzyma jedną parę na proces.
        self._rejestr_z_blokada = ({}, threading.Lock())
        self.ns = {
            "json": json,
            "math": math,
            "threading": threading,
            "urllib": _atrapa_urllib(self.siec),
            "zegar": self.zegar,
            "_rejestr_awarii_api": lambda: self._rejestr_z_blokada,
        }
        for kod in SEGMENTY_STALYCH:
            exec(kod, self.ns)
        for kod in SEGMENTY_FUNKCJI.values():
            exec(kod, self.ns)

    def __getitem__(self, nazwa):
        return self.ns[nazwa]

    @property
    def rejestr(self):
        return self._rejestr_z_blokada[0]


def odpowiedz_czasu(sekundy):
    return {"routes": [{"duration": sekundy}]}


def odpowiedz_geometrii(punkty):
    return {"routes": [{"geometry": {"coordinates": punkty}}]}


# --- Udana odpowiedź OSRM: formatowanie czasu ---

@pytest.mark.parametrize(
    "sekundy, oczekiwany",
    [
        (1800, ("~30 min", 30)),
        (1700, ("~30 min", 30)),
        (3600, ("~1h", 60)),
        (5400, ("~1h 30m", 90)),
        (60, ("~10 min", 10)),
    ],
)
def test_udana_odpowiedz_osrm_formatuje_czas_jak_dotad(sekundy, oczekiwany):
    """Sukces ma dać dokładnie te same napisy co przed zmianą, z zaokrągleniem do 5 min i progiem 10 min."""
    srodowisko = Srodowisko([odpowiedz_czasu(sekundy)])
    assert srodowisko["oblicz_czas_przejazdu_osrm"](*DOMEK, *KNOSSOS) == oczekiwany


def test_udana_odpowiedz_nie_zostawia_sladu_w_rejestrze_awarii():
    """Rejestr dotyczy wyłącznie awarii - po udanym strzale ma zostać pusty."""
    srodowisko = Srodowisko([odpowiedz_czasu(1800)])
    srodowisko["oblicz_czas_przejazdu_osrm"](*DOMEK, *KNOSSOS)
    assert srodowisko.rejestr == {}


def test_zapytanie_o_czas_zachowuje_url_naglowek_i_timeout():
    """Kontrakt z OSRM zostaje bez zmian: ten sam adres, User-Agent i 4.0 s timeoutu."""
    srodowisko = Srodowisko([odpowiedz_czasu(1800)])
    srodowisko["oblicz_czas_przejazdu_osrm"](*DOMEK, *KNOSSOS)

    (url, naglowki, timeout), = srodowisko.siec.zapytania
    assert url == (
        "http://router.project-osrm.org/route/v1/driving/"
        "24.0918,35.5914;25.1631,35.298?overview=false"
    )
    assert naglowki == NAGLOWEK
    assert timeout == 4.0


def test_odpowiedz_bez_tras_schodzi_do_szacunku_geometrycznego():
    """Odpowiedź bez `routes` to dla nas awaria - wynik z szacunku, wpis w rejestrze."""
    srodowisko = Srodowisko([{"code": "NoRoute"}])
    assert srodowisko["oblicz_czas_przejazdu_osrm"](*DOMEK, *KNOSSOS) == ZASTEPCZY_CZAS[KNOSSOS]
    assert ("osrm_czas",) + DOMEK + KNOSSOS in srodowisko.rejestr


# --- Zgodność wartości zastępczych z wersją sprzed zmiany ---

@pytest.mark.parametrize("cel", [KNOSSOS, CHANIA])
def test_szacunek_czasu_jest_identyczny_jak_przed_zmiana(cel):
    """Przy padniętym OSRM wynik musi być co do znaku taki, jak dawał kod sprzed rozdzielenia cache."""
    assert Srodowisko([OSError("timeout OSRM")])["oblicz_czas_przejazdu_osrm"](*DOMEK, *cel) == ZASTEPCZY_CZAS[cel]


@pytest.mark.parametrize("cel", [KNOSSOS, CHANIA])
def test_prosta_linia_jest_identyczna_jak_przed_zmiana(cel):
    """Fallback geometrii to nadal odcinek start-meta w kolejności [lat, lon]."""
    nowe = Srodowisko([OSError("timeout OSRM")])["pobierz_geometrie_trasy_osrm"](*DOMEK, *cel)
    assert nowe == ZASTEPCZA_GEOMETRIA[cel] == [list(DOMEK), list(cel)]


def test_brak_prognozy_jest_identyczny_jak_przed_zmiana():
    """Padnięte wttr.in dalej daje None, a nie wyjątek czy pustą strukturę."""
    assert Srodowisko([OSError("timeout wttr")])["pobierz_prognoze_pogody"](*DOMEK, "2026-09-12") is None


# --- Rejestr awarii: tłumienie powtórek i wygasanie ---

def test_awaria_nie_powtarza_strzalu_w_oknie_i_wraca_po_wygasnieciu():
    """Przez AWARIA_API_PONOW_PO_S render nie dobija padającego API, potem próbuje ponownie."""
    srodowisko = Srodowisko([OSError("timeout OSRM")])
    czas = srodowisko["oblicz_czas_przejazdu_osrm"]

    assert czas(*DOMEK, *KNOSSOS) == ZASTEPCZY_CZAS[KNOSSOS]
    assert srodowisko.siec.liczba_wywolan == 1

    srodowisko.zegar.przesun(599)
    assert czas(*DOMEK, *KNOSSOS) == ZASTEPCZY_CZAS[KNOSSOS]
    assert srodowisko.siec.liczba_wywolan == 1, "Wpis w rejestrze miał stłumić ponowny strzał"

    srodowisko.zegar.przesun(2)
    srodowisko.siec.reakcje = [odpowiedz_czasu(1800)]
    assert czas(*DOMEK, *KNOSSOS) == ("~30 min", 30)
    assert srodowisko.siec.liczba_wywolan == 2
    assert srodowisko.rejestr == {}, "Po udanej próbie klucz ma zniknąć z rejestru"


def test_awaria_jednej_trasy_nie_blokuje_innej():
    """Klucz rejestru zawiera współrzędne - awaria odcinka nie wycisza całego OSRM."""
    srodowisko = Srodowisko([OSError("timeout OSRM")])
    srodowisko["oblicz_czas_przejazdu_osrm"](*DOMEK, *KNOSSOS)

    srodowisko.siec.reakcje = [odpowiedz_czasu(3600)]
    assert srodowisko["oblicz_czas_przejazdu_osrm"](*DOMEK, *CHANIA) == ("~1h", 60)
    assert srodowisko.siec.liczba_wywolan == 2


# --- Geometria trasy ---

def test_geometria_zamienia_pary_lon_lat_na_lat_lon():
    """OSRM oddaje [lon, lat], a folium potrzebuje [lat, lon]."""
    punkty = [[24.0918, 35.5914], [24.5000, 35.4000], [25.1631, 35.2980]]
    srodowisko = Srodowisko([odpowiedz_geometrii(punkty)])
    assert srodowisko["pobierz_geometrie_trasy_osrm"](*DOMEK, *KNOSSOS) == [
        [35.5914, 24.0918],
        [35.4000, 24.5000],
        [35.2980, 25.1631],
    ]
    assert srodowisko.siec.liczba_wywolan == 1


def test_geometria_siega_po_overview_simplified_gdy_pelna_padnie():
    """Drugie podejście z niższym narzutem zostaje - wynik bierzemy z niego."""
    punkty = [[24.0918, 35.5914], [25.1631, 35.2980]]
    srodowisko = Srodowisko([OSError("timeout OSRM"), odpowiedz_geometrii(punkty)])

    assert srodowisko["pobierz_geometrie_trasy_osrm"](*DOMEK, *KNOSSOS) == [
        [35.5914, 24.0918],
        [35.2980, 25.1631],
    ]
    assert srodowisko.siec.liczba_wywolan == 2
    pierwszy, drugi = [zapytanie[0] for zapytanie in srodowisko.siec.zapytania]
    assert "overview=full" in pierwszy and "overview=simplified" in drugi
    assert all(zapytanie[2] == 2.0 for zapytanie in srodowisko.siec.zapytania)


def test_geometria_po_dwoch_awariach_daje_prosta_linie_i_wpis_w_rejestrze():
    """Dopiero upadek obu podejść schodzi do odcinka - i tylko to trafia do rejestru."""
    srodowisko = Srodowisko([OSError("timeout full"), OSError("timeout simplified")])

    assert srodowisko["pobierz_geometrie_trasy_osrm"](*DOMEK, *KNOSSOS) == ZASTEPCZA_GEOMETRIA[KNOSSOS]
    assert srodowisko.siec.liczba_wywolan == 2
    assert ("osrm_geometria",) + DOMEK + KNOSSOS in srodowisko.rejestr


# --- Prognoza pogody ---

PROGNOZA = {
    "weather": [
        {"date": "2026-09-11", "maxtempC": "28"},
        {"date": "2026-09-12", "maxtempC": "31"},
    ]
}


def test_pogoda_zwraca_dzien_o_pasujacej_dacie():
    """Z listy dni bierzemy ten, o który pytał krok wycieczki."""
    srodowisko = Srodowisko([PROGNOZA])
    assert srodowisko["pobierz_prognoze_pogody"](*DOMEK, "2026-09-12") == PROGNOZA["weather"][1]


def test_pogoda_bez_pasujacej_daty_wraca_do_pierwszego_dnia():
    """Data poza horyzontem prognozy nie może wysypać widoku - bierzemy pierwszy dzień."""
    srodowisko = Srodowisko([PROGNOZA])
    assert srodowisko["pobierz_prognoze_pogody"](*DOMEK, "2026-12-24") == PROGNOZA["weather"][0]


def test_pogoda_z_pusta_lista_dni_to_awaria():
    """Odpowiedź bez dni jest bezużyteczna - None dla UI, wpis w rejestrze zamiast cache."""
    srodowisko = Srodowisko([{"weather": []}])
    assert srodowisko["pobierz_prognoze_pogody"](*DOMEK, "2026-09-12") is None
    assert ("wttr",) + DOMEK + ("2026-09-12",) in srodowisko.rejestr


def test_pogoda_po_wyjatku_daje_none_bez_dobijania_api():
    """Timeout wttr.in tłumiony jest tak samo jak awarie OSRM."""
    srodowisko = Srodowisko([OSError("timeout wttr")])

    assert srodowisko["pobierz_prognoze_pogody"](*DOMEK, "2026-09-12") is None
    assert srodowisko["pobierz_prognoze_pogody"](*DOMEK, "2026-09-12") is None
    assert srodowisko.siec.liczba_wywolan == 1


# --- Pomocnicze funkcje rejestru ---

def test_nieznany_klucz_nie_jest_awaria():
    """Pusty rejestr przepuszcza ruch do API."""
    assert Srodowisko([])["_awaria_api_niedawna"](("osrm_czas", 1, 2, 3, 4)) is False


def test_swiezo_zanotowana_awaria_jest_niedawna():
    """Zaraz po zanotowaniu klucz blokuje kolejne strzały."""
    srodowisko = Srodowisko([])
    klucz = ("wttr", 35.0, 24.0, "2026-09-12")
    srodowisko["_zanotuj_awarie_api"](klucz)
    assert srodowisko["_awaria_api_niedawna"](klucz) is True


def test_wygasly_wpis_znika_z_rejestru():
    """Po AWARIA_API_PONOW_PO_S wpis jest kasowany, żeby rejestr nie puchł przez całą sesję."""
    srodowisko = Srodowisko([])
    klucz = ("osrm_geometria", 35.0, 24.0, 35.1, 24.1)
    srodowisko["_zanotuj_awarie_api"](klucz)

    srodowisko.zegar.przesun(srodowisko["AWARIA_API_PONOW_PO_S"])
    assert srodowisko["_awaria_api_niedawna"](klucz) is False
    assert srodowisko.rejestr == {}


def test_rejestr_przycina_wygasle_wpisy_po_przekroczeniu_progu():
    """Rejestr żyje tyle co proces, więc po progu notowanie awarii sprząta to, co i tak wygasło."""
    srodowisko = Srodowisko([])
    prog = srodowisko["AWARIA_API_PROG_SPRZATANIA"]
    for numer in range(prog + 1):
        srodowisko["_zanotuj_awarie_api"](("osrm_czas", numer))
    assert len(srodowisko.rejestr) == prog + 1, "Do progu nic nie jest kasowane"

    srodowisko.zegar.przesun(srodowisko["AWARIA_API_PONOW_PO_S"])
    srodowisko["_zanotuj_awarie_api"](("wttr", "swiezy"))
    assert list(srodowisko.rejestr) == [("wttr", "swiezy")]


# --- Sposób trzymania rejestru i cache (czytane z AST, bo dekoratory nie wchodzą do testu) ---

def test_rejestr_awarii_lezy_w_cache_resource():
    """Skrypt Streamlita startuje od nowa co render - rejestr musi trzymać @st.cache_resource."""
    dekoratory = _wezel_funkcji("_rejestr_awarii_api").decorator_list
    assert [_nazwa_dekoratora(d) for d in dekoratory] == ["st.cache_resource"]


@pytest.mark.parametrize("nazwa", ["_awaria_api_niedawna", "_zanotuj_awarie_api"])
def test_pomocnicze_siegaja_po_rejestr_z_cache_resource(nazwa):
    """Obie funkcje pomocnicze mają brać rejestr z `_rejestr_awarii_api`, a nie z własnej zmiennej."""
    wezel = _wezel_funkcji(nazwa)
    assert any(
        isinstance(w, ast.Name) and w.id == "_rejestr_awarii_api" for w in ast.walk(wezel)
    ), f"{nazwa} nie sięga po _rejestr_awarii_api"


@pytest.mark.parametrize("nazwa", sorted(NAZWY_PUBLICZNE))
def test_opakowania_z_fallbackiem_sa_bez_cache(nazwa):
    """Gdyby opakowanie miało cache, wartość zastępcza wróciłaby do trzymania się przez 24 h / 8 h."""
    assert _wezel_funkcji(nazwa).decorator_list == []


@pytest.mark.parametrize("nazwa", sorted(NAZWY_Z_CACHE_DATA))
def test_funkcje_sieciowe_maja_cache_data(nazwa):
    """Cache zostaje wyłącznie na warstwie, która albo zwraca sukces, albo rzuca wyjątkiem.

    Domyślny show_spinner=True wypisałby przy zimnym trafieniu nazwę prywatnego pomocnika, więc
    dekorator musi podawać jawny komunikat - co do znaku ten sam, co UI pokazywało przed zmianą."""
    dekoratory = _wezel_funkcji(nazwa).decorator_list
    assert [_nazwa_dekoratora(d) for d in dekoratory] == ["st.cache_data"]

    nazwane = {k.arg: k.value for k in getattr(dekoratory[0], "keywords", [])}
    spinner = nazwane.get("show_spinner")
    assert isinstance(spinner, ast.Constant), f"{nazwa}: @st.cache_data bez jawnego show_spinner"
    assert spinner.value == NAZWY_Z_CACHE_DATA[nazwa]


@pytest.mark.parametrize("nazwa", NIEDOZWOLONE_GLOBALNE)
def test_rejestr_nie_wisi_na_zmiennej_modulu(nazwa):
    """Modułowy słownik zerowałby się przy każdym rerunie i backoff nigdy by nie zadziałał."""
    przypisania = [
        cel.id
        for wezel in DRZEWO_APP.body
        if isinstance(wezel, ast.Assign)
        for cel in wezel.targets
        if getattr(cel, "id", None) == nazwa
    ]
    assert przypisania == [], f"{nazwa} nie przetrwa rerunu Streamlita - rejestr ma żyć w st.cache_resource"
