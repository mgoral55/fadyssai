#!/usr/bin/env python3
"""Jednorazowy generator krótkich opisów miejsc (kolumna "Krótki opis" w miejsca.csv).

Dla każdego miejsca model dostaje pełny opis z bazy i zwraca jedno zdanie mieszczące
się w zadanym limicie znaków. Wynik trafia do `miejsca.csv` (źródło prawdy w repo),
a opcjonalnie od razu do bazy SQLite aplikacji.

Skrypt korzysta wyłącznie z biblioteki standardowej i tego samego Claude Code CLI,
którego używa aplikacja (`claude -p`, `--safe-mode`, `--tools ""`).

Przykłady:
    python3 generuj_krotkie_opisy.py --sucho              # podgląd bez zapisu
    python3 generuj_krotkie_opisy.py                      # zapis do miejsca.csv
    python3 generuj_krotkie_opisy.py --db data/cretai.db  # dodatkowo do bazy
    python3 generuj_krotkie_opisy.py --nadpisz            # przelicz też istniejące
"""

import argparse
import csv
import json
import os
import shutil
import sqlite3
import subprocess
import sys

KOLUMNA_KROTKI_OPIS = "Krótki opis"
KOLUMNA_NUMER = "numer miejsca"
KOLUMNA_NAZWA = "nazwa"
KOLUMNA_TYP = "typ"
KOLUMNA_OPIS = "Opis"

CLAUDE_CLI_BIN = os.environ.get("CLAUDE_CLI_BIN", "claude")
MODEL_DOMYSLNY = "claude-opus-5"
MODELE_ZAPASOWE = ["claude-sonnet-5", "claude-haiku-4-5-20251001"]
TIMEOUT_S = int(os.environ.get("CLAUDE_CLI_TIMEOUT_S", "300"))

MAX_ZNAKOW_DOMYSLNIE = 140
WIELKOSC_PACZKI_DOMYSLNIE = 10

