"""Testy regresyjne scalonego geokodera OSM i pojedynczego zapisu czasów dojazdu.

Trzy usterki pilnowane tutaj:
1. `rozwiaz_geolokalizacje_miejsca_kreta` była zdefiniowana dwa razy. Skrypt wykonuje się od góry
   do dołu, więc obowiązywała ta późniejsza - bez parametru `kontekst_miasta` - i wywołanie z
   kontekstem w `utworz_nowe_miejsce` leciało na `TypeError`.
2. `przelicz_i_zsynchronizuj_wycieczke` wstawiała ten sam wiersz do `czasy_dojazdu` dwa razy pod rząd.
3. `utworz_nowe_miejsce` odpytywało Nominatim dwukrotnie tymi samymi frazami - stąd testy budżetu
   zapytań (`pomin_bez_kontekstu`), bo każde zapytanie to 1.8 s wewnątrz pętli narzędziowej modelu.

`app.py` jest skryptem Streamlit - import całego modułu uruchomiłby UI, więc testy wyciągają badane
funkcje ze źródła przez AST i uruchamiają je na tymczasowej bazie SQLite. Sieć podstawiana jest
atrapą (`urllib`), a poza zakresem tych testów zostają OSRM i zrzut do CSV.

Uruchomienie:  pytest test_geokoder_i_dojazdy.py
"""

import ast
import io
import json
import re
import sqlite3
import types
import urllib.parse

import pandas as pd
import pytest

from conftest import SCIEZKA_APP, wczytaj_funkcje_z_app

BADANE_FUNKCJE = [
    "sparsuj_wspolrzedne",
    "sparsuj_godzine_minuty",
    "sparsuj_czas_ogarniania_na_minuty",
    "oblicz_czas_trwania_okienka",
    "kategoryzuj_typ",
    "rozwiaz_geolokalizacje_miejsca_kreta",
    "przelicz_i_zsynchronizuj_wycieczke",
    "utworz_nowe_miejsce",
]

STALE_MODULU = ["GODZINA_GRANICZNA_KOLACJI", "CATEGORIES_CONFIG"]

with io.open(SCIEZKA_APP, encoding="utf-8") as plik:
    ZRODLO_APP = plik.read()
DRZEWO_APP = ast.parse(ZRODLO_APP)

SEGMENTY_FUNKCJI = wczytaj_funkcje_z_app(BADANE_FUNKCJE)

SCHEMAT = """
CREATE TABLE wycieczka (
    id TEXT PRIMARY KEY, tytul_wycieczki TEXT, pobudka TEXT, czas_wyjazdu TEXT,
    szacowana_godzina_powrotu TEXT, calkowity_czas_wycieczki_godziny TEXT,
    czas_powrotu_do_domku TEXT, szacowany_czas_ogarniania_rano TEXT);
CREATE TABLE krok_wycieczki (
    id INTEGER PRIMARY KEY AUTOINCREMENT, id_wycieczki TEXT, krok_wycieczki INTEGER,
    numer_miejsca TEXT, nazwa TEXT, wspolrzedne TEXT, okienko_zwiedzania TEXT,
    godzina_ewakuacji TEXT, podsumowanie_taktyki TEXT, opis TEXT);
CREATE TABLE posilki_kroku (
    id INTEGER PRIMARY KEY AUTOINCREMENT, id_kroku INTEGER, rodzaj_posilku TEXT,
    miejsce TEXT, sugerowana_godzina TEXT, opis TEXT);
CREATE TABLE miejsca (
    numer_miejsca TEXT, nazwa TEXT, nazwa_angielska TEXT, adres TEXT, typ TEXT,
    wspolrzedne TEXT, czas_dojazdu TEXT, orientacyjny_czas TEXT, koszt TEXT,
    godziny_otwarcia TEXT, konieczna_akcja TEXT, trudnosc_adhd TEXT, ochrona_slonce TEXT,
    potencjal_meltdownu TEXT, strategie_meltdown TEXT, opis TEXT, zadania_dla_dzieci TEXT,
    odwiedzone INTEGER);
CREATE TABLE czasy_dojazdu (
    id INTEGER PRIMARY KEY AUTOINCREMENT, id_kroku_z INTEGER, id_kroku_do INTEGER,
    czas_przejazdu TEXT, szacowany_czas_postoju INTEGER DEFAULT 0);
"""

