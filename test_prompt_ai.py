"""Testy regresyjne warstwy promptów AI (cache CLI i środowisko procesu).

Claude Code CLI trafia w cache promptu systemowego tylko wtedy, gdy jego bajty są
identyczne między wywołaniami, więc dane zmienne (rodzic, data, ID wycieczki, kontekst
z bazy) muszą jechać w wiadomości użytkownika, a nie w prompcie systemowym. Testy
pilnują tej niezmienności, identyczności treści bez kontekstu z wersją sprzed zmiany
oraz wyciszenia środowiska procesu CLI.

Uruchomienie:  pytest test_prompt_ai.py
"""

import ast
import hashlib
import io
import json
import os
import subprocess
import sys

import pytest

from conftest import SCIEZKA_APP, wczytaj_funkcje_z_app

BADANE_FUNKCJE = ["zbuduj_tresc_rozmowy", "srodowisko_claude_cli"]


def _zaladuj(nazwy, dodatkowe=None):
    """Uruchamia funkcje z app.py w namespace z ich zależnościami."""
    ns = {"json": json, "os": os}
    ns.update(dodatkowe or {})
    for kod in wczytaj_funkcje_z_app(nazwy).values():
        exec(kod, ns)
    return ns


FUNKCJE = _zaladuj(BADANE_FUNKCJE)

ZRODLO_APP = io.open(SCIEZKA_APP, encoding="utf-8").read()
DRZEWO_APP = ast.parse(ZRODLO_APP)
KATALOG_APP = os.path.dirname(SCIEZKA_APP)

(CZAT_AST,) = [
    w for w in DRZEWO_APP.body
    if isinstance(w, ast.FunctionDef) and w.name == "renderuj_globalny_czat_ai"
]

HISTORIA = [
    {"role": "user", "content": "Zaplanuj jutro Balos"},
    {"role": "model", "content": "Proponuję wyjazd o 6:30"},
]
PROMPT = "Dodaj postój na lody"
WYNIKI = [
    {"narzedzie": "szukaj_miejsca_w_bazie", "argumenty": {"nazwa": "Balos"}, "wynik": {"success": True}}
]

# Format sprzed zmiany, spisany dosłownie - nie wolno go ruszyć, bo to wejście modelu.
TRESC_LEGACY = (
    "HISTORIA ROZMOWY (od najstarszej wiadomości):\n"
    "[RODZIC]: Zaplanuj jutro Balos\n"
    "[ASYSTENT]: Proponuję wyjazd o 6:30"
    "\n\nAKTUALNE POLECENIE RODZICA: Dodaj postój na lody"
    "\n\nWYNIKI NARZĘDZI WYKONANYCH W TEJ TURZE (JSON):\n"
    '[{"narzedzie": "szukaj_miejsca_w_bazie", "argumenty": {"nazwa": "Balos"},'
    ' "wynik": {"success": true}}]'
    '\n\nDokończ zadanie: zleć kolejne narzędzia albo napisz finalną odpowiedź w polu "odpowiedz".'
    " Nie powtarzaj narzędzia, które już zwróciło wynik."
)

KONTEKST = "Rodzic: Magda. Data: 2026-09-12. Aktywna wycieczka w tle ID: 7.\nOdwiedzone: Balos, Elafonisi"

ZMIENNA_WYCISZAJACA = "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"


# --- Treść wiadomości dla modelu ---

def test_tresc_bez_kontekstu_jest_identyczna_jak_przed_zmiana():
    """Domyślne wywołanie musi dać dokładnie ten sam tekst co wersja sprzed zmiany."""
    assert FUNKCJE["zbuduj_tresc_rozmowy"](HISTORIA, PROMPT, WYNIKI) == TRESC_LEGACY


