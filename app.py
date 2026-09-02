import sqlite3
import pandas as pd
import streamlit as st
from google import genai
from google.genai import types
import folium
from branca.element import Element
from streamlit_folium import st_folium
import os
import urllib.request
import json
import re
import math
import base64
import random
import unicodedata
import time as py_time
from datetime import datetime, date, time, timedelta

# Stałe koordynatów
DOMEK_LAT, DOMEK_LON = 35.5914, 24.0918
SKLEP_LAT, SKLEP_LON = 35.586222, 24.091861

# --- 0. BAZA DANYCH (CONCURRENCY & WAL) ---
def get_db():
    conn = sqlite3.connect('cretai.db', timeout=30.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA busy_timeout = 30000;')
    return conn

def zaokraglij_do_5_minut(minuty):
    return int(round(minuty / 5.0) * 5)

@st.cache_data(ttl=86400)
def oblicz_czas_przejazdu_osrm(lat1, lon1, lat2, lon2):
    # Kreta: współczynnik krętości dróg 1.35x i średnia prędkość 42 km/h
    try:
        dist_km = math.sqrt(((lat2 - lat1) * 111.0)**2 + ((lon2 - lon1) * 85.0)**2) * 1.35
        est_min = zaokraglij_do_5_minut(max(int(round((dist_km / 42.0) * 60)), 10))
        if est_min < 60:
            return f"~{est_min} min", est_min
        godziny, reszta = est_min // 60, est_min % 60
        return (f"~{godziny}h", est_min) if reszta == 0 else (f"~{godziny}h {reszta}m", est_min)
    except Exception:
        return "~25 min", 25

@st.cache_data(ttl=86400)
def pobierz_geometrie_trasy_osrm(lat1, lon1, lat2, lon2):
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'CretAiApp/1.0'})
        with urllib.request.urlopen(req, timeout=0.4) as response:
            data = json.loads(response.read().decode())
            if 'routes' in data and len(data['routes']) > 0:
                coords = data['routes'][0]['geometry']['coordinates']
                return [[c[1], c[0]] for c in coords]
    except Exception:
        pass
    return [[lat1, lon1], [lat2, lon2]]

def sparsuj_wspolrzedne(wsp_str):
    if not wsp_str or pd.isna(wsp_str):
        return None, None
    s = str(wsp_str).replace(' ', '').replace(';', ',')
    if ',' not in s:
        return None, None
    try:
        parts = s.split(',')
        return float(parts[0].strip()), float(parts[1].strip())
    except Exception:
        return None, None

def sparsuj_godzine_minuty(czas_str):
    if not czas_str:
        return None
    m = re.search(r'(\d{1,2}):(\d{2})', str(czas_str))
    return (int(m.group(1)), int(m.group(2))) if m else None

def klucz_sortowania_okienka(okienko_str):
    res = sparsuj_godzine_minuty(okienko_str)
    return res[0] * 60 + res[1] if res else 9999

def oblicz_czas_trwania_okienka(okienko_str, domyslny_czas=45):
    if not okienko_str or "-" not in str(okienko_str):
        return domyslny_czas
    try:
        czesci = str(okienko_str).split("-")
        g1, g2 = sparsuj_godzine_minuty(czesci[0]), sparsuj_godzine_minuty(czesci[1])
        if g1 and g2:
            return max((g2[0] * 60 + g2[1]) - (g1[0] * 60 + g1[1]), 15)
    except Exception:
        pass
    return domyslny_czas

def sparsuj_czas_ogarniania_na_minuty(czas_str):
    if not czas_str:
        return 30
    s = str(czas_str).lower()
    g_match, m_match = re.search(r'(\d+(?:\.\d+)?)\s*h', s), re.search(r'(\d+)\s*m', s)
    godziny = float(g_match.group(1)) if g_match else 0.0
    minuty = int(m_match.group(1)) if m_match else 0
    total = int(round(godziny * 60)) + minuty
    if total == 0:
        try:
            total = int(float(s) * 60) if '.' in s else int(s)
        except Exception:
            total = 30
    return max(total, 15)

CATEGORIES_CONFIG = {
    "Must have": {"color": "#B35446", "slug": "must_have", "icon": "🏛️"},
    "Nice to have": {"color": "#C47C48", "slug": "nice_to_have", "icon": "✨"},
    "Plaża": {"color": "#4A7C8F", "slug": "plaza", "icon": "🏖️"},
    "Activity": {"color": "#C6934B", "slug": "activity", "icon": "🧗"},
    "Shop": {"color": "#7D5871", "slug": "shop", "icon": "🛒"},
    "Other": {"color": "#5D7A60", "slug": "other", "icon": "📍"}
}

def kategoryzuj_typ(typ_str):
    if not typ_str or pd.isna(typ_str):
        return "Other"
    t = str(typ_str).lower().strip()
    if any(w in t for w in ["plaż", "plaz", "beach", "zatoka", "morze"]): return "Plaża"
    if any(w in t for w in ["activ", "aktywn", "wąwóz", "wawoz", "sport", "rower", "rejs", "ciuchcia", "pociąg"]): return "Activity"
    if any(w in t for w in ["shop", "sklep", "zakup", "market", "rynek", "targ", "mydlarn", "winnica"]): return "Shop"
    if "must" in t or any(w in t for w in ["pałac", "knossos", "muzeum", "archeo", "ogród botaniczny", "cretaquarium"]): return "Must have"
    if "nice" in t or any(w in t for w in ["lappa", "wodospad", "argyroupoli", "kournas", "aptera", "farma", "arevitis", "manousakis"]): return "Nice to have"
    return "Other"

def pobierz_kolor_kategorii(kategoria):
    return CATEGORIES_CONFIG.get(kategoria, CATEGORIES_CONFIG["Other"])["color"]

def pobierz_ikonke_kategorii(kategoria):
    return CATEGORIES_CONFIG.get(kategoria, CATEGORIES_CONFIG["Other"]).get("icon")

# --- WSTRZYKIWANIE CSS BEZPOŚREDNIO DO IFRAME LEAFLETA ---
def zaaplikuj_style_mapy(folium_map):
    style_element = Element("""
        <style>
            .leaflet-div-icon, .custom-map-pin {
                background: transparent !important;
                border: none !important;
                box-shadow: none !important;
            }
            .pin-inner-content {
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                width: 100% !important;
                height: 100% !important;
                margin: 0 !important;
                padding: 0 !important;
                box-sizing: border-box !important;
            }
        </style>
    """)
    folium_map.get_root().header.add_child(style_element)

def stworz_znacznik_html(tekst, kolor_tla, rozmiar=24):
    return f"""<div style="background-color:{kolor_tla}; color:#FFFFFF; border-radius:50%; width:{rozmiar}px; height:{rozmiar}px; line-height:{rozmiar-4}px; text-align:center; font-size:10px; font-weight:900; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; border:2px solid #FFFFFF; box-shadow:0 2px 5px rgba(0,0,0,0.3); box-sizing:border-box; display:flex; align-items:center; justify-content:center; margin:0; padding:0;"><span style="display:block; transform:translateY(-0.5px);">{tekst}</span></div>"""

# --- UNIWERSALNA FUNKCJA DOPASOWYWANIA KROKU DO BAZY MIEJSC (DRY) ---
def _wyczysc_nazwe_miejsca(nazwa):
    if not nazwa: return ""
    s = str(nazwa).strip().lower()
    s = re.sub(r'^\d+[\.\)]\s*', '', s)
    s = s.split('(')[0].strip()
    return s

def dopasuj_krok_do_bazy_miejsc(nazwa_kroku, wspolrzedne_kroku, df_miejsca_ref):
    if df_miejsca_ref is None or df_miejsca_ref.empty or not nazwa_kroku:
        return None

    nazwa_l = str(nazwa_kroku).strip().lower()
    if any(w in nazwa_l for w in ["domek", "start", "powrót", "powrot", "sklep przy domku"]):
        return None

    czysta_krok = _wyczysc_nazwe_miejsca(nazwa_l)

    for _, m in df_miejsca_ref.iterrows():
        m_nazwa_l = str(m['nazwa']).strip().lower()
        m_czysta = _wyczysc_nazwe_miejsca(m_nazwa_l)
        if czysta_krok == m_czysta or nazwa_l == m_nazwa_l:
            return m

    for _, m in df_miejsca_ref.iterrows():
        m_nazwa_l = str(m['nazwa']).strip().lower()
        m_czysta = _wyczysc_nazwe_miejsca(m_nazwa_l)
        if len(m_czysta) >= 4 and (m_czysta in czysta_krok or czysta_krok in m_czysta):
            return m

    lat_k, lon_k = sparsuj_wspolrzedne(wspolrzedne_kroku)
    if lat_k is not None and lon_k is not None:
        for _, m in df_miejsca_ref.iterrows():
            m_lat, m_lon = sparsuj_wspolrzedne(m.get('wspolrzedne'))
            if m_lat is not None and m_lon is not None:
                if abs(m_lat - lat_k) < 0.003 and abs(m_lon - lon_k) < 0.003:
                    return m

    return None

# --- POMOCNICZE FUNKCJE STRUKTURY KROKÓW ---
def _reindex_kroki(cursor, id_wycieczki):
    cursor.execute('''
        SELECT id FROM krok_wycieczki 
        WHERE id_wycieczki = ? 
        ORDER BY CAST(krok_wycieczki AS REAL) ASC, id ASC
    ''', (str(id_wycieczki),))
    kroki = cursor.fetchall()
    for idx, (k_id,) in enumerate(kroki):
        cursor.execute('UPDATE krok_wycieczki SET krok_wycieczki = ? WHERE id = ?', (idx, k_id))

def _wstaw_krok_do_wycieczki(cursor, id_wycieczki, nazwa, wspolrzedne, okienko, opis, numer_miejsca=None, podsumowanie_taktyki=None, pozycja="koniec"):
    cursor.execute('''
        SELECT id, nazwa, CAST(krok_wycieczki AS INTEGER) as nr 
        FROM krok_wycieczki 
        WHERE id_wycieczki = ? 
        ORDER BY nr ASC, id ASC
    ''', (str(id_wycieczki),))
    rows = cursor.fetchall()
    
    nazwa_lower = nazwa.lower()
    is_shop = any(w in nazwa_lower for w in ["sklep", "market"])
    is_market = any(w in nazwa_lower for w in ["rynek", "targ", "laiki"])

    cursor.execute('''
        INSERT INTO krok_wycieczki (id_wycieczki, krok_wycieczki, numer_miejsca, nazwa, wspolrzedne, okienko_zwiedzania, podsumowanie_taktyki, opis)
        VALUES (?, 9999, ?, ?, ?, ?, ?, ?)
    ''', (str(id_wycieczki), numer_miejsca, nazwa, wspolrzedne, okienko, podsumowanie_taktyki, opis))
    nowy_id = cursor.lastrowid

    start_cottage = []
    morning_shops = []
    morning_markets = []
    middle_steps = []
    evening_markets = []
    evening_shops = []
    end_cottage = []

    total = len(rows)
    for idx, (r_id, r_nazwa, _) in enumerate(rows):
        r_low = str(r_nazwa).lower()
        if idx == 0 and any(w in r_low for w in ["domek", "start", "wyjazd"]):
            start_cottage.append((r_id, r_nazwa))
        elif idx == total - 1 and any(w in r_low for w in ["domek", "powrót", "powrot"]):
            end_cottage.append((r_id, r_nazwa))
        elif any(w in r_low for w in ["sklep", "market"]):
            if idx <= 2:
                morning_shops.append((r_id, r_nazwa))
            else:
                evening_shops.append((r_id, r_nazwa))
        elif any(w in r_low for w in ["rynek", "targ", "laiki"]):
            if idx <= 2:
                morning_markets.append((r_id, r_nazwa))
            else:
                evening_markets.append((r_id, r_nazwa))
        else:
            middle_steps.append((r_id, r_nazwa))

    nowy_element = (nowy_id, nazwa)
    if pozycja == "start":
        if is_shop:
            morning_shops.append(nowy_element)
        elif is_market:
            morning_markets.append(nowy_element)
        else:
            morning_shops.append(nowy_element)
    else:
        if is_shop:
            evening_shops.append(nowy_element)
        elif is_market:
            evening_markets.append(nowy_element)
        else:
            evening_shops.append(nowy_element)

    uporzadkowana_lista = (
        start_cottage +
        morning_shops +
        morning_markets +
        middle_steps +
        evening_markets +
        evening_shops +
        end_cottage
    )

    for index_docelowy, (item_id, _) in enumerate(uporzadkowana_lista):
        cursor.execute('UPDATE krok_wycieczki SET krok_wycieczki = ? WHERE id = ?', (index_docelowy, item_id))

    return nowy_id

def _usun_krok_z_wycieczki(cursor, id_kroku, id_wycieczki):
    cursor.execute("DELETE FROM zakupy WHERE id_kroku = ?", (id_kroku,))
    cursor.execute("DELETE FROM posilki_kroku WHERE id_kroku = ?", (id_kroku,))
    cursor.execute("DELETE FROM czasy_dojazdu WHERE id_kroku_z = ? OR id_kroku_do = ?", (id_kroku, id_kroku))
    cursor.execute("DELETE FROM krok_wycieczki WHERE id = ?", (id_kroku,))
    _reindex_kroki(cursor, id_wycieczki)

def przelicz_i_zsynchronizuj_wycieczke(id_wycieczki, force_pobudka_str=None, force_wyjazd_str=None, force_powrot_str=None):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT szacowany_czas_ogarniania_rano, pobudka, czas_wyjazdu FROM wycieczka WHERE id = ?', (str(id_wycieczki),))
        row_og = cursor.fetchone()
        if not row_og:
            return
        pobudka_z_bazy = row_og[1] if row_og and row_og[1] else '06:00'
        minuty_ogarniania = sparsuj_czas_ogarniania_na_minuty(row_og[0] if row_og else '0.5h')

        cursor.execute('SELECT id, krok_wycieczki, wspolrzedne, okienko_zwiedzania, nazwa FROM krok_wycieczki WHERE id_wycieczki = ? ORDER BY CAST(krok_wycieczki AS INTEGER) ASC, id ASC', (str(id_wycieczki),))
        kroki = cursor.fetchall()
    
    if not kroki:
        return

    dojazdy_minuty, dojazdy_tekst = [], []
    for idx in range(len(kroki) - 1):
        lat1, lon1 = sparsuj_wspolrzedne(kroki[idx][2])
        lat2, lon2 = sparsuj_wspolrzedne(kroki[idx + 1][2])
        tekst_dojazdu, minuty_przejazdu = ("~25 min", 25) if lat1 is None or lon1 is None or lat2 is None or lon2 is None else oblicz_czas_przejazdu_osrm(lat1, lon1, lat2, lon2)
        dojazdy_minuty.append(minuty_przejazdu)
        dojazdy_tekst.append(tekst_dojazdu)

    czasy_pobytu = []
    for idx, k in enumerate(kroki):
        nazwa_l = str(k[4]).lower()
        dur_def = 25 if any(w in nazwa_l for w in ["sklep", "market", "zakup", "apteka", "rynek", "targ"]) else (90 if ("plaż" in nazwa_l or "beach" in nazwa_l) else (30 if (idx == 0 or idx == len(kroki) - 1 or any(w in nazwa_l for w in ["powrót", "powrot", "domek"])) else 60))
        czasy_pobytu.append(oblicz_czas_trwania_okienka(k[3], domyslny_czas=dur_def))

    start_times, end_times = [None] * len(kroki), [None] * len(kroki)
    if force_pobudka_str:
        pobudka_z_bazy = force_pobudka_str

    g_pob = sparsuj_godzine_minuty(pobudka_z_bazy) or (6, 0)
    dt_pob = datetime(2026, 1, 1, g_pob[0], g_pob[1])
    dt_wyj = dt_pob + timedelta(minutes=minuty_ogarniania)
    last_idx = len(kroki) - 1

    if force_powrot_str:
        g_pow = sparsuj_godzine_minuty(force_powrot_str) or (17, 0)
        dt_powrot_anchor = datetime(2026, 1, 1, g_pow[0], g_pow[1])
        
        end_times[last_idx] = dt_powrot_anchor
        start_times[last_idx] = dt_powrot_anchor - timedelta(minutes=czasy_pobytu[last_idx])

        for i in range(last_idx - 1, 0, -1):
            end_times[i] = start_times[i + 1] - timedelta(minutes=dojazdy_minuty[i])
            start_times[i] = end_times[i] - timedelta(minutes=czasy_pobytu[i])

        end_times[0] = start_times[1] - timedelta(minutes=dojazdy_minuty[0])
        dt_pob = end_times[0] - timedelta(minutes=minuty_ogarniania)
        pobudka_z_bazy = dt_pob.strftime("%H:%M")
        start_times[0] = dt_pob

    elif force_wyjazd_str:
        g_wyj = sparsuj_godzine_minuty(force_wyjazd_str) or (6, 30)
        dt_wyj = datetime(2026, 1, 1, g_wyj[0], g_wyj[1])
        dt_pob = dt_wyj - timedelta(minutes=minuty_ogarniania)
        pobudka_z_bazy = dt_pob.strftime("%H:%M")
        start_times[0], end_times[0] = dt_pob, dt_wyj
        cur_dt = dt_wyj
        for i in range(1, len(kroki)):
            cur_dt = cur_dt + timedelta(minutes=dojazdy_minuty[i - 1])
            start_times[i] = cur_dt
            end_times[i] = start_times[i] + timedelta(minutes=czasy_pobytu[i])
            cur_dt = end_times[i]
    else:
        cur_dt = dt_wyj
        for i in range(len(kroki)):
            if i == 0:
                start_times[i], end_times[i] = dt_pob, dt_wyj
            else:
                start_times[i] = cur_dt
                end_times[i] = cur_dt + timedelta(minutes=czasy_pobytu[i])
            if i < len(kroki) - 1:
                cur_dt = end_times[i] + timedelta(minutes=dojazdy_minuty[i])

    with get_db() as conn:
        cursor = conn.cursor()
        krok_ids = [k[0] for k in kroki]
        if krok_ids:
            placeholders = ','.join(['?'] * len(krok_ids))
            cursor.execute(f'DELETE FROM czasy_dojazdu WHERE id_kroku_z IN ({placeholders}) OR id_kroku_do IN ({placeholders})', krok_ids + krok_ids)

        for i in range(len(kroki)):
            s_str, e_str = start_times[i].strftime("%H:%M"), end_times[i].strftime("%H:%M")
            krok_id_val = kroki[i][0]
            cursor.execute('UPDATE krok_wycieczki SET okienko_zwiedzania = ? WHERE id = ?', (f"{s_str} - {e_str}", krok_id_val))
            
            cursor.execute('SELECT id, rodzaj_posilku FROM posilki_kroku WHERE id_kroku = ?', (krok_id_val,))
            pos_rows = cursor.fetchall()
            for p_id, p_rodzaj in pos_rows:
                p_rodz_l = str(p_rodzaj).lower() if p_rodzaj else ""
                if 'śniadan' in p_rodz_l or 'sniadan' in p_rodz_l:
                    nowa_godz_p = pobudka_z_bazy
                elif 'kolacja' in p_rodzaj:
                    nowa_godz_p = (start_times[-1] + timedelta(minutes=30)).strftime("%H:%M") if i == last_idx else s_str
                elif 'obiad' in p_rodz_l or 'lunch' in p_rodz_l or 'duzy' in p_rodz_l:
                    nowa_godz_p = f"{s_str} - {e_str}"
                else:
                    nowa_godz_p = s_str
                cursor.execute('UPDATE posilki_kroku SET sugerowana_godzina = ? WHERE id = ?', (nowa_godz_p, p_id))

            if i < len(kroki) - 1:
                cursor.execute('''
                    INSERT INTO czasy_dojazdu (id_kroku_z, id_kroku_do, czas_przejazdu, szacowany_czas_postoju)
                    VALUES (?, ?, ?, 0)
                ''', (kroki[i][0], kroki[i + 1][0], dojazdy_tekst[i]))

        dt_wyjazd, dt_powrot = end_times[0], start_times[-1]
        czas_trwania_h = round(max((dt_powrot - dt_wyjazd).total_seconds() / 3600.0, 0.5), 1)
        cursor.execute('''
            UPDATE wycieczka 
            SET pobudka = ?, czas_wyjazdu = ?, szacowana_godzina_powrotu = ?, calkowity_czas_wycieczki_godziny = ?, czas_powrotu_do_domku = NULL
            WHERE id = ?
        ''', (pobudka_z_bazy, dt_wyjazd.strftime("%H:%M"), dt_powrot.strftime("%H:%M"), str(czas_trwania_h), str(id_wycieczki)))
        conn.commit()