# Poza zakresem tych testów: prawdziwy OSRM (sieć) - wszystkie odcinki dostają tę samą wartość.
ZASTEPCZY_DOJAZD = ("~25 min", 25)


# --- Atrapy zależności zewnętrznych (wzorzec z test_api_zewnetrzne.py) ---

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
        self.reakcje = list(reakcje) or [OSError("brak sieci")]
        self.zapytania = []

    def __call__(self, req, timeout=None):
        self.zapytania.append((req.url, req.headers, timeout))
        reakcja = self.reakcje[min(len(self.zapytania) - 1, len(self.reakcje) - 1)]
        if isinstance(reakcja, Exception):
            raise reakcja
        return OdpowiedzHTTP(reakcja)

    @property
    def frazy(self):
        """Odpytane frazy w kolejności wywołań - parametr `q` rozkodowany z URL-a."""
        return [
            urllib.parse.unquote(url.split("q=", 1)[1].split("&", 1)[0])
            for url, _, _ in self.zapytania
        ]

    @property
    def timeouty(self):
        return [timeout for _, _, timeout in self.zapytania]


def odpowiedz_nominatim(lat, lon):
    """Trafienie Nominatim - współrzędne przychodzą jako napisy, tak jak z prawdziwego API."""
    return [{"lat": str(lat), "lon": str(lon)}]


class Srodowisko:
    """Świeża baza SQLite i namespace z funkcjami app.py, podstawioną siecią i atrapą OSRM."""

    def __init__(self, sciezka_db, reakcje):
        self.sciezka_db = str(sciezka_db)
        self.conn = sqlite3.connect(self.sciezka_db)
        self.conn.executescript(SCHEMAT)
        self.conn.commit()

        self.siec = SiecAtrapa(reakcje)
        self.ns = {
            "pd": pd,
            "re": re,
            "json": json,
            "sqlite3": sqlite3,
            "datetime": __import__("datetime").datetime,
            "timedelta": __import__("datetime").timedelta,
            "DOMEK_LAT": 35.5914,
            "DOMEK_LON": 24.0918,
            "urllib": types.SimpleNamespace(
                parse=urllib.parse,
                request=types.SimpleNamespace(Request=Zapytanie, urlopen=self.siec),
            ),
            "get_db": lambda: sqlite3.connect(self.sciezka_db, timeout=30.0),
            # Poza zakresem tych testów: trasy z OSRM i zrzut bazy do plików CSV.
            "oblicz_czas_przejazdu_osrm": lambda *a, **k: ZASTEPCZY_DOJAZD,
            "zsynchronizuj_baze_do_csv": lambda *a, **k: None,
        }
        for kod in _segmenty_stalych(STALE_MODULU):
            exec(kod, self.ns)
        for kod in SEGMENTY_FUNKCJI.values():
            exec(kod, self.ns)

    def __getattr__(self, nazwa):
        # `ns` powstaje dopiero w __init__ - bez tej gardy odwołanie do self.ns przed przypisaniem
        # wpadłoby w nieskończoną rekurencję. Nieznane nazwy mają wyglądać jak brakujący atrybut
        # (AttributeError), a nie wysypywać się KeyError-em spod spodu.
        if nazwa == "ns":
            raise AttributeError(nazwa)
        try:
            return self.ns[nazwa]
        except KeyError:
            raise AttributeError(nazwa) from None

    def utworz_wycieczke(self, id_wycieczki, nazwy_krokow):
        self.conn.execute(
            "INSERT INTO wycieczka (id, tytul_wycieczki, pobudka, czas_wyjazdu,"
            " szacowany_czas_ogarniania_rano) VALUES (?, ?, '06:00', '06:30', '0.5h')",
            (id_wycieczki, f"test {id_wycieczki}"),
        )
        ids = []
        for pozycja, nazwa in enumerate(nazwy_krokow):
            kursor = self.conn.execute(
                "INSERT INTO krok_wycieczki (id_wycieczki, krok_wycieczki, nazwa, wspolrzedne,"
                " okienko_zwiedzania) VALUES (?, ?, ?, '35.5000, 24.0000', '10:00 - 11:00')",
                (id_wycieczki, pozycja, nazwa),
            )
            ids.append(kursor.lastrowid)
        self.conn.commit()
        return ids

    def dojazdy(self):
        """Wszystkie pary (krok_z, krok_do) z `czasy_dojazdu` - z powtórzeniami, jeśli są."""
        return [
            (r[0], r[1])
            for r in self.conn.execute(
                "SELECT id_kroku_z, id_kroku_do FROM czasy_dojazdu ORDER BY id"
            )
        ]

    def miejsce(self, nazwa):
        return self.conn.execute(
            "SELECT numer_miejsca, wspolrzedne, typ FROM miejsca WHERE nazwa = ?", (nazwa,)
        ).fetchone()