def test_kontekst_aplikacji_trafia_na_poczatek_wiadomosci():
    """Dane zmienne doklejane są na początku treści, reszta zostaje bez zmian."""
    wynik = FUNKCJE["zbuduj_tresc_rozmowy"](HISTORIA, PROMPT, WYNIKI, kontekst_aplikacji=KONTEKST)
    assert wynik == "KONTEKST APLIKACJI:\n" + KONTEKST + "\n\n" + TRESC_LEGACY


@pytest.mark.parametrize("pusty", [None, "", "   \n  "])
def test_pusty_kontekst_nie_dokleja_naglowka(pusty):
    """Tryb ratunkowy przekazuje None - treść ma wtedy wyglądać jak dotąd."""
    assert FUNKCJE["zbuduj_tresc_rozmowy"](HISTORIA, PROMPT, WYNIKI, kontekst_aplikacji=pusty) == TRESC_LEGACY


# --- Środowisko procesu CLI ---

def test_srodowisko_cli_wycisza_ruch_nieistotny(monkeypatch):
    """Zmienna parasolowa dokładana jest do kopii środowiska, a samo os.environ zostaje nietknięte."""
    monkeypatch.delenv(ZMIENNA_WYCISZAJACA, raising=False)
    monkeypatch.setenv("HOME", "/h")
    monkeypatch.setenv("PATH", "/p")

    srodowisko = FUNKCJE["srodowisko_claude_cli"]()

    assert srodowisko[ZMIENNA_WYCISZAJACA] == "1"
    assert srodowisko["HOME"] == "/h"
    assert srodowisko["PATH"] == "/p"
    assert ZMIENNA_WYCISZAJACA not in os.environ


def test_srodowisko_cli_respektuje_wybor_operatora(monkeypatch):
    """Wartość ustawiona przez operatora wygrywa - setdefault niczego nie nadpisuje."""
    monkeypatch.setenv(ZMIENNA_WYCISZAJACA, "0")
    assert FUNKCJE["srodowisko_claude_cli"]()[ZMIENNA_WYCISZAJACA] == "0"


# --- Niezmienniki cache promptu systemowego ---

def test_prompt_systemowy_nie_zawiera_danych_zmiennych():
    """Prompt systemowy składa się wyłącznie z reguł z pliku - inaczej CLI gubi cache."""
    przypisania = [
        w.value for w in ast.walk(CZAT_AST)
        if isinstance(w, ast.Assign)
        and isinstance(w.value, ast.JoinedStr)
        and any(getattr(cel, "id", None) == "system_prompt" for cel in w.targets)
    ]
    assert len(przypisania) == 1, "Oczekiwano jednego f-stringowego przypisania system_prompt"
    nazwy = {
        n.id
        for pole in przypisania[0].values if isinstance(pole, ast.FormattedValue)
        for n in ast.walk(pole) if isinstance(n, ast.Name)
    }
    assert nazwy == {"rules_content"}


def test_aktywny_prompt_systemowy_sklada_sie_ze_stalych_czesci():
    """To `aktywny_system_prompt` idzie jako --system-prompt: wariant zwykły to reguły plus
    katalog narzędzi, wariant ratunkowy to stały tekst. Żaden nie może wciągnąć danych zmiennych."""
    wartosci = [
        w.value for w in ast.walk(CZAT_AST)
        if isinstance(w, ast.Assign)
        and any(getattr(cel, "id", None) == "aktywny_system_prompt" for cel in w.targets)
    ]
    assert len(wartosci) == 2, "Oczekiwano dwóch przypisań aktywny_system_prompt"

    fstringi = [w for w in wartosci if isinstance(w, ast.JoinedStr)]
    assert len(fstringi) == 1, "Oczekiwano jednego f-stringowego wariantu"
    pola = [p.value for p in fstringi[0].values if isinstance(p, ast.FormattedValue)]
    assert len(pola) == 2, "F-string ma sklejać dokładnie prompt systemowy i protokół narzędzi"
    assert isinstance(pola[0], ast.Name) and pola[0].id == "system_prompt"
    assert isinstance(pola[1], ast.Call)
    assert isinstance(pola[1].func, ast.Name) and pola[1].func.id == "zbuduj_protokol_narzedzi"
    assert pola[1].args == [] and pola[1].keywords == [], "Protokół nie może zależeć od argumentów"

    (ratunkowy,) = [w for w in wartosci if not isinstance(w, ast.JoinedStr)]
    assert isinstance(ratunkowy, ast.Constant) and isinstance(ratunkowy.value, str)


