import sqlite3
import pandas as pd
import streamlit as st
from google import genai
from google.genai import types
import folium
from streamlit_folium import st_folium
import os
import urllib.request
import json
import re
import base64
from datetime import datetime, date, timedelta

# Próba zaimportowania Anthropic SDK dla kolegi używającego Claude'a
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# --- 1. KONFIGURACJA STRONY I DESIGN SYSTEM: DUCH PRZYGODY (DARK + NEONY + SOLAR READABILITY) ---
st.set_page_config(page_title="CretAi - Kreta", layout="centered", page_icon="🧭")

st.markdown("""
    <style>
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 150px !important;
        max-width: 600px;
    }
    .stApp {
        background-color: #050b18 !important;
        color: #ffffff !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    [data-testid="stSidebar"] {
        background-color: #0b1329;
        color: #f8fafc !important;
        border-right: 1px solid #1e293b;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
        color: #f8fafc !important;
    }
    h3 {
        color: #38bdf8;
        font-size: 1.25rem;
        font-weight: 800;
        margin-top: 0.75rem;
        margin-bottom: 0.35rem;
    }
    
    /* Poprawka widoczności wpisywanego tekstu w polach input / czacie (biel na ciemnym tle) */
    input, textarea, [data-baseweb="input"] input, [data-baseweb="base-input"] input, .stChatInput input {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    ::placeholder {
        color: #94a3b8 !important;
        opacity: 1 !important;
    }

    /* Belka tytułowa z logiem z pliku */
    .adventure-header {
        background: linear-gradient(135deg, #111e38 0%, #1e293b 100%);
        border: 2px solid #38bdf8;
        border-radius: 12px;
        padding: 10px 14px;
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 10px;
        box-shadow: 0 4px 15px rgba(56, 189, 248, 0.25);
    }
    .adventure-title-text {
        font-size: 1.2rem;
        font-weight: 900;
        color: #ffffff;
        letter-spacing: 0.03em;
        text-transform: uppercase;
    }

    /* Pasek nawigacji dolnej */
    .bottom-nav-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background-color: rgba(11, 19, 41, 0.98);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-top: 2px solid rgba(56, 189, 248, 0.3);
        padding: 10px 12px;
        display: flex;
        justify-content: space-around;
        gap: 6px;
        z-index: 99999;
        box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.6);
    }
    .bottom-nav-btn {
        flex: 1;
        background-color: rgba(255, 255, 255, 0.08);
        border: 1.5px solid rgba(255, 255, 255, 0.15);
        color: #cbd5e1;
        padding: 8px 0;
        text-align: center;
        border-radius: 10px;
        font-size: 12px;
        font-weight: 700;
        text-decoration: none;
        cursor: pointer;
        transition: all 0.2s ease;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
    }
    .bottom-nav-btn:hover {
        background-color: rgba(56, 189, 248, 0.2);
        color: #38bdf8;
        border-color: rgba(56, 189, 248, 0.6);
    }
    .bottom-nav-btn.active {
        background-color: #38bdf8;
        color: #050b18;
        border-color: #38bdf8;
        font-weight: 900;
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.7);
    }

    /* Pływający kontener globalnego AI nad dolnym paskiem nawigacji */
    .floating-ai-container {
        position: fixed;
        bottom: 65px;
        left: 8px;
        right: 8px;
        max-width: 580px;
        margin: 0 auto;
        z-index: 999998;
    }

    .custom-nav-bar {
        display: flex;
        justify-content: space-between;
        gap: 6px;
        width: 100%;
        margin-bottom: 0.4rem;
    }
    .custom-nav-btn {
        flex: 1;
        background-color: #111e38;
        border: 1.5px solid #334155;
        color: #ffffff;
        padding: 8px 4px;
        text-align: center;
        border-radius: 8px;
        font-size: 11px;
        font-weight: 700;
        text-decoration: none;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
    }
    .custom-nav-btn:hover {
        background-color: #1e293b;
        border-color: #38bdf8;
        color: #38bdf8;
    }
    .custom-nav-btn.active {
        background-color: #38bdf8;
        color: #050b18;
        border-color: #38bdf8;
    }

    .logistics-card {
        background-color: #111e38;
        border: 1.5px solid #1e293b;
        border-radius: 10px;
        padding: 10px;
        text-align: left;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        margin-bottom: 4px;
    }
    .logistics-title {
        font-size: 9.5pt;
        font-weight: 800;
        color: #94a3b8;
        margin-bottom: 2px;
        text-transform: uppercase;
    }
    .logistics-value {
        font-size: 12pt;
        font-weight: 900;
        color: #38bdf8;
    }

    .net-box {
        background-color: #111e38;
        border: 1.5px solid #1e293b;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 6px;
    }
    .net-box-evac {
        background-color: rgba(239, 68, 68, 0.15);
        border: 1.5px solid rgba(239, 68, 68, 0.5);
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 6px;
    }
    .net-box-regen {
        background-color: rgba(34, 197, 94, 0.15);
        border: 1.5px solid rgba(34, 197, 94, 0.5);
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 6px;
    }
    .net-box-warn {
        background-color: rgba(245, 158, 11, 0.15);
        border: 1.5px solid rgba(245, 158, 11, 0.5);
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 6px;
    }
    .net-title {
        font-size: 9.5pt;
        font-weight: 800;
        color: #94a3b8;
        margin-bottom: 2px;
        text-transform: uppercase;
    }
    .net-title-evac {
        font-size: 9.5pt;
        font-weight: 800;
        color: #f87171;
        margin-bottom: 2px;
        text-transform: uppercase;
    }
    .net-title-regen {
        font-size: 9.5pt;
        font-weight: 800;
        color: #4ade80;
        margin-bottom: 2px;
        text-transform: uppercase;
    }
    .net-title-warn {
        font-size: 9.5pt;
        font-weight: 800;
        color: #fbbf24;
        margin-bottom: 2px;
        text-transform: uppercase;
    }
    .net-text {
        font-size: 11pt;
        color: #ffffff;
        font-weight: 600;
        line-height: 1.4;
    }
    .stButton > button {
        background-color: #111e38 !important;
        color: #ffffff !important;
        border: 2px solid #334155 !important;
        font-weight: 800 !important;
        border-radius: 10px !important;
        padding: 0.5rem 1rem !important;
        min-height: 48px !important;
        font-size: 11pt !important;
    }
    .stButton > button:hover {
        background-color: #38bdf8 !important;
        color: #050b18 !important;
        border-color: #38bdf8 !important;
    }
    [data-testid="stExpander"] {
        border: 1.5px solid #1e293b !important;
        border-radius: 10px !important;
        background-color: #111e38 !important;
        margin-bottom: 6px !important;
    }
    
    .note-card {
        background-color: #111e38;
        border: 1.5px solid #1e293b;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    .note-title {
        font-size: 12pt;
        font-weight: 800;
        color: #38bdf8;
    }
    </style>
""", unsafe_allow_html=True)

# Sprawdzenie komunikatów typu Toast po przeładowaniu strony
if "flash_toast" in st.session_state and st.session_state["flash_toast"]:
    st.toast(st.session_state["flash_toast"], icon="🧭")
    st.session_state["flash_toast"] = None

DOMEK_LAT = 35.5914
DOMEK_LON = 24.0918
SKLEP_LAT = 35.586222
SKLEP_LON = 24.091861

def init_db():
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS miejsca (
            numer_miejsca TEXT PRIMARY KEY,
            nazwa TEXT,
            nazwa_angielska TEXT,
            opis TEXT,
            wspolrzedne TEXT,
            typ TEXT,
            czas_dojazdu TEXT,
            godziny_otwarcia TEXT,
            najlepsza_pora TEXT,
            orientacyjny_czas TEXT,
            koszt TEXT,
            konieczna_akcja TEXT,
            zaplecze_gastro TEXT,
            ile_jedzenia TEXT,
            trudnosc_adhd TEXT,
            potencjal_meltdownu TEXT,
            strategie_meltdown TEXT,
            ochrona_slonce TEXT,
            najlepiej_polaczyc TEXT,
            zadania_dla_dzieci TEXT,
            odwiedzone INTEGER DEFAULT 0,
            Base TEXT DEFAULT 'false'
        )
    ''')

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
            odbyta INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notatki (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_wycieczki TEXT,
            id_miejsca TEXT,
            tytul TEXT,
            zawartosc TEXT NOT NULL,
            typ_notatki TEXT CHECK(typ_notatki IN ('text', 'link', 'list')) DEFAULT 'text',
            data_utworzenia TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_wycieczki) REFERENCES wycieczka(id) ON DELETE CASCADE,
            FOREIGN KEY (id_miejsca) REFERENCES miejsca(numer_miejsca) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS czat_historia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uzytkownik TEXT,
            rola TEXT,
            tresc TEXT,
            data_utworzenia TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS uzytkownik_ustawienia (
            uzytkownik TEXT PRIMARY KEY,
            api_key TEXT,
            dostawca_ai TEXT DEFAULT 'Google Gemini',
            model_ai TEXT DEFAULT 'gemini-3.1-flash-lite'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS krok_wycieczki (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_wycieczki TEXT,
            krok_wycieczki TEXT,
            nazwa TEXT,
            wspolrzedne TEXT,
            okienko_zwiedzania TEXT,
            godzina_ewakuacji TEXT,
            czerwona_strefa_ostrzezenie TEXT,
            strefa_luzu_i_regeneracji TEXT,
            podsumowanie_taktyki TEXT,
            potencjal_meltdownu TEXT,
            strategie_meltdown TEXT,
            opis TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS zakupy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_kroku INTEGER,
            nazwa_produktu TEXT NOT NULL,
            ilosc TEXT,
            kupione INTEGER DEFAULT 0,
            FOREIGN KEY (id_kroku) REFERENCES krok_wycieczki(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_wycieczki TEXT,
            typ TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checklist_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_checklisty INTEGER,
            nazwa TEXT,
            ilosc TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS aktywna_wycieczka (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            aktualne_id_wycieczki TEXT
        )
    ''')
    cursor.execute('INSERT OR IGNORE INTO aktywna_wycieczka (id, aktualne_id_wycieczki) VALUES (1, "1")')
    conn.commit()

    if os.path.exists("miejsca.csv"):
        try:
            df_csv = pd.read_csv("miejsca.csv", encoding="utf-8-sig")
        except:
            df_csv = pd.read_csv("miejsca.csv", encoding="cp1250")
            
        df_csv.columns = [c.strip() for c in df_csv.columns]
        
        for _, row in df_csv.iterrows():
            cursor.execute('''
                INSERT OR REPLACE INTO miejsca (
                    numer_miejsca, nazwa, nazwa_angielska, opis, wspolrzedne, typ,
                    czas_dojazdu, godziny_otwarcia, najlepsza_pora, orientacyjny_czas,
                    koszt, konieczna_akcja, zaplecze_gastro, ile_jedzenia, trudnosc_adhd,
                    potencjal_meltdownu, strategie_meltdown, ochrona_slonce, najlepiej_polaczyc, zadania_dla_dzieci, odwiedzone, Base
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'true')
            ''', (
                str(row.get('numer miejsca', '')),
                str(row.get('nazwa', '')),
                str(row.get('nazwa angielska', '')),
                str(row.get('Opis', '')),
                str(row.get('współrzędne', '')),
                str(row.get('typ', '')),
                str(row.get('czas dojazdu ze Stravros', '')),
                str(row.get('godziny otwarcia', '')),
                str(row.get('najlepsza pora zwiedzania', '')),
                str(row.get('orientacyjny czas zwiedzania', '')),
                str(row.get('koszt zwiedzania dla rodziny 2+2', '')),
                str(row.get('Konieczna akcja', '')),
                str(row.get('Zaplecze gastronomiczne', '')),
                str(row.get('Ile jedzenia', '')),
                str(row.get('Poziom trudności ADHD', '')),
                str(row.get('Potencjał meltdownu', '')),
                str(row.get('Strategie na meltdown', '')),
                str(row.get('Ochrona przed słońcem', '')),
                str(row.get('Najlepiej połączyć z', '')),
                str(row.get('Zadania dla dzieci', ''))
            ))
        conn.commit()

    cursor.execute('SELECT COUNT(*) FROM wycieczka')
    if cursor.fetchone()[0] == 0:
        domyslna_data = date.today().strftime("%Y-%m-%d")
        cursor.execute('''
            INSERT INTO wycieczka (id, tytul_wycieczki, calosciowy_opis_wycieczki, calosciowa_taktyka_dnia, calkowity_czas_wycieczki_godziny, szacowana_godzina_powrotu, pobudka, czas_wyjazdu, planowana_data, odbyta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        ''', (
            "1",
            "Mity i Oceaniczne Głębiny: Pałac w Knossos & Cretaquarium",
            "Wyprawa łącząca mityczną historię starożytnej Krety z podwodnym światem głębin w klimatyzowanym akwarium oraz relaksem nad jeziorem Kournas.",
            "Żelazna kontrola czasu rano w Knossos, obiad w Cretaquarium i popołudniowe wyciszenie nad jeziorem.",
            "12.0",
            "18:30",
            "07:00",
            "07:30",
            domyslna_data
        ))

        kroki_w1 = [
            ("1", "1", "Pałac w Knossos", "35.2980, 25.1631", "08:00 - 09:45", "09:45", "BEZWZGLĘDNIE EWAKUOWAĆ SIĘ PRZED 10:00! Tłumy i upał.", "Brak - rygor czasowy.", "Szybkie wejście na otwarcie o 8:00.", "Wysoki (tłumy, brak cienia, duchota)", "Użycie aplikacji 3D na iPadzie jako kotwica uwagi, szybka ewakuacja w razie buntu.", "Legendarna stolica minojskiej Krety z ruinami pałacu króla Minosa."),
            ("1", "2", "Cretaquarium", "35.3326, 25.2825", "10:10 - 12:00", "12:00", "Unikać godzin szczytu (11:00 - 15:00).", "Średnia - kawiarnia obok.", "Wyciszenie sensoryczne w klimatyzowanym półmroku.", "Średni (pogłos w betonowych halach, tłum)", "Słuchawki wygłuszające, powolne tempo, półmrok przy akwariach.", "Jedno z największych i najnowocześniejszych oceanariów w basenie Morza Śródziemnego.")
        ]
        cursor.executemany('''
            INSERT INTO krok_wycieczki (id_wycieczki, krok_wycieczki, nazwa, wspolrzedne, okienko_zwiedzania, godzina_ewakuacji, czerwona_strefa_ostrzezenie, strefa_luzu_i_regeneracji, podsumowanie_taktyki, potencjal_meltdownu, strategie_meltdown, opis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', kroki_w1)

        conn.commit()
    conn.close()

init_db()

# --- FUNKCJE ZARZĄDZANIA USTAWIENIAMI I KLUCZAMI API PER UŻYTKOWNIK ---
def pobierz_ustawienia_z_db(uzytkownik):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT api_key, dostawca_ai, model_ai FROM uzytkownik_ustawienia WHERE uzytkownik = ?', (uzytkownik,))
    res = cursor.fetchone()
    conn.close()
    if res:
        return res[0] or "", res[1] or "Google Gemini", res[2] or "gemini-3.1-flash-lite"
    return "", "Google Gemini", "gemini-3.1-flash-lite"

def zapisz_ustawienia_w_db(uzytkownik, api_key, dostawca_ai, model_ai):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO uzytkownik_ustawienia (uzytkownik, api_key, dostawca_ai, model_ai) 
        VALUES (?, ?, ?, ?)
    ''', (uzytkownik, api_key, dostawca_ai, model_ai))
    conn.commit()
    conn.close()