def _segmenty_stalych(nazwy):
    """Zwraca źródła modułowych przypisań z app.py (stałe używane przez badane funkcje)."""
    znalezione = {}
    for wezel in DRZEWO_APP.body:
        if isinstance(wezel, ast.Assign):
            for cel in wezel.targets:
                if getattr(cel, "id", None) in nazwy:
                    znalezione[cel.id] = ast.get_source_segment(ZRODLO_APP, wezel)
    brakujace = [n for n in nazwy if n not in znalezione]
    assert not brakujace, f"Nie znaleziono przypisań w app.py: {brakujace}"
    return [znalezione[n] for n in nazwy]


def _wezel_init_db():
    """Węzeł AST funkcji `init_db` z app.py."""
    for wezel in DRZEWO_APP.body:
        if isinstance(wezel, ast.FunctionDef) and wezel.name == "init_db":
            return wezel
    raise AssertionError("Nie znaleziono init_db w app.py")


def _sql_sprzatania_duplikatow():
    """Wyciąga z `init_db` zapytanie sprzątające duplikaty w `czasy_dojazdu`."""
    for w in ast.walk(_wezel_init_db()):
        if (
            isinstance(w, ast.Constant)
            and isinstance(w.value, str)
            and "DELETE FROM czasy_dojazdu" in w.value
            and "MIN(rowid)" in w.value
        ):
            return w.value
    raise AssertionError("init_db nie sprząta duplikatów w czasy_dojazdu")


def _instrukcje_init_db():
    """Spłaszczone instrukcje `init_db` (bez bloków opakowujących) w kolejności źródła."""
    liscie = [
        w for w in ast.walk(_wezel_init_db())
        if isinstance(w, ast.stmt)
        and not any(isinstance(p, ast.stmt) and p is not w for p in ast.walk(w))
    ]
    return sorted(liscie, key=lambda w: (w.lineno, w.col_offset))


def _indeks_instrukcji_init_db(fragment):
    """Pozycja instrukcji `init_db`, której literał tekstowy zawiera `fragment`."""
    for indeks, instrukcja in enumerate(_instrukcje_init_db()):
        if any(
            isinstance(w, ast.Constant) and isinstance(w.value, str) and fragment in w.value
            for w in ast.walk(instrukcja)
        ):
            return indeks
    raise AssertionError(f"init_db nie zawiera instrukcji z {fragment!r}")


@pytest.fixture
def srodowisko(tmp_path):
    """Fabryka środowiska - każdy test dostaje własną bazę i własny scenariusz sieci."""
    licznik = []

    def zbuduj(reakcje=()):
        licznik.append(1)
        return Srodowisko(tmp_path / f"test{len(licznik)}.db", reakcje)

    return zbuduj


# --- (a) Jedna definicja geokodera ---

def test_geokoder_ma_w_app_dokladnie_jedna_definicje():
    """Dwie definicje maskowały się nawzajem - zostaje jedna, z opcjonalnym kontekstem miasta."""
    definicje = [
        w for w in DRZEWO_APP.body
        if isinstance(w, ast.FunctionDef) and w.name == "rozwiaz_geolokalizacje_miejsca_kreta"
    ]
    assert len(definicje) == 1

    (definicja,) = definicje
    assert [a.arg for a in definicja.args.args] == [
        "nazwa_miejsca", "kontekst_miasta", "pomin_bez_kontekstu",
    ]
    assert [d.value for d in definicja.args.defaults] == ["", False]


# --- (b) Geokoder: zapytania, granice Krety, awarie ---

def test_nazwa_ze_slowem_do_wyciecia_daje_dwa_zapytania(srodowisko):
    """Bez kontekstu obowiązuje stare zachowanie: pełna nazwa, potem oczyszczona, po 1.8 s."""
    sr = srodowisko([OSError("timeout Nominatim")])
    assert sr.rozwiaz_geolokalizacje_miejsca_kreta("Tawerna Kariatis") == (None, None)

    assert sr.siec.frazy == ["Tawerna Kariatis Crete Greece", "Kariatis Crete Greece"]
    assert sr.siec.timeouty == [1.8, 1.8]