def test_kontekst_aplikacji_podpinany_tylko_poza_trybem_ratunkowym():
    """Wywołanie w pętli musi podać kontekst aplikacji, a w trybie ratunkowym None -
    inaczej dane z bazy wracają do promptu systemowego albo giną."""
    wywolania = [
        w for w in ast.walk(CZAT_AST)
        if isinstance(w, ast.Call)
        and isinstance(w.func, ast.Name)
        and w.func.id == "zbuduj_tresc_rozmowy"
    ]
    assert len(wywolania) == 1, "Oczekiwano jednego wywołania zbuduj_tresc_rozmowy"

    (kontekst,) = [k for k in wywolania[0].keywords if k.arg == "kontekst_aplikacji"]
    warunek = kontekst.value
    assert isinstance(warunek, ast.IfExp), "Kontekst ma być wybierany wyrażeniem warunkowym"
    assert isinstance(warunek.test, ast.Name) and warunek.test.id == "is_emergency"
    assert isinstance(warunek.body, ast.Constant) and warunek.body.value is None
    assert isinstance(warunek.orelse, ast.Name) and warunek.orelse.id == "kontekst_aplikacji"


SNIPPET_PROTOKOLU = """
import ast
import hashlib
import io
import json

from conftest import SCIEZKA_APP, wczytaj_funkcje_z_app

zrodlo = io.open(SCIEZKA_APP, encoding="utf-8").read()
(katalog,) = [
    w for w in ast.parse(zrodlo).body
    if isinstance(w, ast.Assign)
    and any(getattr(cel, "id", None) == "tools_definitions" for cel in w.targets)
]
ns = {"json": json}
exec(ast.get_source_segment(zrodlo, katalog), ns)
exec(wczytaj_funkcje_z_app(["zbuduj_protokol_narzedzi"])["zbuduj_protokol_narzedzi"], ns)
print(hashlib.sha256(ns["zbuduj_protokol_narzedzi"]().encode("utf-8")).hexdigest())
"""


def _protokol_w_procesie():
    """Buduje katalog narzędzi i protokół w bieżącym procesie."""
    (katalog,) = [
        w for w in DRZEWO_APP.body
        if isinstance(w, ast.Assign)
        and any(getattr(cel, "id", None) == "tools_definitions" for cel in w.targets)
    ]
    ns = _zaladuj(["zbuduj_protokol_narzedzi"])
    exec(ast.get_source_segment(ZRODLO_APP, katalog), ns)
    return ns["zbuduj_protokol_narzedzi"]()


def test_protokol_narzedzi_jest_deterministyczny():
    """Kluczem cache CLI jest zawartość bajtowa promptu systemowego, a każde wywołanie modelu
    idzie w osobnym procesie CLI. Protokół musi więc dać ten sam skrót w różnych procesach,
    także przy innym PYTHONHASHSEED - kolejność kluczy w json.dumps nie może zależeć od hashy."""
    skroty = []
    for ziarno in ("1", "2"):
        proces = subprocess.run(
            [sys.executable, "-c", SNIPPET_PROTOKOLU],
            cwd=KATALOG_APP,
            env=dict(os.environ, PYTHONHASHSEED=ziarno),
            capture_output=True,
            text=True,
            check=True,
        )
        skroty.append(proces.stdout.strip())

    assert skroty[0] == skroty[1], "Protokół różni się między procesami - cache CLI nie zostanie trafiony"
    assert skroty[0] == hashlib.sha256(_protokol_w_procesie().encode("utf-8")).hexdigest()
