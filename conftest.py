"""Wspólny loader funkcji z app.py dla testów.

`app.py` jest skryptem Streamlit - import całego modułu uruchomiłby UI, więc testy
wyciągają badane funkcje ze źródła przez AST i uruchamiają je w kontrolowanym
namespace. Dekoratory (`@st.dialog`, `@st.cache_data`) nie wchodzą w segment źródła
funkcji, więc wyciągnięty kod uruchamia się nagi, bez Streamlita.
"""

import ast
import io
import os

SCIEZKA_APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")


def wczytaj_funkcje_z_app(nazwy):
    """Zwraca {nazwa: kod źródłowy} dla funkcji najwyższego poziomu z app.py."""
    zrodlo = io.open(SCIEZKA_APP, encoding="utf-8").read()
    drzewo = ast.parse(zrodlo)
    segmenty = {
        w.name: ast.get_source_segment(zrodlo, w)
        for w in drzewo.body
        if isinstance(w, ast.FunctionDef) and w.name in nazwy
    }
    brakujace = [n for n in nazwy if n not in segmenty]
    assert not brakujace, f"Nie znaleziono funkcji w app.py: {brakujace}"
    return segmenty


def wczytaj_stale_z_app(nazwy):
    """Zwraca {nazwa: wartość} dla modułowych stałych z app.py.

    Wyciągnięta funkcja czyta stałe swojego modułu przez globalny namespace, więc test musi je
    podać razem z nią - przepisanie wartości do testu rozjeżdżałoby się z app.py po cichu.
    """
    zrodlo = io.open(SCIEZKA_APP, encoding="utf-8").read()
    drzewo = ast.parse(zrodlo)
    wartosci = {}
    for wezel in drzewo.body:
        if not isinstance(wezel, ast.Assign):
            continue
        for cel in wezel.targets:
            if isinstance(cel, ast.Name) and cel.id in nazwy:
                wartosci[cel.id] = ast.literal_eval(wezel.value)
    brakujace = [n for n in nazwy if n not in wartosci]
    assert not brakujace, f"Nie znaleziono stałych w app.py: {brakujace}"
    return wartosci
