"""Testy regresyjne kolejki silników trasowania (Valhalla, OSRM, Google) i cache zewnętrznych API.

Czas przejazdu liczy kolejka silników: opcjonalny Google Routes (tylko z kluczem w środowisku),
potem publiczna Valhalla, potem serwer demo OSRM, a na końcu fallback geometryczny bez sieci.
Testy pilnują kolejności silników, tego że każdy ma własny wpis w rejestrze awarii (padnięcie jednego
nie wycisza pozostałych) i że Google nie wchodzi do kolejki bez klucza.

Cache `@st.cache_data` trzyma wyłącznie udane odpowiedzi, a awaria trafia do rejestru awarii
(`AWARIA_API_PONOW_PO_S`) żyjącego w `@st.cache_resource`, a nie do cache na 24 h / 8 h. Reszta testów
pilnuje, że rejestr awarii tłumi powtarzane timeouty, ale sam wygasa, i że jest trzymany tak,
by przetrwał rerun skryptu Streamlita.

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
import urllib.parse

import pandas as pd
import pytest

from conftest import SCIEZKA_APP, wczytaj_funkcje_z_app

BADANE_FUNKCJE = [
    "_awaria_api_niedawna",
    "_zanotuj_awarie_api",
    "zaokraglij_do_5_minut",
    "_sformatuj_czas_przejazdu",
    "oblicz_czas_przejazdu",
    "_valhalla_czas_przejazdu",
    "_osrm_czas_przejazdu",
    "_google_czas_przejazdu",
    "_szacunek_czasu_przejazdu",
    "pobierz_geometrie_trasy_osrm",
    "_osrm_geometria_trasy",
    "pobierz_prognoze_pogody",
    "_prognoza_open_meteo",
    "_wez_z_kolumny",
    "_opis_wmo",
]

STALE_MODULU = [
    "AWARIA_API_PONOW_PO_S",
    "AWARIA_API_PROG_SPRZATANIA",
    "VALHALLA_URL",
    "VALHALLA_TIMEOUT_S",
    "OSRM_TIMEOUT_S",
    "GOOGLE_ROUTES_URL",
    "GOOGLE_ROUTES_KLUCZ",
    "GOOGLE_ROUTES_TIMEOUT_S",
    "CZAS_PRZEJAZDU_MIN_MINUT",
    "SZACUNEK_PROG_KROTKI_KM",
    "SZACUNEK_PROG_SREDNI_KM",
    "SZACUNEK_MIN_NA_KM_KROTKI",
    "SZACUNEK_MIN_NA_KM_SREDNI",
    "SZACUNEK_MIN_NA_KM_DLUGI",
    "OPEN_METEO_URL",
    "POGODA_TIMEOUT_S",
    "POGODA_STREFA",
    "WMO_BEZCHMURNIE",
    "WMO_LEKKIE_CHMURY",
    "WMO_ZACHMURZENIE",
    "WMO_BURZA",
    "WMO_DESZCZ",
    "OPISY_WMO",
]

# Opakowania widoczne dla reszty app.py - muszą być bez cache, żeby wartość zastępcza nie wpadła do cache.
NAZWY_PUBLICZNE = {
    "oblicz_czas_przejazdu",
    "pobierz_geometrie_trasy_osrm",
    "pobierz_prognoze_pogody",
}

# Funkcje sięgające do sieci - tylko one mają @st.cache_data, bo wracają wyłącznie z sukcesem.
# Wartością jest komunikat spinnera spisany z wersji sprzed rozdzielenia: st.cache_data przy zimnym
# trafieniu rysuje go w UI, więc musi zostać przy nazwie publicznej, a nie prywatnego pomocnika.
NAZWY_Z_CACHE_DATA = {
    "_valhalla_czas_przejazdu": "Running `oblicz_czas_przejazdu(...)`.",
    "_osrm_czas_przejazdu": "Running `oblicz_czas_przejazdu(...)`.",
    "_google_czas_przejazdu": "Running `oblicz_czas_przejazdu(...)`.",
    "_osrm_geometria_trasy": "Running `pobierz_geometrie_trasy_osrm(...)`.",
    "_prognoza_open_meteo": "Running `pobierz_prognoze_pogody(...)`.",
}

# Zmienne modułowe zerowałyby się przy każdym rerunie skryptu Streamlita - rejestr ma ich nie używać.
NIEDOZWOLONE_GLOBALNE = ["_AWARIE_API", "_AWARIE_API_BLOKADA"]

with io.open(SCIEZKA_APP, encoding="utf-8") as plik:
    ZRODLO_APP = plik.read()
DRZEWO_APP = ast.parse(ZRODLO_APP)

DOMEK = (35.5914, 24.0918)
KNOSSOS = (35.2980, 25.1631)
CHANIA = (35.5138, 24.0180)

# Fallback geometryczny po padnięciu wszystkich silników. Wartości wynikają z dopasowania min/km do Valhalli
# na 54 miejscach z bazy - poprzednie (~1h 40m dla Knossos, ~20 min dla Chanii) brały się ze współczynników
# zdjętych z OSRM i zaniżały dojazd o medianę 17 min, bo zakładały krętość dróg 1.20-1.35 zamiast realnej 1.58.
ZASTEPCZY_CZAS = {KNOSSOS: ("~2h 40m", 160), CHANIA: ("~35 min", 35)}
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
    """Atrapa `urllib.request.Request` - zapamiętuje URL, nagłówki i ciało POST.

    Valhalla i Google Routes jadą POST-em z ciałem JSON, OSRM i Open-Meteo samym GET-em."""

    def __init__(self, url, data=None, headers=None):
        self.url = url
        self.data = data
        self.headers = headers or {}


class SiecAtrapa:
    """Sterowalny `urlopen`: n-te wywołanie obsługuje n-ta reakcja, ostatnia obowiązuje dalej.

    Reakcją jest ładunek JSON (sukces) albo instancja wyjątku (awaria sieci).
    """

    def __init__(self, reakcje):
        self.reakcje = list(reakcje)
        self.zapytania = []
        self.ciala = []

    def __call__(self, req, timeout=None):
        self.zapytania.append((req.url, req.headers, timeout))
        self.ciala.append(json.loads(req.data.decode()) if req.data else None)
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
    # `parse` jedzie prawdziwy - adapter Open-Meteo skleja nim query stringa, a test sprawdza URL.
    return types.SimpleNamespace(
        request=types.SimpleNamespace(Request=Zapytanie, urlopen=siec),
        parse=urllib.parse,
    )


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
# Rejestr silników wymienia funkcje po nazwie, więc musi wejść do namespace'u po nich, a nie razem
# z pozostałymi stałymi. Jego źródło jest czytane z app.py, żeby test nie przepisywał kolejności silników.
SEGMENT_REJESTRU_SILNIKOW, = _segmenty_stalych(["SILNIKI_CZASU_PRZEJAZDU"])
# Widok podsumowania pogody ładowany osobno - rysuje przez Streamlita, więc nie wchodzi
# do wspólnego namespace'u testów sieciowych.
SEGMENT_PODSUMOWANIA = wczytaj_funkcje_z_app(
    ["renderuj_podsumowanie_pogody_wycieczki"]
)["renderuj_podsumowanie_pogody_wycieczki"]


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

    def __init__(self, reakcje, klucz_google=""):
        self.siec = SiecAtrapa(reakcje)
        self.zegar = ZegarAtrapa()
        # Dekoratory nie wchodzą w segment źródła, więc `_rejestr_awarii_api` wyciągnięty z app.py oddawałby
        # nowy słownik przy każdym wywołaniu i backoff nie miałby czego pamiętać. Podstawiamy domknięcie z jedną
        # parą (rejestr, blokada) na test - dokładnie tak, jak @st.cache_resource trzyma jedną parę na proces.
        self._rejestr_z_blokada = ({}, threading.Lock())
        # GOOGLE_ROUTES_KLUCZ czyta środowisko procesu, więc test podaje własny os - bez klucza kolejka
        # silników ma być dokładnie taka, jaką widzi aplikacja uruchomiona bez żadnych poświadczeń.
        self.ns = {
            "json": json,
            "math": math,
            "threading": threading,
            "os": types.SimpleNamespace(environ={"GOOGLE_ROUTES_API_KEY": klucz_google}),
            "urllib": _atrapa_urllib(self.siec),
            "zegar": self.zegar,
            "_rejestr_awarii_api": lambda: self._rejestr_z_blokada,
        }
        for kod in SEGMENTY_STALYCH:
            exec(kod, self.ns)
        for kod in SEGMENTY_FUNKCJI.values():
            exec(kod, self.ns)
        exec(SEGMENT_REJESTRU_SILNIKOW, self.ns)

    def __getitem__(self, nazwa):
        return self.ns[nazwa]

    @property
    def rejestr(self):
        return self._rejestr_z_blokada[0]


def odpowiedz_czasu(sekundy):
    """Odpowiedź OSRM - `duration` w sekundach."""
    return {"routes": [{"duration": sekundy}]}


def odpowiedz_valhalli(sekundy, km=42.0):
    """Odpowiedź Valhalli - `trip.summary.time` w sekundach."""
    return {"trip": {"summary": {"time": sekundy, "length": km}}}


def odpowiedz_google(sekundy):
    """Odpowiedź Google Routes v2 - `duration` jako napis z sufiksem `s`."""
    return {"routes": [{"duration": f"{sekundy}s"}]}


def odpowiedz_geometrii(punkty):
    return {"routes": [{"geometry": {"coordinates": punkty}}]}


# --- Kolejka silników trasowania ---

@pytest.mark.parametrize(
    "sekundy, oczekiwany",
    [
        (1800, ("~30 min", 30)),
        (1700, ("~30 min", 30)),
        (3600, ("~1h", 60)),
        (5400, ("~1h 30m", 90)),
        (60, ("~5 min", 5)),
    ],
)
def test_udana_odpowiedz_silnika_formatuje_czas(sekundy, oczekiwany):
    """Sekundy z silnika wychodzą jako napis do UI, z zaokrągleniem do 5 min i podłogą CZAS_PRZEJAZDU_MIN_MINUT.

    Podłoga to 5, a nie 10 minut: plaża w Stavros leży 1.2 km od domku i Google daje na nią 5 min,
    więc dawne 10 minut podwajało czas najbliższych celów."""
    srodowisko = Srodowisko([odpowiedz_valhalli(sekundy)])
    assert srodowisko["oblicz_czas_przejazdu"](*DOMEK, *KNOSSOS) == oczekiwany


def test_valhalla_jest_pierwszym_silnikiem_i_osrm_nie_jest_pytany():
    """Valhalla ma medianę błędu +5 min wobec Google, OSRM myli się o -23..+35 min - stąd ta kolejność."""
    srodowisko = Srodowisko([odpowiedz_valhalli(1800)])

    assert srodowisko["oblicz_czas_przejazdu"](*DOMEK, *KNOSSOS) == ("~30 min", 30)
    (url, _, _), = srodowisko.siec.zapytania
    assert url == srodowisko["VALHALLA_URL"]


def test_udana_odpowiedz_nie_zostawia_sladu_w_rejestrze_awarii():
    """Rejestr dotyczy wyłącznie awarii - po udanym strzale ma zostać pusty."""
    srodowisko = Srodowisko([odpowiedz_valhalli(1800)])
    srodowisko["oblicz_czas_przejazdu"](*DOMEK, *KNOSSOS)
    assert srodowisko.rejestr == {}


def test_zapytanie_do_valhalli_ma_wspolrzedne_profil_auto_i_timeout():
    """Kontrakt z Valhallą: POST z parą punktów, costing `auto` i VALHALLA_TIMEOUT_S."""
    srodowisko = Srodowisko([odpowiedz_valhalli(1800)])
    srodowisko["oblicz_czas_przejazdu"](*DOMEK, *KNOSSOS)

    (url, naglowki, timeout), = srodowisko.siec.zapytania
    cialo, = srodowisko.siec.ciala
    assert url == "https://valhalla1.openstreetmap.de/route"
    assert cialo["locations"] == [
        {"lat": 35.5914, "lon": 24.0918},
        {"lat": 35.2980, "lon": 25.1631},
    ]
    assert cialo["costing"] == "auto"
    assert naglowki["Content-Type"] == "application/json"
    assert naglowki["User-Agent"] == NAGLOWEK["User-Agent"]
    assert timeout == 5.0


def test_padniecie_valhalli_schodzi_do_osrm_z_dawnym_kontraktem():
    """OSRM został zapasem, więc jego adres, User-Agent i 4.0 s timeoutu zostają bez zmian."""
    srodowisko = Srodowisko([OSError("timeout Valhalla"), odpowiedz_czasu(1800)])

    assert srodowisko["oblicz_czas_przejazdu"](*DOMEK, *KNOSSOS) == ("~30 min", 30)
    assert srodowisko.siec.liczba_wywolan == 2
    (_, _, _), (url, naglowki, timeout) = srodowisko.siec.zapytania
    assert url == (
        "http://router.project-osrm.org/route/v1/driving/"
        "24.0918,35.5914;25.1631,35.298?overview=false"
    )
    assert naglowki == NAGLOWEK
    assert timeout == 4.0


def test_kazdy_silnik_ma_wlasny_wpis_w_rejestrze_awarii():
    """Padnięta Valhalla nie może wyciszyć OSRM-a - klucze rejestru różnią się nazwą silnika."""
    srodowisko = Srodowisko([OSError("timeout Valhalla"), odpowiedz_czasu(1800)])
    srodowisko["oblicz_czas_przejazdu"](*DOMEK, *KNOSSOS)

    assert ("valhalla_czas",) + DOMEK + KNOSSOS in srodowisko.rejestr
    assert ("osrm_czas",) + DOMEK + KNOSSOS not in srodowisko.rejestr


def test_wyciszona_valhalla_nie_jest_dobijana_a_osrm_liczy_dalej():
    """W oknie AWARIA_API_PONOW_PO_S render nie płaci timeoutu Valhalli, ale czas nadal wraca z OSRM-a."""
    srodowisko = Srodowisko([OSError("timeout Valhalla"), odpowiedz_czasu(1800)])
    czas = srodowisko["oblicz_czas_przejazdu"]

    assert czas(*DOMEK, *KNOSSOS) == ("~30 min", 30)
    assert srodowisko.siec.liczba_wywolan == 2

    assert czas(*DOMEK, *KNOSSOS) == ("~30 min", 30)
    assert srodowisko.siec.liczba_wywolan == 3, "Drugi render miał pytać już tylko OSRM"
    assert srodowisko.siec.zapytania[-1][0].startswith("http://router.project-osrm.org")


@pytest.mark.parametrize("bezuzyteczna", [{"code": "NoRoute"}, {"trip": {}}, {}])
def test_odpowiedz_bez_trasy_jest_awaria_silnika(bezuzyteczna):
    """Odpowiedź bez czasu przejazdu traktujemy jak timeout - schodzimy niżej w kolejce."""
    srodowisko = Srodowisko([bezuzyteczna, odpowiedz_czasu(1800)])
    assert srodowisko["oblicz_czas_przejazdu"](*DOMEK, *KNOSSOS) == ("~30 min", 30)
    assert ("valhalla_czas",) + DOMEK + KNOSSOS in srodowisko.rejestr


# --- Google Routes: tylko z kluczem w środowisku ---

def test_bez_klucza_google_nie_wchodzi_do_kolejki():
    """Aplikacja bez poświadczeń ma odpytywać wyłącznie silniki bezpłatne i bezkluczowe."""
    srodowisko = Srodowisko([odpowiedz_valhalli(1800)])
    assert [nazwa for nazwa, _ in srodowisko["SILNIKI_CZASU_PRZEJAZDU"]] == ["valhalla_czas", "osrm_czas"]


def test_z_kluczem_google_jest_pierwszy():
    """Google Routes jako jedyny uwzględnia ruch, więc z kluczem wyprzedza Valhallę."""
    srodowisko = Srodowisko([odpowiedz_google(1800)], klucz_google="klucz-testowy")
    assert [nazwa for nazwa, _ in srodowisko["SILNIKI_CZASU_PRZEJAZDU"]] == [
        "google_czas", "valhalla_czas", "osrm_czas",
    ]
    assert srodowisko["oblicz_czas_przejazdu"](*DOMEK, *KNOSSOS) == ("~30 min", 30)


def test_zapytanie_do_google_ma_klucz_maske_pol_i_tryb_ruchu():
    """Bez X-Goog-FieldMask Routes v2 odrzuca żądanie, a bez TRAFFIC_AWARE nie ma po co po nie sięgać."""
    srodowisko = Srodowisko([odpowiedz_google(5400)], klucz_google="klucz-testowy")
    srodowisko["oblicz_czas_przejazdu"](*DOMEK, *KNOSSOS)

    (url, naglowki, timeout), = srodowisko.siec.zapytania
    cialo, = srodowisko.siec.ciala
    assert url == "https://routes.googleapis.com/directions/v2:computeRoutes"
    assert naglowki["X-Goog-Api-Key"] == "klucz-testowy"
    assert naglowki["X-Goog-FieldMask"] == "routes.duration"
    assert cialo["travelMode"] == "DRIVE"
    assert cialo["routingPreference"] == "TRAFFIC_AWARE"
    assert cialo["origin"]["location"]["latLng"] == {"latitude": 35.5914, "longitude": 24.0918}
    assert timeout == 6.0


def test_padniecie_google_schodzi_do_valhalli():
    """Wyczerpany limit albo odrzucony klucz nie mogą zabrać rodzinie czasów przejazdu."""
    srodowisko = Srodowisko(
        [OSError("403 z Google"), odpowiedz_valhalli(3600)], klucz_google="klucz-testowy"
    )
    assert srodowisko["oblicz_czas_przejazdu"](*DOMEK, *KNOSSOS) == ("~1h", 60)
    assert ("google_czas",) + DOMEK + KNOSSOS in srodowisko.rejestr


# --- Fallback geometryczny: brak sieci ---

@pytest.mark.parametrize("cel", [KNOSSOS, CHANIA])
def test_padniecie_wszystkich_silnikow_daje_szacunek_geometryczny(cel):
    """Harmonogram dnia musi dostać liczbę minut nawet bez sieci - inaczej nie policzy godzin."""
    srodowisko = Srodowisko([OSError("brak sieci")])
    assert srodowisko["oblicz_czas_przejazdu"](*DOMEK, *cel) == ZASTEPCZY_CZAS[cel]
    assert srodowisko.siec.liczba_wywolan == 2, "Każdy silnik w kolejce ma dostać jedną próbę"


@pytest.mark.parametrize(
    "cel, oczekiwany",
    [
        # Trzy przedziały min/km: poniżej 20 km w linii prostej, do 50 km i powyżej.
        ((35.6105, 24.1065), ("~10 min", 10)),
        ((35.5138, 24.0180), ("~35 min", 35)),
        ((35.3323, 24.2777), ("~1h 15m", 75)),
        ((35.2980, 25.1631), ("~2h 40m", 160)),
    ],
)
def test_szacunek_stosuje_stawke_min_na_km_wlasciwa_dla_dystansu(cel, oczekiwany):
    """Krótki dojazd to serpentyny i miasteczka, długi biegnie trasą VOAK - jedna prędkość tego nie opisze."""
    assert Srodowisko([])["_szacunek_czasu_przejazdu"](*DOMEK, *cel) == oczekiwany


def test_szacunek_trzyma_podloge_czasu_przejazdu():
    """Odcinek zerowej długości wywróciłby układanie godzin w planie dnia."""
    srodowisko = Srodowisko([])
    assert srodowisko["_szacunek_czasu_przejazdu"](*DOMEK, *DOMEK) == (
        "~5 min", srodowisko["CZAS_PRZEJAZDU_MIN_MINUT"],
    )


def test_awaria_nie_powtarza_strzalu_w_oknie_i_wraca_po_wygasnieciu():
    """Przez AWARIA_API_PONOW_PO_S render nie dobija padających API, potem próbuje ponownie."""
    srodowisko = Srodowisko([OSError("brak sieci")])
    czas = srodowisko["oblicz_czas_przejazdu"]

    assert czas(*DOMEK, *KNOSSOS) == ZASTEPCZY_CZAS[KNOSSOS]
    assert srodowisko.siec.liczba_wywolan == 2

    srodowisko.zegar.przesun(599)
    assert czas(*DOMEK, *KNOSSOS) == ZASTEPCZY_CZAS[KNOSSOS]
    assert srodowisko.siec.liczba_wywolan == 2, "Wpisy w rejestrze miały stłumić ponowne strzały"

    srodowisko.zegar.przesun(2)
    srodowisko.siec.reakcje = [odpowiedz_valhalli(1800)]
    assert czas(*DOMEK, *KNOSSOS) == ("~30 min", 30)
    assert srodowisko.siec.liczba_wywolan == 3
    assert ("valhalla_czas",) + DOMEK + KNOSSOS not in srodowisko.rejestr


def test_awaria_jednej_trasy_nie_blokuje_innej():
    """Klucz rejestru zawiera współrzędne - awaria odcinka nie wycisza całego silnika."""
    srodowisko = Srodowisko([OSError("brak sieci")])
    srodowisko["oblicz_czas_przejazdu"](*DOMEK, *KNOSSOS)

    srodowisko.siec.reakcje = [odpowiedz_valhalli(3600)]
    assert srodowisko["oblicz_czas_przejazdu"](*DOMEK, *CHANIA) == ("~1h", 60)


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


# --- Prognoza pogody (Open-Meteo) ---
#
# Open-Meteo oddaje dane kolumnami: `time` plus po jednej liście na każdą wielkość, indeksowane równolegle.
# Aplikacja zszywa je we własny kształt (lista godzin), więc testy pilnują właśnie tego przejścia,
# a nie surowej odpowiedzi dostawcy.

def odpowiedz_pogody(godziny, **kolumny):
    """Buduje kolumnową odpowiedź Open-Meteo dla podanych godzin dnia."""
    data = "2026-09-12"
    domyslne = {
        "temperature_2m": [24.4] * len(godziny),
        "apparent_temperature": [26.6] * len(godziny),
        "weather_code": [0] * len(godziny),
        "wind_speed_10m": [11.5] * len(godziny),
        "uv_index": [7.4] * len(godziny),
    }
    domyslne.update(kolumny)
    return {"hourly": {"time": [f"{data}T{g:02d}:00" for g in godziny], **domyslne}}


def test_pogoda_sklada_kolumny_w_godziny():
    """Kolumnowa odpowiedź musi wyjść jako lista godzin z polami, których używa widok."""
    srodowisko = Srodowisko([odpowiedz_pogody([11, 12])])
    prognoza = srodowisko["pobierz_prognoze_pogody"](*DOMEK, "2026-09-12")

    assert prognoza["data"] == "2026-09-12"
    assert [g["godzina"] for g in prognoza["godziny"]] == [11, 12]
    # Wartości lądują w UI jako liczby całkowite - stopnie po przecinku nie niosą tu informacji.
    assert prognoza["godziny"][0] == {
        "godzina": 11, "temp": 24, "odczuwalna": 27, "wiatr": 12, "uv": 7,
        "opis": "Bezchmurnie", "deszcz": False, "burza": False, "kod": 0,
    }


def test_pogoda_pyta_o_konkretna_date_i_strefe():
    """Dzień wybiera API, a nie zgadywanie po liście - w zapytaniu jedzie data i strefa czasowa."""
    srodowisko = Srodowisko([odpowiedz_pogody([12])])
    srodowisko["pobierz_prognoze_pogody"](*DOMEK, "2026-09-12")

    (url, naglowki, timeout), = srodowisko.siec.zapytania
    assert url.startswith("https://api.open-meteo.com/v1/forecast?")
    assert "start_date=2026-09-12&end_date=2026-09-12" in url
    assert "timezone=Europe%2FAthens" in url
    assert naglowki == NAGLOWEK
    assert timeout == 4


@pytest.mark.parametrize(
    "kod, opis, deszcz, burza",
    [
        (0, "Bezchmurnie", False, False),
        (61, "Słaby deszcz", True, False),
        (80, "Przelotny deszcz", True, False),
        (95, "Burza", False, True),
        (123, "Zmienna pogoda", False, False),
    ],
)
def test_kod_wmo_przeklada_sie_na_opis_i_flagi(kod, opis, deszcz, burza):
    """Ostrzeżenia na karcie wycieczki biorą się z kodu WMO, nie z dopasowywania angielskich napisów."""
    srodowisko = Srodowisko([odpowiedz_pogody([12], weather_code=[kod])])
    godzina, = srodowisko["pobierz_prognoze_pogody"](*DOMEK, "2026-09-12")["godziny"]
    assert (godzina["opis"], godzina["deszcz"], godzina["burza"]) == (opis, deszcz, burza)


def test_dziura_w_serii_nie_wysypuje_prognozy():
    """Brak pojedynczego pomiaru (None w kolumnie) schodzi do zera, nie do wyjątku."""
    srodowisko = Srodowisko([odpowiedz_pogody([12], uv_index=[None], wind_speed_10m=[None])])
    godzina, = srodowisko["pobierz_prognoze_pogody"](*DOMEK, "2026-09-12")["godziny"]
    assert (godzina["uv"], godzina["wiatr"]) == (0, 0)


def test_pogoda_bez_godzin_to_awaria():
    """Odpowiedź bez godzin jest bezużyteczna - None dla UI, wpis w rejestrze zamiast cache."""
    srodowisko = Srodowisko([{"hourly": {"time": []}}])
    assert srodowisko["pobierz_prognoze_pogody"](*DOMEK, "2026-09-12") is None
    assert ("open_meteo",) + DOMEK + ("2026-09-12",) in srodowisko.rejestr


def test_pogoda_po_wyjatku_daje_none_bez_dobijania_api():
    """Timeout serwisu pogodowego tłumiony jest tak samo jak awarie OSRM."""
    srodowisko = Srodowisko([OSError("timeout pogody")])

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
    klucz = ("open_meteo", 35.0, 24.0, "2026-09-12")
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
    srodowisko["_zanotuj_awarie_api"](("open_meteo", "swiezy"))
    assert list(srodowisko.rejestr) == [("open_meteo", "swiezy")]


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


# --- Widok podsumowania pogody na karcie wycieczki ---
#
# Funkcja rysuje kartę przez `st.markdown`, więc test podstawia atrapę Streamlita i czyta,
# co faktycznie poszłoby do HTML.

class StAtrapa:
    """Zbiera wywołania st.markdown - test sprawdza treść, która trafiłaby na ekran."""

    def __init__(self):
        self.markdown = []

    def __call__(self, tresc, **_):
        self.markdown.append(tresc)

    @property
    def html(self):
        return "\n".join(self.markdown)


def _podsumowanie_html(prognoza):
    """Renderuje kartę podsumowania dla podanej prognozy i zwraca HTML, który poszedłby na ekran."""
    st_atrapa = StAtrapa()
    ns = {
        "st": types.SimpleNamespace(markdown=st_atrapa),
        "sparsuj_wspolrzedne": lambda wspolrzedne: DOMEK,
        "pobierz_prognoze_pogody": lambda lat, lon, data: prognoza,
    }
    for kod in _segmenty_stalych(["WMO_BEZCHMURNIE", "WMO_LEKKIE_CHMURY", "WMO_ZACHMURZENIE"]):
        exec(kod, ns)
    exec(SEGMENT_PODSUMOWANIA, ns)

    kroki = pd.DataFrame([{"wspolrzedne": "35.5914, 24.0918"}])
    ns["renderuj_podsumowanie_pogody_wycieczki"](kroki, "2026-09-12")
    return st_atrapa.html


def test_podsumowanie_bez_danych_mowi_wprost_ze_ich_nie_ma():
    """Padnięte API nie może dawać wyssanych z palca stopni - wcześniej szło '99°C – -99°C'."""
    html = _podsumowanie_html(None)

    assert "{TODO}" in html
    assert "nie odpowiada" in html
    assert "99" not in html, "wartowniki z inicjalizacji nie mogą wyciec do UI"


def test_podsumowanie_z_danymi_podaje_zakres_i_ostrzezenia():
    """Przy poprawnej prognozie karta pokazuje zakres temperatur i ostrzeżenie z kodu WMO."""
    prognoza = {"data": "2026-09-12", "godziny": [
        {"godzina": 9, "temp": 24, "odczuwalna": 26, "wiatr": 12, "uv": 6,
         "opis": "Bezchmurnie", "deszcz": False, "burza": False, "kod": 0},
        {"godzina": 15, "temp": 33, "odczuwalna": 36, "wiatr": 21, "uv": 9,
         "opis": "Burza", "deszcz": False, "burza": True, "kod": 95},
    ]}
    html = _podsumowanie_html(prognoza)

    assert "24°C – 33°C" in html
    assert "Ryzyko burz" in html
    assert "Wysoka temperatura (do 33°C)" in html
    assert "Wiatr do 21 km/h" in html
    assert "{TODO}" not in html
