"""Testy loadera AI: animacja tańczącej kozy ze znaku firmowego.

Animacja jedzie inline w HTML (bez /static i bez <img>), więc test pilnuje trzech rzeczy:
plik SVG jest poprawnym XML z klasami animacji, render wstawia go z unikalnym prefiksem
identyfikatorów (dwie instancje na stronie nie mogą dzielić clipPath), a brak pliku
degraduje się do czystego komunikatu tekstowego, nie do pustego statusu.

Uruchomienie:  pytest test_loader_kozy.py
"""

import os
import random
import re
import xml.dom.minidom

import pytest

from conftest import wczytaj_funkcje_z_app

SCIEZKA_SVG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "koza_loader.svg")

BADANE_FUNKCJE = ["pobierz_animacje_kozy", "render_loader_kozy"]


def _zaladuj():
    """Uruchamia funkcje loadera z app.py w namespace z ich zależnościami."""
    ns = {"os": os, "random": random}
    for kod in wczytaj_funkcje_z_app(BADANE_FUNKCJE).values():
        exec(kod, ns)
    return ns


@pytest.fixture(scope="module")
def funkcje():
    return _zaladuj()


def test_svg_jest_poprawnym_xml():
    with open(SCIEZKA_SVG, encoding="utf-8") as f:
        tresc = f.read()
    xml.dom.minidom.parseString(tresc)  # rzuci wyjątkiem przy niedomkniętym tagu
    assert tresc.lstrip().startswith("<svg")


def test_svg_ma_wszystkie_animowane_czesci():
    """Każda ruchoma część kozy musi mieć klasę powiązaną z keyframes o tej samej nazwie."""
    with open(SCIEZKA_SVG, encoding="utf-8") as f:
        tresc = f.read()

    for klasa in ["kozal-koza", "kozal-glowa", "kozal-ogon", "kozal-noga", "kozal-cien", "kozal-nuta"]:
        assert f'class="{klasa}' in tresc or f' {klasa}"' in tresc, f"brak elementu z klasą {klasa}"

    zadeklarowane = set(re.findall(r"@keyframes\s+([\w-]+)", tresc))
    # "none" to wyłącznik z bloku prefers-reduced-motion, nie nazwa animacji.
    uzyte = set(re.findall(r"animation(?:-name)?:\s*([\w-]+)", tresc)) - {"none"}
    assert uzyte <= zadeklarowane, f"animacje bez keyframes: {uzyte - zadeklarowane}"
    assert "prefers-reduced-motion" in tresc, "brak wyłącznika animacji dla użytkowników z redukcją ruchu"


def test_render_wstawia_svg_i_komunikat(funkcje):
    html = funkcje["render_loader_kozy"]("🧠 Sprawdzam strefy cienia...")
    assert "<svg" in html
    assert "🧠 Sprawdzam strefy cienia..." in html
    assert "@keyframes" in html, "styl animacji musi jechać razem z inline SVG"


def test_render_nie_ma_pustych_linii(funkcje):
    """Markdown Streamlita kończy blok surowego HTML na pustej linii.

    Plik SVG rozdziela sekcje pustymi liniami dla czytelności - gdyby trafiły do HTML,
    reszta arkusza animacji wyświetliłaby się rodzicowi w czacie jako goły tekst CSS.
    """
    html = funkcje["render_loader_kozy"]("🧠 Sprawdzam strefy cienia...")
    puste = [nr for nr, linia in enumerate(html.splitlines(), 1) if not linia.strip()]
    assert not puste, f"puste linie w HTML loadera (numery: {puste}) urwą blok HTML w markdownie"


def test_kazda_instancja_ma_wlasne_identyfikatory(funkcje):
    """Dwa loadery na jednej stronie nie mogą dzielić id clipPath ani nazw keyframes."""
    render = funkcje["render_loader_kozy"]
    pierwszy, drugi = render("a"), render("b")

    assert "kozal-" not in pierwszy, "surowy prefiks z pliku nie może trafić do HTML"
    id_pierwszy = set(re.findall(r'id="([\w-]+)"', pierwszy))
    id_drugi = set(re.findall(r'id="([\w-]+)"', drugi))
    assert id_pierwszy, "SVG musi mieć przynajmniej clipPath i glif nuty"
    assert not (id_pierwszy & id_drugi), f"kolizja identyfikatorów: {id_pierwszy & id_drugi}"


def test_brak_pliku_degraduje_do_tekstu(funkcje):
    """Bez pliku animacji rodzic nadal widzi etap pracy modelu."""
    ns = dict(funkcje)
    ns["pobierz_animacje_kozy"] = lambda *a, **k: None
    kod = wczytaj_funkcje_z_app(["render_loader_kozy"])["render_loader_kozy"]
    exec(kod, ns)
    assert ns["render_loader_kozy"]("🥪 Pilnuję licznika głodu...") == "*🥪 Pilnuję licznika głodu...*"


def test_petla_modelu_uzywa_loadera_raz_na_cykl():
    """Placeholder loadera powstaje przed pętlą narzędzi - inaczej animacja mnoży się 4x."""
    with open(os.path.join(os.path.dirname(SCIEZKA_SVG), "..", "app.py"), encoding="utf-8") as f:
        zrodlo = f.read()

    idx_placeholder = zrodlo.index("status_placeholder = st.empty()")
    idx_petla = zrodlo.index("for loop_idx in range(max_loops):")
    assert idx_placeholder < idx_petla, "st.empty() w pętli dokłada kolejną kopię animacji"
    assert "render_loader_kozy(random.choice(status_komunikaty))" in zrodlo
    assert "status_placeholder.empty()" in zrodlo, "loader musi zniknąć po zakończeniu pracy modelu"