# --- INICJALIZACJA BAZY DANYCH ---
def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wycieczka (
                id TEXT PRIMARY KEY,
                tytul_wycieczki TEXT,
                calosciowy_opis_wycieczki TEXT,
                calosciowa_taktyka_dnia TEXT,
                calkowity_czas_wycieczki_godziny TEXT,
                szacowana_godzina_powrotu TEXT,
                pobudka TEXT,
                czas_wyjazdu TEXT,
                planowana_data TEXT,
                czas_powrotu_do_domku TEXT,
                szacowany_czas_ogarniania_rano TEXT DEFAULT '0.5h',
                odbyta INTEGER DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS miejsca (
                numer_miejsca TEXT PRIMARY KEY,
                nazwa TEXT,
                typ TEXT,
                wspolrzedne TEXT,
                czas_dojazdu TEXT,
                orientacyjny_czas TEXT,
                koszt TEXT,
                godziny_otwarcia TEXT,
                konieczna_akcja TEXT,
                trudnosc_adhd TEXT,
                ochrona_slonce TEXT,
                potencjal_meltdownu TEXT,
                strategie_meltdown TEXT,
                opis TEXT,
                zadania_dla_dzieci TEXT,
                odwiedzone INTEGER DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS krok_wycieczki (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_wycieczki TEXT,
                krok_wycieczki INTEGER,
                numer_miejsca TEXT,
                nazwa TEXT,
                wspolrzedne TEXT,
                okienko_zwiedzania TEXT,
                godzina_ewakuacji TEXT,
                czerwona_strefa_ostrzezenie TEXT,
                strefa_luzu_i_regeneracji TEXT,
                podsumowanie_taktyki TEXT,
                potencjal_meltdownu TEXT,
                strategie_meltdown TEXT,
                opis TEXT,
                FOREIGN KEY (numer_miejsca) REFERENCES miejsca(numer_miejsca) ON DELETE SET NULL,
                FOREIGN KEY (id_wycieczki) REFERENCES wycieczka(id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posilki_kroku (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_kroku INTEGER,
                rodzaj_posilku TEXT,
                miejsce TEXT,
                sugerowana_godzina TEXT,
                opis TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS czasy_dojazdu (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_kroku_z INTEGER,
                id_kroku_do INTEGER,
                czas_przejazdu TEXT,
                szacowany_czas_postoju INTEGER DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS zakupy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_wycieczki TEXT,
                id_kroku INTEGER,
                nazwa_produktu TEXT,
                ilosc TEXT,
                kupione INTEGER DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notatki (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_wycieczki TEXT,
                id_miejsca TEXT,
                tytul TEXT,
                zawartosc TEXT,
                typ_notatki TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS czat_historia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uzytkownik TEXT,
                rola TEXT,
                tresc TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS statusy_zadan (
                klucz TEXT PRIMARY KEY,
                ukonczone INTEGER DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS aktywna_wycieczka (
                id INTEGER PRIMARY KEY,
                aktualne_id_wycieczki TEXT
            )
        ''')
        cursor.execute('INSERT OR IGNORE INTO aktywna_wycieczka (id, aktualne_id_wycieczki) VALUES (1, "1")')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_krok_wyc ON krok_wycieczki(id_wycieczki)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_krok_miejsce ON krok_wycieczki(numer_miejsca)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_posilki_krok ON posilki_kroku(id_kroku)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_zakupy_wyc ON zakupy(id_wycieczki)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_czasy_dojazd ON czasy_dojazdu(id_kroku_z, id_kroku_do)')

        cursor.execute('SELECT COUNT(*) FROM miejsca')
        miejsca_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM wycieczka')
        wycieczka_count = cursor.fetchone()[0]

        if miejsca_count == 0 and wycieczka_count == 0:
            if os.path.exists('miejsca.csv'):
                for enc in ['utf-8', 'utf-8-sig', 'cp1250', 'iso-8859-2']:
                    try:
                        df_m = pd.read_csv('miejsca.csv', encoding=enc)
                        df_m.columns = [str(col).strip() for col in df_m.columns]
                        
                        def find_col(possible_names, df):
                            for name in possible_names:
                                for col in df.columns:
                                    if col.lower() == name.lower():
                                        return col
                            return None

                        col_nr = find_col(['numer miejsca', 'numer_miejsca', 'id', 'nr'], df_m)
                        col_nazwa = find_col(['nazwa', 'nazwa miejsca', 'name'], df_m)
                        col_typ = find_col(['typ', 'type', 'kategoria'], df_m)
                        col_wsp = find_col(['współrzędne', 'wspolrzedne', 'coordinates', 'coords'], df_m)
                        col_dojazd = find_col(['czas dojazdu ze Stavros', 'czas dojazdu', 'czas_dojazdu'], df_m)
                        col_orient = find_col(['orientacyjny czas zwiedzania', 'orientacyjny czas', 'orientacyjny_czas'], df_m)
                        col_koszt = find_col(['koszt zwiedzania dla rodziny 2+2', 'koszt zwiedzania', 'koszt', 'cena'], df_m)
                        col_godz = find_col(['godziny otwarcia', 'godziny_otwarcia', 'godziny'], df_m)
                        col_akcja = find_col(['Konieczna akcja', 'konieczna_akcja', 'akcja'], df_m)
                        col_trud = find_col(['Poziom trudności ADHD', 'trudnosc_adhd', 'trudność adhd'], df_m)
                        col_slonce = find_col(['Ochrona przed słońcem', 'ochrona_slonce', 'ochrona przed sloncem'], df_m)
                        col_pot_m = find_col(['Potencjał meltdownu', 'potencjal_meltdownu', 'meltdown'], df_m)
                        col_strat_m = find_col(['Strategie na meltdown', 'strategie_meltdown', 'strategie meltdown'], df_m)
                        col_opis = find_col(['Opis', 'opis', 'description'], df_m)
                        col_zadania = find_col(['Zadania dla dzieci', 'zadania_dla_dzieci', 'zadania'], df_m)

                        for _, r in df_m.iterrows():
                            nr_raw = r.get(col_nr) if col_nr else None
                            nr_m = str(nr_raw).strip() if pd.notna(nr_raw) else ''
                            if not nr_m or nr_m == 'nan':
                                continue
                            
                            nazwa_raw = r.get(col_nazwa) if col_nazwa else ''
                            nazwa_m = str(nazwa_raw).strip() if pd.notna(nazwa_raw) else ''
                            
                            raw_typ = str(r.get(col_typ, '')).strip() if col_typ and pd.notna(r.get(col_typ)) else ''
                            typ_m = raw_typ if raw_typ in CATEGORIES_CONFIG else kategoryzuj_typ(raw_typ or nazwa_m)
                            
                            wsp_m = str(r.get(col_wsp, '')).strip() if col_wsp and pd.notna(r.get(col_wsp)) else ''
                            czas_d = str(r.get(col_dojazd, '—')).strip() if col_dojazd and pd.notna(r.get(col_dojazd)) else '—'
                            orient_c = str(r.get(col_orient, '—')).strip() if col_orient and pd.notna(r.get(col_orient)) else '—'
                            koszt_m = str(r.get(col_koszt, '—')).strip() if col_koszt and pd.notna(r.get(col_koszt)) else '—'
                            godz_otw = str(r.get(col_godz, '—')).strip() if col_godz and pd.notna(r.get(col_godz)) else '—'
                            koniecz_akc = str(r.get(col_akcja, '')).strip() if col_akcja and pd.notna(r.get(col_akcja)) else ''
                            trud_adhd = str(r.get(col_trud, 'Średni')).strip() if col_trud and pd.notna(r.get(col_trud)) else 'Średni'
                            ochr_slonce = str(r.get(col_slonce, 'Standardowa')).strip() if col_slonce and pd.notna(r.get(col_slonce)) else 'Standardowa'
                            potencjal_m = str(r.get(col_pot_m, 'Średni')).strip() if col_pot_m and pd.notna(r.get(col_pot_m)) else 'Średni'
                            strat_m = str(r.get(col_strat_m, 'Brak')).strip() if col_strat_m and pd.notna(r.get(col_strat_m)) else 'Brak'
                            opis_m = str(r.get(col_opis, '')).strip() if col_opis and pd.notna(r.get(col_opis)) else ''
                            zadania_d = str(r.get(col_zadania, '')).strip() if col_zadania and pd.notna(r.get(col_zadania)) else ''

                            cursor.execute('''
                                INSERT OR REPLACE INTO miejsca (
                                    numer_miejsca, nazwa, typ, wspolrzedne, czas_dojazdu, orientacyjny_czas,
                                    koszt, godziny_otwarcia, konieczna_akcja, trudnosc_adhd, ochrona_slonce,
                                    potencjal_meltdownu, strategie_meltdown, opis, zadania_dla_dzieci, odwiedzone
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                            ''', (
                                nr_m, nazwa_m, typ_m, wsp_m, czas_d, orient_c,
                                koszt_m, godz_otw, koniecz_akc, trud_adhd, ochr_slonce,
                                potencjal_m, strat_m, opis_m, zadania_d
                            ))
                        conn.commit()
                        break
                    except Exception:
                        continue

            if os.path.exists('wycieczki.csv'):
                for enc in ['utf-8', 'utf-8-sig', 'cp1250', 'iso-8859-2']:
                    try:
                        df_csv = pd.read_csv('wycieczki.csv', encoding=enc)
                        df_csv.columns = [str(col).strip() for col in df_csv.columns]
                        dzisiaj_str = date.today().strftime("%Y-%m-%d")
                        unikalne_wycieczki = df_csv['id_wycieczki'].unique()

                        col_nr_miejsca_csv = find_col(['numer_miejsca', 'numer miejsca', 'id_miejsca', 'nr_miejsca'], df_csv)

                        for wid in unikalne_wycieczki:
                            w_df = df_csv[df_csv['id_wycieczki'] == wid]
                            first_row = w_df.iloc[0]

                            pobudka_raw = str(first_row.get('godzina_pobudki', '06:00')).strip()
                            pobudka_val = pobudka_raw if (pobudka_raw and pobudka_raw != '-') else '06:00'
                            
                            tytul_val = str(first_row.get('tytul_wycieczki', f'Wycieczka {wid}'))
                            opis_val = str(first_row.get('calosciowy_opis_wycieczki', ''))
                            taktyka_val = str(first_row.get('calosciowa_taktyka_dnia', ''))

                            cursor.execute('''
                                INSERT INTO wycieczka (
                                    id, tytul_wycieczki, calosciowy_opis_wycieczki, calosciowa_taktyka_dnia,
                                    pobudka, planowana_data, szacowany_czas_ogarniania_rano, odbyta
                                ) VALUES (?, ?, ?, ?, ?, ?, '0.5h', 0)
                            ''', (str(wid), tytul_val, opis_val, taktyka_val, pobudka_val, dzisiaj_str))

                            step_counter = 0
                            for _, r in w_df.iterrows():
                                nazwa_kroku = str(r.get('nazwa', '')).strip()
                                wsp_kroku = str(r.get('wspolrzedne', '')).strip()
                                okienko_kroku = str(r.get('okienko_zwiedzania', '')).strip()
                                ewak_kroku = str(r.get('godzina_ewakuacji', '')).strip() if pd.notna(r.get('godzina_ewakuacji')) else None
                                czerwona_kroku = str(r.get('czerwona_strefa_ostrzezenie', '')).strip() if pd.notna(r.get('czerwona_strefa_ostrzezenie')) else None
                                strefa_kroku = str(r.get('strefa_luzu_i_regeneracji', '')).strip() if pd.notna(r.get('strefa_luzu_i_regeneracji')) else None
                                taktyka_kroku = str(r.get('podsumowanie_taktyki', '')).strip() if pd.notna(r.get('podsumowanie_taktyki')) else None
                                
                                numer_m_val = str(r.get(col_nr_miejsca_csv)).strip() if (col_nr_miejsca_csv and pd.notna(r.get(col_nr_miejsca_csv))) else None
                                if not numer_m_val or numer_m_val in ['nan', '-', 'None']:
                                    cursor.execute("SELECT numer_miejsca FROM miejsca WHERE LOWER(nazwa) = LOWER(?)", (nazwa_kroku,))
                                    res_m = cursor.fetchone()
                                    numer_m_val = res_m[0] if res_m else None

                                cursor.execute('''
                                    INSERT INTO krok_wycieczki (
                                        id_wycieczki, krok_wycieczki, numer_miejsca, nazwa, wspolrzedne, okienko_zwiedzania,
                                        godzina_ewakuacji, czerwona_strefa_ostrzezenie, strefa_luzu_i_regeneracji,
                                        podsumowanie_taktyki, opis
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (
                                    str(wid), step_counter, numer_m_val, nazwa_kroku, wsp_kroku, okienko_kroku,
                                    ewak_kroku, czerwona_kroku, strefa_kroku, taktyka_kroku, nazwa_kroku
                                ))
                                nowy_krok_id = cursor.lastrowid

                                nazwa_p_raw = r.get('nazwa_posilku')
                                godz_p_raw = r.get('godzina_posilku')
                                pos_raw = r.get('posilek')

                                nazwa_posilku_val = str(nazwa_p_raw).strip() if (pd.notna(nazwa_p_raw) and str(nazwa_p_raw).strip() and str(nazwa_p_raw).strip() not in ['-', 'nan']) else (
                                    str(pos_raw).strip() if (pd.notna(pos_raw) and str(pos_raw).strip() and str(pos_raw).strip() not in ['-', 'nan']) else None
                                )
                                godzina_posilku_val = str(godz_p_raw).strip() if (pd.notna(godz_p_raw) and str(godz_p_raw).strip() and str(godz_p_raw).strip() not in ['-', 'nan']) else None

                                if nazwa_posilku_val:
                                    p_str = nazwa_posilku_val
                                    p_str_l = p_str.lower()
                                    
                                    if 'śniadanie' in p_str_l or 'sniadanie' in p_str_l:
                                        p_rodzaj = 'śniadanie'
                                        p_miejsce = 'w domku'
                                    elif 'kolacja' in p_str_l:
                                        p_rodzaj = 'kolacja'
                                        p_miejsce = 'w domku'
                                    elif any(w in p_str_l for w in ['obiad', 'lunch', 'tawerna', 'restauracja']) and 'lunchbox' not in p_str_l:
                                        p_rodzaj = 'obiad'
                                        p_miejsce = 'restauracja'
                                    elif 'lunchbox duży' in p_str_l or 'duży lunchbox' in p_str_l or 'obiad z domku' in p_str_l:
                                        p_rodzaj = 'lunchbox_duzy'
                                        p_miejsce = 'z domu (lunchbox)'
                                    elif 'lunchbox' in p_str_l or 'drugie śniadanie' in p_str_l or 'podwieczorek' in p_str_l:
                                        p_rodzaj = 'lunchbox_maly'
                                        p_miejsce = 'z domu (lunchbox)'
                                    else:
                                        p_rodzaj = None
                                        
                                    if p_rodzaj:
                                        sugerowana_godz = godzina_posilku_val if godzina_posilku_val else (
                                            '18:30' if p_rodzaj == 'kolacja' else (
                                                '12:30' if p_rodzaj in ['obiad', 'lunchbox_duzy'] else (
                                                    '10:30' if p_rodzaj == 'lunchbox_maly' else (
                                                        okienko_kroku.split('-')[0].strip() if '-' in okienko_kroku else '11:00'
                                                    )
                                                )
                                            )
                                        )
                                        
                                        cursor.execute('''
                                            INSERT INTO posilki_kroku (id_kroku, rodzaj_posilku, miejsce, sugerowana_godzina, opis)
                                            VALUES (?, ?, ?, ?, ?)
                                        ''', (nowy_krok_id, p_rodzaj, p_miejsce, sugerowana_godz, p_str))

                                step_counter += 1

                        conn.commit()
                        
                        for wid in unikalne_wycieczki:
                            przelicz_i_zsynchronizuj_wycieczke(wid)
                            
                        break
                    except Exception as e:
                        print(f"Błąd importu wycieczki.csv podczas init_db: {e}")

        conn.commit()

init_db()

# --- MODUŁ PRZYWRACANIA BAZY Z PLIKÓW CSV ---
def resetuj_i_przywroc_baze_z_csv():
    with get_db() as conn:
        cursor = conn.cursor()
        tabele = [
            "czasy_dojazdu", "posilki_kroku", "zakupy", "notatki", 
            "statusy_zadan", "czat_historia", "krok_wycieczki", 
            "wycieczka", "miejsca", "aktywna_wycieczka"
        ]
        for t in tabele:
            cursor.execute(f"DELETE FROM {t}")
        try:
            cursor.execute('DELETE FROM sqlite_sequence')
        except Exception:
            pass
        conn.commit()
    
    st.cache_data.clear()
    init_db()

# --- BEZPOŚREDNIE MUTACJE STATUSÓW ODWIDZENIA MIEJSC ---
def zmien_status_odwiedzenia_miejsca(nr_miejsca, nowy_status):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE miejsca SET odwiedzone = ? WHERE TRIM(numer_miejsca) = ?", (1 if nowy_status else 0, str(nr_miejsca).strip()))
        conn.commit()
    st.cache_data.clear()

def ustaw_status_odwiedzenia_dla_wycieczki(wycieczka_id, nowy_status):
    status_int = 1 if nowy_status else 0
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE wycieczka SET odbyta = ? WHERE id = ?", (status_int, str(wycieczka_id)))
        
        cursor.execute('''
            UPDATE miejsca 
            SET odwiedzone = ? 
            WHERE numer_miejsca IN (
                SELECT numer_miejsca 
                FROM krok_wycieczki 
                WHERE id_wycieczki = ? AND numer_miejsca IS NOT NULL AND numer_miejsca != ''
            )
        ''', (status_int, str(wycieczka_id)))
        
        cursor.execute("SELECT nazwa, wspolrzedne FROM krok_wycieczki WHERE id_wycieczki = ? AND (numer_miejsca IS NULL OR numer_miejsca = '')", (str(wycieczka_id),))
        kroki_bez_fk = cursor.fetchall()
        if kroki_bez_fk:
            df_all = pd.read_sql("SELECT numer_miejsca, nazwa, wspolrzedne FROM miejsca", conn)
            for k_nazwa, k_wsp in kroki_bez_fk:
                m = dopasuj_krok_do_bazy_miejsc(k_nazwa, k_wsp, df_all)
                if m is not None:
                    cursor.execute("UPDATE miejsca SET odwiedzone = ? WHERE TRIM(numer_miejsca) = ?", (status_int, str(m['numer_miejsca']).strip()))

        conn.commit()
    st.cache_data.clear()

# --- 1. DESIGN SYSTEM I KONFIGURACJA STRONY ---
st.set_page_config(page_title="CretAi - Kreta", layout="centered", page_icon="🧭")

st.markdown("""
<style>
header[data-testid="stHeader"] { background-color: transparent !important; box-shadow: none !important; }
[data-testid="stHeaderActionElements"] { display: none !important; }
.block-container { padding-top: 0.6rem !important; padding-bottom: 120px !important; max-width: 540px; }
.stApp { background-color: #B4C29D !important; color: #2F241D !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
[data-testid="stSidebar"] { background-color: #F6F0DD !important; border-right: 1.5px solid #E2DEC8 !important; }
[data-testid="stSidebar"] * { color: #2B2118 !important; }
h1, h2, h3, h4, h5 { color: #2F241D !important; font-weight: 800; }

input, textarea, .stChatInput textarea { 
    background-color: #FAF8F2 !important; 
    color: #2B2118 !important; 
    border: 1.5px solid #D6D2C4 !important; 
    border-radius: 16px !important; 
    font-size: 16px !important; 
}
::placeholder { color: #8C827A !important; font-size: 14px !important; }

div[data-baseweb="select"], div[data-baseweb="select"] > div, div[data-baseweb="select"] * { background-color: #FAF8F2 !important; color: #2B2118 !important; fill: #2B2118 !important; }
div[data-baseweb="select"] > div { border: 1.5px solid #D6D2C4 !important; border-radius: 16px !important; }
div[data-baseweb="popover"], div[data-baseweb="popover"] > div, ul[role="listbox"], li[role="option"] { background-color: #FAF8F2 !important; color: #2B2118 !important; }
li[role="option"]:hover, li[aria-selected="true"] { background-color: #EFE8D1 !important; color: #8C5338 !important; }
div[data-baseweb="input"], div[data-baseweb="input"] > div, div[data-baseweb="input"] input { background-color: #FAF8F2 !important; color: #2B2118 !important; border-color: #D6D2C4 !important; }
div[data-testid="stHorizontalBlock"] { display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important; gap: 8px !important; }
div[data-testid="stHorizontalBlock"] > div { flex: 1 1 0px !important; min-width: 0 !important; }

div.st-key-btn_date_picker button { background-color: #F6F0DD !important; color: #2B2118 !important; border: 1.5px solid #E2DEC8 !important; border-radius: 20px !important; padding: 12px 14px !important; min-height: 48px !important; font-size: 0.98rem !important; font-weight: 800 !important; width: 100% !important; box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important; }
div.st-key-btn_date_picker button:hover { border-color: #8C5338 !important; background-color: #EFE8D1 !important; }

div.st-key-btn_powrot_static button, div[class*="btn_powrot_static"] button:disabled {
    background-color: #2E251E !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 18px !important;
    padding: 0.4rem 0.8rem !important;
    min-height: 40px !important;
    font-size: 9.5pt !important;
    font-weight: 800 !important;
    box-shadow: 0 3px 8px rgba(0,0,0,0.08) !important;
    opacity: 0.95 !important;
    cursor: default !important;
}

div[data-testid="stPopover"] { width: 100% !important; }
div[data-testid="stPopover"] > button {
    background-color: #F6F0DD !important;
    color: #2B2118 !important;
    border: 1.5px solid #D6CEBA !important;
    border-radius: 16px !important;
    padding: 8px 12px !important;
    min-height: 42px !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.04) !important;
    width: 100% !important;
    font-weight: 800 !important;
}
div[data-testid="stPopover"] > button:hover { border-color: #8C5338 !important; background-color: #EFE8D1 !important; }

[data-testid="stExpander"], div[data-testid="stExpander"] { 
    border: 1.5px solid #E2DEC8 !important; 
    border-radius: 18px !important; 
    background-color: #F6F0DD !important; 
    margin-bottom: 8px !important; 
    box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important; 
    overflow: hidden !important; 
}
[data-testid="stExpander"] summary { 
    font-size: 9.5pt !important; 
    font-weight: 800 !important; 
    color: #2B2118 !important; 
    padding: 10px 14px !important; 
    background-color: #F6F0DD !important;
}
[data-testid="stExpander"] summary:hover { color: #8C5338 !important; }
[data-testid="stExpander"] summary svg { fill: #8C5338 !important; color: #8C5338 !important; }
[data-testid="stExpander"] [data-testid="stExpanderDetails"] { 
    background-color: #F6F0DD !important; 
    border-top: 1px solid #D1C7AE !important; 
    padding: 10px 12px !important; 
}

.top-sticky-nav-container { position: sticky; top: 0; z-index: 999; background-color: #B4C29D; padding: 6px 0 10px 0; margin-bottom: 6px; border-bottom: 1.5px solid rgba(255, 255, 255, 0.2); }
.custom-top-nav-bar { display: flex; justify-content: space-between; gap: 8px; width: 100%; }
.custom-top-nav-btn { flex: 1; background-color: #EFE8D6; border: 1.5px solid #D6CEBC; color: #8A7B70; padding: 7px 4px; text-align: center; border-radius: 14px; font-size: 11px; font-weight: 800; text-decoration: none; display: flex; flex-direction: column; align-items: center; gap: 2px; box-shadow: 0 2px 6px rgba(0,0,0,0.03); }
.custom-top-nav-btn.active { background-color: #F6F0DD; color: #8C5338; border-color: #C8C0AC; font-weight: 900; }

.adventure-header { background: #2E251E; border: none; border-radius: 18px; padding: 8px 14px; display: flex; align-items: center; gap: 10px; margin-bottom: 8px; box-shadow: 0 4px 14px rgba(46, 37, 30, 0.15); }
.adventure-header-img { height: 28px; width: auto; max-width: 100px; object-fit: contain; }
.adventure-title-text { font-size: 1.05rem; font-weight: 900; color: #F9F7F1; letter-spacing: 0.02em; text-transform: uppercase; }

.trip-top-section { padding: 2px 4px 4px 4px; margin-top: 2px; }
.trip-main-title { font-size: 22pt; font-weight: 900; color: #2B2118; letter-spacing: -0.5px; line-height: 1.15; margin-bottom: 4px; }
div.st-key-btn_date_picker { margin-bottom: 10px !important; }

.section-unified-header { font-size: 1.15rem !important; font-weight: 800 !important; color: #2B2118 !important; margin-top: 14px !important; margin-bottom: 6px !important; display: flex; align-items: center; gap: 6px; }
.section-body-text { font-size: 9pt; color: #2B2118; font-weight: 600; line-height: 1.4; margin-bottom: 10px; }

.tactics-alert-box {
    background-color: #FAF8F2;
    border: 1.5px solid #D6D2C4;
    border-radius: 20px;
    padding: 14px;
    margin-top: 4px;
    margin-bottom: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.03);
}
.tactics-alert-title {
    font-size: 10pt;
    font-weight: 900;
    color: #2B2118;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.tactics-alert-text {
    font-size: 9pt;
    color: #4A3E36;
    font-weight: 700;
    line-height: 1.4;
}

.overview-card { background-color: #F6F0DD; border: 1.5px solid #E2DEC8; border-radius: 20px; padding: 14px; margin-bottom: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.03); }
.overview-card-title { font-size: 9.5pt; font-weight: 800; color: #2B2118; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }
.overview-card-text { font-size: 9pt; color: #2B2118; font-weight: 600; line-height: 1.4; }

.logistics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.logistics-pill { background-color: #FAF8F2; border: 1.5px solid #E2DEC8; border-radius: 14px; padding: 8px 10px; }
.logistics-pill-title { font-size: 7.5pt; font-weight: 800; color: #8C5338; text-transform: uppercase; margin-bottom: 2px; display: flex; align-items: center; gap: 4px; }
.logistics-pill-value { font-size: 10pt; font-weight: 900; color: #2B2118; }

.overview-details-card { background-color: #F6F0DD; border: 1.5px solid #E2DEC8; border-radius: 20px; padding: 12px 14px; margin-bottom: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.03); }
.overview-details-card summary { font-size: 9.5pt; color: #2B2118; cursor: pointer; list-style: none; display: flex; justify-content: space-between; align-items: center; }
.overview-details-card summary::-webkit-details-marker { display: none; }
.overview-details-card summary::after { content: "▼"; font-size: 7.5pt; color: #8C5338; }

.timeline-master-container { position: relative; display: flex; flex-direction: column; width: 100%; margin-bottom: 14px; }
.timeline-master-continuous-line { position: absolute; left: 88px; top: 28px; bottom: 28px; width: 3px; background-color: rgba(0, 0, 0, 0.22) !important; transform: translateX(-50%); z-index: 1 !important; pointer-events: none; }
.timeline-step-row-wrapper { position: relative; width: 100%; z-index: 2; }
.timeline-row-frameless { position: relative; display: flex; align-items: center; min-height: 52px; background-color: transparent !important; border: none !important; padding: 4px 8px; box-sizing: border-box; }

.timeline-step-expander { position: relative; background-color: #F6F0DD; border: 1.5px solid #E2DEC8; border-radius: 18px; box-shadow: 0 4px 12px rgba(0,0,0,0.03); overflow: hidden; box-sizing: border-box; }
.timeline-step-expander summary { list-style: none !important; cursor: pointer; padding: 8px 10px; background-color: #F6F0DD; border-radius: 18px; display: block; }
.timeline-step-expander summary::-webkit-details-marker, .timeline-step-expander summary::marker { display: none !important; }
.timeline-step-expander[open] summary { border-bottom: 1.5px solid #E2DEC8; border-bottom-left-radius: 0; border-bottom-right-radius: 0; }

.timeline-row-inner { position: relative; display: flex; align-items: center; min-height: 40px; width: 100%; }
.timeline-time { position: relative; width: 54px; flex-shrink: 0; display: flex; flex-direction: column; justify-content: center; z-index: 2; }
.timeline-time-start { font-size: 10.5pt; font-weight: 900; color: #2B2118; }
.timeline-time-end { font-size: 8pt; font-weight: 700; color: #8C5338; margin-top: 1px; }

.timeline-center-col { position: relative; width: 44px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; margin-right: 6px; }
.timeline-icon-badge-static { position: relative; width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12pt; font-weight: 900; color: #FFFFFF !important; border: 2px solid #FFFFFF !important; box-shadow: 0 2px 5px rgba(0,0,0,0.15); z-index: 5 !important; }

.badge-pobudka, .badge-wyjazd, .badge-powrot { background-color: #7E9169 !important; }
.badge-miejsce { background-color: #C06C4E !important; }
.badge-obiad { background-color: #B56749 !important; }

.timeline-content-col { position: relative; flex: 1; display: flex; flex-direction: column; justify-content: center; z-index: 2; min-width: 0; }
.timeline-item-title { font-size: 11.5pt; font-weight: 900; color: #2B2118; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.timeline-item-desc { font-size: 9pt; color: #4A3E36; }

.timeline-nav-btn { position: relative; flex-shrink: 0; width: auto; min-width: 44px; height: 42px; background-color: transparent !important; border: none !important; border-radius: 12px; text-align: center; text-decoration: none !important; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1px; margin-left: 6px; padding: 0 2px; z-index: 2; }
.timeline-nav-btn span:first-child { font-size: 12pt; color: #8C5338; }
.timeline-nav-btn span:last-child { font-size: 7pt; font-weight: 800; color: #2B2118; }

.timeline-step-expander .timeline-expander-body { position: relative; padding: 10px 12px; background-color: #F6F0DD !important; z-index: 3; }
.step-details-card { position: relative; background-color: #EDE8D6 !important; border: 1.5px solid #D6CEBA; border-radius: 16px; padding: 12px; margin-bottom: 6px; z-index: 3; }
.step-desc-bubble { background-color: #E2DAC4; border-radius: 14px; padding: 10px 12px; font-size: 9.5pt; color: #2B2118; font-weight: 600; margin-bottom: 8px; }
.step-evac-pill { background-color: rgba(220, 80, 80, 0.08); border: 1.5px solid rgba(220, 80, 80, 0.3); border-radius: 14px; padding: 8px 12px; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between; }
.step-evac-pill-title { font-size: 8.5pt; font-weight: 800; color: #DC5050; text-transform: uppercase; }
.step-evac-pill-val { font-size: 10.5pt; font-weight: 900; color: #DC5050; }
.step-warn-box { background-color: rgba(226, 140, 50, 0.1); border: 1.5px solid rgba(226, 140, 50, 0.35); border-radius: 14px; padding: 8px 12px; margin-bottom: 8px; }
.step-warn-title { font-size: 8pt; font-weight: 800; color: #C06C4E; text-transform: uppercase; }
.step-warn-text { font-size: 8.5pt; font-weight: 700; color: #2B2118; }

.step-combined-card { background-color: #E2DAC4; border-radius: 16px; padding: 10px 12px; margin-bottom: 10px; }
.step-combined-card summary { font-size: 9.5pt; font-weight: 800; color: #8C5338; cursor: pointer; list-style: none; display: flex; justify-content: space-between; align-items: center; }
.step-combined-card summary::-webkit-details-marker { display: none; }
.step-combined-card summary::after { content: "▼"; font-size: 7.5pt; color: #8C5338; }
.step-subitem-title { font-size: 9pt; font-weight: 800; margin-bottom: 2px; }
.step-subitem-body { font-size: 8.5pt; color: #2B2118; font-weight: 600; }

.step-action-vertical-bar { display: flex; flex-direction: column; gap: 6px; margin-top: 10px; margin-bottom: 2px; }
.step-action-vertical-btn { background-color: #C3CBB5; border: 1.5px solid #ACB79C; border-radius: 14px; padding: 8px 12px; text-align: center; text-decoration: none !important; display: flex; align-items: center; justify-content: center; gap: 6px; }
.step-action-vertical-btn span:first-child { font-size: 12pt; }
.step-action-vertical-btn span:last-child { font-size: 9pt; font-weight: 800; color: #2B2118; }

.timeline-transit-spacer { position: relative; width: 100%; min-height: 24px; display: flex; align-items: center; margin: 3px 0; z-index: 2; }
.timeline-transit-text { margin-left: 110px; font-size: 8.5pt; font-weight: 800; color: #2B2118; display: flex; align-items: center; gap: 5px; z-index: 2; background: transparent; border: none; padding: 0; }

div[data-testid="stCheckbox"] { 
    margin-bottom: 6px !important; 
    background-color: transparent !important; 
    border: none !important; 
    border-radius: 0px !important; 
    padding: 0px !important; 
    box-shadow: none !important; 
    accent-color: #8C5338 !important; 
}
div[data-testid="stCheckbox"] label, div[data-testid="stCheckbox"] p, div[data-testid="stCheckbox"] span { 
    font-size: 9.5pt !important; 
    font-weight: 700 !important; 
    color: #2B2118 !important; 
    line-height: 1.35 !important;
}

.floating-ai-container { position: fixed; bottom: 10px; left: 6px; right: 6px; max-width: 520px; margin: 0 auto; z-index: 999998; }
.custom-nav-bar { display: flex; justify-content: space-between; gap: 6px; width: 100%; }
.custom-nav-btn { flex: 1; background-color: #FAF8F2; border: 1.5px solid #D6D2C4; color: #2B2118; padding: 7px 3px; text-align: center; border-radius: 14px; font-size: 10.5px; font-weight: 800; text-decoration: none; display: flex; flex-direction: column; align-items: center; gap: 2px; }

.stButton > button { background-color: #2E251E !important; color: #FFFFFF !important; border: none !important; font-weight: 800 !important; border-radius: 18px !important; padding: 0.4rem 0.8rem !important; min-height: 40px !important; font-size: 9.5pt !important; box-shadow: 0 3px 8px rgba(0,0,0,0.08) !important; }
div[class*="st-key-btn_add_shop_"] button, div[class*="st-key-btn_add_market_"] button,
div[class*="st-key-btn_del_shop_"] button, div[class*="st-key-btn_del_market_"] button { 
    height: 40px !important; 
    min-height: 40px !important; 
    max-height: 40px !important; 
    font-size: 8.5pt !important; 
    font-weight: 800 !important; 
    border-radius: 14px !important; 
    margin-bottom: 4px !important; 
    display: flex !important; 
    align-items: center !important; 
    justify-content: center !important; 
    text-align: center !important; 
}
div[class*="st-key-btn_add_shop_"] button:disabled, div[class*="st-key-btn_add_market_"] button:disabled { background-color: #D6CEBA !important; color: #73695F !important; border: 1.5px solid #C4BC9E !important; opacity: 0.85 !important; cursor: not-allowed !important; box-shadow: none !important; }
.note-card { background-color: #F4EFE6; border: 1.5px solid #D8D2BC; border-radius: 16px; padding: 12px; margin-bottom: 8px; }

[data-testid="stChatMessage"] { padding: 8px 10px !important; margin-bottom: 6px !important; border-radius: 14px !important; font-size: 9.5pt !important; }
[data-testid="stChatMessageContent"] p { font-size: 9.5pt !important; line-height: 1.35 !important; margin-bottom: 0 !important; }
</style>
""", unsafe_allow_html=True)

if "flash_toast" in st.session_state and st.session_state["flash_toast"]:
    st.toast(st.session_state["flash_toast"], icon="🧭")
    st.session_state["flash_toast"] = None

# --- SIDEBAR CONFIG ---
with st.sidebar:
    st.markdown("### ⚙️ Konfiguracja CretAi")
    aktualny_uzytkownik = st.selectbox("Profil użytkownika", options=["Magda", "Michał", "Jurek", "Julia"], index=0)
    wybrany_model = st.selectbox(
        "Model Gemini", 
        options=[
            "gemini-3.5-flash",
            "gemini-3.1-pro",
            "gemini-3.5-flash-lite",
            "gemini-3.6-flash"
        ], 
        index=2
    )
    env_gemini_key = os.environ.get("GEMINI_API_KEY", "")
    api_key_input = st.text_input("Gemini API Key", value=env_gemini_key, type="password")

    if aktualny_uzytkownik == "Magda":
        st.markdown("<div style='margin-top: 50px;'></div>", unsafe_allow_html=True)
        with st.expander("🔒 Konsola deweloperska", expanded=False):
            potwierdzenie_kod = st.text_input("Hasło", type="password", key="input_reset_db_auth")
            if st.button("🔥 Przywróć bazę z CSV", disabled=(potwierdzenie_kod != "RESET"), use_container_width=True):
                resetuj_i_przywroc_baze_z_csv()
                st.session_state["flash_toast"] = "♻️ Baza danych została całkowicie zresetowana i odtworzona z CSV!"
                st.rerun()

# --- OBSŁUGA LOGO I ZDJĘĆ MIEJSC ---
@st.cache_data
def pobierz_logo_b64(sciezka_pliku="logo.png"):
    if os.path.exists(sciezka_pliku):
        try:
            with open(sciezka_pliku, "rb") as f:
                return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
        except Exception:
            return None
    return None

_PL_MAP = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")

def generuj_slug_miejsca(nazwa):
    if not nazwa:
        return ""
    s = _wyczysc_nazwe_miejsca(nazwa)
    s = str(s).translate(_PL_MAP)
    s = unicodedata.normalize('NFKD', s)
    s = "".join([c for c in s if not unicodedata.combining(c)])
    return re.sub(r'[^a-zA-Z0-9]+', '_', s).strip('_').lower()

@st.cache_data
def pobierz_zdjecie_miejsca_b64(numer_miejsca, nazwa_miejsca=None):
    katalogi = ["zdjęcia", "zdjecia", "assets/zdjecia", "assets/places", "."]
    rozszerzenia = [
        ("webp", "image/webp"),
        ("jpg", "image/jpeg"), 
        ("jpeg", "image/jpeg"), 
        ("png", "image/png")
    ]
    
    kandydaci_plikow = []

    if nazwa_miejsca:
        slug = generuj_slug_miejsca(nazwa_miejsca)
        if slug:
            for ext, _ in rozszerzenia:
                kandydaci_plikow.append(f"{slug}.{ext}")

    if numer_miejsca:
        nr_clean = str(numer_miejsca).strip()
        for ext, _ in rozszerzenia:
            kandydaci_plikow.append(f"{nr_clean}.{ext}")

    for kat in katalogi:
        if not os.path.isdir(kat):
            continue
        for nazwa_pliku in kandydaci_plikow:
            sciezka = os.path.join(kat, nazwa_pliku)
            if os.path.exists(sciezka):
                try:
                    ext = sciezka.rsplit('.', 1)[-1].lower()
                    mime_map = {
                        "webp": "image/webp",
                        "jpg": "image/jpeg",
                        "jpeg": "image/jpeg",
                        "png": "image/png"
                    }
                    mime = mime_map.get(ext, "image/jpeg")
                    with open(sciezka, "rb") as img_file:
                        encoded = base64.b64encode(img_file.read()).decode()
                        return f"data:{mime};base64,{encoded}"
                except Exception:
                    continue
    return None

def render_adventure_header(tytul_belki):
    logo_base64 = pobierz_logo_b64("logo.png")
    if logo_base64:
        logo_html = f'<img src="{logo_base64}" class="adventure-header-img" alt="CretAi Logo">'
    else:
        logo_html = '<div style="font-size:22px;">🧭</div>'
    
    st.markdown(f"""
    <div class="adventure-header">
        {logo_html}
        <div><div class="adventure-title-text">{tytul_belki}</div></div>
    </div>
    """, unsafe_allow_html=True)

LAIKI_SCHEDULE = {
    0: {"dzien_pl": "Poniedziałek", "opis_miejsca": "Plac Markopoulou / ul. Malinou", "coords": "35.5118, 24.0239"},
    1: {"dzien_pl": "Wtorek", "opis_miejsca": "Plac Agias Marinas / ul. Plastira", "coords": "35.4962, 24.0148"},
    2: {"dzien_pl": "Środa", "opis_miejsca": "ul. Therisou 1 / dawny Biochym", "coords": "35.5057, 24.0094"},
    3: {"dzien_pl": "Czwartek", "opis_miejsca": "Nea Chora – dawna ABEA / Akti Kanari", "coords": "35.5147, 24.0076"},
    4: None,
    5: {"dzien_pl": "Sobota", "opis_miejsca": "ul. Minoos przy murach weneckich", "coords": "35.5166, 24.0237"},
    6: None
}

def pobierz_dane_rynku_dla_daty(data_str):
    try:
        dt = datetime.strptime(str(data_str), "%Y-%m-%d").date()
        weekday = dt.weekday()
    except Exception:
        weekday = date.today().weekday()
    return LAIKI_SCHEDULE.get(weekday), weekday

DNI_TYGODNIA_PL = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
MIESIACE_PL = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]

def sformatuj_date_pl(data_str):
    try:
        dt = datetime.strptime(str(data_str), "%Y-%m-%d").date() if data_str else date.today()
    except Exception:
        dt = date.today()
    return dt, dt.day, MIESIACE_PL[dt.month - 1], DNI_TYGODNIA_PL[dt.weekday()]

def formatuj_posilki_kroku(df_pos):
    if df_pos.empty:
        return ""
    posiłki_str = []
    for _, prow in df_pos.iterrows():
        p_rodzaj = str(prow.get('rodzaj_posilku', '')).strip().lower()
        p_godz = str(prow.get('sugerowana_godzina', '')).strip()
        p_opis = str(prow.get('opis', '')).strip()
        
        if p_rodzaj in ['śniadanie', 'sniadanie']:
            nazwa = "Śniadanie"
        elif p_rodzaj == 'kolacja':
            nazwa = "Kolacja"
        elif p_rodzaj in ['obiad', 'lunch']:
            nazwa = "Obiad"
        elif p_rodzaj == 'lunchbox_maly':
            nazwa = "Mały lunchbox"
        elif p_rodzaj == 'lunchbox_duzy':
            nazwa = "Duży lunchbox"
        else:
            nazwa = p_opis.capitalize() if p_opis and p_opis not in ['-', 'nan', 'Brak'] else p_rodzaj.capitalize()
            
        if p_godz and p_godz not in ['-', 'nan', 'Brak']:
            posiłki_str.append(f"{nazwa} - ok {p_godz}")
        else:
            posiłki_str.append(nazwa)
            
    return f"<span style='color:#8C5338; font-weight:700;'>{' / '.join(posiłki_str)}</span>" if posiłki_str else ""

def render_action_bar(coords_clean, search_name=""):
    google_search_btn = f'<a href="https://www.google.com/search?q={search_name} Kreta" target="_blank" class="step-action-vertical-btn"><span>🔍</span><span>Szukaj w Google</span></a>' if search_name else ""
    return f"""
    <div class="step-action-vertical-bar">
        <a href="https://www.google.com/maps/search/?api=1&query={coords_clean}" target="_blank" class="step-action-vertical-btn"><span>🧭</span><span>Nawiguj do tego miejsca</span></a>
        {google_search_btn}
    </div>
    """

def formatuj_komunikat_bledu_ai(e):
    kod = getattr(e, 'code', None) or getattr(e, 'status_code', None)
    msg = str(e)
    if "429" in msg or kod == 429 or "RESOURCE_EXHAUSTED" in msg:
        return "⏳ Przekroczono limit zapytań (429 Rate Limit)", "Wyczerpano limit zapytań na minutę (RPM/TPM). Odczekaj chwilę."
    if "401" in msg or "403" in msg or kod in [401, 403]:
        return "🔑 Błąd uwierzytelnienia klucza API", "Wprowadzony klucz API jest nieprawidłowy lub wygasł."
    return f"⚠️ Błąd połączenia z API ({type(e).__name__})", f"Szczegóły: {msg}"

# --- FUNKCJE POGODOWE ---
@st.cache_data(ttl=28800)
def pobierz_prognoze_pogody(lat, lon, data_docelowa):
    try:
        url = f"https://wttr.in/{lat},{lon}?format=j1"
        req = urllib.request.Request(url, headers={'User-Agent': 'CretAiApp/1.0'})
        with urllib.request.urlopen(req, timeout=0.5) as response:
            data = json.loads(response.read().decode())
            weather_list = data.get('weather', [])
            for day in weather_list:
                if day.get('date') == data_docelowa:
                    return day
            if weather_list:
                return weather_list[0]
    except Exception:
        pass
    return None

def pobierz_szczegoly_pogody_dla_godziny(wspolrzedne, planowana_data, okienko_czasowe="12:00 - 14:00"):
    if not planowana_data or not str(planowana_data).strip():
        return None
    lat, lon = sparsuj_wspolrzedne(wspolrzedne)
    if lat is None or lon is None:
        return None

    prognoza_dnia = pobierz_prognoze_pogody(lat, lon, str(planowana_data))
    if not prognoza_dnia:
        return None

    hourly_list = prognoza_dnia.get('hourly', [])
    target_hour = 12
    if okienko_czasowe and "-" in okienko_czasowe:
        try:
            target_hour = int(okienko_czasowe.split("-")[0].strip().split(":")[0])
        except Exception:
            pass

    dopasowana_godzina, min_diff = None, 999
    for h in hourly_list:
        try:
            diff = abs(int(h.get('time', '0')) // 100 - target_hour)
            if diff < min_diff:
                min_diff, dopasowana_godzina = diff, h
        except Exception:
            pass

    if dopasowana_godzina:
        return {
            "temp": dopasowana_godzina.get('tempC', '—'),
            "feel": dopasowana_godzina.get('FeelsLikeC', '—'),
            "desc": dopasowana_godzina.get('weatherDesc', [{}])[0].get('value', 'Sunny'),
            "wind": dopasowana_godzina.get('windspeedKmph', '—'),
            "uv": dopasowana_godzina.get('uvIndex', '—'),
            "data": planowana_data
        }
    return None

def renderuj_podsumowanie_pogody_wycieczki(kroki_df, planowana_data):
    if not planowana_data or not str(planowana_data).strip() or kroki_df.empty:
        return

    ostrzezenia, max_temp, min_temp = [], -99, 99
    opisy_pogody = []
    max_wind = 0
    deszcz_prognozowany = False

    for _, k in kroki_df.iterrows():
        lat, lon = sparsuj_wspolrzedne(k['wspolrzedne'])
        if lat is not None and lon is not None:
            prognoza = pobierz_prognoze_pogody(lat, lon, str(planowana_data))
            if prognoza and 'hourly' in prognoza:
                for h in prognoza['hourly']:
                    t = int(h.get('tempC', 20))
                    max_temp = max(max_temp, t)
                    min_temp = min(min_temp, t)
                    w_spd = int(h.get('windspeedKmph', 0))
                    max_wind = max(max_wind, w_spd)
                    
                    desc = h.get('weatherDesc', [{}])[0].get('value', '').strip()
                    if desc:
                        opisy_pogody.append(desc)

    desc_lower_all = " ".join(opisy_pogody).lower()
    if any(w in desc_lower_all for w in ['rain', 'deszcz', 'shower', 'drizzle']):
        deszcz_prognozowany = True
        ostrzezenia.append("🌧️ Możliwe przelotne opady deszczu na trasie!")
    if any(w in desc_lower_all for w in ['storm', 'thunder', 'burza']):
        ostrzezenia.append("⚡ Ryzyko burz i wyładowań!")
    if max_temp >= 32:
        ostrzezenia.append(f"🔥 Wysoka temperatura (do {max_temp}°C) – bezwzględnie unikaj słońca w południe.")

    if any(w in desc_lower_all for w in ['sunny', 'clear']):
        glowny_stan = "☀️ Słonecznie i bezchmurnie"
    elif any(w in desc_lower_all for w in ['partly cloudy']):
        glowny_stan = "⛅ Częściowo słonecznie z lekkim zachmurzeniem"
    elif any(w in desc_lower_all for w in ['cloudy', 'overcast']):
        glowny_stan = "☁️ Umiarkowane / duże zachmurzenie"
    else:
        glowny_stan = "🌤️ Przeważnie pogodnie"

    opady_tekst = "🌧️ Możliwy deszcz" if deszcz_prognozowany else "💧 Brak opadów"
    wiatr_tekst = f"💨 Wiatr do {max_wind} km/h" if max_wind > 0 else ""

    ostrzezenia_html = "".join([f'<div style="color: #DC5050; font-weight: 800; font-size: 8.5pt; margin-top: 3px;">{ost}</div>' for ost in ostrzezenia])

    st.markdown(f"""
    <div class="overview-card" style="margin-top: 4px; margin-bottom: 12px; background-color: #FAF8F2; border: 1.5px solid #D6D2C4;">
        <div style="display: space-between; align-items: center; margin-bottom: 4px; display: flex;">
            <div style="font-size: 10pt; font-weight: 900; color: #2B2118;">🌤️ Podsumowanie pogody</div>
            <div style="font-size: 9.5pt; font-weight: 900; color: #8C5338;">{min_temp}°C – {max_temp}°C</div>
        </div>
        <div style="font-size: 9pt; color: #4A3E36; font-weight: 700; margin-bottom: 2px;">
            {glowny_stan} • {opady_tekst} {('• ' + wiatr_tekst) if wiatr_tekst else ''}
        </div>
        {ostrzezenia_html}
    </div>
    """, unsafe_allow_html=True)

# --- FUNKCJE CZATU I NOTATEK ---
def pobierz_historie_czatu_z_db(uzytkownik):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT rola, tresc FROM czat_historia WHERE uzytkownik = ? ORDER BY id ASC', (uzytkownik,))
        rows = cursor.fetchall()
    return [{"role": rola, "content": tresc} for rola, tresc in rows]

def zapisz_wiadomosc_w_db(uzytkownik, rola, tresc):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO czat_historia (uzytkownik, rola, tresc) VALUES (?, ?, ?)', (uzytkownik, rola, tresc))
        conn.commit()

def wyczysc_historie_czatu_w_db(uzytkownik):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM czat_historia WHERE uzytkownik = ?', (uzytkownik,))
        conn.commit()

def pobierz_notatki(id_wycieczki=None, id_miejsca=None):
    with get_db() as conn:
        if id_wycieczki:
            return pd.read_sql('SELECT * FROM notatki WHERE id_wycieczki = ?', conn, params=(str(id_wycieczki),))
        elif id_miejsca:
            return pd.read_sql('SELECT * FROM notatki WHERE id_miejsca = ?', conn, params=(str(id_miejsca),))
    return pd.DataFrame()

def dodaj_notatke(zawartosc, typ_notatki="text", id_wycieczki=None, id_miejsca=None, tytul=""):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO notatki (id_wycieczki, id_miejsca, tytul, zawartosc, typ_notatki)
            VALUES (?, ?, ?, ?, ?)
        ''', (str(id_wycieczki) if id_wycieczki else None, str(id_miejsca) if id_miejsca else None, tytul, zawartosc, typ_notatki))
        conn.commit()
    return {"success": True, "action": "dodaj_notatke", "message": "Pomyślnie dodano notatkę."}

def renderuj_sekcje_notatek(id_wycieczki=None, id_miejsca=None):
    st.markdown('<div class="section-unified-header">📌 Notatki</div>', unsafe_allow_html=True)
    df_notatki = pobierz_notatki(id_wycieczki=id_wycieczki, id_miejsca=id_miejsca)

    if not df_notatki.empty:
        for _, note in df_notatki.iterrows():
            st.markdown(f'<div class="note-card"><div style="font-weight: 800; font-size: 10pt; color: #2B2118; margin-bottom: 3px;">📌 {note.get("tytul") or "Notatka"}</div><div style="font-size: 9pt; color: #4A3E36;">{note["zawartosc"]}</div></div>', unsafe_allow_html=True)

    with st.expander("➕ Dodaj nową notatkę", expanded=False):
        with st.form(key=f"form_add_note_{id_wycieczki}_{id_miejsca}", clear_on_submit=True):
            nt_tytul = st.text_input("Tytuł (opcjonalnie)")
            nt_typ = st.selectbox("Typ notatki", options=["text", "link", "list"], format_func=lambda x: {"text": "📝 Tekst", "link": "🔗 Link", "list": "📋 Checklista"}[x])
            nt_zawartosc = st.text_area("Treść notatki")
            if st.form_submit_button("💾 Zapisz notatkę", use_container_width=True) and nt_zawartosc:
                dodaj_notatke(zawartosc=nt_zawartosc, typ_notatki=nt_typ, id_wycieczki=id_wycieczki, id_miejsca=id_miejsca, tytul=nt_tytul)
                st.session_state["flash_toast"] = "💾 Dodano notatkę!"
                st.rerun()

# --- ZAKUPY I STATUSY ---
def zmien_status_zakupu(id_zakupu, status):
    with get_db() as conn:
        conn.cursor().execute('UPDATE zakupy SET kupione = ? WHERE id = ?', (1 if status else 0, id_zakupu))
        conn.commit()

def dodaj_produkt_zakupow(id_wycieczki, nazwa_produktu, id_kroku=None, ilosc="1"):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO zakupy (id_wycieczki, id_kroku, nazwa_produktu, ilosc, kupione)
            VALUES (?, ?, ?, ?, 0)
        ''', (str(id_wycieczki), int(id_kroku) if id_kroku else None, str(nazwa_produktu).strip(), str(ilosc).strip()))
        conn.commit()
    return {"success": True, "action": "dodaj_produkt_zakupow", "message": f"Dodano produkt: {nazwa_produktu}"}

def dodaj_wiele_produktow_zakupow(id_wycieczki, produkty, id_kroku=None):
    with get_db() as conn:
        cursor = conn.cursor()
        for prod in produkty:
            nazwa = prod.get("nazwa") if isinstance(prod, dict) else str(prod)
            ilosc = prod.get("ilosc", "1") if isinstance(prod, dict) else "1"
            cursor.execute('''
                INSERT INTO zakupy (id_wycieczki, id_kroku, nazwa_produktu, ilosc, kupione)
                VALUES (?, ?, ?, ?, 0)
            ''', (str(id_wycieczki), int(id_kroku) if id_kroku else None, str(nazwa).strip(), str(ilosc).strip()))
        conn.commit()
    return {"success": True, "action": "dodaj_wiele_produktow_zakupow", "message": f"Dodano {len(produkty)} produktów do listy zakupów."}

# --- OBSŁUGA ZADAŃ DLA DZIECI ---
def sparsuj_liste_zadan(zadania_raw):
    if not zadania_raw or pd.isna(zadania_raw):
        return []
    if isinstance(zadania_raw, list):
        return [str(z).strip() for z in zadania_raw if str(z).strip()]
    
    zadania_str = str(zadania_raw).strip()
    try:
        parsed_json = json.loads(zadania_str)
        if isinstance(parsed_json, list):
            return [str(z).strip() for z in parsed_json if str(z).strip()]
    except Exception:
        pass

    linie = []
    for line in zadania_str.split('\n'):
        line_clean = line.strip()
        if not line_clean:
            continue
        czesci = re.split(r'(?:^|\s+)(?:\d+[\.\)]\s*|[-•*]\s*)', line_clean)
        for czesc in czesci:
            czesc_clean = czesc.strip()
            if czesc_clean and len(czesc_clean) > 2:
                linie.append(czesc_clean)
                
    if not linie:
        linie = [zadania_str]
    return linie

def pobierz_status_zadania(klucz_zadania):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT ukonczone FROM statusy_zadan WHERE klucz = ?', (klucz_zadania,))
        row = cursor.fetchone()
        return bool(row[0]) if row else False

def zapisz_status_zadania(klucz_zadania, status):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO statusy_zadan (klucz, ukonczone) VALUES (?, ?)
            ON CONFLICT(klucz) DO UPDATE SET ukonczone = excluded.ukonczone
        ''', (klucz_zadania, 1 if status else 0))
        conn.commit()

def pobierz_grupy_zadan_dla_wycieczki(wycieczka_id, kroki_df, df_wszystkie_miejsca_ref):
    grupy = []
    if kroki_df.empty or df_wszystkie_miejsca_ref.empty:
        return grupy

    for _, krok in kroki_df.iterrows():
        nazwa_kroku = str(krok.get('nazwa', '')).strip()
        wsp_kroku = str(krok.get('wspolrzedne', '')).strip()
        krok_id = krok.get('id')
        nr_fk = krok.get('numer_miejsca')

        m_row = None
        if pd.notna(nr_fk) and str(nr_fk).strip() and str(nr_fk).strip() not in ['None', 'nan', '']:
            match_df = df_wszystkie_miejsca_ref[df_wszystkie_miejsca_ref['numer_miejsca'].astype(str) == str(nr_fk).strip()]
            if not match_df.empty:
                m_row = match_df.iloc[0]

        if m_row is None:
            m_row = dopasuj_krok_do_bazy_miejsc(nazwa_kroku, wsp_kroku, df_wszystkie_miejsca_ref)

        if m_row is not None:
            zadania_raw = m_row.get('zadania_dla_dzieci', '')
            zadania = sparsuj_liste_zadan(zadania_raw)
            if zadania:
                tytul = f"📍 {m_row.get('numer_miejsca')}. {m_row.get('nazwa')}"
                grupy.append((tytul, zadania, f"trip_{wycieczka_id}_step_{krok_id}"))

    return grupy

def znajdz_id_kroku_w_db(cursor, id_wycieczki, identyfikator):
    ident_str = str(identyfikator).strip().lower()
    cursor.execute('SELECT id, krok_wycieczki, nazwa FROM krok_wycieczki WHERE id_wycieczki = ?', (str(id_wycieczki),))
    rows = cursor.fetchall()
    
    for r_id, r_num, r_nazwa in rows:
        if str(r_id) == str(identyfikator) or str(r_num) == str(identyfikator):
            return r_id, r_nazwa

    for r_id, r_num, r_nazwa in rows:
        nazwa_l = r_nazwa.lower()
        if ident_str in nazwa_l or nazwa_l in ident_str:
            return r_id, r_nazwa
        if ident_str in ["sklep", "market", "zakupy"] and any(w in nazwa_l for w in ["sklep", "market", "zakup"]):
            return r_id, r_nazwa
        if ident_str in ["rynek", "targ", "laiki"] and any(w in nazwa_l for w in ["rynek", "targ", "laiki"]):
            return r_id, r_nazwa

    return None

def render_shopping_checkbox_list(df_items, key_prefix):
    for _, zrow in df_items.iterrows():
        z_id, z_nazwa, z_kup = zrow['id'], str(zrow['nazwa_produktu']), bool(zrow['kupione'])
        z_ilosc = f" ({zrow['ilosc']})" if pd.notna(zrow['ilosc']) and str(zrow['ilosc']).strip() else ""
        nowy_status = st.checkbox(f"{z_nazwa}{z_ilosc}", value=z_kup, key=f"cb_{key_prefix}_{z_id}")
        if nowy_status != z_kup:
            zmien_status_zakupu(z_id, nowy_status)
            st.rerun()

def pobierz_wszystkie_miejsca():
    with get_db() as conn:
        return pd.read_sql('SELECT * FROM miejsca ORDER BY CAST(numer_miejsca AS INTEGER) ASC', conn)

def pobierz_aktywna_wycieczke_id():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT aktualne_id_wycieczki FROM aktywna_wycieczka WHERE id = 1')
        res = cursor.fetchone()
        if not res:
            cursor.execute('INSERT INTO aktywna_wycieczka (id, aktualne_id_wycieczki) VALUES (1, "1")')
            conn.commit()
            return "1"
    return str(res[0]) if res else "1"

def ustaw_aktywna_wycieczke_id(nowe_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE aktywna_wycieczka SET aktualne_id_wycieczki = ? WHERE id = 1', (str(nowe_id),))
        conn.commit()

def szukaj_miejsca_w_bazie(nazwa_zapytania):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT numer_miejsca, nazwa, typ, wspolrzedne, czas_dojazdu, orientacyjny_czas, 
                   godziny_otwarcia, konieczna_akcja, ochrona_slonce, potencjal_meltdownu, 
                   strategie_meltdown, opis
            FROM miejsca 
            WHERE nazwa LIKE ? OR numer_miejsca = ?
        ''', (f"%{nazwa_zapytania}%", str(nazwa_zapytania)))
        row = cursor.fetchone()
        if row:
            return {
                "numer_miejsca": row[0], "nazwa": row[1], "typ": row[2], "wspolrzedne": row[3], 
                "czas_dojazdu": row[4], "orientacyjny_czas": row[5], "godziny_otwarcia": row[6], 
                "konieczna_akcja": row[7], "ochrona_slonce": row[8], "potencjal_meltdownu": row[9], 
                "strategie_meltdown": row[10], "opis": row[11]
            }
    return None

# --- STRAŻNIK AuDHD ---
def sprawdz_ryzyka_audhd_dla_kroku(id_wycieczki, nazwa_nowego_miejsca, planowane_okienko):
    miejsce_info = szukaj_miejsca_w_bazie(nazwa_nowego_miejsca)
    nazwa_l = str(nazwa_nowego_miejsca).lower()
    
    g_start = sparsuj_godzine_minuty(planowane_okienko.split("-")[0].strip()) if "-" in str(planowane_okienko) else sparsuj_godzine_minuty(str(planowane_okienko))
    if g_start:
        godz_dec = g_start[0] + g_start[1] / 60.0
        if 11.5 <= godz_dec <= 15.5:
            ochrona = str(miejsce_info.get('ochrona_slonce', '')).lower() if miejsce_info else ""
            if any(w in ochrona for w in ['brak', 'niska', 'odkryte', 'pełne słońce', 'patelnia']) or \
               any(w in nazwa_l for w in ['knossos', 'phaistos', 'ruiny', 'gortyna', 'falasarna', 'elafonisi']):
                return False, (
                    f"⛔ ODMOWA: Planowanie '{nazwa_nowego_miejsca}' w oknie {planowane_okienko} narusza regułę sjesty i ochrony przed słońcem (11:30–15:30). "
                    f"Jest to otwarty teren w pełnym słońcu – gwarantowane przebodźcowanie sensoryczne i ryzyko udaru termicznego. "
                    f"💡 PROPOZYCJA: Zaplanuj tę atrakcję z samego rana (np. 08:00–10:00) lub w tych godzinach wybierz klimatyzowane Cretaquarium, jaskinię lub obiad w tawernie w głębokim cieniu."
                )

    if g_start:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.rodzaj_posilku, p.sugerowana_godzina, k.okienko_zwiedzania, k.nazwa
                FROM posilki_kroku p
                JOIN krok_wycieczki k ON p.id_kroku = k.id
                WHERE k.id_wycieczki = ? AND p.rodzaj_posilku IN ('śniadanie', 'obiad', 'kolacja', 'lunchbox', 'lunchbox_maly', 'lunchbox_duzy')
                ORDER BY CAST(k.krok_wycieczki AS INTEGER) ASC
            ''', (str(id_wycieczki),))
            glowne_posilki = cursor.fetchall()
        
        if glowne_posilki:
            ostatni_posilek = glowne_posilki[-1]
            pos_godz_str = ostatni_posilek[1] or (ostatni_posilek[2].split("-")[0].strip() if ostatni_posilek[2] else None)
            g_pos = sparsuj_godzine_minuty(pos_godz_str)
            if g_pos:
                pos_dec = g_pos[0] + g_pos[1] / 60.0
                if (godz_dec - pos_dec) > 4.0:
                    return False, (
                        f"⛔ ODMOWA: Od ostatniego posiłku stabilizującego ({ostatni_posilek[0]} w punkcie '{ostatni_posilek[3]}', ok. {pos_godz_str}) "
                        f"do planowanego punktu '{nazwa_nowego_miejsca}' ({planowane_okienko}) mija ponad 4.0 godziny. "
                        f"Podgryzajki nie zastępują posiłku. Dzieci z AuDHD wejdą w stan silnego przebodźcowania i głodu. "
                        f"💡 PROPOZYCJA: Zaplanuj Lunchbox mały, ciepły obiad na mieście w cieniu lub Lunchbox duży przed '{nazwa_nowego_miejsca}'."
                    )

    return True, ""

# --- OPERACJE NA KROKACH I WYCIECZKACH ---
def utworz_nowe_miejsce(nazwa, typ="Other", wspolrzedne="", orientacyjny_czas="45 min", 
                        koszt="—", godziny_otwarcia="—", konieczna_akcja="", trudnosc_adhd="Średni", 
                        ochrona_slonce="Standardowa", potencjal_meltdownu="Średni", 
                        strategie_meltdown="Brak", opis="", zadania_dla_dzieci=""):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT numer_miejsca FROM miejsca WHERE LOWER(nazwa) = ?", (nazwa.strip().lower(),))
        istniejace = cursor.fetchone()
        if istniejace:
            return {"success": False, "error": f"Miejsce o nazwie '{nazwa}' już istnieje w bazie pod numerem #{istniejace[0]}."}

        cursor.execute("SELECT MAX(CAST(numer_miejsca AS INTEGER)) FROM miejsca")
        max_row = cursor.fetchone()
        nowy_nr = str((max_row[0] or 0) + 1) if max_row and max_row[0] is not None else "1"

        lat_p, lon_p = sparsuj_wspolrzedne(wspolrzedne)
        czas_dojazdu_z_domku = "—"
        if lat_p is not None and lon_p is not None:
            tekst_dojazdu, _ = oblicz_czas_przejazdu_osrm(DOMEK_LAT, DOMEK_LON, lat_p, lon_p)
            czas_dojazdu_z_domku = tekst_dojazdu

        kat_norm = kategoryzuj_typ(typ if typ in CATEGORIES_CONFIG else nazwa)

        cursor.execute('''
            INSERT INTO miejsca (
                numer_miejsca, nazwa, typ, wspolrzedne, czas_dojazdu, orientacyjny_czas,
                koszt, godziny_otwarcia, konieczna_akcja, trudnosc_adhd, ochrona_slonce,
                potencjal_meltdownu, strategie_meltdown, opis, zadania_dla_dzieci, odwiedzone
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        ''', (
            nowy_nr, nazwa.strip(), kat_norm, wspolrzedne.strip(), czas_dojazdu_z_domku,
            orientacyjny_czas, koszt, godziny_otwarcia, konieczna_akcja, trudnosc_adhd,
            ochrona_slonce, potencjal_meltdownu, strategie_meltdown, opis, zadania_dla_dzieci
        ))
        conn.commit()

    st.cache_data.clear()
    return {
        "success": True, 
        "action": "utworz_nowe_miejsce", 
        "numer_miejsca": nowy_nr, 
        "czas_dojazdu": czas_dojazdu_z_domku,
        "message": f"Pomyślnie dodano nowe miejsce #{nowy_nr}: '{nazwa}' (Dojazd z domku: {czas_dojazdu_z_domku})."
    }

def utworz_nowa_wycieczke(tytul_wycieczki, planowana_data=None, pobudka="06:00", 
                          czas_wyjazdu="06:30", opis="", taktyka_dnia=""):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM wycieczka")
        wszystkie_id = [int(r[0]) for r in cursor.fetchall() if str(r[0]).isdigit()]
        nowe_id = str(max(wszystkie_id) + 1 if wszystkie_id else 1)
        data_val = planowana_data or date.today().strftime("%Y-%m-%d")

        cursor.execute('''
            INSERT INTO wycieczka (
                id, tytul_wycieczki, calosciowy_opis_wycieczki, calosciowa_taktyka_dnia,
                calkowity_czas_wycieczki_godziny, szacowana_godzina_powrotu, pobudka, czas_wyjazdu,
                planowana_data, czas_powrotu_do_domku, szacowany_czas_ogarniania_rano, odbyta
            ) VALUES (?, ?, ?, ?, '0', '17:00', ?, ?, ?, NULL, '0.5h', 0)
        ''', (nowe_id, tytul_wycieczki, opis, taktyka_dnia, pobudka, czas_wyjazdu, data_val))

        cursor.execute('''
            INSERT INTO krok_wycieczki (id_wycieczki, krok_wycieczki, numer_miejsca, nazwa, wspolrzedne, okienko_zwiedzania, opis)
            VALUES (?, 0, NULL, 'Nasz Domek (Start)', ?, ?, 'Poranne przygotowanie i bezpieczne śniadanie')
        ''', (nowe_id, f"{DOMEK_LAT}, {DOMEK_LON}", f"{pobudka} - {czas_wyjazdu}"))
        id_start = cursor.lastrowid
        
        cursor.execute('''
            INSERT INTO posilki_kroku (id_kroku, rodzaj_posilku, miejsce, sugerowana_godzina, opis)
            VALUES (?, 'śniadanie', 'w domku', ?, 'Śniadanie')
        ''', (id_start, pobudka))

        cursor.execute('UPDATE aktywna_wycieczka SET aktualne_id_wycieczki = ? WHERE id = 1', (nowe_id,))
        conn.commit()

    przelicz_i_zsynchronizuj_wycieczke(nowe_id)
    return {
        "success": True, 
        "action": "utworz_nowa_wycieczke", 
        "id_wycieczki": nowe_id, 
        "message": f"Utworzono nową wycieczkę #{nowe_id}: '{tytul_wycieczki}' i ustawiono ją jako aktywną."
    }

def dodaj_sklep_przy_domku_do_wycieczki(id_wycieczki, pozycja="koniec"):
    with get_db() as conn:
        cursor = conn.cursor()
        nowy_id = _wstaw_krok_do_wycieczki(
            cursor=cursor,
            id_wycieczki=id_wycieczki,
            nazwa='Sklep przy domku w Stavros',
            wspolrzedne=f"{SKLEP_LAT}, {SKLEP_LON}",
            okienko='16:00 - 16:30',
            opis='',
            numer_miejsca=None,
            pozycja=pozycja
        )
        conn.commit()

    przelicz_i_zsynchronizuj_wycieczke(id_wycieczki)
    return {"success": True, "action": "dodaj_sklep_przy_domku", "id_kroku": nowy_id, "message": "Pomyślnie dodano sklep."}

def usun_sklep_z_wycieczki_handler(id_wycieczki, pozycja=None):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, krok_wycieczki, nazwa FROM krok_wycieczki WHERE id_wycieczki = ? ORDER BY CAST(krok_wycieczki AS INTEGER) ASC", (str(id_wycieczki),))
        rows = cursor.fetchall()
        
        shop_rows = [r for r in rows if any(w in str(r[2]).lower() for w in ['sklep', 'market'])]
        if not shop_rows:
            return {"success": False, "message": "Nie znaleziono sklepu w tej wycieczce."}
        
        target = shop_rows[-1] if pozycja == "koniec" else shop_rows[0]
        _usun_krok_z_wycieczki(cursor, target[0], id_wycieczki)
        conn.commit()

    przelicz_i_zsynchronizuj_wycieczke(id_wycieczki)
    return {"success": True, "action": "usun_sklep_z_wycieczki", "message": "Pomyślnie usunięto sklep z wycieczki."}

def dodaj_rynek_w_chanii_do_wycieczki(id_wycieczki, pozycja="start"):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT planowana_data FROM wycieczka WHERE id = ?', (str(id_wycieczki),))
        plan_d = cursor.fetchone()
        plan_data_val = plan_d[0] if plan_d else None
        rynek_info, _ = pobierz_dane_rynku_dla_daty(plan_data_val)
        
        wsp = rynek_info["coords"] if rynek_info else "35.5118, 24.0239"
        opis = f"Targ miejski: {rynek_info['opis_miejsca']}" if rynek_info else "Targ miejski Chania"
        
        nowy_id = _wstaw_krok_do_wycieczki(
            cursor=cursor,
            id_wycieczki=id_wycieczki,
            nazwa='Rynek w Chanii (Laiki)',
            wspolrzedne=wsp,
            okienko='08:30 - 09:30',
            opis=opis,
            numer_miejsca=None,
            pozycja=pozycja
        )
        conn.commit()

    przelicz_i_zsynchronizuj_wycieczke(id_wycieczki)
    return {"success": True, "action": "dodaj_rynek_w_chanii", "id_kroku": nowy_id, "message": f"Pomyślnie dodano rynek w Chanii."}

def usun_rynek_z_wycieczki_handler(id_wycieczki, pozycja=None):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, krok_wycieczki, nazwa FROM krok_wycieczki WHERE id_wycieczki = ? ORDER BY CAST(krok_wycieczki AS INTEGER) ASC", (str(id_wycieczki),))
        rows = cursor.fetchall()
        
        market_rows = [r for r in rows if any(w in str(r[2]).lower() for w in ['rynek', 'targ', 'laiki'])]
        if not market_rows:
            return {"success": False, "message": "Nie znaleziono rynku w tej wycieczce."}
        
        target = market_rows[-1] if pozycja == "koniec" else market_rows[0]
        _usun_krok_z_wycieczki(cursor, target[0], id_wycieczki)
        conn.commit()

    przelicz_i_zsynchronizuj_wycieczke(id_wycieczki)
    return {"success": True, "action": "usun_rynek_z_wycieczki", "message": "Pomyślnie usunięto rynek z wycieczki."}

def edytuj_wycieczke(id, tytul_wycieczki=None, planowana_data=None, czas_wyjazdu=None, szacowany_czas_ogarniania_rano=None, calosciowa_taktyka_dnia=None, calosciowy_opis_wycieczki=None):
    with get_db() as conn:
        cursor = conn.cursor()
        if tytul_wycieczki:
            cursor.execute('UPDATE wycieczka SET tytul_wycieczki = ? WHERE id = ?', (tytul_wycieczki, str(id)))
        if calosciowy_opis_wycieczki is not None:
            cursor.execute('UPDATE wycieczka SET calosciowy_opis_wycieczki = ? WHERE id = ?', (calosciowy_opis_wycieczki, str(id)))
        if planowana_data:
            cursor.execute('UPDATE wycieczka SET planowana_data = ? WHERE id = ?', (planowana_data, str(id)))
        if czas_wyjazdu:
            cursor.execute('UPDATE wycieczka SET czas_wyjazdu = ? WHERE id = ?', (czas_wyjazdu, str(id)))
        if szacowany_czas_ogarniania_rano:
            cursor.execute('UPDATE wycieczka SET szacowany_czas_ogarniania_rano = ? WHERE id = ?', (szacowany_czas_ogarniania_rano, str(id)))
        if calosciowa_taktyka_dnia is not None:
            cursor.execute('UPDATE wycieczka SET calosciowa_taktyka_dnia = ? WHERE id = ?', (calosciowa_taktyka_dnia, str(id)))
        conn.commit()
    przelicz_i_zsynchronizuj_wycieczke(id, force_wyjazd_str=czas_wyjazdu)
    return {"success": True, "action": "edytuj_wycieczke", "message": "Pomyślnie zaktualizowano parametry wycieczki."}

def dodaj_krok_wycieczki(id_wycieczki, nazwa_z_bazy, okienko_zwiedzania="12:00 - 13:30", podsumowanie_taktyki="", wzgledem_kroku=None, relacja="przed"):
    ok, err_msg = sprawdz_ryzyka_audhd_dla_kroku(id_wycieczki, nazwa_z_bazy, okienko_zwiedzania)
    if not ok:
        return {"success": False, "blocked_by_guardrail": True, "error": err_msg}

    miejsce = szukaj_miejsca_w_bazie(nazwa_z_bazy)
    wsp = miejsce.get("wspolrzedne", f"{SKLEP_LAT}, {SKLEP_LON}") if miejsce else f"{SKLEP_LAT}, {SKLEP_LON}"
    opis = miejsce.get("opis", "") if miejsce else ""
    nr_miejsca = miejsce.get("numer_miejsca") if miejsce else None

    with get_db() as conn:
        cursor = conn.cursor()
        nowy_id = _wstaw_krok_do_wycieczki(
            cursor=cursor,
            id_wycieczki=id_wycieczki,
            nazwa=nazwa_z_bazy,
            wspolrzedne=wsp,
            okienko=okienko_zwiedzania,
            opis=opis,
            numer_miejsca=nr_miejsca,
            podsumowanie_taktyki=podsumowanie_taktyki,
            pozycja="koniec"
        )

        # AUTOMATYCZNE WYKRYWANIE OBIADU / LUNCHBOXA
        nazwa_l = nazwa_z_bazy.lower()
        if any(w in nazwa_l for w in ["obiad", "tawerna", "lunch", "restauracja", "jedzenie", "lunchbox"]):
            rodzaj = "lunchbox_duzy" if "duży" in nazwa_l else ("lunchbox_maly" if "mały" in nazwa_l or "lunchbox" in nazwa_l else "obiad")
            miejsce_pos = "z domu (lunchbox)" if "lunchbox" in rodzaj else "restauracja"
            godz_pos = okienko_zwiedzania.split("-")[0].strip() if "-" in okienko_zwiedzania else "13:00"
            cursor.execute('''
                INSERT INTO posilki_kroku (id_kroku, rodzaj_posilku, miejsce, sugerowana_godzina, opis)
                VALUES (?, ?, ?, ?, ?)
            ''', (nowy_id, rodzaj, miejsce_pos, godz_pos, nazwa_z_bazy))

        conn.commit()

    if wzgledem_kroku is not None:
        przenies_krok_wycieczki(id_wycieczki, krok_identyfikator=nowy_id, wzgledem_kroku=wzgledem_kroku, relacja=relacja)
    else:
        przelicz_i_zsynchronizuj_wycieczke(id_wycieczki)

    return {"success": True, "action": "dodaj_krok_wycieczki", "id_kroku": nowy_id, "message": f"Dodano punkt {nazwa_z_bazy} (#{nr_miejsca})."}

def edytuj_krok_wycieczki(id_wycieczki, krok_wycieczki, okienko_zwiedzania):
    with get_db() as conn:
        cursor = conn.cursor()
        k_info = znajdz_id_kroku_w_db(cursor, id_wycieczki, krok_wycieczki)
        if not k_info:
            return {"success": False, "error": f"Nie znaleziono kroku: {krok_wycieczki}"}
        k_id, _ = k_info
        cursor.execute('UPDATE krok_wycieczki SET okienko_zwiedzania = ? WHERE id = ?', (okienko_zwiedzania, k_id))
        conn.commit()

    przelicz_i_zsynchronizuj_wycieczke(id_wycieczki)
    return {"success": True, "action": "edytuj_krok_wycieczki", "message": f"Zaktualizowano okienko dla kroku {krok_wycieczki}."}
    
def pobierz_pelny_plan_wycieczki(id_wycieczki):
    """Zwraca precyzyjną listę kroków z bazy z ID, godzinami i posiłkami."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, krok_wycieczki, numer_miejsca, nazwa, okienko_zwiedzania, opis
            FROM krok_wycieczki 
            WHERE id_wycieczki = ? 
            ORDER BY CAST(krok_wycieczki AS INTEGER) ASC, id ASC
        ''', (str(id_wycieczki),))
        rows = cursor.fetchall()
        
        plan = []
        for r in rows:
            cursor.execute('SELECT id, rodzaj_posilku, sugerowana_godzina, opis FROM posilki_kroku WHERE id_kroku = ?', (r[0],))
            posilki = cursor.fetchall()
            plan.append({
                "id_kroku": r[0],
                "pozycja_kroku": r[1],
                "numer_miejsca": r[2],
                "nazwa": r[3],
                "okienko": r[4],
                "opis": r[5],
                "posilki": [{"id": p[0], "typ": p[1], "godzina": p[2], "opis": p[3]} for p in posilki]
            })
    return {"id_wycieczki": str(id_wycieczki), "kroki": plan}


def przenies_krok_wycieczki(id_wycieczki, krok_identyfikator, docelowa_pozycja=None, wzgledem_kroku=None, relacja="przed"):
    """
    Przenosi krok na podany indeks lub bezpośrednio przed/po innym kroku, 
    a następnie przelicza bufory czasowe.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        k_info = znajdz_id_kroku_w_db(cursor, id_wycieczki, krok_identyfikator)
        if not k_info:
            return {"success": False, "error": f"Nie znaleziono kroku do przeniesienia: {krok_identyfikator}"}
        krok_id, krok_nazwa = k_info

        cursor.execute('''
            SELECT id FROM krok_wycieczki 
            WHERE id_wycieczki = ? 
            ORDER BY CAST(krok_wycieczki AS INTEGER) ASC, id ASC
        ''', (str(id_wycieczki),))
        kroki_ids = [r[0] for r in cursor.fetchall()]

        if krok_id not in kroki_ids:
            return {"success": False, "error": "Błąd spójności bazy."}

        kroki_ids.remove(krok_id)

        if wzgledem_kroku is not None:
            ref_info = znajdz_id_kroku_w_db(cursor, id_wycieczki, wzgledem_kroku)
            if not ref_info:
                return {"success": False, "error": f"Nie znaleziono punktu odniesienia: {wzgledem_kroku}"}
            ref_id, _ = ref_info
            idx_ref = kroki_ids.index(ref_id)
            target_idx = idx_ref if relacja == "przed" else idx_ref + 1
        elif docelowa_pozycja is not None:
            target_idx = max(0, min(int(docelowa_pozycja), len(kroki_ids)))
        else:
            return {"success": False, "error": "Podaj docelową pozycję lub punkt odniesienia."}

        kroki_ids.insert(target_idx, krok_id)

        for new_pos, k_id in enumerate(kroki_ids):
            cursor.execute('UPDATE krok_wycieczki SET krok_wycieczki = ? WHERE id = ?', (new_pos, k_id))
        conn.commit()

    przelicz_i_zsynchronizuj_wycieczke(id_wycieczki)
    return {
        "success": True, 
        "action": "przenies_krok_wycieczki", 
        "message": f"Krok '{krok_nazwa}' przestawiony na pozycję {target_idx}. Czasy przejazdów i bufory zostały przeliczone automatycznie."
    }


def zamien_kroki_miejscami(id_wycieczki, krok_a, krok_b):
    """Zamienia kolejnością dwa punkty i automatycznie wyrównuje czasy."""
    with get_db() as conn:
        cursor = conn.cursor()
        k_a = znajdz_id_kroku_w_db(cursor, id_wycieczki, krok_a)
        k_b = znajdz_id_kroku_w_db(cursor, id_wycieczki, krok_b)
        if not k_a or not k_b:
            return {"success": False, "error": f"Nie znaleziono jednego z kroków ({krok_a} lub {krok_b})."}
        
        id_a, _ = k_a
        id_b, _ = k_b

        cursor.execute('SELECT krok_wycieczki FROM krok_wycieczki WHERE id = ?', (id_a,))
        pos_a = cursor.fetchone()[0]
        cursor.execute('SELECT krok_wycieczki FROM krok_wycieczki WHERE id = ?', (id_b,))
        pos_b = cursor.fetchone()[0]

        cursor.execute('UPDATE krok_wycieczki SET krok_wycieczki = ? WHERE id = ?', (pos_b, id_a))
        cursor.execute('UPDATE krok_wycieczki SET krok_wycieczki = ? WHERE id = ?', (pos_a, id_b))
        conn.commit()

    przelicz_i_zsynchronizuj_wycieczke(id_wycieczki)
    return {"success": True, "action": "zamien_kroki_miejscami", "message": f"Zamieniono miejscami kroki {krok_a} oraz {krok_b}."}

def usun_krok_wycieczki(id_wycieczki, krok_wycieczki, pomin_ostrzezenie_posilku=False):
    with get_db() as conn:
        cursor = conn.cursor()
        k_info = znajdz_id_kroku_w_db(cursor, id_wycieczki, krok_wycieczki)
        if not k_info:
            return {"success": False, "error": f"Nie znaleziono kroku: {krok_wycieczki}"}
        k_id, k_nazwa = k_info

        # Sprawdzenie, czy krok ma przypisany posiłek kotwiczący
        cursor.execute('SELECT rodzaj_posilku, opis FROM posilki_kroku WHERE id_kroku = ?', (k_id,))
        powiazane_posilki = cursor.fetchall()
        
        posilki_glowne = [p[0] for p in powiazane_posilki if str(p[0]).lower() in ['obiad', 'lunch', 'lunchbox_duzy', 'sniadanie', 'śniadanie', 'kolacja']]

        if posilki_glowne and not pomin_ostrzezenie_posilku:
            nazwy_pos = ", ".join(posilki_glowne)
            return {
                "success": False,
                "blocked_by_guardrail": True,
                "error": (
                    f"⛔ ZATRZYMANO (AuDHD Hangry Guard): Krok '{k_nazwa}' ma przypisany kluczowy posiłek ({nazwy_pos}). "
                    f"Usunięcie go spowoduje wielogodzinną przerwę w jedzeniu, co wywoła silny meltdown u dzieci. "
                    f"Najpierw zaplanuj alternatywny posiłek (obiad w tawernie lub lunchbox z safe food), "
                    f"albo potwierdź usunięcie z parametrem pomin_ostrzezenie_posilku=True."
                )
            }

        _usun_krok_z_wycieczki(cursor, k_id, id_wycieczki)
        conn.commit()

    przelicz_i_zsynchronizuj_wycieczke(id_wycieczki)
    return {"success": True, "action": "usun_krok_wycieczki", "message": f"Pomyślnie usunięto krok: {k_nazwa}."}

def zarzadzaj_posilkiem_kroku(id_wycieczki, id_kroku, rodzaj_posilku, miejsce="restauracja", sugerowana_godzina="12:30", opis=""):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO posilki_kroku (id_kroku, rodzaj_posilku, miejsce, sugerowana_godzina, opis)
            VALUES (?, ?, ?, ?, ?)
        ''', (int(id_kroku), rodzaj_posilku, miejsce, sugerowana_godzina, opis))
        conn.commit()
    return {"success": True, "action": "zarzadzaj_posilkiem_kroku", "message": f"Dodano posiłek {rodzaj_posilku}."}

def usun_posilek(id_posilku):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM posilki_kroku WHERE id = ?', (int(id_posilku),))
        conn.commit()
    return {"success": True, "action": "usun_posilek", "message": "Pomyślnie usunięto posiłek."}

def duplikuj_wycieczke(id_zrodlowe):
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM wycieczka WHERE id = ?", (str(id_zrodlowe),))
        trip = cursor.fetchone()
        if not trip:
            return None
            
        cursor.execute("PRAGMA table_info(wycieczka)")
        cols_w = [c[1] for c in cursor.fetchall()]
        trip_dict = dict(zip(cols_w, trip))

        cursor.execute("SELECT id FROM wycieczka")
        wszystkie_id = [int(r[0]) for r in cursor.fetchall() if str(r[0]).isdigit()]
        nowe_id = str(max(wszystkie_id) + 1 if wszystkie_id else 2)

        stary_tytul = trip_dict.get('tytul_wycieczki', 'Wycieczka')
        
        if ":" in stary_tytul:
            czesci = stary_tytul.split(":", 1)
            nowy_tytul = f"{czesci[0].strip()} - kopia: {czesci[1].strip()}"
        else:
            nowy_tytul = f"{stary_tytul.strip()} - kopia"

        cursor.execute('''
            INSERT INTO wycieczka (
                id, tytul_wycieczki, calosciowy_opis_wycieczki, calosciowa_taktyka_dnia,
                calkowity_czas_wycieczki_godziny, szacowana_godzina_powrotu, pobudka, czas_wyjazdu,
                planowana_data, czas_powrotu_do_domku, szacowany_czas_ogarniania_rano, odbyta
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        ''', (
            nowe_id, nowy_tytul, trip_dict.get('calosciowy_opis_wycieczki'), trip_dict.get('calosciowa_taktyka_dnia'),
            trip_dict.get('calkowity_czas_wycieczki_godziny'), trip_dict.get('szacowana_godzina_powrotu'),
            trip_dict.get('pobudka'), trip_dict.get('czas_wyjazdu'), trip_dict.get('planowana_data'),
            trip_dict.get('czas_powrotu_do_domku'), trip_dict.get('szacowany_czas_ogarniania_rano', '0.5h')
        ))

        cursor.execute("SELECT * FROM krok_wycieczki WHERE id_wycieczki = ? ORDER BY CAST(krok_wycieczki AS INTEGER) ASC, id ASC", (str(id_zrodlowe),))
        kroki = cursor.fetchall()
        cursor.execute("PRAGMA table_info(krok_wycieczki)")
        cols_k = [c[1] for c in cursor.fetchall()]

        stare_do_nowe_id_krokow = {}

        for k in kroki:
            k_dict = dict(zip(cols_k, k))
            stary_krok_id = k_dict['id']
            
            cursor.execute('''
                INSERT INTO krok_wycieczki (
                    id_wycieczki, krok_wycieczki, numer_miejsca, nazwa, wspolrzedne, okienko_zwiedzania,
                    godzina_ewakuacji, czerwona_strefa_ostrzezenie, strefa_luzu_i_regeneracji,
                    podsumowanie_taktyki, potencjal_meltdownu, strategie_meltdown, opis
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                nowe_id, k_dict.get('krok_wycieczki'), k_dict.get('numer_miejsca'), k_dict.get('nazwa'), k_dict.get('wspolrzedne'),
                k_dict.get('okienko_zwiedzania'), k_dict.get('godzina_ewakuacji'), k_dict.get('czerwona_strefa_ostrzezenie'),
                k_dict.get('strefa_luzu_i_regeneracji'), k_dict.get('podsumowanie_taktyki'),
                k_dict.get('potencjal_meltdownu'), k_dict.get('strategie_meltdown'), k_dict.get('opis')
            ))
            nowy_krok_id = cursor.lastrowid
            stare_do_nowe_id_krokow[stary_krok_id] = nowy_krok_id

            cursor.execute("SELECT rodzaj_posilku, miejsce, sugerowana_godzina, opis FROM posilki_kroku WHERE id_kroku = ?", (stary_krok_id,))
            for p in cursor.fetchall():
                cursor.execute('''
                    INSERT INTO posilki_kroku (id_kroku, rodzaj_posilku, miejsce, sugerowana_godzina, opis)
                    VALUES (?, ?, ?, ?, ?)
                ''', (nowy_krok_id, p[0], p[1], p[2], p[3]))

        cursor.execute("SELECT id_kroku, nazwa_produktu, ilosc FROM zakupy WHERE id_wycieczki = ?", (str(id_zrodlowe),))
        for z in cursor.fetchall():
            stary_id_k = z[0]
            nowy_id_k = stare_do_nowe_id_krokow.get(stary_id_k) if (stary_id_k and stary_id_k in stare_do_nowe_id_krokow) else None
            cursor.execute('''
                INSERT INTO zakupy (id_wycieczki, id_kroku, nazwa_produktu, ilosc, kupione)
                VALUES (?, ?, ?, ?, 0)
            ''', (nowe_id, nowy_id_k, z[1], z[2]))

        for stary_z, nowy_z in stare_do_nowe_id_krokow.items():
            for stary_do, nowy_do in stare_do_nowe_id_krokow.items():
                cursor.execute("SELECT czas_przejazdu, szacowany_czas_postoju FROM czasy_dojazdu WHERE id_kroku_z = ? AND id_kroku_do = ?", (stary_z, stary_do))
                dojazd = cursor.fetchone()
                if dojazd:
                    cursor.execute('''
                        INSERT INTO czasy_dojazdu (id_kroku_z, id_kroku_do, czas_przejazdu, szacowany_czas_postoju)
                        VALUES (?, ?, ?, ?)
                    ''', (nowy_z, nowy_do, dojazd[0], dojazd[1]))

        cursor.execute("SELECT id_miejsca, tytul, zawartosc, typ_notatki FROM notatki WHERE id_wycieczki = ?", (str(id_zrodlowe),))
        for n in cursor.fetchall():
            cursor.execute('''
                INSERT INTO notatki (id_wycieczki, id_miejsca, tytul, zawartosc, typ_notatki)
                VALUES (?, ?, ?, ?, ?)
            ''', (nowe_id, n[0], n[1], n[2], n[3]))

        conn.commit()

    przelicz_i_zsynchronizuj_wycieczke(nowe_id)
    return nowe_id

def usun_wycieczke(id_wycieczki):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tytul_wycieczki FROM wycieczka WHERE id = ?", (str(id_wycieczki),))
        trip_row = cursor.fetchone()
        if not trip_row:
            return {"success": False, "action": "usun_wycieczke", "error": f"Nie znaleziono wycieczki #{id_wycieczki}."}
        
        tytul = trip_row[0]
        
        cursor.execute("SELECT id FROM krok_wycieczki WHERE id_wycieczki = ?", (str(id_wycieczki),))
        krok_ids = [r[0] for r in cursor.fetchall()]
        
        if krok_ids:
            ph = ','.join(['?'] * len(krok_ids))
            cursor.execute(f"DELETE FROM posilki_kroku WHERE id_kroku IN ({ph})", krok_ids)
            cursor.execute(f"DELETE FROM czasy_dojazdu WHERE id_kroku_z IN ({ph}) OR id_kroku_do IN ({ph})", krok_ids + krok_ids)
            
        cursor.execute("DELETE FROM zakupy WHERE id_wycieczki = ?", (str(id_wycieczki),))
        cursor.execute("DELETE FROM notatki WHERE id_wycieczki = ?", (str(id_wycieczki),))
        cursor.execute("DELETE FROM krok_wycieczki WHERE id_wycieczki = ?", (str(id_wycieczki),))
        cursor.execute("DELETE FROM wycieczka WHERE id = ?", (str(id_wycieczki),))
        
        cursor.execute("SELECT aktualne_id_wycieczki FROM aktywna_wycieczka WHERE id = 1")
        akt_res = cursor.fetchone()
        if akt_res and str(akt_res[0]) == str(id_wycieczki):
            cursor.execute("SELECT id FROM wycieczka ORDER BY CAST(id AS INTEGER) ASC LIMIT 1")
            pierwsza_w = cursor.fetchone()
            nowe_akt_id = str(pierwsza_w[0]) if pierwsza_w else "1"
            cursor.execute("UPDATE aktywna_wycieczka SET aktualne_id_wycieczki = ? WHERE id = 1", (nowe_akt_id,))

        conn.commit()

    return {"success": True, "action": "usun_wycieczke", "message": f"Pomyślnie usunięto wycieczkę #{id_wycieczki}: '{tytul}'."}

# --- DEKLARACJE FUNKCJI NARZĘDZIOWYCH DLA MODELU AI ---
tools_definitions = [
    types.FunctionDeclaration(
        name="szukaj_miejsca_w_bazie",
        description="Wyszukuje miejsce w lokalnej bazie danych CretAi. Zwraca dane, współrzędne i analizę AuDHD.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "nazwa_zapytania": types.Schema(type=types.Type.STRING, description="Nazwa miejsca lub numer"),
            },
            required=["nazwa_zapytania"]
        ),
    ),
    types.FunctionDeclaration(
        name="utworz_nowe_miejsce",
        description="Tworzy i zapisuje nowe miejsce w bazie.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "nazwa": types.Schema(type=types.Type.STRING, description="Nazwa miejsca"),
                "typ": types.Schema(type=types.Type.STRING, description="Plaża, Must have, Nice to have, Activity, Shop, Other"),
                "wspolrzedne": types.Schema(type=types.Type.STRING, description="Koordynaty np. '35.5138, 24.0180'"),
                "orientacyjny_czas": types.Schema(type=types.Type.STRING, description="np. '1.5h'"),
                "koszt": types.Schema(type=types.Type.STRING, description="Koszt 2+2"),
                "godziny_otwarcia": types.Schema(type=types.Type.STRING, description="Godziny otwarcia"),
                "konieczna_akcja": types.Schema(type=types.Type.STRING, description="Akcja wymagana"),
                "trudnosc_adhd": types.Schema(type=types.Type.STRING, description="'Niski', 'Średni', 'Wysoki'"),
                "ochrona_slonce": types.Schema(type=types.Type.STRING, description="Ochrona przed słońcem"),
                "potencjal_meltdownu": types.Schema(type=types.Type.STRING, description="'Niski', 'Średni', 'Wysoki'"),
                "strategie_meltdown": types.Schema(type=types.Type.STRING, description="Taktyka wyciszenia i cienia"),
                "opis": types.Schema(type=types.Type.STRING, description="Krótki opis"),
                "zadania_dla_dzieci": types.Schema(type=types.Type.STRING, description="Misje dla dzieci rozdzielone nową linią"),
            },
            required=["nazwa", "typ", "wspolrzedne", "ochrona_slonce", "potencjal_meltdownu", "strategie_meltdown", "opis", "zadania_dla_dzieci"]
        ),
    ),
    types.FunctionDeclaration(
        name="utworz_nowa_wycieczke",
        description="Tworzy nową wycieczkę ze szkieletem bazy w Stavros.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "tytul_wycieczki": types.Schema(type=types.Type.STRING, description="Tytuł trasy"),
                "planowana_data": types.Schema(type=types.Type.STRING, description="RRRR-MM-DD"),
                "pobudka": types.Schema(type=types.Type.STRING, description="Godzina pobudki np. '06:00'"),
                "czas_wyjazdu": types.Schema(type=types.Type.STRING, description="Godzina wyjazdu np. '06:30'"),
                "opis": types.Schema(type=types.Type.STRING, description="Cel trasy"),
                "taktyka_dnia": types.Schema(type=types.Type.STRING, description="Całościowa taktyka dnia (zarządzanie przebodźcowaniem, sjesta, strefy cienia)")
            },
            required=["tytul_wycieczki"]
        ),
    ),
    types.FunctionDeclaration(
        name="sprawdz_pogode",
        description="Pobiera prognozę pogody dla podanych współrzędnych i daty.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "wspolrzedne": types.Schema(type=types.Type.STRING, description="Koordynaty np. '35.2980, 25.1631'"),
                "planowana_data": types.Schema(type=types.Type.STRING, description="RRRR-MM-DD"),
                "okienko_czasowe": types.Schema(type=types.Type.STRING, description="Okienko np. '12:00 - 14:00'"),
            },
            required=["wspolrzedne", "planowana_data"]
        ),
    ),
    types.FunctionDeclaration(
        name="dodaj_sklep_przy_domku",
        description="Dodaje sklep w Stavros jako krok wycieczki.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                "pozycja": types.Schema(type=types.Type.STRING, description="'start' lub 'koniec'"),
            },
            required=["id_wycieczki"]
        ),
    ),
    types.FunctionDeclaration(
        name="usun_sklep_z_wycieczki",
        description="Usuwa sklep z trasy wycieczki.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                "pozycja": types.Schema(type=types.Type.STRING, description="'start' lub 'koniec'"),
            },
            required=["id_wycieczki"]
        ),
    ),
    types.FunctionDeclaration(
        name="dodaj_rynek_w_chanii",
        description="Dodaje targ miejski (Laiki) w Chanii do trasy.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                "pozycja": types.Schema(type=types.Type.STRING, description="'start' lub 'koniec'"),
            },
            required=["id_wycieczki"]
        ),
    ),
    types.FunctionDeclaration(
        name="usun_rynek_z_wycieczki",
        description="Usuwa targ miejski (Laiki) z trasy.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                "pozycja": types.Schema(type=types.Type.STRING, description="'start' lub 'koniec'"),
            },
            required=["id_wycieczki"]
        ),
    ),
    types.FunctionDeclaration(
        name="dodaj_notatke",
        description="Dodaje notatkę do wycieczki lub miejsca.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "zawartosc": types.Schema(type=types.Type.STRING, description="Treść"),
                "typ_notatki": types.Schema(type=types.Type.STRING, description="'text', 'link' lub 'list'"),
                "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                "id_miejsca": types.Schema(type=types.Type.STRING, description="Numer miejsca"),
                "tytul": types.Schema(type=types.Type.STRING, description="Tytuł"),
            },
            required=["zawartosc"]
        ),
    ),
    types.FunctionDeclaration(
        name="edytuj_wycieczke",
        description="Aktualizuje parametry wycieczki. Służy do automatycznego odświeżania celu wycieczki oraz całościowej taktyki dnia po każdej modyfikacji planu kroków.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                "tytul_wycieczki": types.Schema(type=types.Type.STRING, description="Nowy lub zaktualizowany tytuł"),
                "calosciowy_opis_wycieczki": types.Schema(type=types.Type.STRING, description="Zaktualizowany cel całej wycieczki, podsumowujący nowy przebieg dnia"),
                "calosciowa_taktyka_dnia": types.Schema(type=types.Type.STRING, description="Zaktualizowana taktyka całościowa dnia: bezpieczne strefy cienia w 11:30–15:30, ewakuacja, Safe Foods, regeneracja AuDHD"),
                "planowana_data": types.Schema(type=types.Type.STRING, description="RRRR-MM-DD"),
                "czas_wyjazdu": types.Schema(type=types.Type.STRING, description="Godzina np. '06:30'"),
                "szacowany_czas_ogarniania_rano": types.Schema(type=types.Type.STRING, description="np. '0.5h' lub '45m'"),
            },
            required=["id"]
        ),
    ),
    types.FunctionDeclaration(
        name="usun_wycieczke",
        description="Usuwa wycieczkę z bazy danych.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
            },
            required=["id_wycieczki"]
        ),
    ),
    types.FunctionDeclaration(
        name="dodaj_krok_wycieczki",
        description="Dodaje miejsce z bazy jako krok wycieczki, opcjonalnie bezpośrednio przed lub po wskazanym innym kroku.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                "nazwa_z_bazy": types.Schema(type=types.Type.STRING, description="Nazwa miejsca"),
                "okienko_zwiedzania": types.Schema(type=types.Type.STRING, description="Okienko np. '13:00 - 14:30'"),
                "podsumowanie_taktyki": types.Schema(type=types.Type.STRING, description="Taktyka"),
                "wzgledem_kroku": types.Schema(type=types.Type.STRING, description="Nazwa lub ID kroku referencyjnego, jeśli chcesz wstawić przed/po nim"),
                "relacja": types.Schema(type=types.Type.STRING, description="'przed' lub 'po' (domyślnie 'przed')"),
            },
            required=["id_wycieczki", "nazwa_z_bazy"]
        ),
    ),
    types.FunctionDeclaration(
        name="pobierz_pelny_plan_wycieczki",
        description="Pobiera pełną listę kroków wycieczki po kolei z ich ID bazy, kolejnością, godzinami i posiłkami.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
            },
            required=["id_wycieczki"]
        ),
    ),
    types.FunctionDeclaration(
        name="przenies_krok_wycieczki",
        description="Przenosi istniejący krok przed lub po innym kroku (albo na podany indeks) i automatycznie przelicza godziny dojazdów i buforów.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                "krok_identyfikator": types.Schema(type=types.Type.STRING, description="ID lub nazwa kroku do przestawienia"),
                "wzgledem_kroku": types.Schema(type=types.Type.STRING, description="Nazwa lub ID kroku punktu odniesienia"),
                "relacja": types.Schema(type=types.Type.STRING, description="'przed' lub 'po'"),
                "docelowa_pozycja": types.Schema(type=types.Type.INTEGER, description="Opcjonalny indeks liczbowy"),
            },
            required=["id_wycieczki", "krok_identyfikator"]
        ),
    ),
    types.FunctionDeclaration(
        name="zamien_kroki_miejscami",
        description="Zamienia kolejnością dwa kroki w wycieczce i przelicza czasy.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                "krok_a": types.Schema(type=types.Type.STRING, description="ID lub nazwa pierwszego kroku"),
                "krok_b": types.Schema(type=types.Type.STRING, description="ID lub nazwa drugiego kroku"),
            },
            required=["id_wycieczki", "krok_a", "krok_b"]
        ),
    ),
    types.FunctionDeclaration(
        name="edytuj_krok_wycieczki",
        description="Edytuje okienko czasowe wybranego kroku.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                "krok_wycieczki": types.Schema(type=types.Type.STRING, description="ID lub nazwa kroku"),
                "okienko_zwiedzania": types.Schema(type=types.Type.STRING, description="Okienko np. '10:00 - 13:00'"),
            },
            required=["id_wycieczki", "krok_wycieczki"]
        ),
    ),
    types.FunctionDeclaration(
        name="usun_krok_wycieczki",
        description="Usuwa krok z trasy. Posiada strażnika posiłków – jeśli krok zawierał obiad/posiłek kotwiczący, funkcja zwróci błąd z ostrzeżeniem AuDHD.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                "krok_wycieczki": types.Schema(type=types.Type.STRING, description="ID lub nazwa kroku"),
                "pomin_ostrzezenie_posilku": types.Schema(type=types.Type.BOOLEAN, description="Ustaw True TYLKO wtedy, gdy rodzic wyraźnie zażądał usunięcia mimo utraty posiłku lub gdy przeniesiono już obiad gdzie indziej"),
            },
            required=["id_wycieczki", "krok_wycieczki"]
        ),
    ),
    types.FunctionDeclaration(
        name="zarzadzaj_posilkiem_kroku",
        description="Dodaje posiłek stabilizujący (śniadanie, obiad, kolacja, lunchbox_maly, lunchbox_duzy).",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                "id_kroku": types.Schema(type=types.Type.STRING, description="ID kroku wycieczki"),
                "rodzaj_posilku": types.Schema(type=types.Type.STRING, description="'śniadanie', 'obiad', 'kolacja', 'lunchbox_maly', 'lunchbox_duzy'"),
                "miejsce": types.Schema(type=types.Type.STRING, description="'w domku', 'z domu (lunchbox)', 'restauracja'"),
                "sugerowana_godzina": types.Schema(type=types.Type.STRING, description="Godzina posiłku"),
                "opis": types.Schema(type=types.Type.STRING, description="Opis (Safe Foods)")
            },
            required=["id_wycieczki", "id_kroku", "rodzaj_posilku"]
        ),
    ),
    types.FunctionDeclaration(
        name="usun_posilek",
        description="Usuwa posiłek z bazy po jego ID.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id_posilku": types.Schema(type=types.Type.STRING, description="ID posiłku"),
            },
            required=["id_posilku"]
        ),
    ),
    types.FunctionDeclaration(
        name="dodaj_produkt_zakupow",
        description="Dodaje produkt do listy zakupów.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                "nazwa_produktu": types.Schema(type=types.Type.STRING, description="Nazwa produktu"),
                "id_kroku": types.Schema(type=types.Type.STRING, description="ID kroku sklepu"),
                "ilosc": types.Schema(type=types.Type.STRING, description="Ilość"),
            },
            required=["id_wycieczki", "nazwa_produktu"]
        ),
    ),
    types.FunctionDeclaration(
        name="dodaj_wiele_produktow_zakupow",
        description="Dodaje listę produktów do zakupów.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                "produkty": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "nazwa": types.Schema(type=types.Type.STRING, description="Nazwa produktu"),
                            "ilosc": types.Schema(type=types.Type.STRING, description="Ilość")
                        },
                        required=["nazwa"]
                    ),
                    description="Lista składników"
                ),
                "id_kroku": types.Schema(type=types.Type.STRING, description="ID kroku sklepu")
            },
            required=["id_wycieczki", "produkty"]
        ),
    )
]

NARZEDZIA_DISPATCHER = {
    "szukaj_miejsca_w_bazie": lambda args: szukaj_miejsca_w_bazie(**args) or {"error": "Brak miejsca w bazie."},
    "utworz_nowe_miejsce": lambda args: utworz_nowe_miejsce(**args),
    "utworz_nowa_wycieczke": lambda args: utworz_nowa_wycieczke(**args),
    "sprawdz_pogode": lambda args: pobierz_szczegoly_pogody_dla_godziny(**args) or {"error": "Brak danych pogodowych."},
    "dodaj_sklep_przy_domku": lambda args: dodaj_sklep_przy_domku_do_wycieczki(id_wycieczki=args.get("id_wycieczki"), pozycja=args.get("pozycja", "koniec")),
    "usun_sklep_z_wycieczki": lambda args: usun_sklep_z_wycieczki_handler(args.get("id_wycieczki"), pozycja=args.get("pozycja")),
    "dodaj_rynek_w_chanii": lambda args: dodaj_rynek_w_chanii_do_wycieczki(id_wycieczki=args.get("id_wycieczki"), pozycja=args.get("pozycja", "start")),
    "usun_rynek_z_wycieczki": lambda args: usun_rynek_z_wycieczki_handler(args.get("id_wycieczki"), pozycja=args.get("pozycja")),
    "dodaj_notatke": lambda args: dodaj_notatke(**args),
    "edytuj_wycieczke": lambda args: edytuj_wycieczke(**args),
    "usun_wycieczke": lambda args: usun_wycieczke(args.get("id_wycieczki")),
    "dodaj_krok_wycieczki": lambda args: dodaj_krok_wycieczki(**args),
    "edytuj_krok_wycieczki": lambda args: edytuj_krok_wycieczki(**args),
    "usun_krok_wycieczki": lambda args: usun_krok_wycieczki(**args),
    "pobierz_pelny_plan_wycieczki": lambda args: pobierz_pelny_plan_wycieczki(**args),
    "przenies_krok_wycieczki": lambda args: przenies_krok_wycieczki(**args),
    "zamien_kroki_miejscami": lambda args: zamien_kroki_miejscami(**args),
    "zarzadzaj_posilkiem_kroku": lambda args: zarzadzaj_posilkiem_kroku(**args),
    "usun_posilek": lambda args: usun_posilek(**args),
    "dodaj_produkt_zakupow": lambda args: dodaj_produkt_zakupow(**args),
    "dodaj_wiele_produktow_zakupow": lambda args: dodaj_wiele_produktow_zakupow(**args),
}

def wykonaj_narzedzie_bazy(call_name, args):
    handler = NARZEDZIA_DISPATCHER.get(call_name)
    if not handler:
        return {"success": False, "error": f"Nierozpoznane narzędzie: {call_name}"}
    res = handler(args)
    return res if isinstance(res, dict) else {"success": True, "result": str(res)}

# --- ZOPTYMALIZOWANY KONTEKST ---
def wczytaj_kontekst_zewnetrzny(id_wycieczki):
    with get_db() as conn:
        wyc_df = pd.read_sql(
            'SELECT id, tytul_wycieczki, planowana_data, czas_wyjazdu, szacowana_godzina_powrotu, pobudka, calosciowa_taktyka_dnia FROM wycieczka WHERE id = ?', 
            conn, params=(str(id_wycieczki),)
        )
        query = '''
            SELECT 
                k.krok_wycieczki, 
                k.id, 
                k.nazwa, 
                k.okienko_zwiedzania,
                GROUP_CONCAT(
                    p.rodzaj_posilku || ' (' || COALESCE(p.miejsce, '') || ', ' || COALESCE(p.sugerowana_godzina, '') || 
                    CASE WHEN p.opis IS NOT NULL AND p.opis != '' THEN ': ' || p.opis ELSE '' END || ')',
                    ' | '
                ) AS posilki
            FROM krok_wycieczki k
            LEFT JOIN posilki_kroku p ON k.id = p.id_kroku
            WHERE k.id_wycieczki = ?
            GROUP BY k.id
            ORDER BY CAST(k.krok_wycieczki AS INTEGER) ASC
        '''
        kroki_df = pd.read_sql(query, conn, params=(str(id_wycieczki),))
    
    opis = ""
    if not wyc_df.empty:
        w = wyc_df.iloc[0]
        opis += f"Aktywna wycieczka #{w['id']}: {w.get('tytul_wycieczki')} (Pobudka: {w.get('pobudka')}, Wyjazd: {w.get('czas_wyjazdu')}, Powrót: {w.get('szacowana_godzina_powrotu')}).\n"
        if pd.notna(w.get('calosciowa_taktyka_dnia')) and str(w.get('calosciowa_taktyka_dnia')).strip():
            opis += f"Aktualna taktyka dnia: {w.get('calosciowa_taktyka_dnia')}\n"
    
    if not kroki_df.empty:
        opis += "Kroki i zaplanowane posiłki w planie:\n"
        for _, r in kroki_df.iterrows():
            posilki_str = f" [Posiłki: {r['posilki']}]" if pd.notna(r['posilki']) and r['posilki'] else " [Posiłki: brak]"
            opis += f"- #{r['krok_wycieczki']}: {r['nazwa']} ({r['okienko_zwiedzania']}){posilki_str}\n"
    
    return opis

def sprobuj_wykonac_komende_lokalnie(prompt, id_wycieczki):
    p = prompt.strip().lower()
    if p.startswith("+") or p.startswith("kup ") or p.startswith("dodaj do zakupów:"):
        czysty = re.sub(r'^(\+|kup\s+|dodaj do zakupów:\s*)', '', prompt, flags=re.IGNORECASE).strip()
        if czysty:
            dodaj_produkt_zakupow(id_wycieczki=id_wycieczki, nazwa_produktu=czysty)
            return f"✅ Dodano do listy zakupów: **{czysty}**"
    return None
    
# --- GŁÓWNY WIDOK CZATU AI ---
@st.cache_resource
def get_gemini_client(api_key):
    return genai.Client(api_key=api_key)

# --- GŁÓWNY WIDOK CZATU AI ---
def renderuj_globalny_czat_ai(uzytkownik, id_wycieczki=None, inline=False):
    akt_wyc_id = str(id_wycieczki) if id_wycieczki else pobierz_aktywna_wycieczke_id()
    
    if not inline:
        st.markdown('<div class="floating-ai-container">', unsafe_allow_html=True)
    with st.expander(f"💬 Asystent AI ({uzytkownik})", expanded=False):
        
        chat_historia_z_db = pobierz_historie_czatu_z_db(uzytkownik)
        
        col_h1, col_h2 = st.columns([5, 1])
        with col_h1:
            st.markdown(f"<div style='font-size: 8pt; font-weight: 800; padding-top: 6px;'>🧠 AuDHD • Wycieczka #{akt_wyc_id}</div>", unsafe_allow_html=True)
        with col_h2:
            if st.button("🗑️", key=f"btn_clear_{uzytkownik}_{akt_wyc_id}_{'inline' if inline else 'float'}", use_container_width=True, help="Wyczyść historię"):
                wyczysc_historie_czatu_w_db(uzytkownik)
                st.session_state["flash_toast"] = "🗑️ Wyczyszczono czat."
                st.rerun()

        chat_container = st.container(height=190)
        with chat_container:
            for message in chat_historia_z_db:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"] if isinstance(message["content"], str) else "")

        prompt = st.chat_input(f"Napisz np. 'zaplanuj nową wycieczkę', 'zmień taktykę dnia'...", key=f"chat_input_{uzytkownik}_{akt_wyc_id}_{'inline' if inline else 'float'}")
        if prompt:
            zapisz_wiadomosc_w_db(uzytkownik, "user", prompt)

            odpowiedz_lokalna = sprobuj_wykonac_komende_lokalnie(prompt, akt_wyc_id)

            if odpowiedz_lokalna:
                zapisz_wiadomosc_w_db(uzytkownik, "model", odpowiedz_lokalna)
                st.session_state["flash_toast"] = "⚡ Zaktualizowano listę zakupów!"
                st.rerun()

            if not api_key_input:
                st.warning("⚠️ Wprowadź klucz API w menu bocznym, aby korzystać z doradcy AI.")
                if not inline:
                    st.markdown('</div>', unsafe_allow_html=True)
                return

            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)
                with st.chat_message("assistant"):
                    dzisiaj_str = date.today().strftime("%Y-%m-%d")
                    zewnetrzny_kontekst = wczytaj_kontekst_zewnetrzny(akt_wyc_id)
                    
                    rules_content = ""
                    if os.path.exists("SYSTEM_RULES_KRETA_ADHD.md"):
                        with open("SYSTEM_RULES_KRETA_ADHD.md", "r", encoding="utf-8") as rf:
                            rules_content = rf.read()

                    rules_content = ""
                    if os.path.exists("SYSTEM_RULES_KRETA_ADHD.md"):
                        with open("SYSTEM_RULES_KRETA_ADHD.md", "r", encoding="utf-8") as rf:
                            rules_content = rf.read()

                    system_prompt = f"""Rola: Planer wycieczek AuDHD Kreta dla rodzica {uzytkownik}. Data: {dzisiaj_str}. Wycieczka ID: {akt_wyc_id}.
{zewnetrzny_kontekst}

ZASADY SYSTEMOWE:
{rules_content}

ŻELAZNA REGUŁA PO KAŻDEJ ZMIANIE KROKÓW:
1. Jeżeli dodajesz, przesuwasz lub usuwasz JAKIKOLWIEK krok wycieczki, masz BEZWZGLĘDNY OBOWIĄZEK w tej samej serii wywołań uruchomić narzędzie:
   `edytuj_wycieczke(id="{akt_wyc_id}", calosciowy_opis_wycieczki=..., calosciowa_taktyka_dnia=...)`.
2. `calosciowy_opis_wycieczki` – zwięzły, zaktualizowany cel dnia uwzględniający nowe punkty.
3. `calosciowa_taktyka_dnia` – zaktualizowana taktyka: ochrona przed upałem 11:30–15:30, gdzie zaplanowano regenerację/cień, gdzie i kiedy jest bezpieczny obiad oraz prowiant Safe Foods.
4. Posiłki: Jeśli dodany krok to punkt gastronomiczny lub lunchbox, wywołaj też `zarzadzaj_posilkiem_kroku`.
5. STRAŻNIK USUWANIA KROKÓW (AuDHD): Przed usunięciem kroku sprawdź, czy nie zawiera on posiłku kotwiczącego (obiad, lunchbox duży). Jeśli użytkownik prosi o usunięcie punktu z posiłkiem, NIE usuwaj go po cichu. Ostrzeż rodzica o ryzyku meltdownu z głodu (luka >4h) i zapytaj, gdzie najpierw przenieść posiłek.
6. Zwracaj się do użytkownika po imieniu: {uzytkownik}."""

                    try:
                        with st.status("🧭 Przygotowuję plan AuDHD...", expanded=True) as status:
                            st.write("🔌 Łączenie z API Gemini...")
                            client = get_gemini_client(api_key_input)
                            
                            contents = []
                            for m in chat_historia_z_db[-2:]:
                                role = "model" if m["role"] in ["assistant", "model"] else "user"
                                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))
                            
                            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=prompt)]))

                            config = types.GenerateContentConfig(
                                tools=[types.Tool(function_declarations=tools_definitions)],
                                system_instruction=system_prompt,
                                temperature=0.1,
                                max_output_tokens=512
                            )

                            assistant_reply = ""
                            executed_actions = []

                            for loop_idx in range(4):
                                st.write(f"🧠 Czekam na odpowiedź modelu (krok {loop_idx + 1})...")
                                response = client.models.generate_content(
                                    model=wybrany_model,
                                    contents=contents,
                                    config=config
                                )

                                candidate = response.candidates[0] if response and response.candidates else None
                                calls = []
                                if hasattr(response, 'function_calls') and response.function_calls:
                                    calls = response.function_calls
                                elif candidate and candidate.content and candidate.content.parts:
                                    for p_part in candidate.content.parts:
                                        if hasattr(p_part, 'function_call') and p_part.function_call:
                                            calls.append(p_part.function_call)

                                if calls:
                                    if candidate and candidate.content:
                                        contents.append(candidate.content)
                                    
                                    function_responses_parts = []
                                    for call in calls:
                                        call_name, args = call.name, call.args or {}
                                        st.write(f"⚙️ Baza danych: `{call_name}`...")
                                        
                                        wynik_bazy = wykonaj_narzedzie_bazy(call_name, args)
                                        msg = wynik_bazy.get('message', wynik_bazy) if isinstance(wynik_bazy, dict) else str(wynik_bazy)
                                        executed_actions.append(f"{call_name}: {msg}")
                                        st.write(f"✅ Zrobione: {msg}")
                                        
                                        function_responses_parts.append(
                                            types.Part.from_function_response(
                                                name=call_name, 
                                                response={"result": wynik_bazy}
                                            )
                                        )
                                    contents.append(types.Content(role="user", parts=function_responses_parts))
                                else:
                                    if candidate and candidate.content and candidate.content.parts:
                                        assistant_reply = "".join([p_text.text for p_text in candidate.content.parts if hasattr(p_text, "text") and p_text.text])
                                    elif hasattr(response, 'text') and response.text:
                                        assistant_reply = response.text
                                    break

                            if not assistant_reply.strip() and executed_actions:
                                assistant_reply = f"✅ **Zaktualizowano plan dla Ciebie, {uzytkownik}:**\n* " + "\n* ".join(executed_actions)
                            elif not assistant_reply.strip():
                                assistant_reply = f"✅ Zrealizowano, {uzytkownik}."

                            status.update(label="✅ Gotowe!", state="complete", expanded=False)

                        zapisz_wiadomosc_w_db(uzytkownik, "model", assistant_reply)
                        st.markdown(assistant_reply)
                        st.session_state["flash_toast"] = "🧭 Zaktualizowano harmonogram!"
                        st.rerun()

                    except Exception as e:
                        naglowek_bledu, komunikat = formatuj_komunikat_bledu_ai(e)
                        st.markdown(f"""
                        <div style="background-color: rgba(220, 80, 80, 0.15); border: 2px solid #DC5050; border-radius: 14px; padding: 10px; margin: 6px 0;">
                            <div style="font-weight: 900; color: #DC5050; font-size: 9.5pt;">{naglowek_bledu}</div>
                            <div style="font-size: 8.5pt; color: #2B2118; margin-top: 3px;">{komunikat}</div>
                        </div>
                        """, unsafe_allow_html=True)

    if not inline:
        st.markdown('</div>', unsafe_allow_html=True)

# --- DIALOGI ZARZĄDZANIA WYCIECZKĄ I MIEJSCAMI ---
@st.dialog("Wybierz nową datę")
def edit_date_dialog(wycieczka_id, aktualna_data):
    dzisiaj = date.today()
    nowa_data = st.date_input("Wybierz nową datę wycieczki", value=aktualna_data, min_value=dzisiaj)
    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button("💾 Zapisz", use_container_width=True):
            str_data = nowa_data.strftime("%Y-%m-%d")
            edytuj_wycieczke(wycieczka_id, planowana_data=str_data)
            st.session_state["flash_toast"] = f"📅 Zmieniono datę: {str_data}"
            st.rerun()
    with col_cancel:
        if st.button("Anuluj", use_container_width=True):
            st.rerun()

@st.dialog("Status wycieczki")
def potwierdz_zakonczenie_wycieczki_dialog(wycieczka_id, tytul, czy_odbyta):
    st.markdown(f"Czy chcesz zmienić status wycieczki **{tytul}** na: **{'Nieukończona (przywróć)' if czy_odbyta else 'Ukończona'}**?")
    if not czy_odbyta:
        st.info("ℹ️ Wszystkie miejsca wchodzące w skład tej wycieczki zostaną automatycznie oznaczone jako **odwiedzone**.")
    col_ok, col_no = st.columns(2)
    with col_ok:
        if st.button("Tak, zmień", use_container_width=True):
            nowy_status = 0 if czy_odbyta else 1
            ustaw_status_odwiedzenia_dla_wycieczki(wycieczka_id, nowy_status)
            st.session_state["flash_toast"] = "🏁 Zaktualizowano status wycieczki oraz powiązanych miejsc!"
            st.rerun()
    with col_no:
        if st.button("Anuluj", use_container_width=True):
            st.rerun()

@st.dialog("Status miejsca")
def potwierdz_odwiedzenie_dialog(nr_miejsca, nazwa_miejsca, czy_odwiedzone):
    st.markdown(f"Czy oznaczyć miejsce **{nazwa_miejsca}** jako **{'Nieodwiedzone' if czy_odwiedzone else 'Odwiedzone'}**?")
    col_ok, col_no = st.columns(2)
    with col_ok:
        if st.button("Tak, zmień", use_container_width=True):
            nowy_status = 0 if czy_odwiedzone else 1
            zmien_status_odwiedzenia_miejsca(nr_miejsca, nowy_status)
            st.session_state["flash_toast"] = "🎯 Zaktualizowano status miejsca!"
            st.rerun()
    with col_no:
        if st.button("Anuluj", use_container_width=True):
            st.rerun()

def pobierz_skrocone_opcje_wycieczek(pokaz_ukonczone=False):
    with get_db() as conn:
        q = 'SELECT id, tytul_wycieczki, odbyta FROM wycieczka ORDER BY CAST(id AS INTEGER) ASC'
        df_w = pd.read_sql(q, conn)
    
    if not pokaz_ukonczone:
        df_w = df_w[df_w['odbyta'] == 0]
        
    opcje = []
    for _, r in df_w.iterrows():
        t = str(r['tytul_wycieczki'])
        skrocony = t.split(':')[0] if ':' in t else t
        status_icon = " ✓" if bool(r.get('odbyta', 0)) else ""
        opcje.append(f"{r['id']}. {skrocony}{status_icon}")
    return opcje

def pobierz_wycieczki_dla_miejsca(numer_miejsca, nazwa_miejsca):
    with get_db() as conn:
        cursor = conn.cursor()
        nazwa_czysta = _wyczysc_nazwe_miejsca(nazwa_miejsca)
        cursor.execute('''
            SELECT DISTINCT w.id, w.tytul_wycieczki
            FROM wycieczka w
            JOIN krok_wycieczki k ON w.id = k.id_wycieczki
            WHERE k.numer_miejsca = ? OR LOWER(k.nazwa) LIKE ? OR ? LIKE ('%' || LOWER(k.nazwa) || '%')
            ORDER BY CAST(w.id AS INTEGER) ASC
        ''', (str(numer_miejsca).strip(), f"%{nazwa_czysta}%", nazwa_czysta))
        rows = cursor.fetchall()
    return pd.DataFrame(rows, columns=['id', 'tytul_wycieczki'])

def dodaj_marker_domku(m):
    icon_domek = f'<div style="background-color:#2E251E;color:white;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:12px;border:2px solid white;box-shadow:0 2px 5px rgba(0,0,0,0.3);margin:0;padding:0;box-sizing:border-box;">🏠</div>'
    folium.Marker([DOMEK_LAT, DOMEK_LON], icon=folium.DivIcon(html=icon_domek, icon_size=(26, 26), icon_anchor=(13, 13), class_name="custom-map-pin"), tooltip="Nasz domek w Stavros").add_to(m)

# --- RENDEROWANIE KARTY WYCIECZKI ---
def render_timeline_row_simple(time_start, badge_icon, badge_class, title, desc, nav_btn_html="", time_end="", extra_box_class=""):
    time_end_markup = f'<span class="timeline-time-end">{time_end}</span>' if time_end else ''
    box_classes = f"timeline-row-frameless {extra_box_class}".strip()
    return (
        f'<div class="timeline-step-row-wrapper">'
        f'<div class="{box_classes}">'
        f'<div class="timeline-row-inner">'
        f'<div class="timeline-time"><span class="timeline-time-start">{time_start}</span>{time_end_markup}</div>'
        f'<div class="timeline-center-col"><div class="timeline-icon-badge-static {badge_class}">{badge_icon}</div></div>'
        f'<div class="timeline-content-col">'
        f'<div class="timeline-item-title">{title}</div>'
        f'<div class="timeline-item-desc">{desc}</div>'
        f'</div>'
        f'{nav_btn_html}'
        f'</div>'
        f'</div>'
        f'</div>'
    )

def renderuj_karte_wycieczki(wycieczka_id, df_wszystkie_miejsca_ref, pokaz_mape=True, pokaz_pogode=False):
    with get_db() as conn:
        wycieczka_row = pd.read_sql('SELECT * FROM wycieczka WHERE id = ?', conn, params=(str(wycieczka_id),))
        kroki_df = pd.read_sql('SELECT * FROM krok_wycieczki WHERE id_wycieczki = ? ORDER BY CAST(krok_wycieczki AS INTEGER) ASC', conn, params=(str(wycieczka_id),))
        czasy_dojazdu_df = pd.read_sql('SELECT * FROM czasy_dojazdu', conn)
        posilki_wszystkie_df = pd.read_sql('SELECT * FROM posilki_kroku', conn)
        zakupy_wszystkie_df = pd.read_sql('SELECT * FROM zakupy WHERE id_wycieczki = ?', conn, params=(str(wycieczka_id),))
    
    if wycieczka_row.empty:
        st.info("Brak danych wycieczki.")
        return

    w_gen = wycieczka_row.iloc[0]
    tytul_wycieczki = w_gen.get('tytul_wycieczki', 'Wycieczka')
    planowana_data_val = w_gen.get('planowana_data', '')
    parsed_date, dzien_val, miesiac_val, dzien_tyg_val = sformatuj_date_pl(planowana_data_val)
    
    if st.button(f"📅 Planowana data: {dzien_val} {miesiac_val} ({dzien_tyg_val}) ▾", key=f"btn_date_picker_{wycieczka_id}", use_container_width=True):
        edit_date_dialog(wycieczka_id, parsed_date)
        
    st.markdown(f'<div class="trip-top-section"><div class="trip-main-title">{tytul_wycieczki}</div></div>', unsafe_allow_html=True)
    
    if pd.notna(w_gen.get('calosciowy_opis_wycieczki')) and str(w_gen['calosciowy_opis_wycieczki']).strip():
        st.markdown(f"""
        <div style="margin-top: 4px; margin-bottom: 8px;">
            <div class="section-unified-header">📝 Cel wycieczki</div>
            <div class="section-body-text">{w_gen['calosciowy_opis_wycieczki']}</div>
        </div>
        """, unsafe_allow_html=True)

    if pokaz_pogode:
        renderuj_podsumowanie_pogody_wycieczki(kroki_df, planowana_data_val)

    taktyka_dnia_val = w_gen.get('calosciowa_taktyka_dnia')
    taktyka_tekst = str(taktyka_dnia_val).strip() if (pd.notna(taktyka_dnia_val) and str(taktyka_dnia_val).strip() not in ['-', 'nan', 'None']) else "Brak zdefiniowanej taktyki. Zdefiniuj ją w asystencie AI."
    
    st.markdown(f"""
    <div class="tactics-alert-box">
        <div class="tactics-alert-title">🎯 Taktyka całościowa na dzień</div>
        <div class="tactics-alert-text">{taktyka_tekst}</div>
    </div>
    """, unsafe_allow_html=True)

    pobudka_val = w_gen.get('pobudka', '06:00') if pd.notna(w_gen.get('pobudka')) else '06:00'
    ogarnianie_val = w_gen.get('szacowany_czas_ogarniania_rano', '0.5h') if pd.notna(w_gen.get('szacowany_czas_ogarniania_rano')) else '0.5h'
    wyjazd_val = w_gen.get('czas_wyjazdu', '06:30') if pd.notna(w_gen.get('czas_wyjazdu')) else '06:30'
    
    if not kroki_df.empty:
        pobudka_val = kroki_df.iloc[0]['okienko_zwiedzania'].split("-")[0].strip() if "-" in str(kroki_df.iloc[0]['okienko_zwiedzania']) else pobudka_val
        wyjazd_val = kroki_df.iloc[0]['okienko_zwiedzania'].split("-")[1].strip() if "-" in str(kroki_df.iloc[0]['okienko_zwiedzania']) else wyjazd_val
        powrot_val = kroki_df.iloc[-1]['okienko_zwiedzania'].split("-")[0].strip() if "-" in str(kroki_df.iloc[-1]['okienko_zwiedzania']) else w_gen.get('szacowana_godzina_powrotu', '17:33')
    else:
        powrot_val = w_gen.get('szacowana_godzina_powrotu', '17:33')

    st.markdown('<div class="section-unified-header">🧭 Logistyka</div>', unsafe_allow_html=True)
    col_log1, col_log2, col_log3 = st.columns(3)
    with col_log1:
        st.markdown('<div style="text-align: center; font-size: 7.5pt; font-weight: 800; color: #8C5338; text-transform: uppercase; margin-bottom: 3px;">⏰ Pobudka</div>', unsafe_allow_html=True)
        with st.popover(pobudka_val, use_container_width=True):
            g_pob = sparsuj_godzine_minuty(pobudka_val) or (6, 0)
            t_pob = st.time_input("Nowa godzina pobudki", value=time(g_pob[0], g_pob[1]), step=300, key=f"ti_pob_{wycieczka_id}")
            if st.button("💾 Zapisz", key=f"btn_save_pob_{wycieczka_id}", use_container_width=True):
                przelicz_i_zsynchronizuj_wycieczke(str(wycieczka_id), force_pobudka_str=t_pob.strftime("%H:%M"))
                st.session_state["flash_toast"] = "⏱️ Zaktualizowano godzinę pobudki!"
                st.rerun()

    with col_log2:
        st.markdown('<div style="text-align: center; font-size: 7.5pt; font-weight: 800; color: #8C5338; text-transform: uppercase; margin-bottom: 3px;">🎒 Ile do wyjazdu</div>', unsafe_allow_html=True)
        with st.popover(ogarnianie_val, use_container_width=True):
            nowy_czas_ogarniania = st.text_input("Szacowany czas rano", value=ogarnianie_val, key=f"ti_ogarnianie_{wycieczka_id}")
            if st.button("💾 Zapisz", key=f"btn_save_ogarnianie_{wycieczka_id}", use_container_width=True):
                edytuj_wycieczke(wycieczka_id, szacowany_czas_ogarniania_rano=nowy_czas_ogarniania)
                st.session_state["flash_toast"] = "⏱️ Zaktualizowano czas do wyjazdu!"
                st.rerun()

    with col_log3:
        st.markdown('<div style="text-align: center; font-size: 7.5pt; font-weight: 800; color: #8C5338; text-transform: uppercase; margin-bottom: 3px;">🏠 Powrót</div>', unsafe_allow_html=True)
        st.button(powrot_val, disabled=True, key=f"btn_powrot_static_{wycieczka_id}", use_container_width=True)

    # --- MAPA TRASY WYCIECZKI ---
    if pokaz_mape and not kroki_df.empty:
        st.markdown('<div class="section-unified-header">🗺️ Trasa wycieczki na mapie</div>', unsafe_allow_html=True)
        coords_list = []
        for _, k_row in kroki_df.iterrows():
            lat_k, lon_k = sparsuj_wspolrzedne(k_row.get('wspolrzedne'))
            if lat_k is not None and lon_k is not None:
                coords_list.append((lat_k, lon_k, str(k_row.get('nazwa', '')), str(k_row.get('krok_wycieczki', ''))))

        if coords_list:
            avg_lat = sum(c[0] for c in coords_list) / len(coords_list)
            avg_lon = sum(c[1] for c in coords_list) / len(coords_list)
            m_trip = folium.Map(location=[avg_lat, avg_lon], zoom_start=9, tiles="OpenStreetMap")
            zaaplikuj_style_mapy(m_trip)
            dodaj_marker_domku(m_trip)

            detailed_route_points = []
            for i in range(len(coords_list) - 1):
                lat_start, lon_start = coords_list[i][0], coords_list[i][1]
                lat_end, lon_end = coords_list[i + 1][0], coords_list[i + 1][1]
                segment_pts = pobierz_geometrie_trasy_osrm(lat_start, lon_start, lat_end, lon_end)
                detailed_route_points.extend(segment_pts)

            if detailed_route_points:
                folium.PolyLine(
                    detailed_route_points, 
                    color="#8C5338", 
                    weight=4, 
                    opacity=0.85
                ).add_to(m_trip)

            for lat_c, lon_c, nazwa_c, krok_c in coords_list:
                if "domek" in nazwa_c.lower():
                    continue
                icon_html = stworz_znacznik_html(krok_c, "#C06C4E", 24)
                folium.Marker([lat_c, lon_c], icon=folium.DivIcon(html=icon_html, icon_size=(24, 24), icon_anchor=(12, 12), class_name="custom-map-pin"), tooltip=nazwa_c).add_to(m_trip)

            st_folium(m_trip, width=None, height=260, returned_objects=[], key=f"trip_map_view_{wycieczka_id}")

    st.markdown('<div class="section-unified-header">🗺️ Plan na dzień</div>', unsafe_allow_html=True)

    total_steps = len(kroki_df)
    timeline_full_html = ['<div class="timeline-master-container">', '<div class="timeline-master-continuous-line"></div>']

    df_pos_sniadanie = posilki_wszystkie_df[
        (posilki_wszystkie_df['id_kroku'].isin(kroki_df['id'].tolist())) & 
        (posilki_wszystkie_df['rodzaj_posilku'].str.lower().str.contains('śniadan|sniadan', na=False))
    ] if not kroki_df.empty else pd.DataFrame()

    if not df_pos_sniadanie.empty:
        pobudka_posilki_tekst = formatuj_posilki_kroku(df_pos_sniadanie)
    else:
        pobudka_posilki_tekst = f"<span style='color:#8C5338; font-weight:700;'>Śniadanie - ok {pobudka_val}</span>"

    timeline_full_html.append(render_timeline_row_simple(pobudka_val, "⏰", "badge-pobudka", "Pobudka", pobudka_posilki_tekst))

    for idx, (_, k) in enumerate(kroki_df.iterrows()):
        krok_row_id = int(k['id'])
        nazwa = str(k['nazwa'])
        nazwa_lower = nazwa.lower()
        okienko = str(k.get('okienko_zwiedzania', ''))
        krok_num = str(k['krok_wycieczki'])
        wspolrzedne = str(k.get('wspolrzedne', ''))
        coords_clean = wspolrzedne.replace(" ", "")
        
        godzina_start = okienko.split("-")[0].strip() if "-" in okienko else (okienko if okienko else "08:00")
        godzina_koniec = okienko.split("-")[1].strip() if "-" in okienko else str(k.get('godzina_ewakuacji', '')).strip()
        
        is_cottage_step = any(w in nazwa_lower for w in ["domek", "powrót", "powrot", "start", "wyjazd"])

        lat_parsed, lon_parsed = sparsuj_wspolrzedne(wspolrzedne)
        nav_btn_html = f'<a href="https://www.google.com/maps/search/?api=1&query={coords_clean}" target="_blank" class="timeline-nav-btn" title="Nawiguj"><span>🧭</span><span>Nawiguj</span></a>' if (lat_parsed is not None and lon_parsed is not None) else ""

        matched_place_id = str(k['numer_miejsca']).strip() if (pd.notna(k.get('numer_miejsca')) and str(k.get('numer_miejsca')).strip() not in ['', 'None', 'nan']) else None
        m_dopasowane_krok = None
        if matched_place_id:
            m_match = df_wszystkie_miejsca_ref[df_wszystkie_miejsca_ref['numer_miejsca'].astype(str) == matched_place_id]
            if not m_match.empty:
                m_dopasowane_krok = m_match.iloc[0]

        if m_dopasowane_krok is None:
            m_dopasowane_krok = dopasuj_krok_do_bazy_miejsc(nazwa, wspolrzedne, df_wszystkie_miejsca_ref)
            if m_dopasowane_krok is not None:
                matched_place_id = str(m_dopasowane_krok['numer_miejsca'])

        if any(w in nazwa_lower for w in ["sklep", "market", "zakup", "rynek", "targ", "laiki"]):
            detected_icon = "🛒"
        elif "apteka" in nazwa_lower:
            detected_icon = "💊"
        elif "kawa" in nazwa_lower or "cafe" in nazwa_lower:
            detected_icon = "☕"
        elif "widok" in nazwa_lower or "punkt widokowy" in nazwa_lower:
            detected_icon = "📸"
        elif "parking" in nazwa_lower or "postój" in nazwa_lower:
            detected_icon = "🅿️"
        elif "toaleta" in nazwa_lower or "wc" in nazwa_lower:
            detected_icon = "🚻"
        elif any(w in nazwa_lower for w in ["obiad", "lunch", "jedzenie", "lunchbox"]):
            detected_icon = "🍴"
        elif "plaż" in nazwa_lower or "beach" in nazwa_lower:
            detected_icon = "🏖️"
        elif any(w in nazwa_lower for w in ["powrót", "powrot", "domek", "wyjazd"]):
            detected_icon = "🏠"
        else:
            kat = kategoryzuj_typ(m_dopasowane_krok['typ']) if m_dopasowane_krok is not None else kategoryzuj_typ(nazwa_lower)
            detected_icon = pobierz_ikonke_kategorii(kat)

        badge_symbol = detected_icon if detected_icon is not None else (krok_num if (krok_num and krok_num != "0") else str(idx))
        
        is_in_places_db = bool(matched_place_id)
        is_custom_flat = not is_cottage_step and (
            not is_in_places_db or 
            any(w in nazwa_lower for w in ["sklep", "market", "zakup", "apteka", "postój", "parking", "kawa", "cafe", "toaleta", "punkt widokowy", "widok", "rynek", "targ"])
        )

        df_pos_kroku = posilki_wszystkie_df[posilki_wszystkie_df['id_kroku'] == krok_row_id]
        df_pos_kroku_display = df_pos_kroku[~df_pos_kroku['rodzaj_posilku'].str.lower().str.contains('śniadan|sniadan', na=False)] if any(w in nazwa_lower for w in ["wyjazd", "start"]) else df_pos_kroku
        posilki_tekst = formatuj_posilki_kroku(df_pos_kroku_display)

        if is_cottage_step:
            is_wyjazd = any(w in nazwa_lower for w in ["wyjazd", "start"])
            godzina_cottage = godzina_koniec if (is_wyjazd and godzina_koniec and godzina_koniec != godzina_start) else godzina_start
            opis_kroku_cottage = posilki_tekst if posilki_tekst else ("" if is_wyjazd else "Wypoczynek i relaks")
            badge_icon_cottage = "🚗" if is_wyjazd else "🏠"
            badge_class_cottage = "badge-wyjazd" if is_wyjazd else "badge-powrot"
            timeline_full_html.append(render_timeline_row_simple(godzina_cottage, badge_icon_cottage, badge_class_cottage, nazwa, opis_kroku_cottage, nav_btn_html=""))
        
        elif is_custom_flat:
            opis_kroku_cust = str(k.get('opis', '')).strip()
            if opis_kroku_cust in ["Brak", "None"]:
                opis_kroku_cust = ""

            tytul_kroku_display = nazwa
            if "rynek" in nazwa_lower or "targ" in nazwa_lower:
                tytul_kroku_display = "Rynek w Chanii"
                rynek_info_krok, _ = pobierz_dane_rynku_dla_daty(planowana_data_val)
                dzien_nazwa = rynek_info_krok["dzien_pl"] if rynek_info_krok else dzien_tyg_val.capitalize()
                opis_kroku_cust = f"<span style='color:#8C5338; font-weight:700;'>{dzien_nazwa} (max 14:00)</span>"

            details_inner_html = f'###SHOPPING_LIST_PLACEHOLDER_{krok_row_id}###'
            expander_html = (
                f'<div class="timeline-step-row-wrapper">'
                f'<details class="timeline-step-expander">'
                f'<summary>'
                f'<div class="timeline-row-inner">'
                f'<div class="timeline-time"><span class="timeline-time-start">{godzina_start}</span><span class="timeline-time-end">do {godzina_koniec}</span></div>'
                f'<div class="timeline-center-col"><div class="timeline-icon-badge-static badge-pobudka">{badge_symbol}</div></div>'
                f'<div class="timeline-content-col">'
                f'<div class="timeline-item-title">{tytul_kroku_display}</div>'
                f'<div class="timeline-item-desc">{opis_kroku_cust}</div>'
                f'</div>'
                f'{nav_btn_html}'
                f'</div>'
                f'</summary>'
                f'<div class="timeline-expander-body">{details_inner_html}</div>'
                f'</details>'
                f'</div>'
            )
            timeline_full_html.append(expander_html)

        else:
            badge_class = "badge-obiad" if "🍴" in str(badge_symbol) else "badge-miejsce"
            time_end_html = f'<span class="timeline-time-end">do {godzina_koniec}</span>' if (godzina_koniec and godzina_koniec != godzina_start) else ''
            sklep_maps_url = f"https://www.google.com/maps/search/supermarket/@{coords_clean},15z" if coords_clean else "#"
            resto_maps_url = f"https://www.google.com/maps/search/restaurant/@{coords_clean},15z" if coords_clean else "#"

            pogoda_kroku = pobierz_szczegoly_pogody_dla_godziny(k['wspolrzedne'], planowana_data_val, okienko)
            pogoda_html = f'<div style="background-color: #FAF8F2; border: 1.5px solid #D8D2BC; border-radius: 14px; padding: 8px 12px; margin-bottom: 10px; text-align: center;"><div style="font-size: 8pt; font-weight: 800; color: #8C5338; text-transform: uppercase; margin-bottom: 2px;">☀️ POGODA ({pogoda_kroku["data"]})</div><div style="font-size: 9.5pt; font-weight: 800; color: #2B2118;">{pogoda_kroku["temp"]}°C (odcz. {pogoda_kroku["feel"]}°C), {pogoda_kroku["desc"]} 💨 {pogoda_kroku["wind"]} km/h | UV {pogoda_kroku["uv"]}</div></div>' if pogoda_kroku else ""
            opis_glowny = str(k.get('opis', '')).strip()
            opis_glowny_html = f'<div class="step-desc-bubble">{opis_glowny}</div>' if (opis_glowny and opis_glowny != "None") else ""

            ewakuacja_val = str(k.get('godzina_ewakuacji', '')).strip()
            evac_html = f'<div class="step-evac-pill"><div class="step-evac-pill-title">🚨 Godzina ewakuacji</div><div class="step-evac-pill-val">{ewakuacja_val}</div></div>' if (ewakuacja_val and ewakuacja_val not in ["None", "Brak"]) else ""

            ostrzezenie_val = str(k.get('czerwona_strefa_ostrzezenie', '')).strip()
            warn_html = f'<div class="step-warn-box"><div class="step-warn-title">⚠️ Ostrzeżenie (Czerwona strefa)</div><div class="step-warn-text">{ostrzezenie_val}</div></div>' if (ostrzezenie_val and ostrzezenie_val not in ["None", "Brak"]) else ""

            place_link_html = ""
            if matched_place_id:
                cur_tab = "route" if st.session_state.active_tab == "route" else "map"
                place_url = f"?tab=zabytek&place={matched_place_id}&return_tab={cur_tab}&return_trip={wycieczka_id}"
                place_link_html = (
                    f'<a href="{place_url}" target="_self" class="step-action-vertical-btn" '
                    f'style="background-color: #FAF8F2 !important; border: 2px solid #8C5338 !important; color: #8C5338 !important; margin-bottom: 8px; font-weight: 900; text-decoration: none;">'
                    f'<span>🏛️</span><span>Pokaż kartę miejsca #{matched_place_id}</span></a>'
                )

            details_inner_html = (
                f'<div class="step-details-card">'
                f'{place_link_html}'
                f'{pogoda_html}'
                f'{opis_glowny_html}'
                f'{evac_html}'
                f'{warn_html}'
                f'<details class="step-combined-card">'
                f'<summary>🎯 Taktyka & Regeneracja</summary>'
                f'<div style="margin-top: 8px; border-top: 1px solid #D1C7AE; padding-top: 6px;">'
                f'<div class="step-subitem-title" style="color: #8C5338;">🎯 Taktyka</div>'
                f'<div class="step-subitem-body">{k.get("podsumowanie_taktyki", "Brak szczegółów taktyki")}</div>'
                f'<div class="step-subitem-title" style="color: #6D8257; margin-top: 6px;">🌿 Regeneracja</div>'
                f'<div class="step-subitem-body">{k.get("strefa_luzu_i_regeneracji", "Brak strefy regeneracji")}</div>'
                f'</div>'
                f'</details>'
                f'###SHOPPING_LIST_PLACEHOLDER_{krok_row_id}###'
                f'<div class="step-action-vertical-bar">'
                f'<a href="{sklep_maps_url}" target="_blank" class="step-action-vertical-btn"><span>🛒</span><span>Sklepy w pobliżu</span></a>'
                f'<a href="{resto_maps_url}" target="_blank" class="step-action-vertical-btn"><span>🍽️</span><span>Gastro w pobliżu</span></a>'
                f'</div>'
                f'</div>'
            )

            expander_html = (
                f'<div class="timeline-step-row-wrapper">'
                f'<details class="timeline-step-expander">'
                f'<summary>'
                f'<div class="timeline-row-inner">'
                f'<div class="timeline-time"><span class="timeline-time-start">{godzina_start}</span>{time_end_html}</div>'
                f'<div class="timeline-center-col"><div class="timeline-icon-badge-static {badge_class}">{badge_symbol}</div></div>'
                f'<div class="timeline-content-col">'
                f'<div class="timeline-item-title">{tytul_kroku_display if "tytul_kroku_display" in locals() else nazwa}</div>'
                f'<div class="timeline-item-desc">{posilki_tekst}</div>'
                f'</div>'
                f'{nav_btn_html}'
                f'</div>'
                f'</summary>'
                f'<div class="timeline-expander-body">{details_inner_html}</div>'
                f'</details>'
                f'</div>'
            )
            timeline_full_html.append(expander_html)

        if idx < total_steps - 1:
            k2_row_id = int(kroki_df.iloc[idx + 1]['id'])
            match_row = czasy_dojazdu_df[(czasy_dojazdu_df['id_kroku_z'] == krok_row_id) & (czasy_dojazdu_df['id_kroku_do'] == k2_row_id)]
            transit_html = ""
            if not match_row.empty:
                czas_dojazdu_dalej = match_row.iloc[0]['czas_przejazdu']
                postoj_val = match_row.iloc[0]['szacowany_czas_postoju']
                if pd.notna(czas_dojazdu_dalej) and str(czas_dojazdu_dalej).strip() != "":
                    transit_html = f'<div class="timeline-transit-text">🚗 {czas_dojazdu_dalej} | + {postoj_val}m</div>' if (postoj_val is not None and int(postoj_val) > 0) else f'<div class="timeline-transit-text">🚗 {czas_dojazdu_dalej}</div>'
            else:
                lat1_c, lon1_c = sparsuj_wspolrzedne(k['wspolrzedne'])
                lat2_c, lon2_c = sparsuj_wspolrzedne(kroki_df.iloc[idx + 1]['wspolrzedne'])
                if lat1_c and lon1_c and lat2_c and lon2_c:
                    t_osrm, _ = oblicz_czas_przejazdu_osrm(lat1_c, lon1_c, lat2_c, lon2_c)
                    transit_html = f'<div class="timeline-transit-text">🚗 {t_osrm}</div>'

            timeline_full_html.append(f'<div class="timeline-transit-spacer">{transit_html}</div>')

    timeline_full_html.append('</div>')
    full_timeline_string = "".join(timeline_full_html)

    for _, k in kroki_df.iterrows():
        if "domek" in str(k['nazwa']).lower():
            continue
        krok_row_id = int(k['id'])
        ph = f"###SHOPPING_LIST_PLACEHOLDER_{krok_row_id}###"
        if ph in full_timeline_string:
            df_zak = zakupy_wszystkie_df[zakupy_wszystkie_df['id_kroku'] == krok_row_id]
            if not df_zak.empty:
                zak_items_html = []
                for _, zrow in df_zak.iterrows():
                    z_ilosc = str(zrow['ilosc']) if pd.notna(zrow['ilosc']) and str(zrow['ilosc']).strip() else ""
                    z_kup = bool(zrow['kupione'])
                    strike_style = "text-decoration: line-through; opacity: 0.6;" if z_kup else ""
                    checked_attr = "checked" if z_kup else ""
                    ilosc_badge = f'<span style="font-size: 7.5pt; background: #D1C7AE; color: #2B2118; padding: 2px 5px; border-radius: 6px; font-weight: 800; margin-left: auto;">{z_ilosc}</span>' if z_ilosc else ""
                    zak_items_html.append(f'<div style="display: flex; align-items: center; gap: 6px; padding: 4px 0; border-bottom: 1px solid rgba(0,0,0,0.05);"><input type="checkbox" {checked_attr} disabled style="accent-color: #8C5338; width: 15px; height: 15px;"><span style="font-size: 9pt; font-weight: 700; color: #2B2118; {strike_style}">{zrow["nazwa_produktu"]}</span>{ilosc_badge}</div>')
                card_zakupy_html = f'<details class="step-combined-card" style="margin-top: 6px; margin-bottom: 6px;"><summary>🛒 Lista zakupów ({len(df_zak)})</summary><div style="margin-top: 8px; border-top: 1px solid #D1C7AE; padding-top: 6px;">{"".join(zak_items_html)}</div></details>'
                full_timeline_string = full_timeline_string.replace(ph, card_zakupy_html)
            else:
                full_timeline_string = full_timeline_string.replace(ph, "")

    st.markdown(full_timeline_string, unsafe_allow_html=True)
    st.markdown('<div class="section-unified-header">🛒 Zaopatrzenie</div>', unsafe_allow_html=True)
    df_wszystkie_zakupy = zakupy_wszystkie_df

    with st.expander("🛒 Zaopatrzenie", expanded=False):
        st.markdown("<div style='font-size: 8pt; font-weight: 800; color: #8C5338; text-transform: uppercase; margin-bottom: 6px;'>⚡ Szybkie przystanki na trasie</div>", unsafe_allow_html=True)
        
        all_k_list = [r for _, r in kroki_df.iterrows()]
        total_k_count = len(all_k_list)

        has_shop_start = any("sklep" in str(r['nazwa']).lower() and int(r['krok_wycieczki']) in [1, 2] for r in all_k_list)
        has_market_start = any(("rynek" in str(r['nazwa']).lower() or "targ" in str(r['nazwa']).lower()) and int(r['krok_wycieczki']) in [1, 2] for r in all_k_list)

        has_shop_end = any("sklep" in str(r['nazwa']).lower() and int(r['krok_wycieczki']) >= max(total_k_count - 3, 1) for r in all_k_list)
        has_market_end = any(("rynek" in str(r['nazwa']).lower() or "targ" in str(r['nazwa']).lower()) and int(r['krok_wycieczki']) >= max(total_k_count - 3, 1) for r in all_k_list)

        rynek_dla_daty, _ = pobierz_dane_rynku_dla_daty(planowana_data_val)
        rynek_czynny = (rynek_dla_daty is not None)

        col_qs_am, col_qs_pm = st.columns(2)
        with col_qs_am:
            st.markdown("<div style='font-size: 7.5pt; font-weight: 800; color: #5D7A60; text-transform: uppercase; margin-bottom: 4px;'>🌅 Po wyjeździe</div>", unsafe_allow_html=True)
            if has_shop_start:
                if st.button("🗑️ Usuń sklep rano", key=f"btn_del_shop_am_{wycieczka_id}", use_container_width=True):
                    usun_sklep_z_wycieczki_handler(wycieczka_id, pozycja="start")
                    st.session_state["flash_toast"] = "🗑️ Usunięto Sklep po wyjeździe!"
                    st.rerun()
            else:
                if st.button("🛒 Sklep rano", key=f"btn_add_shop_am_{wycieczka_id}", use_container_width=True):
                    dodaj_sklep_przy_domku_do_wycieczki(wycieczka_id, pozycja="start")
                    st.session_state["flash_toast"] = "🌅 Dodano Sklep po wyjeździe!"
                    st.rerun()
            
            if has_market_start:
                if st.button("🗑️ Usuń rynek rano", key=f"btn_del_market_am_{wycieczka_id}", use_container_width=True):
                    usun_rynek_z_wycieczki_handler(wycieczka_id, pozycja="start")
                    st.session_state["flash_toast"] = "🗑️ Usunięto Rynek rano!"
                    st.rerun()
            else:
                btn_market_am_label = "🛒 Rynek rano" if rynek_czynny else "🛒 Rynek (nieczynny)"
                if st.button(btn_market_am_label, key=f"btn_add_market_am_{wycieczka_id}", use_container_width=True, disabled=(not rynek_czynny), help=f"Lokalizacja: {rynek_dla_daty['opis_miejsca']}" if rynek_czynny else "Dziś brak targu w Chanii"):
                    dodaj_rynek_w_chanii_do_wycieczki(wycieczka_id, pozycja="start")
                    st.session_state["flash_toast"] = f"🌅 Dodano Rynek w Chanii ({rynek_dla_daty['dzien_pl']})!"
                    st.rerun()

        with col_qs_pm:
            st.markdown("<div style='font-size: 7.5pt; font-weight: 800; color: #8C5338; text-transform: uppercase; margin-bottom: 4px;'>🌇 Przed powrotem</div>", unsafe_allow_html=True)
            if has_shop_end:
                if st.button("🗑️ Usuń sklep powrót", key=f"btn_del_shop_pm_{wycieczka_id}", use_container_width=True):
                    usun_sklep_z_wycieczki_handler(wycieczka_id, pozycja="koniec")
                    st.session_state["flash_toast"] = "🗑️ Usunięto Sklep przed powrotem!"
                    st.rerun()
            else:
                if st.button("🛒 Sklep powrót", key=f"btn_add_shop_pm_{wycieczka_id}", use_container_width=True):
                    dodaj_sklep_przy_domku_do_wycieczki(wycieczka_id, pozycja="koniec")
                    st.session_state["flash_toast"] = "🌇 Dodano Sklep przed powrotem!"
                    st.rerun()
            
            if has_market_end:
                if st.button("🗑️ Usuń rynek powrót", key=f"btn_del_market_pm_{wycieczka_id}", use_container_width=True):
                    usun_rynek_z_wycieczki_handler(wycieczka_id, pozycja="koniec")
                    st.session_state["flash_toast"] = "🗑️ Usunięto Rynek powrót!"
                    st.rerun()
            else:
                btn_market_pm_label = "🛒 Rynek powrót" if rynek_czynny else "🛒 Rynek (nieczynny)"
                if st.button(btn_market_pm_label, key=f"btn_add_market_pm_{wycieczka_id}", use_container_width=True, disabled=(not rynek_czynny), help=f"Lokalizacja: {rynek_dla_daty['opis_miejsca']}" if rynek_czynny else "Dziś brak targu w Chanii"):
                    dodaj_rynek_w_chanii_do_wycieczki(wycieczka_id, pozycja="koniec")
                    st.session_state["flash_toast"] = f"🌇 Dodano Rynek w Chanii ({rynek_dla_daty['dzien_pl']})!"
                    st.rerun()

        st.markdown("<div style='border-top: 1px solid #D6CEBC; margin: 10px 0 8px 0;'></div>", unsafe_allow_html=True)

        with st.form(key=f"form_add_shopping_item_{wycieczka_id}", clear_on_submit=True):
            st.markdown("<div style='font-size: 9pt; font-weight: 800; color: #8C5338; margin-bottom: 3px;'>➕ Dodaj nową pozycję do listy</div>", unsafe_allow_html=True)
            col_nazwa, col_ilosc = st.columns([2, 1])
            with col_nazwa:
                nowy_prod = st.text_input("Produkt", placeholder="np. Woda 1.5L, Owoce, Plastry", label_visibility="collapsed")
            with col_ilosc:
                nowa_ilosc = st.text_input("Ilość", placeholder="Ilość (np. 6 szt)", label_visibility="collapsed")

            opcje_przypisania = [("📦 Cała wycieczka (ogólne)", None)]
            for _, k_row in kroki_df.iterrows():
                if "domek" not in str(k_row['nazwa']).lower():
                    opcje_przypisania.append((f"📍 Krok {k_row['krok_wycieczki']}: {k_row['nazwa']}", int(k_row['id'])))

            wybrany_target = st.selectbox("Przypisz do:", options=opcje_przypisania, format_func=lambda x: x[0])
            if st.form_submit_button("➕ Dodaj do listy", use_container_width=True) and nowy_prod.strip():
                dodaj_produkt_zakupow(
                    id_wycieczki=wycieczka_id,
                    nazwa_produktu=nowy_prod.strip(),
                    id_kroku=wybrany_target[1],
                    ilosc=nowa_ilosc.strip() if nowa_ilosc.strip() else "1"
                )
                st.session_state["flash_toast"] = f"🛒 Dodano: {nowy_prod.strip()}"
                st.rerun()

        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

        if df_wszystkie_zakupy.empty:
            st.markdown("<div style='font-size: 8.5pt; color: #8C827A; font-style: italic; margin-top: 4px;'>Lista zakupów jest pusta. Dodaj produkty powyżej!</div>", unsafe_allow_html=True)
        else:
            ogolne_zakupy = df_wszystkie_zakupy[df_wszystkie_zakupy['id_kroku'].isna() | (df_wszystkie_zakupy['id_kroku'] == '')]
            if not ogolne_zakupy.empty:
                st.markdown("<div style='font-size: 9pt; font-weight: 800; color: #8C5338; margin: 6px 0 3px 0;'>📦 Na całą wycieczkę:</div>", unsafe_allow_html=True)
                render_shopping_checkbox_list(ogolne_zakupy, "zakup_main")

            for _, k in kroki_df.iterrows():
                if "domek" in str(k['nazwa']).lower():
                    continue
                k_id = int(k['id'])
                zakupy_kroku = df_wszystkie_zakupy[df_wszystkie_zakupy['id_kroku'] == k_id]
                if not zakupy_kroku.empty:
                    st.markdown(f"<div style='font-size: 9pt; font-weight: 800; color: #8C5338; margin: 8px 0 3px 0;'>📍 {k['nazwa']}:</div>", unsafe_allow_html=True)
                    render_shopping_checkbox_list(zakupy_kroku, "zakup_krok_view")

    renderuj_sekcje_notatek(id_wycieczki=wycieczka_id)
    
    st.markdown('<div class="section-unified-header">🎯 Zadania dla dzieci</div>', unsafe_allow_html=True)
    grupy_zadan = pobierz_grupy_zadan_dla_wycieczki(wycieczka_id, kroki_df, df_wszystkie_miejsca_ref)
    
    with st.expander("🎯 Zadania", expanded=False):
        if grupy_zadan:
            for tytul_grupy, lista_zadan, prefix in grupy_zadan:
                if not lista_zadan:
                    continue
                with st.expander(tytul_grupy, expanded=False):
                    for idx, zad in enumerate(lista_zadan):
                        klucz = f"{prefix}_task_{idx}"
                        stan = pobierz_status_zadania(klucz)
                        nowy_stan = st.checkbox(zad, value=stan, key=f"cb_{klucz}")
                        if nowy_stan != stan:
                            zapisz_status_zadania(klucz, nowy_stan)
                            st.rerun()
        else:
            st.markdown("<div style='font-size: 8.5pt; color: #8C827A; font-style: italic; margin: 4px 0;'>Brak zadań dla tej wycieczki.</div>", unsafe_allow_html=True)
    
    czy_odbyta = bool(w_gen.get('odbyta', 0))
    st.markdown('<div class="section-unified-header">⚙️ Zarządzanie Wycieczką</div>', unsafe_allow_html=True)
    
    akt_id = pobierz_aktywna_wycieczke_id()
    col_stat, col_dup, col_active = st.columns(3)
    
    with col_stat:
        btn_finish_label = "✓ Ukończona" if czy_odbyta else "🏁 Zakończ"
        if st.button(btn_finish_label, key=f"btn_finish_trip_{wycieczka_id}", use_container_width=True):
            potwierdz_zakonczenie_wycieczki_dialog(wycieczka_id, tytul_wycieczki, czy_odbyta)

    with col_dup:
        if st.button("📋 Klonuj", key=f"btn_dup_trip_{wycieczka_id}", use_container_width=True):
            nowe_id = duplikuj_wycieczke(wycieczka_id)
            if nowe_id:
                st.session_state["selected_trip_from_click"] = nowe_id
                ustaw_aktywna_wycieczke_id(nowe_id)
                st.session_state["flash_toast"] = f"📋 Skopiowano wycieczkę jako #{nowe_id}!"
                st.rerun()

    with col_active:
        if str(wycieczka_id) == str(akt_id):
            st.button("⭐ Aktywna", disabled=True, key=f"btn_is_active_{wycieczka_id}", use_container_width=True)
        else:
            if st.button("⭐ Aktywuj", key=f"btn_make_active_{wycieczka_id}", use_container_width=True):
                ustaw_aktywna_wycieczke_id(wycieczka_id)
                st.session_state["flash_toast"] = f"⭐ Ustawiono wycieczkę #{wycieczka_id} jako Trasę Dnia!"
                st.rerun()

# --- GŁÓWNY ROUTING ZAKŁADEK I PARAMETRÓW POWROTNYCH ---
if "tab" in st.query_params:
    st.session_state.active_tab = st.query_params["tab"]
elif "active_tab" not in st.session_state:
    st.session_state.active_tab = "route"

if "place" in st.query_params:
    st.session_state.active_place_id = str(st.query_params["place"]).strip()
    st.session_state.active_tab = "zabytek"

if "return_tab" in st.query_params:
    st.session_state.return_tab = st.query_params["return_tab"]
if "return_trip" in st.query_params:
    st.session_state.return_trip = st.query_params["return_trip"]

if "active_place_id" not in st.session_state:
    st.session_state.active_place_id = None
if "return_tab" not in st.session_state:
    st.session_state.return_tab = None
if "return_trip" not in st.session_state:
    st.session_state.return_trip = None
if "map_tab_selected_place" not in st.session_state:
    st.session_state.map_tab_selected_place = None
if "selected_category" not in st.session_state:
    st.session_state.selected_category = None
if "show_visited_places" not in st.session_state:
    st.session_state.show_visited_places = False
if "last_map_click_place" not in st.session_state:
    st.session_state.last_map_click_place = None
if "last_map_click_trips" not in st.session_state:
    st.session_state.last_map_click_trips = None
if "filter_map_places" not in st.session_state:
    st.session_state.filter_map_places = "Przypisane miejsca"

df_miejsca = pobierz_wszystkie_miejsca()

active_zabytek = "active" if st.session_state.active_tab == "zabytek" else ""
active_map = "active" if st.session_state.active_tab == "map" else ""
active_route = "active" if st.session_state.active_tab == "route" else ""

st.markdown(f"""
<div class="top-sticky-nav-container">
    <div class="custom-top-nav-bar">
        <a href="?tab=zabytek" target="_self" class="custom-top-nav-btn {active_zabytek}"><span>🏛️</span><span>Miejsca</span></a>
        <a href="?tab=map" target="_self" class="custom-top-nav-btn {active_map}"><span>🗺️</span><span>Wycieczki</span></a>
        <a href="?tab=route" target="_self" class="custom-top-nav-btn {active_route}"><span>🚗</span><span>Trasa Dnia</span></a>
    </div>
</div>
""", unsafe_allow_html=True)

if st.session_state.active_tab == "route":
    render_adventure_header("CretAi • Aktualna Wycieczka")
    renderuj_karte_wycieczki(pobierz_aktywna_wycieczke_id(), df_miejsca, pokaz_mape=True, pokaz_pogode=True)
    st.markdown('<div class="section-unified-header">🤖 Asystent AI</div>', unsafe_allow_html=True)
    renderuj_globalny_czat_ai(aktualny_uzytkownik, id_wycieczki=pobierz_aktywna_wycieczke_id(), inline=True)

elif st.session_state.active_tab == "map":
    render_adventure_header("CretAi • Nasze wycieczki")
    
    # Zastąpienie checkboxa listą wyboru
    filtr_miejsc = st.selectbox(
        "Filtruj miejsca na mapie:",
        options=["Wszystkie", "Przypisane miejsca", "Nieprzypisane miejsca"],
        index=1,
        key="filter_map_places"
    )

    with get_db() as conn:
        przypisane_df = pd.read_sql("SELECT DISTINCT numer_miejsca FROM krok_wycieczki WHERE numer_miejsca IS NOT NULL AND numer_miejsca != ''", conn)
        przypisane_ids = [str(x).strip() for x in przypisane_df['numer_miejsca'].tolist()]

    df_miejsca_mapa = df_miejsca.copy()
    if filtr_miejsc == "Przypisane miejsca":
        df_miejsca_mapa = df_miejsca_mapa[df_miejsca_mapa['numer_miejsca'].astype(str).str.strip().isin(przypisane_ids)]
        wycieczki_options_filtrowane = pobierz_skrocone_opcje_wycieczek(pokaz_ukonczone=True)
    elif filtr_miejsc == "Nieprzypisane miejsca":
        df_miejsca_mapa = df_miejsca_mapa[~df_miejsca_mapa['numer_miejsca'].astype(str).str.strip().isin(przypisane_ids)]
        wycieczki_options_filtrowane = []
    else:
        wycieczki_options_filtrowane = pobierz_skrocone_opcje_wycieczek(pokaz_ukonczone=True)

    opcje_wycieczek_lista = [None] + wycieczki_options_filtrowane

    m_all = folium.Map(location=[35.2401, 24.8093], zoom_start=8, tiles="OpenStreetMap")
    zaaplikuj_style_mapy(m_all)
    dodaj_marker_domku(m_all)
    
    map_coords_lookup = {}
    for _, row in df_miejsca_mapa.iterrows():
        lat, lon = sparsuj_wspolrzedne(row.get('wspolrzedne'))
        if lat is not None and lon is not None:
            num = str(row.get('numer_miejsca', '')).strip()
            nazwa = str(row.get('nazwa', '')).strip()
            kolor = "#A8A29E" if bool(row.get('odwiedzone', 0)) else pobierz_kolor_kategorii(kategoryzuj_typ(row.get('typ')))
            map_coords_lookup[(round(lat, 4), round(lon, 4))] = (num, nazwa)
            
            icon_html = stworz_znacznik_html(num, kolor, 24)
            folium.Marker([lat, lon], icon=folium.DivIcon(html=icon_html, icon_size=(24, 24), icon_anchor=(12, 12), class_name="custom-map-pin"), tooltip=f"#{num} {nazwa}").add_to(m_all)
            
    map_out = st_folium(m_all, width=None, height=300, returned_objects=["last_object_clicked"], key="map_all_trips_view")
    if map_out and map_out.get("last_object_clicked"):
        c_lat, c_lng = map_out["last_object_clicked"].get("lat"), map_out["last_object_clicked"].get("lng")
        if c_lat is not None and c_lng is not None:
            click_pt = (round(c_lat, 4), round(c_lng, 4))
            if st.session_state.last_map_click_trips != click_pt:
                st.session_state.last_map_click_trips = click_pt
                matched_place = map_coords_lookup.get(click_pt)
                if not matched_place:
                    for (mlat, mlon), data_tuple in map_coords_lookup.items():
                        if abs(mlat - c_lat) < 0.005 and abs(mlon - c_lng) < 0.005:
                            matched_place = data_tuple
                            break
                if matched_place:
                    st.session_state.map_tab_selected_place = matched_place
                    st.rerun()

    if st.session_state.map_tab_selected_place:
        nr_m, nazwa_m = st.session_state.map_tab_selected_place
        df_przypisane = pobierz_wycieczki_dla_miejsca(nr_m, nazwa_m)
        
        with st.container():
            st.markdown(f'<div style="font-size: 10.5pt; font-weight: 900; color: #2B2118; margin-bottom: 3px;">📍 {nr_m}. {nazwa_m}</div><div style="font-size: 9pt; font-weight: 800; color: #8C5338; margin-bottom: 6px;">🗺️ Występuje w wycieczkach:</div>', unsafe_allow_html=True)
            if df_przypisane.empty:
                st.markdown("<div style='font-size: 8.5pt; color: #8C827A; font-style: italic; margin-bottom: 3px;'>Nie jest przypisany do żadnej wycieczki.</div>", unsafe_allow_html=True)
            else:
                for _, row_trip in df_przypisane.iterrows():
                    w_id, w_tytul = str(row_trip['id']), str(row_trip['tytul_wycieczki'])
                    skrocony = w_tytul.split(':')[0] if ':' in w_tytul else w_tytul
                    btn_text = f"🧭 {w_id}. {skrocony}"
                    if st.button(btn_text, key=f"btn_go_to_trip_{w_id}_{nr_m}", use_container_width=True):
                        for opt in opcje_wycieczek_lista:
                            if opt and opt.startswith(f"{w_id}."):
                                st.session_state["map_wycieczka_select"] = opt
                                break
                        st.session_state.map_tab_selected_place = None
                        st.rerun()

    # Obsługa wyboru z parametru URL lub przycisku ze szczegółów miejsca
    target_tid = st.query_params.get("trip") or st.session_state.get("target_trip_id")
    if target_tid:
        for opt in opcje_wycieczek_lista:
            if opt and opt.startswith(f"{target_tid}."):
                st.session_state["map_wycieczka_select"] = opt
                break
        st.session_state.target_trip_id = None

    selected_idx = 0
    curr_sel = st.session_state.get("map_wycieczka_select")
    if curr_sel and curr_sel in opcje_wycieczek_lista:
        selected_idx = opcje_wycieczek_lista.index(curr_sel)

    wybrana_mapa_sb = st.selectbox(
        "", 
        options=opcje_wycieczek_lista, 
        index=selected_idx, 
        format_func=lambda x: "**Brak przypisanych wycieczek**" if (x is None and filtr_miejsc == "Nieprzypisane miejsca") else ("**Wybierz wycieczkę**" if x is None else x),
        key="map_wycieczka_select", 
        label_visibility="collapsed",
        disabled=(filtr_miejsc == "Nieprzypisane miejsca")
    )

    if wybrana_mapa_sb is not None and filtr_miejsc != "Nieprzypisane miejsca":
        wybrana_id = wybrana_mapa_sb.split(". ")[0]
        renderuj_karte_wycieczki(wybrana_id, df_miejsca, pokaz_mape=True, pokaz_pogode=False)
        st.markdown('<div class="section-unified-header">🤖 Asystent AI</div>', unsafe_allow_html=True)
        renderuj_globalny_czat_ai(aktualny_uzytkownik, id_wycieczki=wybrana_id, inline=True)

elif st.session_state.active_tab == "zabytek":
    render_adventure_header("CretAi • Baza Miejsc")
    
    ret_tab = st.session_state.get("return_tab")
    ret_trip = st.session_state.get("return_trip")

    if ret_tab and ret_trip:
        if ret_tab == "map":
            powrot_url = f"?tab=map&return_trip={ret_trip}"
        else:
            powrot_url = f"?tab={ret_tab}"
        nazwa_docelowa = "Trasy Dnia" if ret_tab == "route" else f"Wycieczki #{ret_trip}"
        
        st.markdown(f"""
        <div style="margin-bottom: 8px;">
            <a href="{powrot_url}" target="_self" style="
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                background-color: #2E251E;
                color: #FAF8F2 !important;
                text-decoration: none;
                padding: 10px 14px;
                border-radius: 16px;
                font-size: 9.5pt;
                font-weight: 900;
                box-shadow: 0 4px 12px rgba(0,0,0,0.18);
                border: 2px solid #D6CEBA;
            ">
                <span>◀</span><span>Wróć do planu: {nazwa_docelowa}</span>
            </a>
        </div>
        """, unsafe_allow_html=True)
    
    all_cats = list(CATEGORIES_CONFIG.keys())
    active_cat = st.session_state.selected_category

    category_button_css = []
    for cat_name, cat_data in CATEGORIES_CONFIG.items():
        c_slug = cat_data["slug"]
        c_color = cat_data["color"]
        category_button_css.append(f"""
            div.st-key-pop_btn_cat_{c_slug} button {{
                background-color: {c_color} !important;
                color: #FFFFFF !important;
                border: 2px solid rgba(255, 255, 255, 0.4) !important;
                box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15) !important;
                transition: opacity 0.2s ease-in-out, transform 0.1s ease-in-out !important;
            }}
            div.st-key-pop_btn_cat_{c_slug} button:hover {{
                opacity: 0.9 !important;
                transform: scale(0.98) !important;
                border-color: #FFFFFF !important;
            }}
        """)
    st.markdown(f"<style>{''.join(category_button_css)}</style>", unsafe_allow_html=True)

    filtr_label = f"🌪️ Filtr: {active_cat}" if active_cat else "🌪️ Filtry i opcje widoku"
    if st.session_state.show_visited_places:
        filtr_label += " (z odwiedzonymi)"

    with st.popover(filtr_label, use_container_width=True):
        st.markdown("<div style='font-size: 8.5pt; font-weight: 800; color: #8C5338; text-transform: uppercase; margin-bottom: 4px;'>Kategoria miejsc</div>", unsafe_allow_html=True)
        col_c1, col_c2 = st.columns(2)
        for idx, cat_name in enumerate(all_cats):
            col_target = col_c1 if idx % 2 == 0 else col_c2
            slug = CATEGORIES_CONFIG[cat_name]["slug"]
            cat_icon = CATEGORIES_CONFIG[cat_name].get("icon") or "📍"
            with col_target:
                btn_txt = f"✓ {cat_name}" if active_cat == cat_name else f"{cat_icon} {cat_name}"
                if st.button(btn_txt, key=f"pop_btn_cat_{slug}", use_container_width=True):
                    st.session_state.selected_category = None if active_cat == cat_name else cat_name
                    st.rerun()
        if active_cat:
            if st.button("Pokaż wszystkie kategorie", use_container_width=True):
                st.session_state.selected_category = None
                st.rerun()

        st.markdown("<div style='border-top: 1px solid #D1C7AE; margin: 8px 0 6px 0;'></div>", unsafe_allow_html=True)
        st.checkbox("Pokaż odwiedzone miejsca", key="show_visited_places")

    df_miejsca_filtrowane = df_miejsca.copy()
    if not df_miejsca_filtrowane.empty:
        df_miejsca_filtrowane['kategoria_normalizowana'] = df_miejsca_filtrowane['typ'].apply(kategoryzuj_typ)
        if st.session_state.selected_category is not None:
            df_miejsca_filtrowane = df_miejsca_filtrowane[df_miejsca_filtrowane['kategoria_normalizowana'] == st.session_state.selected_category]
        if not st.session_state.show_visited_places:
            df_miejsca_filtrowane = df_miejsca_filtrowane[df_miejsca_filtrowane['odwiedzone'] == 0]

        df_miejsca_filtrowane['sort_num'] = pd.to_numeric(df_miejsca_filtrowane['numer_miejsca'], errors='coerce').fillna(9999)
        df_miejsca_filtrowane = df_miejsca_filtrowane.sort_values(by='sort_num').drop(columns=['sort_num'])

    m_miejsca = folium.Map(location=[35.2401, 24.8093], zoom_start=8, tiles="OpenStreetMap")
    zaaplikuj_style_mapy(m_miejsca)
    dodaj_marker_domku(m_miejsca)

    marker_coords_dict = {}
    if not df_miejsca_filtrowane.empty:
        for _, row in df_miejsca_filtrowane.iterrows():
            lat, lon = sparsuj_wspolrzedne(row.get('wspolrzedne'))
            if lat is not None and lon is not None:
                num = str(row.get('numer_miejsca', '')).strip()
                nazwa_p = str(row.get('nazwa', '')).strip()
                kolor = "#A8A29E" if bool(row.get('odwiedzone', 0)) else pobierz_kolor_kategorii(row.get('kategoria_normalizowana', 'Other'))
                marker_coords_dict[(round(lat, 4), round(lon, 4))] = (num, nazwa_p)
                icon_html = stworz_znacznik_html(num, kolor, 24)
                folium.Marker([lat, lon], icon=folium.DivIcon(html=icon_html, icon_size=(24, 24), icon_anchor=(12, 12), class_name="custom-map-pin"), tooltip=f"#{num} {nazwa_p}").add_to(m_miejsca)

    map_output = st_folium(m_miejsca, width=None, height=230, returned_objects=["last_object_clicked"], key="map_places_view")

    if map_output and map_output.get("last_object_clicked"):
        c_lat, c_lng = map_output["last_object_clicked"].get("lat"), map_output["last_object_clicked"].get("lng")
        if c_lat is not None and c_lng is not None:
            click_pt = (round(c_lat, 4), round(c_lng, 4))
            if st.session_state.last_map_click_place != click_pt:
                st.session_state.last_map_click_place = click_pt
                match_info = marker_coords_dict.get(click_pt)
                if not match_info:
                    for (mlat, mlon), data_tuple in marker_coords_dict.items():
                        if abs(mlat - c_lat) < 0.005 and abs(mlon - c_lng) < 0.005:
                            match_info = data_tuple
                            break
                if match_info:
                    clicked_id, clicked_nazwa = match_info
                    st.session_state.active_place_id = str(clicked_id).strip()
                    st.query_params["place"] = str(clicked_id).strip()
                    st.session_state["flash_toast"] = f"📍 Wybrano: #{clicked_id} {clicked_nazwa}"
                    st.rerun()

    docelowy_nr = str(st.session_state.active_place_id).strip() if st.session_state.active_place_id else None

    if docelowy_nr:
        with get_db() as conn:
            p_df_fresh = pd.read_sql("SELECT * FROM miejsca WHERE TRIM(numer_miejsca) = ?", conn, params=(str(docelowy_nr).strip(),))

        if not p_df_fresh.empty:
            p = p_df_fresh.iloc[0]
            kat_p = kategoryzuj_typ(p.get('typ'))
            kolor_p = pobierz_kolor_kategorii(kat_p)
            coords_p = str(p.get('wspolrzedne', '')).replace(" ", "")
            czy_odwiedzone = bool(p.get('odwiedzone', 0))

            zdjecie_b64 = pobierz_zdjecie_miejsca_b64(numer_miejsca=docelowy_nr, nazwa_miejsca=p.get('nazwa'))
            zdjecie_html = f"""<div style="width: calc(100% + 28px); height: 185px; margin: -14px -14px 12px -14px; overflow: hidden; border-radius: 18px 18px 0 0; background-color: #EDE8D6;"><img src="{zdjecie_b64}" style="width: 100%; height: 100%; object-fit: cover; display: block;" alt="{p.get('nazwa')}" /></div>""" if zdjecie_b64 else ""

            st.markdown(f"""<div class="overview-card" style="margin-top: 6px; overflow: hidden;">
{zdjecie_html}
<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
<div style="font-size: 13pt; font-weight: 900; color: #2B2118; line-height: 1.2;">{p.get('numer_miejsca')}. {p.get('nazwa')}</div>
<span style="background-color: {kolor_p}; color: #FAF8F2; font-size: 8pt; font-weight: 800; padding: 2px 8px; border-radius: 10px;">{kat_p}</span>
</div>
<div class="overview-card-text">{p.get('opis', '')}</div>
</div>""", unsafe_allow_html=True)

            st.markdown(f"""<div class="overview-card">
<div class="overview-card-title"><span>ℹ️</span> INFORMACJE PRAKTYCZNE</div>
<div class="logistics-grid">
<div class="logistics-pill">
<div class="logistics-pill-title">🚗 Czas dojazdu</div>
<div class="logistics-pill-value" style="font-size: 9.5pt;">{p.get('czas_dojazdu', '—')}</div>
</div>
<div class="logistics-pill">
<div class="logistics-pill-title">⏱️ Czas na miejscu</div>
<div class="logistics-pill-value" style="font-size: 9.5pt;">{p.get('orientacyjny_czas', '—')}</div>
</div>
<div class="logistics-pill">
<div class="logistics-pill-title">💶 Koszt (2+2)</div>
<div class="logistics-pill-value" style="font-size: 9.5pt;">{p.get('koszt', '—')}</div>
</div>
<div class="logistics-pill">
<div class="logistics-pill-title">🕒 Godziny otwarcia</div>
<div class="logistics-pill-value" style="font-size: 9.5pt;">{p.get('godziny_otwarcia', '—')}</div>
</div>
</div>
</div>""", unsafe_allow_html=True)

            st.markdown(f"""<div class="overview-card">
<div class="overview-card-title"><span>📊</span> POZIOM TRUDNOŚCI</div>
<div class="overview-card-text">{p.get('trudnosc_adhd', 'Średni')}</div>
</div>""", unsafe_allow_html=True)

            st.markdown(f"""<div class="overview-card">
<div class="overview-card-title"><span>☀️</span> OCHRONA PRZED SŁOŃCEM</div>
<div class="overview-card-text">{p.get('ochrona_slonce', 'Standardowa')}</div>
</div>""", unsafe_allow_html=True)

            st.markdown(f"""<details class="overview-details-card">
<summary>🧠 SPECYFIKA AuDHD & SENSORYKA</summary>
<div style="margin-top: 8px; border-top: 1px solid #D1C7AE; padding-top: 6px;">
<div style="font-size: 9pt; color: #2B2118; margin-bottom: 4px;"><b>Potencjał meltdownu:</b> {p.get('potencjal_meltdownu', 'Średni')}</div>
<div style="font-size: 9pt; color: #2B2118;"><b>Strategia zaradcza:</b> {p.get('strategie_meltdown', 'Brak')}</div>
</div>
</details>""", unsafe_allow_html=True)

            zadania_miejsca = sparsuj_liste_zadan(p.get('zadania_dla_dzieci', ''))
            if zadania_miejsca:
                with st.expander("🎯 Zadania dla dzieci", expanded=False):
                    for idx, zad in enumerate(zadania_miejsca):
                        klucz = f"place_{docelowy_nr}_task_{idx}"
                        stan = pobierz_status_zadania(klucz)
                        nowy_stan = st.checkbox(zad, value=stan, key=f"cb_{klucz}")
                        if nowy_stan != stan:
                            zapisz_status_zadania(klucz, nowy_stan)
                            st.rerun()

            if coords_p and ',' in coords_p:
                st.markdown(render_action_bar(coords_p, p.get('nazwa', '')), unsafe_allow_html=True)

            btn_vis_label = "✓ Miejsce odwiedzone (przywróć)" if czy_odwiedzone else "🎯 Oznacz jako odwiedzone"
            if st.button(btn_vis_label, key=f"btn_toggle_vis_{docelowy_nr}", use_container_width=True):
                potwierdz_odwiedzenie_dialog(docelowy_nr, p.get('nazwa'), czy_odwiedzone)

            renderuj_sekcje_notatek(id_miejsca=str(docelowy_nr))
            
            df_wycieczki_miejsca = pobierz_wycieczki_dla_miejsca(docelowy_nr, p.get('nazwa', ''))
            
            st.markdown(
                '<div class="section-unified-header" style="margin-top: 14px;">🗺️ Występuje w wycieczkach</div>', 
                unsafe_allow_html=True
            )
            
            if df_wycieczki_miejsca.empty:
                st.markdown(
                    "<div style='font-size: 8.5pt; color: #4A3E36; font-style: italic; margin-bottom: 6px; font-weight: 600;'>"
                    "To miejsce nie jest obecnie przypisane do żadnej wycieczki.</div>", 
                    unsafe_allow_html=True
                )
            else:
                for _, row_trip in df_wycieczki_miejsca.iterrows():
                    w_id = str(row_trip['id'])
                    w_tytul = str(row_trip['tytul_wycieczki'])
                    skrocony = w_tytul.split(':')[0] if ':' in w_tytul else w_tytul
                    btn_label = f"🧭 #{w_id} • {skrocony}"
                    
                    if st.button(btn_label, key=f"btn_place_to_trip_{docelowy_nr}_{w_id}", use_container_width=True):
                        st.session_state.active_tab = "map"
                        st.query_params["tab"] = "map"
                        st.query_params["trip"] = str(w_id)
                        if "place" in st.query_params:
                            del st.query_params["place"]
                        st.session_state.active_place_id = None
                        st.session_state.target_trip_id = str(w_id)
                        st.rerun()

    miejsca_opcje_lista = [f"{str(r['numer_miejsca']).strip()}. {r['nazwa']}" for _, r in df_miejsca_filtrowane.iterrows()]
    sb_key = f"place_selectbox_selector_bottom_{st.session_state.show_visited_places}"

    def on_place_select_changed_bottom():
        val = st.session_state.get(sb_key)
        if val:
            nowy_id = str(val).split(".")[0].strip()
            st.session_state.active_place_id = nowy_id
            st.query_params["place"] = nowy_id
        else:
            st.session_state.active_place_id = None
            if "place" in st.query_params:
                del st.query_params["place"]

    domyslny_indeks = 0
    if st.session_state.active_place_id:
        target_prefix = f"{str(st.session_state.active_place_id).strip()}."
        for idx, opt in enumerate(miejsca_opcje_lista):
            if opt.startswith(target_prefix):
                domyslny_indeks = idx + 1
                break

    st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)
    with st.expander("🔍 Wybór miejsca z listy", expanded=False):
        st.selectbox(
            "Wybierz miejsce ręcznie",
            options=[None] + miejsca_opcje_lista,
            index=domyslny_indeks,
            format_func=lambda x: "Wybierz miejsce..." if x is None else x,
            key=sb_key,
            on_change=on_place_select_changed_bottom,
            label_visibility="collapsed"
        )

    renderuj_globalny_czat_ai(aktualny_uzytkownik, id_wycieczki=pobierz_aktywna_wycieczke_id(), inline=False)