def test_nazwa_bez_slowa_do_wyciecia_daje_jedno_zapytanie(srodowisko):
    """Gdy czyszczenie nic nie zmienia, oba warianty są identyczne - pytamy raz.

    Przy okazji kształt samego żądania: Nominatim wymaga własnego User-Agenta, a viewbox
    i limit=1 trzymają odpowiedzi w granicach Krety.
    """
    sr = srodowisko([OSError("timeout Nominatim")])
    sr.rozwiaz_geolokalizacje_miejsca_kreta("Knossos")

    assert sr.siec.frazy == ["Knossos Crete Greece"]

    (url, naglowki, _), = sr.siec.zapytania
    assert naglowki["User-Agent"] == "CretAiApp/1.0 (FamilyTripPlanner)"
    assert "format=json&limit=1&bounded=1&viewbox=23.40,35.75,26.40,34.80" in url


def test_kontekst_miasta_bez_slowa_do_wyciecia_daje_dwa_zapytania(srodowisko):
    """Nazwa, której regułka nie rusza: zapytanie z miastem, a po nim jeden wariant bazowy."""
    sr = srodowisko([OSError("timeout Nominatim")])
    sr.rozwiaz_geolokalizacje_miejsca_kreta("Knossos", kontekst_miasta="Heraklion")

    assert sr.siec.frazy == ["Knossos Heraklion Crete Greece", "Knossos Crete Greece"]


@pytest.mark.parametrize("pusta_nazwa", ["", None])
def test_pusta_nazwa_nie_rusza_sieci(srodowisko, pusta_nazwa):
    """Model potrafi podać pustą nazwę - to ma kosztować zero zapytań, a nie wyjątek."""
    sr = srodowisko([odpowiedz_nominatim(35.3387, 25.1332)])

    assert sr.rozwiaz_geolokalizacje_miejsca_kreta(pusta_nazwa) == (None, None)
    assert sr.siec.zapytania == []


def test_pominiecie_wariantow_bez_kontekstu_zostawia_samo_zapytanie_z_miastem(srodowisko):
    """Druga próba w `utworz_nowe_miejsce` nie powtarza wariantów odpytanych już wcześniej."""
    sr = srodowisko([OSError("timeout Nominatim")])
    sr.rozwiaz_geolokalizacje_miejsca_kreta(
        "Tawerna Kariatis", kontekst_miasta="Heraklion", pomin_bez_kontekstu=True
    )

    assert sr.siec.frazy == ["Kariatis Heraklion Crete Greece"]


def test_pominiecie_wariantow_bez_miasta_nie_rusza_sieci(srodowisko):
    """Bez kontekstu miasta nie ma czego dokładać - zero zapytań i od razu (None, None)."""
    sr = srodowisko([odpowiedz_nominatim(35.3387, 25.1332)])
    wynik = sr.rozwiaz_geolokalizacje_miejsca_kreta("Tawerna Kariatis", pomin_bez_kontekstu=True)

    assert wynik == (None, None)
    assert sr.siec.zapytania == []


def test_kontekst_miasta_dokladany_jest_jako_pierwsze_zapytanie(srodowisko):
    """Kontekst miasta ma zawęzić wyszukiwanie, więc idzie przed wariantami bez miasta."""
    sr = srodowisko([OSError("timeout Nominatim")])
    sr.rozwiaz_geolokalizacje_miejsca_kreta("Tawerna Kariatis", kontekst_miasta="Heraklion")

    assert sr.siec.frazy == [
        "Kariatis Heraklion Crete Greece",
        "Tawerna Kariatis Crete Greece",
        "Kariatis Crete Greece",
    ]


def test_kontekst_miasta_juz_w_nazwie_nie_dubluje_zapytania(srodowisko):
    """Miasto siedzące już w nazwie niesie sam wariant bazowy - doklejanie go drugi raz dałoby
    "Peskesi Heraklion Heraklion Crete Greece" i spaliło 1.8 s na bezsensownej frazie."""
    sr = srodowisko([OSError("timeout Nominatim")])
    sr.rozwiaz_geolokalizacje_miejsca_kreta("Peskesi Heraklion", kontekst_miasta="Heraklion")

    assert sr.siec.frazy == ["Peskesi Heraklion Crete Greece"]

    # Skoro zapytanie z kontekstem odpada, to przy pominiętych wariantach bazowych nie zostaje nic.
    sr_pomin = srodowisko([odpowiedz_nominatim(35.3387, 25.1332)])
    wynik = sr_pomin.rozwiaz_geolokalizacje_miejsca_kreta(
        "Peskesi Heraklion", kontekst_miasta="Heraklion", pomin_bez_kontekstu=True
    )

    assert wynik == (None, None)
    assert sr_pomin.siec.zapytania == []