SCHEMAT_ODPOWIEDZI = {
    "type": "object",
    "properties": {
        "opisy": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "numer_miejsca": {"type": "string"},
                    "krotki_opis": {"type": "string"},
                },
                "required": ["numer_miejsca", "krotki_opis"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["opisy"],
    "additionalProperties": False,
}


def prompt_systemowy(max_znakow):
    return (
        "Jesteś redaktorem rodzinnego przewodnika po Krecie. Dla każdego miejsca z wejścia piszesz "
        "JEDEN krótki opis po polsku.\n"
        "ZASADY (twarde):\n"
        f"- Dokładnie jedno zdanie, maksymalnie {max_znakow} znaków ze spacjami. Krótsze jest lepsze.\n"
        "- Zdanie zakończone kropką, bez emoji, bez cudzysłowów, bez znaczników i bez nowych linii.\n"
        "- Opisujesz, czym to miejsce JEST i co się tam robi - konkret, nie marketing "
        "('największa', 'niezapomniana', 'must-have' są zakazane).\n"
        "- Nie powtarzaj nazwy miejsca na początku zdania, jeśli da się bez niej.\n"
        "- Nie wymyślaj faktów: korzystasz wyłącznie z opisu podanego na wejściu.\n"
        "- Odbiorcą są rodzice dwójki dzieci (5 i 7 lat, ADHD/AuDHD) planujący dzień, "
        "więc liczy się informacja przydatna przy wyborze miejsca.\n"
        "- Zwracasz opis dla KAŻDEGO numeru miejsca z wejścia, z niezmienionym numerem."
    )


def wczytaj_csv(sciezka):
    with open(sciezka, encoding="utf-8", newline="") as f:
        czytnik = csv.DictReader(f)
        wiersze = list(czytnik)
        naglowki = list(czytnik.fieldnames or [])
    if KOLUMNA_NUMER not in naglowki:
        sys.exit(f"Brak kolumny '{KOLUMNA_NUMER}' w {sciezka}")
    return naglowki, wiersze


def zapisz_csv(sciezka, naglowki, wiersze):
    tymczasowy = sciezka + ".tmp"
    with open(tymczasowy, "w", encoding="utf-8", newline="") as f:
        pisarz = csv.DictWriter(f, fieldnames=naglowki)
        pisarz.writeheader()
        for w in wiersze:
            pisarz.writerow({k: w.get(k, "") for k in naglowki})
    os.replace(tymczasowy, sciezka)


def wywolaj_model(system_prompt, tresc, model):
    sciezka = shutil.which(CLAUDE_CLI_BIN)
    if not sciezka:
        sys.exit(f"Nie znaleziono Claude Code CLI ('{CLAUDE_CLI_BIN}') w PATH.")

    zapasowe = [m for m in MODELE_ZAPASOWE if m != model]
    cmd = [
        sciezka, "-p",
        "--model", model,
        "--safe-mode",
        "--tools", "",
        "--no-session-persistence",
        "--output-format", "json",
        "--system-prompt", system_prompt,
        "--json-schema", json.dumps(SCHEMAT_ODPOWIEDZI, ensure_ascii=False),
    ]
    if zapasowe:
        cmd += ["--fallback-model", ",".join(zapasowe)]

    srodowisko = dict(os.environ)
    srodowisko.setdefault("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")

    proces = subprocess.run(
        cmd, input=tresc, capture_output=True, text=True,
        encoding="utf-8", env=srodowisko, timeout=TIMEOUT_S,
    )

    surowe = (proces.stdout or "").strip()
    try:
        koperta = json.loads(surowe) if surowe else None
    except json.JSONDecodeError:
        koperta = None
    if not isinstance(koperta, dict):
        detal = (proces.stderr or surowe or "brak wyjścia").strip()
        raise RuntimeError(f"Nieczytelna odpowiedź CLI (kod {proces.returncode}): {detal[:400]}")
    if koperta.get("is_error") or koperta.get("subtype") != "success":
        raise RuntimeError(str(koperta.get("result") or koperta.get("subtype") or "nieznany błąd")[:400])

    dane = koperta.get("structured_output")
    if not isinstance(dane, dict):
        try:
            dane = json.loads(koperta.get("result") or "")
        except (TypeError, json.JSONDecodeError):
            dane = None
    if not isinstance(dane, dict) or not isinstance(dane.get("opisy"), list):
        raise RuntimeError("Model nie zwrócił listy 'opisy' w wymaganym formacie JSON.")
    return dane["opisy"]


def przytnij(tekst, max_znakow):
    """Awaryjne docięcie, gdy model przekroczy limit - do granicy słowa, z kropką na końcu."""
    tekst = " ".join(str(tekst or "").split()).strip()
    if len(tekst) <= max_znakow:
        return tekst
    uciete = tekst[:max_znakow].rsplit(" ", 1)[0].rstrip(" ,;:-–—")
    return uciete + "." if not uciete.endswith(".") else uciete


def zbuduj_wejscie(paczka, max_znakow):
    miejsca = [
        {
            "numer_miejsca": w.get(KOLUMNA_NUMER, "").strip(),
            "nazwa": w.get(KOLUMNA_NAZWA, "").strip(),
            "typ": w.get(KOLUMNA_TYP, "").strip(),
            "opis": " ".join(str(w.get(KOLUMNA_OPIS, "")).split()),
        }
        for w in paczka
    ]
    return (
        f"Limit: {max_znakow} znaków na opis. Miejsca do opisania "
        f"({len(miejsca)}):\n{json.dumps(miejsca, ensure_ascii=False, indent=1)}"
    )


def zapisz_do_bazy(sciezka_db, opisy):
    if not os.path.exists(sciezka_db):
        sys.exit(f"Baza {sciezka_db} nie istnieje.")
    conn = sqlite3.connect(sciezka_db, timeout=30.0)
    try:
        try:
            conn.execute("ALTER TABLE miejsca ADD COLUMN krotki_opis TEXT")
        except sqlite3.OperationalError:
            pass
        zmienione = 0
        for nr, krotki in opisy.items():
            kursor = conn.execute(
                "UPDATE miejsca SET krotki_opis = ? WHERE TRIM(numer_miejsca) = ?",
                (krotki, str(nr).strip()),
            )
            zmienione += kursor.rowcount
        conn.commit()
        return zmienione
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Generuje krótkie opisy miejsc modelem Claude.")
    parser.add_argument("--csv", default="miejsca.csv", help="plik z bazą miejsc (domyślnie miejsca.csv)")
    parser.add_argument("--db", default=None, help="dodatkowo zapisz do bazy SQLite pod tą ścieżką")
    parser.add_argument("--model", default=MODEL_DOMYSLNY)
    parser.add_argument("--max-znakow", type=int, default=MAX_ZNAKOW_DOMYSLNIE)
    parser.add_argument("--paczka", type=int, default=WIELKOSC_PACZKI_DOMYSLNIE, help="miejsc na jedno wywołanie modelu")
    parser.add_argument("--nadpisz", action="store_true", help="przelicz też miejsca, które mają już krótki opis")
    parser.add_argument("--sucho", action="store_true", help="tylko wypisz wyniki, nie zapisuj")
    args = parser.parse_args()

    naglowki, wiersze = wczytaj_csv(args.csv)
    if KOLUMNA_KROTKI_OPIS not in naglowki:
        naglowki.append(KOLUMNA_KROTKI_OPIS)

    do_zrobienia = [
        w for w in wiersze
        if str(w.get(KOLUMNA_NUMER, "")).strip()
        and (args.nadpisz or not str(w.get(KOLUMNA_KROTKI_OPIS, "") or "").strip())
    ]
    if not do_zrobienia:
        print("Wszystkie miejsca mają już krótki opis. Użyj --nadpisz, żeby je przeliczyć ponownie.")
        return 0

    print(f"Do wygenerowania: {len(do_zrobienia)} z {len(wiersze)} miejsc "
          f"(model {args.model}, limit {args.max_znakow} znaków, paczki po {args.paczka}).")

    system_prompt = prompt_systemowy(args.max_znakow)
    zebrane = {}
    liczba_paczek = (len(do_zrobienia) + args.paczka - 1) // args.paczka

    for nr_paczki in range(liczba_paczek):
        paczka = do_zrobienia[nr_paczki * args.paczka:(nr_paczki + 1) * args.paczka]
        numery = [w[KOLUMNA_NUMER].strip() for w in paczka]
        print(f"[{nr_paczki + 1}/{liczba_paczek}] miejsca {', '.join(numery)} ...", flush=True)

        try:
            odpowiedzi = wywolaj_model(system_prompt, zbuduj_wejscie(paczka, args.max_znakow), args.model)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            print(f"  BŁĄD paczki: {e}", file=sys.stderr)
            continue

        zwrocone = {str(o.get("numer_miejsca", "")).strip(): str(o.get("krotki_opis", "")).strip()
                    for o in odpowiedzi if isinstance(o, dict)}
        for numer in numery:
            krotki = przytnij(zwrocone.get(numer, ""), args.max_znakow)
            if not krotki:
                print(f"  UWAGA: brak opisu dla miejsca {numer}", file=sys.stderr)
                continue
            zebrane[numer] = krotki
            print(f"  {numer}: {krotki}")

    if not zebrane:
        print("Nic nie wygenerowano.", file=sys.stderr)
        return 1

    if args.sucho:
        print(f"\n[--sucho] Pominięto zapis. Gotowych opisów: {len(zebrane)}.")
        return 0

    for w in wiersze:
        numer = str(w.get(KOLUMNA_NUMER, "")).strip()
        if numer in zebrane:
            w[KOLUMNA_KROTKI_OPIS] = zebrane[numer]
        else:
            w.setdefault(KOLUMNA_KROTKI_OPIS, "")
    zapisz_csv(args.csv, naglowki, wiersze)
    print(f"\nZapisano {len(zebrane)} opisów do {args.csv}.")

    if args.db:
        zmienione = zapisz_do_bazy(args.db, zebrane)
        print(f"Zaktualizowano {zmienione} wierszy w {args.db}.")

    brakujace = [str(w.get(KOLUMNA_NUMER, "")).strip() for w in wiersze
                 if str(w.get(KOLUMNA_NUMER, "")).strip() and not str(w.get(KOLUMNA_KROTKI_OPIS, "")).strip()]
    if brakujace:
        print(f"Bez opisu zostały miejsca: {', '.join(brakujace)}. Uruchom skrypt ponownie.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