# --- FUNKCJE POBIERANIA POGODY (wttr.in) ORAZ OBEJŚCIE DLA ASYSTENTA AI ---
@st.cache_data(ttl=3600)
def pobierz_prognoze_pogody(lat, lon, data_docelowa):
    try:
        url = f"https://wttr.in/{lat},{lon}?format=j1"
        req = urllib.request.Request(url, headers={'User-Agent': 'CretAiApp/1.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            weather_list = data.get('weather', [])
            for day in weather_list:
                if day.get('date') == data_docelowa:
                    return day
            if weather_list:
                return weather_list[0]
    except:
        pass
    return None

def sprawdź_pogodę_w_locie(szerokosc_geograficzna, dlugosc_geograficzna, data_wspolrzedne="dzisiaj"):
    """Narzędzie dla asystenta AI pozwalające sprawdzić aktualną prognozę pogody online dla dowolnych współrzędnych."""
    try:
        lat = float(szerokosc_geograficzna)
        lon = float(dlugosc_geograficzna)
    except:
        return "Błąd: Niepoprawne współrzędne geograficzne."
    
    docelowa_data = str(data_wspolrzedne).strip()
    if docelowa_data.lower() in ["dzisiaj", "today", ""]:
        docelowa_data = date.today().strftime("%Y-%m-%d")

    prognoza = pobierz_prognoze_pogody(lat, lon, docelowa_data)
    if not prognoza:
        return f"Nie udało się pobrać pogody dla współrzędnych {lat}, {lon} na dzień {docelowa_data}."
    
    max_t = prognoza.get('maxtempC', 'brak')
    min_t = prognoza.get('mintempC', 'brak')
    hourly = prognoza.get('hourly', [])
    opis = "Brak szczegółów"
    if hourly:
        opis = hourly[0].get('weatherDesc', [{}])[0].get('value', 'Brak opisu')

    return f"Prognoza pogody dla współrzędnych ({lat}, {lon}) na dzień {docelowa_data}: Maks: {max_t}°C, Min: {min_t}°C, Stan: {opis}."

def renderuj_pogode_dla_kroku(wspolrzedne, planowana_data, okienko_czasowe):
    if not planowana_data or not str(planowana_data).strip():
        return
    
    try:
        parts = wspolrzedne.split(',')
        lat = float(parts[0].strip())
        lon = float(parts[1].strip())
    except:
        return

    prognoza_dnia = pobierz_prognoze_pogody(lat, lon, str(planowana_data))
    if not prognoza_dnia:
        return

    st.markdown(f"""
        <div style="background-color: rgba(56, 189, 248, 0.12); border: 1.5px solid rgba(56, 189, 248, 0.4); border-radius: 8px; padding: 10px; margin: 6px 0;">
            <div style="font-size: 9pt; font-weight: 800; color: #38bdf8; text-transform: uppercase; margin-bottom: 4px;">
                🌤️ Prognoza pogody ({planowana_data})
            </div>
    """, unsafe_allow_html=True)

    hourly_list = prognoza_dnia.get('hourly', [])
    
    target_hour = 12
    if okienko_czasowe and "-" in okienko_czasowe:
        try:
            start_str = okienko_czasowe.split("-")[0].strip()
            target_hour = int(start_str.split(":")[0])
        except:
            pass

    dopasowana_godzina = None
    min_diff = 999
    for h in hourly_list:
        try:
            time_val = int(h.get('time', '0')) // 100
            diff = abs(time_val - target_hour)
            if diff < min_diff:
                min_diff = diff
                dopasowana_godzina = h
        except:
            pass

    if dopasowana_godzina:
        temp = dopasowana_godzina.get('tempC', '—')
        feel = dopasowana_godzina.get('FeelsLikeC', '—')
        desc = dopasowana_godzina.get('weatherDesc', [{}])[0].get('value', 'Brak opisu')
        wind = dopasowana_godzina.get('windspeedKmph', '—')
        uv = dopasowana_godzina.get('uvIndex', '—')
        
        st.markdown(f"""
            <div style="font-size: 10.5pt; color: #ffffff; font-weight: 700; display: flex; justify-content: space-between; align-items: center;">
                <span><b>{temp}°C</b> (odczuwalna {feel}°C), {desc}</span>
                <span>💨 {wind} km/h | ☀️ UV {uv}</span>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

def renderuj_podsumowanie_pogody_wycieczki(kroki_df, planowana_data):
    if not planowana_data or not str(planowana_data).strip() or kroki_df.empty:
        return

    ostrzezenia = []
    max_temp = -99
    min_temp = 99
    opis_pogody_zbiorczy = set()

    for _, k in kroki_df.iterrows():
        coords = str(k['wspolrzedne'])
        if ',' in coords:
            try:
                parts = coords.split(',')
                lat = float(parts[0].strip())
                lon = float(parts[1].strip())
                prognoza = pobierz_prognoze_pogody(lat, lon, str(planowana_data))
                if prognoza and 'hourly' in prognoza:
                    for h in prognoza['hourly']:
                        t = int(h.get('tempC', 20))
                        if t > max_temp: max_temp = t
                        if t < min_temp: min_temp = t
                        desc = h.get('weatherDesc', [{}])[0].get('value', '').lower()
                        opis_pogody_zbiorczy.add(desc)
            except:
                pass

    for desc in opis_pogody_zbiorczy:
        if 'rain' in desc or 'deszcz' in desc or 'shower' in desc:
            ostrzezenia.append("🌧️ Prognozowane opady deszczu na trasie!")
        if 'storm' in desc or 'thunder' in desc or 'burza' in desc:
            ostrzezenia.append("⚡ Ryzyko burz na trasie wycieczki!")

    if max_temp >= 32:
        ostrzezenia.append(f"🔥 Ekstremalny upał! Maksymalna temperatura sięgnie {max_temp}°C. Bezwzględnie zadbaj o nawodnienie i ochronę przed słońcem.")

    st.markdown(f"""
        <div style="background-color: #111e38; border: 2.5px solid {'#ef4444' if ostrzezenia else '#38bdf8'}; border-radius: 12px; padding: 14px; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.4);">
            <div style="font-size: 10.5pt; font-weight: 900; color: {'#f87171' if ostrzezenia else '#38bdf8'}; margin-bottom: 6px; text-transform: uppercase;">
                📊 Podsumowanie pogody dla całej wycieczki ({planowana_data})
            </div>
            <div style="font-size: 10.5pt; color: #ffffff; font-weight: 700; margin-bottom: 6px;">
                Temperatury w przedziale: <b>{min_temp}°C do {max_temp}°C</b>
            </div>
    """, unsafe_allow_html=True)

    if ostrzezenia:
        for ost in ostrzezenia:
            st.markdown(f'<div style="color: #f87171; font-weight: 800; font-size: 10.5pt; margin-top: 4px;">{ost}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="color: #4ade80; font-weight: 800; font-size: 10.5pt;">✨ Brak ekstremów pogodowych. Warunki sprzyjające wyprawie!</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# --- FUNKCJE OBSŁUGI BAZY CZATU ---
def pobierz_historie_czatu_z_db(uzytkownik):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT rola, tresc FROM czat_historia WHERE uzytkownik = ? ORDER BY id ASC', (uzytkownik,))
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for rola, tresc in rows:
        raw_content = types.Content(role=rola, parts=[types.Part.from_text(text=tresc)])
        history.append({"role": rola, "content": tresc, "raw_content": raw_content})
    return history

def zapisz_wiadomosc_w_db(uzytkownik, rola, tresc):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO czat_historia (uzytkownik, rola, tresc) VALUES (?, ?, ?)', (uzytkownik, rola, tresc))
    conn.commit()
    conn.close()

def wyczysc_historie_czatu_w_db(uzytkownik):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM czat_historia WHERE uzytkownik = ?', (uzytkownik,))
    conn.commit()
    conn.close()

# --- FUNKCJE OBSŁUGI NOTATEK, MIEJSC, WYCIECZEK, KROKÓW I ZAKUPÓW (Z EDYCJĄ I OCHRONĄ BASE=TRUE) ---
def dodaj_notatke(zawartosc, typ_notatki='text', id_wycieczki=None, id_miejsca=None, tytul=None):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO notatki (id_wycieczki, id_miejsca, tytul, zawartosc, typ_notatki)
        VALUES (?, ?, ?, ?, ?)
    ''', (str(id_wycieczki) if id_wycieczki else None, str(id_miejsca) if id_miejsca else None, tytul, zawartosc, typ_notatki))
    conn.commit()
    conn.close()
    return "Dodano nową notatkę!"

def edytuj_notatke(notatka_id, zawartosc=None, tytul=None, typ_notatki=None):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    if zawartosc:
        cursor.execute('UPDATE notatki SET zawartosc = ? WHERE id = ?', (zawartosc, notatka_id))
    if tytul is not None:
        cursor.execute('UPDATE notatki SET tytul = ? WHERE id = ?', (tytul, notatka_id))
    if typ_notatki:
        cursor.execute('UPDATE notatki SET typ_notatki = ? WHERE id = ?', (typ_notatki, notatka_id))
    conn.commit()
    conn.close()
    return f"Zaktualizowano notatkę nr {notatka_id}."

def usun_notatke(notatka_id):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM notatki WHERE id = ?', (notatka_id,))
    conn.commit()
    conn.close()
    return f"Usunięto notatkę nr {notatka_id}."

def pobierz_notatki(id_wycieczki=None, id_miejsca=None):
    conn = sqlite3.connect('cretai.db')
    if id_wycieczki:
        df = pd.read_sql('SELECT * FROM notatki WHERE id_wycieczki = ?', conn, params=(str(id_wycieczki),))
    elif id_miejsca:
        df = pd.read_sql('SELECT * FROM notatki WHERE id_miejsca = ?', conn, params=(str(id_miejsca),))
    else:
        df = pd.DataFrame()
    conn.close()
    return df

def renderuj_sekcje_notatek(id_wycieczki=None, id_miejsca=None):
    st.markdown("---")
    st.markdown("### 📌 Notatki i Linki")
    
    df_notatki = pobierz_notatki(id_wycieczki=id_wycieczki, id_miejsca=id_miejsca)
    
    with st.expander("➕ Dodaj nową notatkę"):
        with st.form(key=f"form_add_note_{id_wycieczki}_{id_miejsca}", clear_on_submit=True):
            nt_tytul = st.text_input("Tytuł notatki (opcjonalnie)")
            nt_typ = st.selectbox(
                "Typ notatki", 
                options=["text", "link", "list"], 
                format_func=lambda x: {"text": "📝 Zwykły tekst", "link": "🔗 Link / URL", "list": "📋 Punkty listy"}[x]
            )
            nt_zawartosc = st.text_area("Treść / URL / Elementy (każdy w nowej linii)")
            submitted = st.form_submit_button("💾 Zapisz nową notatkę", use_container_width=True)
            if submitted and nt_zawartosc:
                dodaj_notatke(zawartosc=nt_zawartosc, typ_notatki=nt_typ, id_wycieczki=id_wycieczki, id_miejsca=id_miejsca, tytul=nt_tytul)
                st.session_state["flash_toast"] = "💾 Dodano nową notatkę!"
                st.rerun()

    if df_notatki.empty:
        st.markdown("<p style='color: #94a3b8; font-size: 10pt; font-style: italic;'>Brak notatek. Dodaj pierwszą powyżej, aby zapisać ważne wskazówki.</p>", unsafe_allow_html=True)
        return

    if "editing_note_id" not in st.session_state:
        st.session_state.editing_note_id = None

    for _, note in df_notatki.iterrows():
        note_id = note['id']
        tytul = note['tytul']
        zawartosc = note['zawartosc']
        typ = note['typ_notatki']
        
        is_editing_this = (st.session_state.editing_note_id == note_id)
        
        st.markdown(f'<div class="note-card">', unsafe_allow_html=True)
        
        col_t1, col_t2 = st.columns([5, 1])
        with col_t1:
            if tytul and str(tytul).strip():
                st.markdown(f'<div style="font-size: 11.5pt; font-weight: 800; color: #38bdf8; margin-bottom: 4px;">📌 {tytul}</div>', unsafe_allow_html=True)
        with col_t2:
            edit_icon = "❌" if is_editing_this else "✏️"
            subcol1, subcol2 = st.columns(2)
            with subcol1:
                if st.button(edit_icon, key=f"btn_toggle_edit_{note_id}", help="Edytuj"):
                    st.session_state.editing_note_id = None if is_editing_this else note_id
                    st.rerun()
            with subcol2:
                if st.button("🗑️", key=f"btn_del_{note_id}", help="Usuń"):
                    usun_notatke(note_id)
                    if st.session_state.editing_note_id == note_id:
                        st.session_state.editing_note_id = None
                    st.session_state["flash_toast"] = "🗑️ Usunięto notatkę!"
                    st.rerun()

        if tytul and str(tytul).strip():
            st.markdown("<hr style='border: none; border-top: 1px solid rgba(255,255,255,0.1); margin: 6px 0 8px 0;'>", unsafe_allow_html=True)

        if not is_editing_this:
            if typ == 'text':
                st.markdown(f"<div style='color: #ffffff; font-weight: 600; font-size: 10.5pt; line-height: 1.4; word-break: break-word;'>{zawartosc}</div>", unsafe_allow_html=True)
            elif typ == 'link':
                st.markdown(f'<a href="{zawartosc}" target="_blank" style="color: #38bdf8; text-decoration: underline; font-weight: 800; word-break: break-all; font-size: 10.5pt;">🔗 {zawartosc}</a>', unsafe_allow_html=True)
            elif typ == 'list':
                punkty = [p.strip() for p in zawartosc.split('\n') if p.strip()]
                for idx_p, punkt in enumerate(punkty):
                    st.checkbox(punkt, key=f"note_item_{note_id}_{idx_p}")
        else:
            with st.form(key=f"form_edit_note_{note_id}"):
                nowy_tytul_ed = st.text_input("Tytuł", value=tytul if tytul else "")
                nowa_tresc_ed = st.text_area("Treść", value=zawartosc)
                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.form_submit_button("💾 Zapisz", use_container_width=True):
                        edytuj_notatke(note_id, zawartosc=nowa_tresc_ed, tytul=nowy_tytul_ed)
                        st.session_state.editing_note_id = None
                        st.session_state["flash_toast"] = "💾 Zaktualizowano notatkę!"
                        st.rerun()
                with col_cancel:
                    if st.form_submit_button("Anuluj", use_container_width=True):
                        st.session_state.editing_note_id = None
                        st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

def dodaj_miejsce(
    numer_miejsca, nazwa, nazwa_angielska="", opis="", wspolrzedne="35.3,24.5", 
    typ="others", czas_dojazdu="30 min", godziny_otwarcia="08:00 - 20:00", 
    najlepsza_pora="Rano", orientacyjny_czas="1.5 godz.", koszt="Brak", 
    konieczna_akcja="Brak", zaplecze_gastro="Dostępne", ile_jedzenia="Woda", 
    trudnosc_adhd="Niski", potencjal_meltdownu="Niski", strategie_meltdown="Spokojne tempo", 
    ochrona_slonce="Czapka", najlepiej_polaczyc="Brak", zadania_dla_dzieci="Obserwacja"
):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT numer_miejsca FROM miejsca WHERE numer_miejsca = ?', (str(numer_miejsca),))
    if cursor.fetchone():
        conn.close()
        return f"OSTRZEŻENIE: Miejsce o numerze {numer_miejsca} już istnieje w bazie!"

    cursor.execute('''
        INSERT INTO miejsca (
            numer_miejsca, nazwa, nazwa_angielska, opis, wspolrzedne, typ,
            czas_dojazdu, godziny_otwarcia, najlepsza_pora, orientacyjny_czas,
            koszt, konieczna_akcja, zaplecze_gastro, ile_jedzenia, trudnosc_adhd,
            potencjal_meltdownu, strategie_meltdown, ochrona_slonce, najlepiej_polaczyc, zadania_dla_dzieci, odwiedzone, Base
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'false')
    ''', (
        str(numer_miejsca), str(nazwa), str(nazwa_angielska), str(opis), str(wspolrzedne), str(typ),
        str(czas_dojazdu), str(godziny_otwarcia), str(najlepsza_pora), str(orientacyjny_czas),
        str(koszt), str(konieczna_akcja), str(zaplecze_gastro), str(ile_jedzenia), str(trudnosc_adhd),
        str(potencjal_meltdownu), str(strategie_meltdown), str(ochrona_slonce), str(najlepiej_polaczyc), str(zadania_dla_dzieci)
    ))
    conn.commit()
    conn.close()
    return f"Pomyślnie dodano nowe miejsce nr {numer_miejsca} ({nazwa}) do bazy!"

def edytuj_miejsce(numer_miejsca, nazwa=None, opis=None, konieczna_akcja=None, koszt=None):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT Base FROM miejsca WHERE numer_miejsca = ?', (str(numer_miejsca),))
    res = cursor.fetchone()
    if res and str(res[0]).lower() == 'true':
        conn.close()
        return f"OSTRZEŻENIE: Miejsce nr {numer_miejsca} posiada flagę Base=true. Pełna edycja bazy bazowej jest zablokowana."

    if nazwa:
        cursor.execute('UPDATE miejsca SET nazwa = ? WHERE numer_miejsca = ?', (nazwa, str(numer_miejsca)))
    if opis:
        cursor.execute('UPDATE miejsca SET opis = ? WHERE numer_miejsca = ?', (opis, str(numer_miejsca)))
    if konieczna_akcja:
        cursor.execute('UPDATE miejsca SET konieczna_akcja = ? WHERE numer_miejsca = ?', (konieczna_akcja, str(numer_miejsca)))
    if koszt:
        cursor.execute('UPDATE miejsca SET koszt = ? WHERE numer_miejsca = ?', (koszt, str(numer_miejsca)))
    conn.commit()
    conn.close()
    return f"Miejsce nr {numer_miejsca} zostało zaktualizowane."

def usun_miejsce(numer_miejsca):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT Base FROM miejsca WHERE numer_miejsca = ?', (str(numer_miejsca),))
    res = cursor.fetchone()
    if res and str(res[0]).lower() == 'true':
        conn.close()
        return f"OSTRZEŻENIE: Miejsce nr {numer_miejsca} posiada flagę Base=true i jest chronione przed usunięciem!"
    
    cursor.execute('DELETE FROM miejsca WHERE numer_miejsca = ?', (str(numer_miejsca),))
    conn.commit()
    conn.close()
    return f"Miejsce nr {numer_miejsca} zostało usunięte."

def edytuj_wycieczke(id, tytul_wycieczki=None, calosciowy_opis_wycieczki=None, calosciowa_taktyka_dnia=None, szacowana_godzina_powrotu=None, pobudka=None, czas_wyjazdu=None, planowana_data=None):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    if tytul_wycieczki:
        cursor.execute('UPDATE wycieczka SET tytul_wycieczki = ? WHERE id = ?', (tytul_wycieczki, str(id)))
    if calosciowy_opis_wycieczki:
        cursor.execute('UPDATE wycieczka SET calosciowy_opis_wycieczki = ? WHERE id = ?', (calosciowy_opis_wycieczki, str(id)))
    if calosciowa_taktyka_dnia:
        cursor.execute('UPDATE wycieczka SET calosciowa_taktyka_dnia = ? WHERE id = ?', (calosciowa_taktyka_dnia, str(id)))
    if szacowana_godzina_powrotu:
        cursor.execute('UPDATE wycieczka SET szacowana_godzina_powrotu = ? WHERE id = ?', (szacowana_godzina_powrotu, str(id)))
    if pobudka:
        cursor.execute('UPDATE wycieczka SET pobudka = ? WHERE id = ?', (pobudka, str(id)))
    if czas_wyjazdu:
        cursor.execute('UPDATE wycieczka SET czas_wyjazdu = ? WHERE id = ?', (czas_wyjazdu, str(id)))
    if planowana_data is not None:
        cursor.execute('UPDATE wycieczka SET planowana_data = ? WHERE id = ?', (planowana_data, str(id)))
    conn.commit()
    conn.close()
    return f"Wycieczka #{id} została zaktualizowana."

def dodaj_krok_wycieczki(
    id_wycieczki, krok_wycieczki, nazwa, wspolrzedne="35.3,24.5", 
    okienko_zwiedzania="10:00 - 12:00", godzina_ewakuacji="12:00", 
    czerwona_strefa_ostrzezenie="Unikać upału", strefa_luzu_i_regeneracji="Cień", 
    podsumowanie_taktyki="Spokojne tempo", potencjal_meltdownu="Średni", 
    strategie_meltdown="Okulary i woda", opis="Brak opisu"
):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO krok_wycieczki (
            id_wycieczki, krok_wycieczki, nazwa, wspolrzedne, okienko_zwiedzania, 
            godzina_ewakuacji, czerwona_strefa_ostrzezenie, 
            strefa_luzu_i_regeneracji, podsumowanie_taktyki, potencjal_meltdownu, 
            strategie_meltdown, opis
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        str(id_wycieczki), str(krok_wycieczki), str(nazwa), str(wspolrzedne), 
        str(okienko_zwiedzania), str(godzina_ewakuacji), str(czerwona_strefa_ostrzezenie), 
        str(strefa_luzu_i_regeneracji), str(podsumowanie_taktyki), str(potencjal_meltdownu), 
        str(strategie_meltdown), str(opis)
    ))
    conn.commit()
    conn.close()
    return f"Dodano krok nr {krok_wycieczki} ({nazwa}) do wycieczki #{id_wycieczki}!"

def edytuj_krok_wycieczki(id_wycieczki, krok_wycieczki, nazwa=None, okienko_zwiedzania=None, godzina_ewakuacji=None, czerwona_strefa_ostrzezenie=None, podsumowanie_taktyki=None, opis=None):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM krok_wycieczki WHERE id_wycieczki = ? AND (krok_wycieczki = ? OR nazwa LIKE ?)', (str(id_wycieczki), str(krok_wycieczki), f"%{krok_wycieczki}%"))
    res = cursor.fetchone()
    if not res:
        conn.close()
        return f"Nie znaleziono kroku wycieczki."
    krok_row_id = res[0]
    if nazwa:
        cursor.execute('UPDATE krok_wycieczki SET nazwa = ? WHERE id = ?', (nazwa, krok_row_id))
    if okienko_zwiedzania:
        cursor.execute('UPDATE krok_wycieczki SET okienko_zwiedzania = ? WHERE id = ?', (okienko_zwiedzania, krok_row_id))
    if godzina_ewakuacji:
        cursor.execute('UPDATE krok_wycieczki SET godzina_ewakuacji = ? WHERE id = ?', (godzina_ewakuacji, krok_row_id))
    if czerwona_strefa_ostrzezenie:
        cursor.execute('UPDATE krok_wycieczki SET czerwona_strefa_ostrzezenie = ? WHERE id = ?', (czerwona_strefa_ostrzezenie, krok_row_id))
    if podsumowanie_taktyki:
        cursor.execute('UPDATE krok_wycieczki SET podsumowanie_taktyki = ? WHERE id = ?', (podsumowanie_taktyki, krok_row_id))
    if opis:
        cursor.execute('UPDATE krok_wycieczki SET opis = ? WHERE id = ?', (opis, krok_row_id))
    conn.commit()
    conn.close()
    return f"Zaktualizowano krok wycieczki."

def usun_krok_wycieczki(id_wycieczki, krok_wycieczki):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM krok_wycieczki WHERE id_wycieczki = ? AND (krok_wycieczki = ? OR nazwa LIKE ?)', (str(id_wycieczki), str(krok_wycieczki), f"%{krok_wycieczki}%"))
    conn.commit()
    conn.close()
    return f"Usunięto krok z wycieczki."

def pobierz_zakupy_dla_kroku(id_kroku):
    conn = sqlite3.connect('cretai.db')
    df = pd.read_sql('SELECT * FROM zakupy WHERE id_kroku = ?', conn, params=(str(id_kroku),))
    conn.close()
    return df

def dodaj_produkt_zakupow(id_kroku, nazwa_produktu, ilosc="1"):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO zakupy (id_kroku, nazwa_produktu, ilosc, kupione)
        VALUES (?, ?, ?, 0)
    ''', (str(id_kroku), nazwa_produktu, str(ilosc)))
    conn.commit()
    conn.close()
    return f"Dodano produkt '{nazwa_produktu}' do listy zakupów kroku."

def edytuj_produkt_zakupow(zakup_id, nazwa_produktu=None, ilosc=None):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    if nazwa_produktu:
        cursor.execute('UPDATE zakupy SET nazwa_produktu = ? WHERE id = ?', (nazwa_produktu, zakup_id))
    if ilosc:
        cursor.execute('UPDATE zakupy SET ilosc = ? WHERE id = ?', (ilosc, zakup_id))
    conn.commit()
    conn.close()
    return f"Zaktualizowano produkt zakupowy."

def zmien_status_zakupu(zakup_id, kupione):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE zakupy SET kupione = ? WHERE id = ?', (1 if kupione else 0, zakup_id))
    conn.commit()
    conn.close()

def usun_produkt_zakupow(zakup_id):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM zakupy WHERE id = ?', (zakup_id,))
    conn.commit()
    conn.close()

def pobierz_wszystkie_miejsca():
    conn = sqlite3.connect('cretai.db')
    df = pd.read_sql('SELECT * FROM miejsca', conn)
    conn.close()
    return df

def pobierz_aktywna_wycieczke_id():
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT aktualne_id_wycieczki FROM aktywna_wycieczka WHERE id = 1')
    res = cursor.fetchone()
    conn.close()
    return str(res[0]) if res else "1"

def ustaw_aktywna_wycieczke_id(wycieczka_id):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE aktywna_wycieczka SET aktualne_id_wycieczki = ? WHERE id = 1', (str(wycieczka_id),))
    conn.commit()
    conn.close()

def pobierz_skrocone_opcje_wycieczek():
    conn = sqlite3.connect('cretai.db')
    df_w = pd.read_sql('SELECT id, tytul_wycieczki FROM wycieczka WHERE odbyta = 0', conn)
    conn.close()
    if df_w.empty:
        return []
    opcje = []
    for _, row in df_w.iterrows():
        wid = str(row['id'])
        pelny = str(row['tytul_wycieczki'])
        skrocony = pelny.split(':')[0] if ':' in pelny else pelny
        if len(skrocony) > 35:
            skrocony = skrocony[:35] + "..."
        opcje.append(f"{wid}. {skrocony}")
    return opcje

def wczytaj_kontekst_zewnetrzny():
    tekst = f"Jesteś asystentem podróży CretAi na Kretę.\n"
    tekst += f"- Lokalizacja naszego DOMEK (baza wypadowa): {DOMEK_LAT}, {DOMEK_LON}\n"
    tekst += f"- Lokalizacja SKLEP obok domku: {SKLEP_LAT}, {SKLEP_LON}\n"
    tekst += "--- BAZA DANYCH SQLITE ---\n"
    conn = sqlite3.connect('cretai.db')
    try:
        miejsca_df = pd.read_sql('SELECT numer_miejsca, nazwa, typ, czas_dojazdu, orientacyjny_czas, koszt, konieczna_akcja, odwiedzone, Base FROM miejsca', conn)
        wycieczki_df = pd.read_sql('SELECT id, tytul_wycieczki, calosciowy_opis_wycieczki, calosciowa_taktyka_dnia, planowana_data, odbyta FROM wycieczka', conn)
        kroki_df = pd.read_sql('SELECT id, id_wycieczki, krok_wycieczki, nazwa, okienko_zwiedzania FROM krok_wycieczki', conn)
        zakupy_df = pd.read_sql('SELECT id, id_kroku, nazwa_produktu, ilosc, kupione FROM zakupy', conn)
        notatki_df = pd.read_sql('SELECT id, id_wycieczki, id_miejsca, tytul, zawartosc, typ_notatki FROM notatki', conn)
    except:
        miejsca_df = pd.DataFrame()
        wycieczki_df = pd.DataFrame()
        kroki_df = pd.DataFrame()
        zakupy_df = pd.DataFrame()
        notatki_df = pd.DataFrame()
    conn.close()

    if not miejsca_df.empty:
        tekst += "Miejsca:\n"
        for _, r in miejsca_df.iterrows():
            tekst += f"- Nr {r['numer_miejsca']}: {r['nazwa']} (Typ: {r['typ']}, Odwiedzone: {r['odwiedzone']}, Dojazd: {r['czas_dojazdu']}, Base: {r['Base']})\n"
    if not wycieczki_df.empty:
        tekst += "\nWycieczki:\n"
        for _, w in wycieczki_df.iterrows():
            if int(w.get('odbyta', 0)) == 1:
                continue
            tekst += f"- Wycieczka #{w['id']}: {w['tytul_wycieczki']} | Data: {w.get('planowana_data', 'brak')} | Opis: {w['calosciowy_opis_wycieczki']}\n"
    if not kroki_df.empty:
        tekst += "\nMapa Kroków Wycieczek (ID kroku w bazie, ID wycieczki, Nazwa):\n"
        for _, k in kroki_df.iterrows():
            tekst += f"- Krok DB_ID: {k['id']} (Wycieczka #{k['id_wycieczki']}, Numer kroku: {k['krok_wycieczki']}): {k['nazwa']}\n"
    if not zakupy_df.empty:
        tekst += "\nZakupy zaplanowane na trasie:\n"
        for _, z in zakupy_df.iterrows():
            tekst += f"- ID Zakupu {z['id']} (Krok DB_ID {z['id_kroku']}): {z['nazwa_produktu']} (ilość: {z['ilosc']}, kupione: {z['kupione']})\n"
    if not notatki_df.empty:
        tekst += "\nNotatki użytkownika:\n"
        for _, n in notatki_df.iterrows():
            t_tytul = f"[{n['tytul']}] " if pd.notna(n['tytul']) and str(n['tytul']).strip() != "" else ""
            tekst += f"- ID {n['id']}: {t_tytul}{n['zawartosc']}\n"

    return tekst

def pobierz_trase_osrm(punkty):
    if len(punkty) < 2:
        return []
    wsp_str = ";".join([f"{p[1]},{p[0]}" for p in punkty])
    url = f"http://router.project-osrm.org/route/v1/driving/{wsp_str}?overview=full&geometries=geojson"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'CretAiApp/1.0'})
        with urllib.request.urlopen(req, timeout=2) as response:
            data = json.loads(response.read().decode())
            if 'routes' in data and len(data['routes']) > 0:
                geojson_coords = data['routes'][0]['geometry']['coordinates']
                return [[c[1], c[0]] for c in geojson_coords]
    except:
        pass
    return [[p[0], p[1]] for p in punkty]

def dodaj_marker_domku(m):
    domek_icon_html = '<div style="background-color:#38bdf8;color:#050b18;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:14px;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.4);">🏠</div>'
    domek_icon = folium.DivIcon(html=domek_icon_html, icon_size=(28, 28), icon_anchor=(14, 14))
    folium.Marker([DOMEK_LAT, DOMEK_LON], icon=domek_icon, tooltip="Nasz Domek").add_to(m)

# --- NARZĘDZIA AI (FUNCTIONS DLA GEMINI WRAZ Z FUNKCJĄ POGODOWĄ W LOCIE) ---
dodaj_notatke_tool = types.FunctionDeclaration(
    name="dodaj_notatke",
    description="Dodaje nową notatkę, link lub listę do wycieczki lub miejsca.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "zawartosc": types.Schema(type=types.Type.STRING, description="Treść notatki, URL lub elementy listy"),
            "typ_notatki": types.Schema(type=types.Type.STRING, description="Typ: 'text', 'link' lub 'list'"),
            "id_wycieczki": types.Schema(type=types.Type.STRING, description="Opcjonalne ID wycieczki"),
            "id_miejsca": types.Schema(type=types.Type.STRING, description="Opcjonalny numer miejsca"),
            "tytul": types.Schema(type=types.Type.STRING, description="Tytuł notatki"),
        },
        required=["zawartosc"]
    ),
)

edytuj_notatke_tool = types.FunctionDeclaration(
    name="edytuj_notatke",
    description="Edytuje treść lub tytuł istniejącej notatki.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "notatka_id": types.Schema(type=types.Type.INTEGER, description="ID notatki do edycji"),
            "zawartosc": types.Schema(type=types.Type.STRING, description="Nowa treść notatki"),
            "tytul": types.Schema(type=types.Type.STRING, description="Nowy tytuł notatki"),
        },
        required=["notatka_id"]
    ),
)

usun_notatke_tool = types.FunctionDeclaration(
    name="usun_notatke",
    description="Usuwa wskazaną notatkę po jej ID.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "notatka_id": types.Schema(type=types.Type.INTEGER, description="ID notatki do usunięcia"),
        },
        required=["notatka_id"]
    ),
)

edytuj_miejsce_tool = types.FunctionDeclaration(
    name="edytuj_miejsce",
    description="Edytuje dane miejsca w bazie (z uwzględnieniem ochrony Base=true).",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "numer_miejsca": types.Schema(type=types.Type.STRING, description="Numer miejsca"),
            "nazwa": types.Schema(type=types.Type.STRING, description="Nowa nazwa"),
            "opis": types.Schema(type=types.Type.STRING, description="Nowy opis"),
            "konieczna_akcja": types.Schema(type=types.Type.STRING, description="Nowa konieczna akcja"),
            "koszt": types.Schema(type=types.Type.STRING, description="Nowy koszt"),
        },
        required=["numer_miejsca"]
    ),
)

usun_miejsce_tool = types.FunctionDeclaration(
    name="usun_miejsce",
    description="Usuwa miejsce z bazy, pod warunkiem że nie posiada flagi Base=true (chronione).",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "numer_miejsca": types.Schema(type=types.Type.STRING, description="Numer miejsca do usunięcia"),
        },
        required=["numer_miejsca"]
    ),
)

edytuj_wycieczke_tool = types.FunctionDeclaration(
    name="edytuj_wycieczke",
    description="Edytuje parametry wycieczki, w tym planowaną datę (format RRRR-MM-DD).",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id": types.Schema(type=types.Type.STRING),
            "tytul_wycieczki": types.Schema(type=types.Type.STRING),
            "planowana_data": types.Schema(type=types.Type.STRING, description="Planowana data w formacie RRRR-MM-DD"),
        },
        required=["id"]
    ),
)

dodaj_zakup_tool = types.FunctionDeclaration(
    name="dodaj_produkt_zakupow",
    description="Dodaje nowy produkt do checklisty zakupowej powiązanej z konkretnym krokiem wycieczki.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id_kroku": types.Schema(type=types.Type.STRING, description="ID kroku wycieczki"),
            "nazwa_produktu": types.Schema(type=types.Type.STRING, description="Nazwa produktu zakupowego"),
            "ilosc": types.Schema(type=types.Type.STRING, description="Ilość lub opakowanie, np. '2 szt', '1 litr'"),
        },
        required=["id_kroku", "nazwa_produktu"]
    ),
)

edytuj_zakup_tool = types.FunctionDeclaration(
    name="edytuj_produkt_zakupow",
    description="Edytuje produkt lub ilość na liście zakupów.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "zakup_id": types.Schema(type=types.Type.INTEGER, description="ID pozycji zakupowej"),
            "nazwa_produktu": types.Schema(type=types.Type.STRING, description="Nowa nazwa produktu"),
            "ilosc": types.Schema(type=types.Type.STRING, description="Nowa ilość"),
        },
        required=["zakup_id"]
    ),
)

usun_zakup_tool = types.FunctionDeclaration(
    name="usun_produkt_zakupow",
    description="Usuwa produkt z listy zakupów.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "zakup_id": types.Schema(type=types.Type.INTEGER, description="ID pozycji zakupowej do usunięcia"),
        },
        required=["zakup_id"]
    ),
)

dodaj_krok_wycieczki_tool = types.FunctionDeclaration(
    name="dodaj_krok_wycieczki",
    description="Dodaje nowy krok (punkt programu) do wskazanej wycieczki.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki (np. '1' lub '2')"),
            "krok_wycieczki": types.Schema(type=types.Type.STRING, description="Numer kolejny kroku (np. '3')"),
            "nazwa": types.Schema(type=types.Type.STRING, description="Nazwa miejsca / kroku"),
            "wspolrzedne": types.Schema(type=types.Type.STRING, description="Współrzędne GPS (np. '35.2980, 25.1631')"),
            "okienko_zwiedzania": types.Schema(type=types.Type.STRING, description="Godziny np. '10:00 - 12:00'"),
            "opis": types.Schema(type=types.Type.STRING, description="Krótki opis"),
        },
        required=["id_wycieczki", "krok_wycieczki", "nazwa"]
    ),
)

edytuj_krok_wycieczki_tool = types.FunctionDeclaration(
    name="edytuj_krok_wycieczki",
    description="Edytuje parametry istniejącego kroku wycieczki.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
            "krok_wycieczki": types.Schema(type=types.Type.STRING, description="Numer lub nazwa kroku"),
            "nazwa": types.Schema(type=types.Type.STRING, description="Nowa nazwa"),
            "okienko_zwiedzania": types.Schema(type=types.Type.STRING, description="Nowy harmonogram"),
            "godzina_ewakuacji": types.Schema(type=types.Type.STRING, description="Nowa godzina ewakuacji"),
            "czerwona_strefa_ostrzezenie": types.Schema(type=types.Type.STRING, description="Nowe ostrzeżenie"),
            "podsumowanie_taktyki": types.Schema(type=types.Type.STRING, description="Nowa taktyka"),
            "opis": types.Schema(type=types.Type.STRING, description="Nowy opis"),
        },
        required=["id_wycieczki", "krok_wycieczki"]
    ),
)

usun_krok_wycieczki_tool = types.FunctionDeclaration(
    name="usun_krok_wycieczki",
    description="Usuwa wskazany krok z wycieczki.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
            "krok_wycieczki": types.Schema(type=types.Type.STRING, description="Numer lub nazwa kroku do usunięcia"),
        },
        required=["id_wycieczki", "krok_wycieczki"]
    ),
)

sprawdz_pogode_w_locie_tool = types.FunctionDeclaration(
    name="sprawdz_pogode_w_locie",
    description="Pobiera aktualną prognozę pogody online dla podanych współrzędnych i daty w formacie RRRR-MM-DD.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "szerokosc_geograficzna": types.Schema(type=types.Type.STRING, description="Szerokość geograficzna np. '35.2980'"),
            "dlugosc_geograficzna": types.Schema(type=types.Type.STRING, description="Długość geograficzna np. '25.1631'"),
            "data_wspolrzedne": types.Schema(type=types.Type.STRING, description="Data w formacie RRRR-MM-DD lub słowo 'dzisiaj'"),
        },
        required=["szerokosc_geograficzna", "dlugosc_geograficzna"]
    ),
)

cretai_tools = types.Tool(function_declarations=[
    dodaj_notatke_tool, edytuj_notatke_tool, usun_notatke_tool, 
    edytuj_miejsce_tool, usun_miejsce_tool, edytuj_wycieczke_tool, 
    dodaj_zakup_tool, edytuj_zakup_tool, usun_zakup_tool, 
    dodaj_krok_wycieczki_tool, edytuj_krok_wycieczki_tool, usun_krok_wycieczki_tool,
    sprawdz_pogode_w_locie_tool
])

def wykonaj_narzedzie_bazy(call_name, args):
    if call_name == "dodaj_notatke":
        return dodaj_notatke(**args)
    elif call_name == "edytuj_notatke":
        return edytuj_notatke(**args)
    elif call_name == "usun_notatke":
        return usun_notatke(**args)
    elif call_name == "edytuj_miejsce":
        return edytuj_miejsce(**args)
    elif call_name == "usun_miejsce":
        return usun_miejsce(**args)
    elif call_name == "edytuj_wycieczke":
        return edytuj_wycieczke(**args)
    elif call_name == "dodaj_produkt_zakupow":
        return dodaj_produkt_zakupow(**args)
    elif call_name == "edytuj_produkt_zakupow":
        return edytuj_produkt_zakupow(**args)
    elif call_name == "usun_produkt_zakupow":
        return usun_produkt_zakupow(**args)
    elif call_name == "dodaj_krok_wycieczki":
        return dodaj_krok_wycieczki(**args)
    elif call_name == "edytuj_krok_wycieczki":
        return edytuj_krok_wycieczki(**args)
    elif call_name == "usun_krok_wycieczki":
        return usun_krok_wycieczki(**args)
    elif call_name == "sprawdz_pogode_w_locie":
        return sprawdź_pogodę_w_locie(**args)
    return "Wykonano."

# --- W PANELU BOCZNYM: WYBÓR UŻYTKOWNIKA, DOSTAWCY AI I KLUCZA ---
with st.sidebar:
    st.markdown("### 👤 Profil Użytkownika")
    dostepni_uzytkownicy = ["Rodzic 1", "Rodzic 2", "Rodzic 3", "Rodzic 4"]
    aktualny_uzytkownik = st.selectbox("Wybierz swój profil", options=dostepni_uzytkownicy, index=0)
    st.markdown("---")
    
    st.header("⚙️ Ustawienia Asystenta")
    
    zapisany_klucz, zapisany_dostawca, zapisany_model = pobierz_ustawienia_z_db(aktualny_uzytkownik)
    
    dostawcy_ai = ["Google Gemini", "Anthropic Claude"]
    dostawca_index = dostawcy_ai.index(zapisany_dostawca) if zapisany_dostawca in dostawcy_ai else 0
    wybrany_dostawca = st.selectbox("Wybierz dostawcę AI", options=dostawcy_ai, index=dostawca_index)
    
    if wybrany_dostawca == "Google Gemini":
        dostepne_modele = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.6-flash"]
    else:
        dostepne_modele = ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"]
    
    model_index = dostepne_modele.index(zapisany_model) if zapisany_model in dostepne_modele else 0
    wybrany_model = st.selectbox("Wybierz model AI", options=dostepne_modele, index=model_index)
    
    klucz_label = f"Klucz API ({wybrany_dostawca})"
    api_key_input = st.text_input(klucz_label, value=zapisany_klucz, type="password", key=f"api_key_{aktualny_uzytkownik}")
    
    if api_key_input != zapisany_klucz or wybrany_dostawca != zapisany_dostawca or wybrany_model != zapisany_model:
        zapisz_ustawienia_w_db(aktualny_uzytkownik, api_key_input, wybrany_dostawca, wybrany_model)

    st.markdown("---")
    st.markdown("### 🧭 Szybka Nawigacja")
    st.markdown(f"""
        <div class="custom-nav-bar">
            <a href="https://www.google.com/maps/search/?api=1&query={SKLEP_LAT},{SKLEP_LON}" target="_blank" class="custom-nav-btn" title="Sklep"><span>🛒</span><span>Sklep</span></a>
            <a href="https://www.google.com/maps/search/?api=1&query={DOMEK_LAT},{DOMEK_LON}" target="_blank" class="custom-nav-btn" title="Domek"><span>🏠</span><span>Domek</span></a>
        </div>
    """, unsafe_allow_html=True)

# --- GLOBALNY, PŁYWAJĄCY ASYSTENT AI ---
def renderuj_globalny_czat_ai(uzytkownik):
    st.markdown('<div class="floating-ai-container">', unsafe_allow_html=True)
    
    with st.expander(f"💬 Asystent AI ({uzytkownik}) [{wybrany_dostawca}]", expanded=False):
        col_h1, col_h2, col_h3 = st.columns([3, 1, 1])
        with col_h1:
            st.markdown(f"<span style='font-size: 9.5pt; color: #38bdf8; font-weight: 800;'>🧠 TRYB ADHD • {uzytkownik}</span>", unsafe_allow_html=True)
        with col_h2:
            if st.button("🔄 Odśwież", key=f"btn_refresh_{uzytkownik}", use_container_width=True, help="Odśwież widok aplikacji"):
                st.session_state["flash_toast"] = "🔄 Widok został odświeżony!"
                st.rerun()
        with col_h3:
            if st.button("🗑️ Nowy", key=f"btn_new_chat_{uzytkownik}", use_container_width=True, help="Wyczyść historię"):
                wyczysc_historie_czatu_w_db(uzytkownik)
                st.session_state["flash_toast"] = "🗑️ Historia czatu wyczyszczona."
                st.rerun()

        if not api_key_input:
            st.warning(f"Wprowadź swój klucz API dla {wybrany_dostawca} w menu bocznym.")
            st.markdown('</div>', unsafe_allow_html=True)
            return

        dzisiaj_str = date.today().strftime("%Y-%m-%d")
        zewnetrzny_kontekst = wczytaj_kontekst_zewnetrzny()
        
        system_prompt = f"""Jesteś inteligentnym asystentem podróży CretAi na Kretę, pomagającym rodzicom dzieci z ADHD.
Dzisiejsza data to: {dzisiaj_str}.
{zewnetrzny_kontekst}
- Masz na stałe wgląd w lokalizację domku ({DOMEK_LAT}, {DOMEK_LON}) oraz sklepu obok domku ({SKLEP_LAT}, {SKLEP_LON}).
- Masz do dyspozycji funkcję `sprawdz_pogode_w_locie` w swoich narzędziach, dzięki której możesz odpytywać serwis pogodowy o aktualne warunki online. Korzystaj z niej, gdy użytkownik pyta o pogodę!
- Pamiętaj o żelaznej zasadzie: miejsca z flagą Base=true są bezwzględnie chronione i nie wolno ich usuwać ani modyfikować ich flag bazowych.
- Zawsze przed edycją lub usunięciem kroku, zapoznaj się z mapą ID kroków w kontekście bazy, aby upewnić się, że operujesz na właściwym kroku.
- Pamiętaj o pełnej kontroli czasu, ewakuacji przed upałem i redukcji stresu."""

        chat_historia_z_db = pobierz_historie_czatu_z_db(uzytkownik)

        chat_container = st.container(height=240)
        ostatnia_wiadomosc_modelu = ""
        with chat_container:
            for message in chat_historia_z_db:
                role = message["role"]
                content = message["content"]
                if role == "model":
                    ostatnia_wiadomosc_modelu = content if isinstance(content, str) else "".join([p.text for p in content.parts if hasattr(p, "text") and p.text])
                
                with st.chat_message(role):
                    if isinstance(content, str):
                        st.markdown(content)
                    elif hasattr(content, "parts"):
                        for p in content.parts:
                            if hasattr(p, "text") and p.text:
                                st.markdown(p.text)

        if ostatnia_wiadomosc_modelu:
            czysty_tekst = json.dumps(ostatnia_wiadomosc_modelu)
            st.components.v1.html(f"""
                <div style="text-align: right; margin-bottom: 6px;">
                    <button onclick="navigator.clipboard.writeText({czysty_tekst}); alert('Skopiowano ostatnią odpowiedź do schowka!');" 
                            style="background-color: #111e38; color: #38bdf8; border: 1.5px solid #38bdf8; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 800; cursor: pointer;">
                        📋 Kopiuj ostatnią odpowiedź
                    </button>
                </div>
            """, height=35)

        prompt = st.chat_input(f"Pytanie do AI ({uzytkownik})...", key=f"chat_input_{uzytkownik}")
        if prompt:
            zapisz_wiadomosc_w_db(uzytkownik, "user", prompt)
            
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    assistant_reply = ""
                    try:
                        if wybrany_dostawca == "Google Gemini":
                            client = genai.Client(api_key=api_key_input)
                            aktualna_historia_db = pobierz_historie_czatu_z_db(uzytkownik)
                            contents = [item["raw_content"] for item in aktualna_historia_db if "raw_content" in item]
                            if not contents:
                                contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]

                            response = client.models.generate_content(
                                model=wybrany_model,
                                contents=contents,
                                config=types.GenerateContentConfig(
                                    tools=[cretai_tools],
                                    system_instruction=system_prompt
                                )
                            )

                            candidate = response.candidates[0] if response.candidates else None
                            has_fc = False
                            if candidate and candidate.content and candidate.content.parts:
                                for p in candidate.content.parts:
                                    if p.function_call:
                                        has_fc = True
                                        break

                            if has_fc or response.function_calls:
                                model_content = candidate.content
                                calls = response.function_calls if response.function_calls else [p.function_call for p in model_content.parts if p.function_call]
                                
                                for call in calls:
                                    args = call.args
                                    call_name = call.name
                                    wynik_bazy = wykonaj_narzedzie_bazy(call_name, args)
                                    
                                    follow_up = client.models.generate_content(
                                        model=wybrany_model,
                                        contents=contents + [
                                            model_content,
                                            types.Content(role="user", parts=[types.Part.from_function_response(name=call_name, response={"result": wynik_bazy})])
                                        ],
                                        config=types.GenerateContentConfig(tools=[cretai_tools])
                                    )
                                    fu_cand = follow_up.candidates[0] if follow_up.candidates else None
                                    if fu_cand and fu_cand.content and fu_cand.content.parts:
                                        text_parts = [p.text for p in fu_cand.content.parts if hasattr(p, "text") and p.text]
                                        assistant_reply = "".join(text_parts) if text_parts else "Operacja zakończona."
                                    else:
                                        assistant_reply = "Zaktualizowano bazę."
                            else:
                                text_parts = [p.text for p in candidate.content.parts if hasattr(p, "text") and p.text] if candidate and candidate.content and candidate.content.parts else []
                                assistant_reply = "".join(text_parts) if text_parts else (response.text if hasattr(response, "text") else "Brak odpowiedzi.")

                        else:  # --- ANTHROPIC CLAUDE ---
                            if not ANTHROPIC_AVAILABLE:
                                assistant_reply = "Błąd: Pakiet `anthropic` nie jest zainstalowany."
                            else:
                                client_c = anthropic.Anthropic(api_key=api_key_input)
                                claude_messages = []
                                conn = sqlite3.connect('cretai.db')
                                cursor = conn.cursor()
                                cursor.execute('SELECT rola, tresc FROM czat_historia WHERE uzytkownik = ? ORDER BY id ASC', (uzytkownik,))
                                rows = cursor.fetchall()
                                conn.close()
                                
                                for rola, tresc in rows:
                                    c_role = "user" if rola == "user" else "assistant"
                                    claude_messages.append({"role": c_role, "content": tresc})

                                response = client_c.messages.create(
                                    model=wybrany_model,
                                    max_tokens=2048,
                                    system=system_prompt,
                                    messages=claude_messages
                                )
                                text_blocks = [block.text for block in response.content if hasattr(block, "text")]
                                assistant_reply = "".join(text_blocks)

                        zapisz_wiadomosc_w_db(uzytkownik, "model", assistant_reply)
                    except Exception as e:
                        assistant_reply = f"Błąd komunikacji z AI: {e}"
                        zapisz_wiadomosc_w_db(uzytkownik, "model", assistant_reply)

                    st.markdown(assistant_reply)
                    st.session_state["flash_toast"] = "✨ Asystent odpowiedział!"
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

if "tab" in st.query_params:
    st.session_state.active_tab = st.query_params["tab"]
elif "active_tab" not in st.session_state:
    st.session_state.active_tab = "zabytek"

if "place" in st.query_params:
    st.session_state.active_place_id = st.query_params["place"]
    st.session_state.active_tab = "zabytek"

if "active_place_id" not in st.session_state:
    st.session_state.active_place_id = None

COLORS = {
    'must have': '#f43f5e',
    'nice to have': '#fb923c',
    'others': '#38bdf8',
    'activity': '#facc15',
    'shop': '#4ade80',
    'plaża': '#22d3ee'
}
DEFAULT_COLOR = '#ef4444'

df_miejsca = pobierz_wszystkie_miejsca()
wycieczki_options = pobierz_skrocone_opcje_wycieczek()

def renderuj_zadania_dzieci_expander(tekst_zadan, unikalny_klucz):
    zadania_lista = [z.strip() for z in str(tekst_zadan).split('.') if z.strip()]
    if not zadania_lista:
        zadania_lista = [str(tekst_zadan)]
    for i, zadanie in enumerate(zadania_lista):
        st.checkbox(f"{zadanie}", key=f"zad_dziecko_exp_{unikalny_klucz}_{i}")

def renderuj_karty_meltdown_ux(p):
    adhd_val = p.get('trudnosc_adhd', 'Niski')
    meltdown_val = p.get('potencjal_meltdownu', 'Brak danych')
    strategie_val = p.get('strategie_meltdown', 'Brak strategii')

    is_high_risk = "wysok" in str(meltdown_val).lower()
    
    st.markdown("---")
    if is_high_risk:
        st.error("**🚨 STREFA RATUNKOWA ADHD & MELTDOWN**")
    else:
        st.info("**🛡️ STREFA RATUNKOWA ADHD & MELTDOWN**")
        
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**🧠 Trudność ADHD:**\n{adhd_val}")
    with col2:
        st.markdown(f"**⚡ Potencjał meltdownu:**\n{meltdown_val}")
        
    st.success(f"**🛡️ Natychmiastowa Strategia Ratunkowa:**\n{strategie_val}")

def renderuj_karte_wycieczki(wycieczka_id, pokaz_mape=True, pokaz_pogode=False):
    conn = sqlite3.connect('cretai.db')
    wycieczka_row = pd.read_sql('SELECT * FROM wycieczka WHERE id = ?', conn, params=(str(wycieczka_id),))
    # Poprawione sortowanie: alfanumeryczne lub po dacie/czasie rozpoczęcia okienka
    kroki_df = pd.read_sql('SELECT * FROM krok_wycieczki WHERE id_wycieczki = ? ORDER BY okienko_zwiedzania ASC', conn, params=(str(wycieczka_id),))
    conn.close()
    
    if not wycieczka_row.empty:
        w_gen = wycieczka_row.iloc[0]
        tytul_w = str(w_gen['tytul_wycieczki'])
        planowana_data_val = w_gen.get('planowana_data', '')
        if not pd.notna(planowana_data_val):
            planowana_data_val = ""
        
        st.markdown(f"""
        <div style="background-color:#111e38; padding:12px; border:2.5px solid #38bdf8; border-radius:12px; text-align:center; font-size:12pt; font-weight:900; text-transform:uppercase; margin-bottom:10px; color:#38bdf8; box-shadow: 0 4px 12px rgba(56,189,248,0.2);">
            {tytul_w}
        </div>
        """, unsafe_allow_html=True)

        with st.form(key=f"form_plan_data_{wycieczka_id}"):
            st.markdown(f'<div style="font-size: 9.5pt; font-weight: 800; color: #94a3b8; text-transform: uppercase; margin-bottom: 4px;">📅 Planowana data wycieczki</div>', unsafe_allow_html=True)
            
            dzisiaj = date.today()
            try:
                parsed_date = datetime.strptime(planowana_data_val, "%Y-%m-%d").date() if planowana_data_val else dzisiaj
                if parsed_date < dzisiaj:
                    parsed_date = dzisiaj
            except:
                parsed_date = dzisiaj

            col_input, col_btn = st.columns([2, 1])
            with col_input:
                nowa_data_input = st.date_input("Planowana data", value=parsed_date, min_value=dzisiaj, key=f"date_input_{wycieczka_id}", label_visibility="collapsed")
            with col_btn:
                if st.form_submit_button("💾 Zapisz", use_container_width=True):
                    if nowa_data_input < dzisiaj:
                        st.error("Nie można wybrać daty z przeszłości!")
                    else:
                        str_data = nowa_data_input.strftime("%Y-%m-%d")
                        edytuj_wycieczke(wycieczka_id, planowana_data=str_data)
                        st.session_state["flash_toast"] = f"📅 Zapisano datę wycieczki: {str_data}"
                        st.rerun()

        if pokaz_pogode:
            renderuj_podsumowanie_pogody_wycieczki(kroki_df, planowana_data_val)

        if pokaz_mape:
            punkty_trasy = [(DOMEK_LAT, DOMEK_LON)]
            surowe_wspolrzedne = [(DOMEK_LAT, DOMEK_LON)]
            
            for _, k in kroki_df.iterrows():
                coords = str(k['wspolrzedne'])
                if ',' in coords:
                    try:
                        parts = coords.split(',')
                        lat = float(parts[0].strip())
                        lon = float(parts[1].strip())
                        punkty_trasy.append((lat, lon, str(k['krok_wycieczki']), str(k['nazwa'])))
                        surowe_wspolrzedne.append((lat, lon))
                    except:
                        pass
            surowe_wspolrzedne.append((DOMEK_LAT, DOMEK_LON))

            if len(punkty_trasy) > 1:
                srodek_lat = sum([p[0] for p in punkty_trasy]) / len(punkty_trasy)
                srodek_lon = sum([p[1] for p in punkty_trasy]) / len(punkty_trasy)
                
                m_trasa = folium.Map(location=[srodek_lat, srodek_lon], zoom_start=10, tiles="CartoDB dark_matter")
                dodaj_marker_domku(m_trasa)
                
                for p in punkty_trasy:
                    if len(p) == 4:
                        lat, lon, krok, nazwa = p
                        icon_html = f'<div style="background-color:#38bdf8;color:#050b18;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:900;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.4);">{krok}</div>'
                        icon = folium.DivIcon(html=icon_html, icon_size=(28, 28), icon_anchor=(14, 14))
                        folium.Marker([lat, lon], icon=icon, tooltip=f"Krok {krok}: {nazwa}").add_to(m_trasa)
                    
                trasa_po_drogach = pobierz_trase_osrm(surowe_wspolrzedne)
                if trasa_po_drogach:
                    folium.PolyLine(trasa_po_drogach, color="#38bdf8", weight=5, opacity=0.9).add_to(m_trasa)
                    
                st_folium(m_trasa, width="100%", height=240, returned_objects=[])

            st.markdown("---")

        pobudka_val = w_gen.get('pobudka', '07:00') if pd.notna(w_gen.get('pobudka')) else '07:00'
        wyjazd_val = w_gen.get('czas_wyjazdu', '07:30') if pd.notna(w_gen.get('czas_wyjazdu')) else '07:30'
        powrot_val = w_gen.get('szacowana_godzina_powrotu', '17:00')
        czas_trwania = f"{w_gen['calkowity_czas_wycieczki_godziny']} godz."

        st.markdown(f"""
        <div style="background-color:#111e38; border:1.5px solid #1e293b; border-radius:10px; padding:12px; margin-bottom:10px;">
            <div style="font-size:10pt; font-weight:800; color:#38bdf8; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
                <span>🧭</span> LOGISTYKA DNIA
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                <div class="logistics-card">
                    <div class="logistics-title">⏰ Pobudka</div>
                    <div class="logistics-value">{pobudka_val}</div>
                </div>
                <div class="logistics-card">
                    <div class="logistics-title">🚗 Wyjazd</div>
                    <div class="logistics-value">{wyjazd_val}</div>
                </div>
                <div class="logistics-card">
                    <div class="logistics-title">🏠 Powrót</div>
                    <div class="logistics-value">{powrot_val}</div>
                </div>
                <div class="logistics-card">
                    <div class="logistics-title">⏱️ Czas trwania</div>
                    <div class="logistics-value">{czas_trwania}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if pd.notna(w_gen['calosciowy_opis_wycieczki']) and str(w_gen['calosciowy_opis_wycieczki']).strip() != "":
            st.markdown(f"""
            <div style="background-color:#111e38; border:1.5px solid #1e293b; border-radius:10px; padding:12px; margin-bottom:10px;">
                <div style="font-size:10pt; font-weight:800; color:#38bdf8; margin-bottom:4px;">📝 Cel wycieczki</div>
                <div style="color:#ffffff; font-weight:600; font-size:10.5pt; line-height:1.4;">{w_gen['calosciowy_opis_wycieczki']}</div>
            </div>
            """, unsafe_allow_html=True)

        if pd.notna(w_gen['calosciowa_taktyka_dnia']) and str(w_gen['calosciowa_taktyka_dnia']).strip() != "":
            st.markdown(f"""
            <div style="background-color:#111e38; padding:12px; border:1.5px solid #1e293b; border-radius:10px; margin-bottom:10px;">
                <span style="font-size:10pt; font-weight:800; color:#38bdf8;">🧠 TAKTYKA DNIA:</span><br>
                <span style="color:#ffffff; font-weight:600; font-size:10.5pt; line-height:1.4;">{w_gen['calosciowa_taktyka_dnia']}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<h3>Szczegółowy plan</h3>", unsafe_allow_html=True)
        
        for _, k in kroki_df.iterrows():
            krok_num = str(k['krok_wycieczki'])
            krok_nazwa = str(k['nazwa'])
            okienko = str(k.get('okienko_zwiedzania', ''))
            krok_row_id = k['id']
            
            pasujące_miejsce = df_miejsca[df_miejsca['numer_miejsca'] == krok_num]
            miejsce_id_cel = str(pasujące_miejsce.iloc[0]['numer_miejsca']) if not pasujące_miejsce.empty else "1"
            
            google_search_url = f"https://www.google.com/search?q={krok_nazwa} Kreta"
            gps_maps_url = f"https://www.google.com/maps/search/?api=1&query={k['wspolrzedne']}"
            coords_clean = str(k['wspolrzedne']).replace(" ", "")
            sklep_maps_url = f"https://www.google.com/maps/search/supermarket/@{coords_clean},15z"
            resto_maps_url = f"https://www.google.com/maps/search/restaurant/@{coords_clean},15z"

            warn_html = f'<div class="net-box-warn"><div class="net-title-warn">⚠️ Ostrzeżenie</div><div class="net-text" style="color:#fbbf24; font-weight:800;">{k["czerwona_strefa_ostrzezenie"]}</div></div>' if pd.notna(k.get('czerwona_strefa_ostrzezenie')) and str(k['czerwona_strefa_ostrzezenie']).strip() != "" else ""
            desc_html = f'<div style="margin-top: 6px; background-color:rgba(255,255,255,0.05); border:1.5px solid #1e293b; border-radius:8px; padding:10px; font-size:10.5pt; color:#ffffff; font-weight:600; line-height:1.4;">{k["opis"]}</div>' if pd.notna(k.get('opis')) and str(k.get('opis')).strip() != "" else ""

            tytul_expandera = f"🕒 {okienko}  |  📌 {krok_nazwa}" if okienko else f"📌 {krok_nazwa}"

            with st.expander(tytul_expandera):
                if pokaz_pogode and planowana_data_val:
                    renderuj_pogode_dla_kroku(k['wspolrzedne'], planowana_data_val, okienko)

                card_html = f'''<div style="background-color:#111e38; padding:4px;"><div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;"><div style="background-color:#f43f5e; color:white; border-radius:50%; width:26px; height:26px; display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:10pt;">{krok_num}</div><span style="font-size:11.5pt; font-weight:900; color:#38bdf8;">{krok_nazwa}</span></div>{desc_html}<div style="display: flex; gap: 6px; margin-top: 10px; margin-bottom: 10px;"><a href="{gps_maps_url}" target="_blank" class="custom-nav-btn" style="padding:6px 0;" title="GPS"><span>📍</span><span>GPS</span></a><a href="{google_search_url}" target="_blank" class="custom-nav-btn" style="padding:6px 0;" title="Google"><span>🔍</span><span>Google</span></a><a href="{sklep_maps_url}" target="_blank" class="custom-nav-btn" style="padding:6px 0;" title="Sklep"><span>🛒</span><span>Sklep</span></a><a href="{resto_maps_url}" target="_blank" class="custom-nav-btn" style="padding:6px 0;" title="Restauracja"><span>🍽️</span><span>Resto</span></a><a href="?tab=zabytek&place={miejsce_id_cel}" target="_self" class="custom-nav-btn" style="padding:6px 0;" title="Opis"><span>📝</span><span>Opis</span></a></div><div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 8px;"><div class="net-box" style="margin-bottom:0;"><div class="net-title">⏱️ Harmonogram</div><div style="font-size:11pt; font-weight:900; color:#ffffff;">{k["okienko_zwiedzania"]}</div></div><div class="net-box-evac" style="margin-bottom:0;"><div class="net-title-evac">🚨 Ewakuacja</div><div style="font-size:11pt; font-weight:900; color:#f87171;">{k.get("godzina_ewakuacji", "Brak")}</div></div></div><div class="net-box"><div class="net-title">🎯 Taktyka</div><div class="net-text">{k["podsumowanie_taktyki"]}</div></div><div class="net-box-regen" style="margin-bottom:0;"><div class="net-title-regen">🌿 Regeneracja</div><div class="net-text" style="color:#4ade80; font-weight:800;">{k["strefa_luzu_i_regeneracji"]}</div></div>{warn_html}</div>'''
                st.markdown(card_html, unsafe_allow_html=True)

                # ROZWIJANE MENU: CHECKLISTA ZAKUPÓW W TYM MIEJSCU
                df_zakupy_kroku = pobierz_zakupy_dla_kroku(krok_row_id)
                with st.expander("🛒 Checklista zakupów w tym miejscu"):
                    with st.form(key=f"form_add_zakup_{krok_row_id}", clear_on_submit=True):
                        st.markdown('<div style="font-size: 9pt; font-weight: 800; color: #94a3b8; margin-bottom: 2px;">PRODUKT I ILOŚĆ</div>', unsafe_allow_html=True)
                        col_z1, col_z2 = st.columns([3, 1])
                        with col_z1:
                            nowy_prod = st.text_input("Nowy produkt", placeholder="np. Woda, owoce", label_visibility="collapsed")
                        with col_z2:
                            nowa_il = st.text_input("Ilość", value="1", placeholder="Ilość", label_visibility="collapsed")
                        
                        if st.form_submit_button("➕ Dodaj zakup", use_container_width=True):
                            if nowy_prod.strip():
                                dodaj_produkt_zakupow(krok_row_id, nowy_prod.strip(), nowa_il.strip())
                                st.session_state["flash_toast"] = "🛒 Dodano produkt do zakupów!"
                                st.rerun()

                    if df_zakupy_kroku.empty:
                        st.markdown("<p style='color: #94a3b8; font-size: 9.5pt; font-style: italic;'>Brak zakupów zaplanowanych w tym miejscu.</p>", unsafe_allow_html=True)
                    else:
                        for _, z in df_zakupy_kroku.iterrows():
                            z_id = z['id']
                            z_nazwa = z['nazwa_produktu']
                            z_ilosc = z['ilosc']
                            z_kupione = bool(z['kupione'])
                            
                            col_chk, col_del = st.columns([5, 1])
                            with col_chk:
                                etykieta_z = f"{z_nazwa} (*{z_ilosc}*)" if z_ilosc and z_ilosc != "1" else z_nazwa
                                stan_checkboxa = st.checkbox(etykieta_z, value=z_kupione, key=f"chk_zakup_{z_id}")
                                if stan_checkboxa != z_kupione:
                                    zmien_status_zakupu(z_id, stan_checkboxa)
                                    st.rerun()
                            with col_del:
                                if st.button("🗑️", key=f"del_zakup_{z_id}", help="Usuń produkt"):
                                    usun_produkt_zakupow(z_id)
                                    st.session_state["flash_toast"] = "🗑️ Usunięto produkt!"
                                    st.rerun()

        renderuj_sekcje_notatek(id_wycieczki=wycieczka_id)

active_zabytek = "active" if st.session_state.active_tab == "zabytek" else ""
active_map = "active" if st.session_state.active_tab == "map" else ""
active_route = "active" if st.session_state.active_tab == "route" else ""

st.markdown(f"""
    <div class="bottom-nav-container">
        <a href="?tab=zabytek" target="_self" class="bottom-nav-btn {active_zabytek}"><span>🏛️</span><span>Miejsca</span></a>
        <a href="?tab=map" target="_self" class="bottom-nav-btn {active_map}"><span>🗺️</span><span>Wycieczki</span></a>
        <a href="?tab=route" target="_self" class="bottom-nav-btn {active_route}"><span>🚗</span><span>Aktualna Wycieczka</span></a>
    </div>
""", unsafe_allow_html=True)

if st.session_state.active_tab == "zabytek":
    logo_b64 = ""
    if os.path.exists("logo.png"):
        with open("logo.png", "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode("utf-8")

    logo_img_tag = f'<img src="data:image/png;base64,{logo_b64}" style="width:42px;height:42px;border-radius:8px;object-fit:cover;">' if logo_b64 else '<div style="font-size:26px;">🧭</div>'

    st.markdown(f"""
        <div class="adventure-header">
            {logo_img_tag}
            <div>
                <div class="adventure-title-text">CretAi • Kreta</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 🗺️ Nasze miejsca")
    
    df_miejsca_sorted = df_miejsca.copy()
    df_miejsca_sorted['sort_key'] = pd.to_numeric(df_miejsca_sorted['numer_miejsca'], errors='coerce')
    df_miejsca_sorted = df_miejsca_sorted.sort_values(by=['sort_key', 'numer_miejsca']).drop(columns=['sort_key'])

    miejsca_opcje_lista = [f"{r['numer_miejsca']}. {r['nazwa']}" for _, r in df_miejsca_sorted.iterrows()]
    
    def aktualizuj_wybrane_miejsce():
        wybrany_tekst = st.session_state.selected_place_sb
        if wybrany_tekst:
            wybrany_num = wybrany_tekst.split(".")[0].strip()
            st.session_state.active_place_id = wybrany_num
        else:
            st.session_state.active_place_id = None

    current_selection_index = None
    if st.session_state.active_place_id:
        match_idx = [i for i, opt in enumerate(miejsca_opcje_lista) if opt.startswith(f"{st.session_state.active_place_id}.")]
        if match_idx:
            current_selection_index = match_idx[0] + 1

    selected_option = st.selectbox(
        "Wybierz miejsce:", 
        options=[None] + miejsca_opcje_lista,
        index=current_selection_index,
        format_func=lambda x: "🌐 Pokaż całą mapę (wybierz miejsce...)" if x is None else x,
        key="selected_place_sb", 
        on_change=aktualizuj_wybrane_miejsce,
        label_visibility="collapsed"
    )

    map_lat, map_lon, map_zoom = 35.3, 24.5, 9
    if st.session_state.active_place_id:
        active_row = df_miejsca[df_miejsca['numer_miejsca'] == str(st.session_state.active_place_id)]
        if not active_row.empty:
            coords_str = str(active_row.iloc[0]['wspolrzedne'])
            if ',' in coords_str:
                try:
                    parts = coords_str.split(',')
                    map_lat = float(parts[0].strip())
                    map_lon = float(parts[1].strip())
                    map_zoom = 14
                except:
                    pass

    m = folium.Map(location=[map_lat, map_lon], zoom_start=map_zoom, tiles="CartoDB dark_matter")
    dodaj_marker_domku(m)

    for _, row in df_miejsca.iterrows():
        coords = str(row['wspolrzedne'])
        if ',' in coords:
            try:
                parts = coords.split(',')
                lat = float(parts[0].strip())
                lon = float(parts[1].strip())
                name = row['nazwa']
                num = str(row['numer_miejsca'])
                typ_raw = str(row.get('typ', '')).strip().lower()
                is_visited = int(row.get('odwiedzone', 0)) == 1
                bg_color = '#475569' if is_visited else COLORS.get(typ_raw, DEFAULT_COLOR)
                
                icon_html = f'<div style="background-color:{bg_color};color:white;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:900;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.4);">{num}</div>'
                icon = folium.DivIcon(html=icon_html, icon_size=(28, 28), icon_anchor=(14, 14))
                folium.Marker([lat, lon], icon=icon, tooltip=f"{num}. {name}").add_to(m)
            except:
                pass

    map_data = st_folium(m, width="100%", height=300)

    if map_data and map_data.get("last_object_clicked_tooltip"):
        clicked_tooltip = map_data["last_object_clicked_tooltip"]
        if "." in clicked_tooltip:
            clicked_id = clicked_tooltip.split(".")[0].strip()
            if clicked_id.isdigit() and clicked_id != st.session_state.active_place_id:
                st.session_state.active_place_id = clicked_id
                st.rerun()

    st.markdown("---")

    if st.session_state.active_place_id:
        place_row = df_miejsca[df_miejsca['numer_miejsca'] == str(st.session_state.active_place_id)]
        
        if not place_row.empty:
            p = place_row.iloc[0]
            numer_m = str(p['numer_miejsca'])
            tytul_miejsca = f"{numer_m}. {str(p['nazwa']).upper()}"
            google_search_url = f"https://www.google.com/search?q={p['nazwa']} Kreta"
            
            st.markdown(f"""
            <div id="selected-place-details" style="background-color: #111e38; border: 2.5px solid #38bdf8; border-radius: 14px; padding: 14px; margin-bottom: 12px; box-shadow: 0 4px 15px rgba(56,189,248,0.3);">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                    <span style="font-size: 13.5pt; font-weight: 900; color: #38bdf8;">{tytul_miejsca}</span>
                    <a href="{google_search_url}" target="_blank" style="text-decoration: none; font-size: 16px; background-color: #1e293b; border: 1.5px solid #334155; border-radius: 50%; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; color: #ffffff;" title="Szukaj w Google">🔍</a>
                </div>
            """, unsafe_allow_html=True)

            is_visited = int(p.get('odwiedzone', 0)) == 1
            if is_visited:
                st.markdown("""
                <div style="text-align: center; margin-bottom: 8px;">
                    <span style="background-color: rgba(34,197,94,0.15); color: #4ade80; padding: 4px 12px; border-radius: 10px; font-weight: 800; border: 1.5px solid rgba(34,197,94,0.5); font-size: 10pt;">
                        ✨ Odwiedzone
                    </span>
                </div>
                """, unsafe_allow_html=True)

            for ekst in ['.jpg', '.jpeg', '.png']:
                sciezka_zdjecia = os.path.join("zdjecia", f"{numer_m}{ekst}")
                if os.path.exists(sciezka_zdjecia):
                    st.image(sciezka_zdjecia, caption=f"{p['nazwa']}")
                    break
            
            if pd.notna(p['opis']) and str(p['opis']).strip() != "":
                st.info(p['opis'])

            coords_clean = str(p['wspolrzedne']).replace(" ", "") if pd.notna(p['wspolrzedne']) else "35.3,24.5"
            gps_maps_url = f"https://www.google.com/maps/search/?api=1&query={coords_clean}"

            st.markdown(f"""
                <div style="display: flex; align-items: center; justify-content: space-between; margin: 12px 0 10px 0;">
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <div style="background-color: #38bdf8; color: #050b18; border-radius: 50%; width: 26px; height: 26px; display: flex; align-items:center; justify-content:center; font-size: 12px; font-weight: 900;">📍</div>
                        <span style="font-size: 10pt; font-weight: 800; color: #94a3b8; text-transform: uppercase;">Lokalizacja GPS</span>
                    </div>
                    <a href="{gps_maps_url}" target="_blank" style="background-color: #38bdf8; color: #050b18; padding: 6px 14px; border-radius: 16px; font-size: 10pt; font-weight: 900; text-decoration: none; box-shadow: 0 2px 8px rgba(56,189,248,0.4);">NAWIGUJ ➔</a>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                    <div style="background-color: #050b18; border: 1.5px solid #1e293b; border-radius: 10px; padding: 10px;">
                        <div style="font-size: 9pt; font-weight: 800; color: #94a3b8; text-transform: uppercase; margin-bottom: 2px;">Dojazd (Stravros)</div>
                        <div style="font-size: 11pt; font-weight: 900; color: #ffffff;">{p['czas_dojazdu']}</div>
                    </div>
                    <div style="background-color: #050b18; border: 1.5px solid #1e293b; border-radius: 10px; padding: 10px;">
                        <div style="font-size: 9pt; font-weight: 800; color: #94a3b8; text-transform: uppercase; margin-bottom: 2px;">Godziny otwarcia</div>
                        <div style="font-size: 11pt; font-weight: 900; color: #ffffff;">{p['godziny_otwarcia']}</div>
                    </div>
                    <div style="background-color: #050b18; border: 1.5px solid #1e293b; border-radius: 10px; padding: 10px;">
                        <div style="font-size: 9pt; font-weight: 800; color: #94a3b8; text-transform: uppercase; margin-bottom: 2px;">Najlepsza pora</div>
                        <div style="font-size: 10.5pt; font-weight: 900; color: #ffffff;">{p['najlepsza_pora']}</div>
                    </div>
                    <div style="background-color: #050b18; border: 1.5px solid #1e293b; border-radius: 10px; padding: 10px;">
                        <div style="font-size: 9pt; font-weight: 800; color: #94a3b8; text-transform: uppercase; margin-bottom: 2px;">Czas zwiedzania</div>
                        <div style="font-size: 11pt; font-weight: 900; color: #ffffff;">{p['orientacyjny_czas']}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            koszt_val = p.get('koszt', '')
            if pd.notna(koszt_val) and str(koszt_val).strip() != "":
                st.markdown(f"""
                <div style="background-color: #111e38; border: 1.5px solid #1e293b; border-radius: 10px; padding: 12px; margin-bottom: 10px; display: flex; align-items: flex-start; gap: 8px;">
                    <div style="font-size: 18px;">💶👥</div>
                    <div>
                        <div style="font-size: 9pt; font-weight: 800; color: #94a3b8; text-transform: uppercase; margin-bottom: 2px;">Koszt dla rodziny 2+2:</div>
                        <div style="font-size: 11pt; color: #ffffff; font-weight: 800;">{koszt_val}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            akcja_val = p.get('konieczna_akcja', '')
            if pd.notna(akcja_val) and str(akcja_val).strip() != "Brak" and str(akcja_val).strip() != "":
                st.markdown(f"""
                <div style="background-color: rgba(239,68,68,0.15); border: 1.5px solid rgba(239,68,68,0.5); border-radius: 10px; padding: 12px; margin-bottom: 10px; display: flex; align-items: flex-start; gap: 8px;">
                    <div style="font-size: 18px;">⚠️</div>
                    <div>
                        <div style="font-size: 9pt; font-weight: 800; color: #f87171; text-transform: uppercase; margin-bottom: 2px;">Konieczna akcja</div>
                        <div style="font-size: 11pt; color: #ffffff; font-weight: 800;">{akcja_val}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            renderuj_karty_meltdown_ux(p)
            
            if pd.notna(p['zadania_dla_dzieci']) and str(p['zadania_dla_dzieci']).strip() != "":
                with st.expander("🧒 Zadania dla dzieci w tym miejscu"):
                    renderuj_zadania_dzieci_expander(p['zadania_dla_dzieci'], p['numer_miejsca'])
            
            polaczenie_tekst = str(p['najlepiej_polaczyc'])
            def zamien_na_link(match):
                nr_miejsca = match.group(1)
                return f'<a href="?tab=zabytek&place={nr_miejsca}" target="_self" style="color: #38bdf8; font-weight: 900; text-decoration: underline;">Miejsce {nr_miejsca}</a>'
            
            polaczenie_przetworzone = re.sub(r'Miejsce\s+(\d+)', zamien_na_link, polaczenie_tekst, flags=re.IGNORECASE)
            st.markdown(f"**🔗 Najlepiej połączyć z:** {polaczenie_przetworzone}", unsafe_allow_html=True)

            renderuj_sekcje_notatek(id_miejsca=numer_m)

elif st.session_state.active_tab == "map":
    st.markdown("""
        <div class="adventure-header">
            <div style="font-size:26px;">🗺️</div>
            <div>
                <div class="adventure-title-text">CretAi • Wycieczki i Trasy</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    opcje_wycieczek_lista = ["-- Wybierz wycieczkę lub zobacz mapę wszystkich miejsc --"] + wycieczki_options
    wybrana_mapa_sb = st.selectbox("", options=opcje_wycieczek_lista, key="map_wycieczka_select", label_visibility="collapsed")
    
    if wybrana_mapa_sb == "-- Wybierz wycieczkę lub zobacz mapę wszystkich miejsc --":
        m_all = folium.Map(location=[35.3, 24.5], zoom_start=9, tiles="CartoDB dark_matter")
        dodaj_marker_domku(m_all)
        
        for _, row in df_miejsca.iterrows():
            coords = str(row['wspolrzedne'])
            if ',' in coords:
                try:
                    parts = coords.split(',')
                    lat = float(parts[0].strip())
                    lon = float(parts[1].strip())
                    name = row['nazwa']
                    num = str(row['numer_miejsca'])
                    typ_raw = str(row.get('typ', '')).strip().lower()
                    is_visited = int(row.get('odwiedzone', 0)) == 1
                    bg_color = '#475569' if is_visited else COLORS.get(typ_raw, DEFAULT_COLOR)
                    
                    icon_html = f'<div style="background-color:{bg_color};color:white;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:900;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.4);">{num}</div>'
                    icon = folium.DivIcon(html=icon_html, icon_size=(28, 28), icon_anchor=(14, 14))
                    folium.Marker([lat, lon], icon=icon, tooltip=f"{num}. {name}").add_to(m_all)
                except:
                    pass
        
        st_folium(m_all, width="100%", height=340)
    else:
        if wybrana_mapa_sb:
            wybrana_id = wybrana_mapa_sb.split(". ")[0]
            st.markdown("---")
            renderuj_karte_wycieczki(wybrana_id, pokaz_mape=True, pokaz_pogode=False)

elif st.session_state.active_tab == "route":
    st.markdown("""
        <div class="adventure-header">
            <div style="font-size:26px;">🚗</div>
            <div>
                <div class="adventure-title-text">CretAi • Trasa Dnia</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    aktualne_id = pobierz_aktywna_wycieczke_id()
    
    conn = sqlite3.connect('cretai.db')
    curr_w_check = pd.read_sql('SELECT odbyta FROM wycieczka WHERE id = ?', conn, params=(str(aktualne_id),))
    conn.close()
    
    if not curr_w_check.empty and int(curr_w_check.iloc[0]['odbyta']) == 1:
        st.info("✨ Aktualnie ustawiona wycieczka została ukończona.")
    else:
        renderuj_karte_wycieczki(aktualne_id, pokaz_mape=False, pokaz_pogode=True)

renderuj_globalny_czat_ai(aktualny_uzytkownik)