def test_trafienie_spoza_krety_jest_pomijane(srodowisko):
    """Nominatim potrafi oddać Ateny mimo viewboxa - takie trafienie odrzucamy i pytamy dalej."""
    sr = srodowisko([odpowiedz_nominatim(37.9838, 23.7275), odpowiedz_nominatim(35.3387, 25.1332)])

    assert sr.rozwiaz_geolokalizacje_miejsca_kreta("Tawerna Kariatis") == (35.3387, 25.1332)
    assert sr.siec.frazy == ["Tawerna Kariatis Crete Greece", "Kariatis Crete Greece"]


def test_trafienie_w_granicach_krety_wraca_jako_liczby(srodowisko):
    """Współrzędne przychodzą z API jako napisy, a wołający dostaje floaty."""
    sr = srodowisko([odpowiedz_nominatim(35.2980, 25.1631)])
    lat, lon = sr.rozwiaz_geolokalizacje_miejsca_kreta("Knossos")

    assert (lat, lon) == (35.2980, 25.1631)
    assert isinstance(lat, float) and isinstance(lon, float)
    assert sr.siec.timeouty == [1.8]


def test_wszystkie_zapytania_nieudane_daja_brak_wspolrzednych(srodowisko):
    """Padnięty geokoder ma oddać (None, None), a nie wyjątek - wołający ma własne awaryjne ścieżki."""
    sr = srodowisko([OSError("timeout Nominatim")])
    assert sr.rozwiaz_geolokalizacje_miejsca_kreta("Tawerna Kariatis") == (None, None)


# --- (c) utworz_nowe_miejsce: ścieżka awaryjna z kontekstem miasta ---

def test_nowe_miejsce_bez_wspolrzednych_laduje_w_heraklionie(srodowisko):
    """Regresja: wywołanie geokodera z `kontekst_miasta` leciało na TypeError, bo obowiązywała
    druga definicja funkcji (jednoargumentowa). Model widział tylko 'Błędne argumenty narzędzia'."""
    sr = srodowisko([OSError("timeout Nominatim")])

    wynik = sr.utworz_nowe_miejsce(
        nazwa="Tawerna Testowa Heraklion", typ="Other", wspolrzedne=""
    )

    assert wynik["success"] is True
    assert sr.miejsce("Tawerna Testowa Heraklion") == ("1", "35.3387, 25.1332", "Other")
    # Druga próba geokodowania (ta, która wcześniej się wywracała) nie dokłada nic: warianty bazowe
    # poszły już w pierwszej próbie, a miasto siedzi w nazwie, więc zapytanie z kontekstem odpada.
    assert sr.siec.frazy == [
        "Tawerna Testowa Heraklion Crete Greece",
        "Testowa Heraklion Crete Greece",
    ]


def test_nowe_miejsce_ze_wspolrzednymi_spoza_krety_laduje_w_domku(srodowisko):
    """Regresja: stary strażnik pytał tylko `if lat_p is None`, więc ateńskie współrzędne podane przez
    model trafiały do bazy - mimo że `czy_w_granicach` przed chwilą je odrzuciło. Tutaj geokodowanie
    pada, żaden krok wycieczki nie ma współrzędnych, więc zostaje awaryjny domek."""
    sr = srodowisko([OSError("timeout Nominatim")])

    wynik = sr.utworz_nowe_miejsce(
        nazwa="Restauracja Kariatis", typ="Other", wspolrzedne="37.9838, 23.7275"
    )

    assert wynik["success"] is True
    # Pierwsza próba geokodowania nie poszła (współrzędne były podane, a w nazwie nie ma
    # tavern/tawern/ammoudi/gefyra), więc lecą same warianty bazowe z próby awaryjnej - bez
    # kontekstu miasta, bo żadnego nie ma ani w nazwie, ani w opisie, ani w adresie.
    assert sr.siec.frazy == ["Restauracja Kariatis Crete Greece", "Kariatis Crete Greece"]
    assert sr.miejsce("Restauracja Kariatis") == (
        "1", f"{sr.DOMEK_LAT:.4f}, {sr.DOMEK_LON:.4f}", "Other"
    )


# --- (d) Czasy dojazdu: jeden wiersz na odcinek ---

def test_przeliczenie_zapisuje_jeden_wiersz_na_odcinek(srodowisko):
    """Regresja: blok INSERT-a stał w kodzie dwa razy pod rząd, więc każdy odcinek szedł podwójnie."""
    sr = srodowisko()
    ids = sr.utworz_wycieczke("1", ["Nasz Domek (Start)", "Plaza Falasarna", "Nasz Domek (Powrot)"])

    sr.przelicz_i_zsynchronizuj_wycieczke("1")

    assert sr.dojazdy() == [(ids[0], ids[1]), (ids[1], ids[2])]


def test_ponowne_przeliczenie_nie_mnozy_wierszy(srodowisko):
    """Przeliczanie jest idempotentne - kasowanie starych wierszy plus jeden zapis na odcinek."""
    sr = srodowisko()
    ids = sr.utworz_wycieczke("1", ["Nasz Domek (Start)", "Plaza Falasarna", "Nasz Domek (Powrot)"])

    sr.przelicz_i_zsynchronizuj_wycieczke("1")
    sr.przelicz_i_zsynchronizuj_wycieczke("1")

    assert sr.dojazdy() == [(ids[0], ids[1]), (ids[1], ids[2])]


# --- (e) Sprzątanie duplikatów z init_db ---

def test_sprzatanie_z_init_db_zostawia_najstarszy_wiersz_pary(tmp_path):
    """Zapytanie z init_db czyści bazy sprzed poprawki: jedna para - jeden wiersz, ten pierwszy."""
    conn = sqlite3.connect(str(tmp_path / "duplikaty.db"))
    conn.executescript(SCHEMAT)
    rowidy = {}
    for id_z, id_do, czas in [(1, 2, "~10 min"), (1, 2, "~10 min"), (2, 3, "~20 min"),
                              (2, 3, "~20 min"), (3, 4, "~30 min")]:
        kursor = conn.execute(
            "INSERT INTO czasy_dojazdu (id_kroku_z, id_kroku_do, czas_przejazdu,"
            " szacowany_czas_postoju) VALUES (?, ?, ?, 0)", (id_z, id_do, czas))
        rowidy.setdefault((id_z, id_do), kursor.lastrowid)
    conn.commit()

    conn.execute(_sql_sprzatania_duplikatow())
    conn.commit()

    zostale = list(conn.execute("SELECT id_kroku_z, id_kroku_do, rowid FROM czasy_dojazdu ORDER BY rowid"))
    assert [(z, do) for z, do, _ in zostale] == [(1, 2), (2, 3), (3, 4)]
    assert {(z, do): rid for z, do, rid in zostale} == rowidy


def test_sprzatanie_duplikatow_stoi_po_utworzeniu_tabeli_i_indeksu():
    """Kolejność w `init_db` jest istotna: bez CREATE TABLE nie ma czego czyścić, a bez indeksu
    czyszczenie schodzi do pełnego skanu przy każdym przebiegu skryptu."""
    indeks_tabeli = _indeks_instrukcji_init_db("CREATE TABLE IF NOT EXISTS czasy_dojazdu")
    indeks_indeksu = _indeks_instrukcji_init_db("idx_czasy_dojazd")
    indeks_delete = _indeks_instrukcji_init_db("DELETE FROM czasy_dojazdu")

    assert indeks_tabeli < indeks_delete
    assert indeks_indeksu < indeks_delete


def test_sprzatanie_z_init_db_jest_idempotentne(tmp_path):
    """Zapytanie leci przy każdym starcie aplikacji - na czystej bazie nie może niczego ruszyć."""
    conn = sqlite3.connect(str(tmp_path / "czysta.db"))
    conn.executescript(SCHEMAT)
    conn.execute(
        "INSERT INTO czasy_dojazdu (id_kroku_z, id_kroku_do, czas_przejazdu,"
        " szacowany_czas_postoju) VALUES (1, 2, '~10 min', 0)")
    conn.commit()

    for _ in range(2):
        conn.execute(_sql_sprzatania_duplikatow())
    conn.commit()

    assert list(conn.execute("SELECT id_kroku_z, id_kroku_do FROM czasy_dojazdu")) == [(1, 2)]
