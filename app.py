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

# Próba zaimportowania Anthropic SDK dla Claude'a
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# --- 1. KONFIGURACJA STRONY I DESIGN SYSTEM: SAGE & TERRACOTTA TIMELINE ---
st.set_page_config(page_title="CretAi - Kreta", layout="centered", page_icon="🧭")

st.markdown("""
<style>
/* OCZYSZCZENIE GÓRNEJ BELKI STREAMLIT */
header[data-testid="stHeader"] {
    background-color: transparent !important;
    box-shadow: none !important;
}
[data-testid="stHeaderActionElements"] {
    display: none !important; 
}

/* BAZA MOTYWU OLIVE/CREAM */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 140px !important;
    max-width: 540px;
}
.stApp {
    background-color: #B4C29D !important;
    color: #2F241D !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

/* PASEK BOCZNY - DOPASOWANY STYL I KOLORYSTYKA */
[data-testid="stSidebar"] {
    background-color: #F6F0DD !important;
    border-right: 1.5px solid #E2DEC8 !important;
}
[data-testid="stSidebar"] * {
    color: #2B2118 !important;
}

/* Nagłówki */
h1, h2, h3, h4, h5 {
    color: #2F241D !important;
    font-weight: 800;
}

/* INPUTY I COMBOBOXY W CAŁEJ APLIKACJI ORAZ PANELU BOCZNYM */
input, textarea, .stChatInput textarea {
    background-color: #FAF8F2 !important;
    color: #2F241D !important;
    border: 1.5px solid #D6D2C4 !important;
    border-radius: 16px !important;
}
::placeholder {
    color: #8C827A !important;
}

div[data-baseweb="select"] > div {
    background-color: #FAF8F2 !important;
    border-color: #D6D2C4 !important;
    border-radius: 16px !important;
    color: #2F241D !important;
}

/* ZINTEGROWANY STYL NOTATEK I ROZWIJANYCH ELEMENTÓW (EXPANDERÓW) */
[data-testid="stExpander"] {
    border: 1.5px solid #E2DEC8 !important;
    border-radius: 24px !important;
    background-color: #F6F0DD !important;
    margin-bottom: 12px !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;
}
[data-testid="stExpander"] * {
    color: #2B2118 !important;
}

/* Belka nagłówkowa aplikacji */
.adventure-header {
    background: #2E251E;
    border: none;
    border-radius: 20px;
    padding: 12px 16px;
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 14px;
    box-shadow: 0 6px 18px rgba(46, 37, 30, 0.15);
}
.adventure-title-text {
    font-size: 1.15rem;
    font-weight: 900;
    color: #F9F7F1;
    letter-spacing: 0.02em;
    text-transform: uppercase;
}

/* NAGŁÓWEK WYCIECZKI */
.trip-top-section {
    padding: 4px 4px 14px 4px;
    margin-top: 4px;
}
.trip-main-title {
    font-size: 26pt;
    font-weight: 900;
    color: #2B2118;
    letter-spacing: -0.5px;
    line-height: 1.15;
    margin-bottom: 4px;
}
.trip-date-subtitle {
    font-size: 14pt;
    font-weight: 700;
    color: #8C5338;
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 12px;
}

/* SEKCJA LOGISTYKI I OPISÓW WYCIECZKI */
.overview-card {
    background-color: #F6F0DD;
    border: 1.5px solid #E2DEC8;
    border-radius: 24px;
    padding: 16px;
    margin-bottom: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.03);
}
.overview-card-title {
    font-size: 10pt;
    font-weight: 800;
    color: #2B2118;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.overview-card-text {
    font-size: 9.5pt;
    color: #2B2118;
    font-weight: 600;
    line-height: 1.4;
}

/* ZWIJANA KARTA TAKTYKI DNIA (GŁÓWNA WYCIECZKA) */
.overview-details-card {
    background-color: #F6F0DD;
    border: 1.5px solid #E2DEC8;
    border-radius: 24px;
    padding: 14px 16px;
    margin-bottom: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.03);
}
.overview-details-card summary {
    font-size: 10pt;
    font-weight: 800;
    color: #2B2118;
    cursor: pointer;
    outline: none;
    list-style: none;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.overview-details-card summary::-webkit-details-marker {
    display: none;
}
.overview-details-card summary::after {
    content: "▼";
    font-size: 8pt;
    color: #8C5338;
    transition: transform 0.2s;
}
.overview-details-card[open] summary::after {
    transform: rotate(180deg);
}

.logistics-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
}
.logistics-pill {
    background-color: #FAF8F2;
    border: 1.5px solid #E2DEC8;
    border-radius: 16px;
    padding: 10px 12px;
}
.logistics-pill-title {
    font-size: 8pt;
    font-weight: 800;
    color: #8C5338;
    text-transform: uppercase;
    margin-bottom: 3px;
    display: flex;
    align-items: center;
    gap: 4px;
}
.logistics-pill-value {
    font-size: 11pt;
    font-weight: 900;
    color: #2B2118;
}

/* GŁÓWNA KARTA PLANU DNIA */
.day-plan-container {
    background-color: #F6F0DD;
    border-radius: 36px 36px 28px 28px;
    padding: 24px 18px 20px 18px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.06);
    margin-bottom: 16px;
    margin-top: 14px;
}
.day-plan-heading {
    font-size: 16pt;
    font-weight: 900;
    color: #2B2118;
    margin-bottom: 20px;
}

/* TIMELINE WRAPPER Z CIĄGŁĄ LINIĄ W TLE */
.timeline-wrapper {
    position: relative;
}
.timeline-wrapper::before {
    content: "";
    position: absolute;
    top: 24px;
    bottom: 24px;
    left: 83px;
    width: 2.5px;
    background-color: #BCC8A4;
    z-index: 1;
}

/* TIMELINE CONTAINER & ITEMS */
.timeline-row {
    position: relative;
    display: flex;
    align-items: flex-start;
    min-height: 64px;
    padding-bottom: 16px;
    z-index: 2;
}
.timeline-time {
    width: 62px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    padding-top: 4px;
    z-index: 2;
}
.timeline-time-start {
    font-size: 11pt;
    font-weight: 900;
    color: #2B2118;
    line-height: 1.1;
}
.timeline-time-end {
    font-size: 8.5pt;
    font-weight: 700;
    color: #8C5338;
    margin-top: 2px;
    line-height: 1.1;
}

.timeline-center-col {
    position: relative;
    width: 44px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    margin-right: 10px;
    z-index: 2;
}

.timeline-icon-badge {
    position: relative;
    z-index: 3;
    width: 38px;
    height: 38px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13pt;
    font-weight: 900;
    color: #FFFFFF !important;
    text-decoration: none !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.12);
    border: 2px solid #FFFFFF;
    cursor: pointer;
    transition: transform 0.1s ease;
}
.timeline-icon-badge:hover {
    transform: scale(1.08);
}
.badge-pobudka { background-color: #94A77E; }
.badge-miejsce { background-color: #C06C4E; }
.badge-obiad { background-color: #B56749; }
.badge-powrot { background-color: #DDAE92; }

.timeline-content-col {
    flex: 1;
    padding-top: 2px;
    z-index: 2;
}
.timeline-item-title {
    font-size: 12.5pt;
    font-weight: 900;
    color: #2B2118;
    line-height: 1.25;
    margin-bottom: 3px;
}
.timeline-item-desc {
    font-size: 9.5pt;
    color: #4A3E36;
    line-height: 1.35;
    font-weight: 500;
}

/* KAFLEK SZCZEGÓŁÓW KROKU */
.step-details-card {
    background-color: #EDE8D6;
    border: 1.5px solid #D6CEBA;
    border-radius: 24px;
    padding: 16px;
    margin: 4px 0 18px 0;
    box-shadow: 0 4px 12px rgba(0,0,0,0.03);
    position: relative;
    z-index: 3;
}

.step-desc-bubble {
    background-color: #E2DAC4;
    border-radius: 16px;
    padding: 12px 14px;
    font-size: 10pt;
    color: #2B2118;
    line-height: 1.4;
    font-weight: 600;
    margin-bottom: 10px;
}

/* KAFLEK EWAKUACJI I OSTRZEŻENIA */
.step-evac-pill {
    background-color: rgba(220, 80, 80, 0.08);
    border: 1.5px solid rgba(220, 80, 80, 0.3);
    border-radius: 16px;
    padding: 10px 14px;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.step-evac-pill-title {
    font-size: 9pt;
    font-weight: 800;
    color: #DC5050;
    text-transform: uppercase;
}
.step-evac-pill-val {
    font-size: 11pt;
    font-weight: 900;
    color: #DC5050;
}

.step-warn-box {
    background-color: rgba(226, 140, 50, 0.1);
    border: 1.5px solid rgba(226, 140, 50, 0.35);
    border-radius: 16px;
    padding: 10px 14px;
    margin-bottom: 10px;
}
.step-warn-title {
    font-size: 8.5pt;
    font-weight: 800;
    color: #C06C4E;
    text-transform: uppercase;
    margin-bottom: 3px;
}
.step-warn-text {
    font-size: 9pt;
    font-weight: 700;
    color: #2B2118;
    line-height: 1.35;
}

/* ZWIJANA KARTA WEWNĄTRZ KROKU */
.step-combined-card {
    background-color: #E2DAC4;
    border-radius: 18px;
    padding: 12px 14px;
    margin-bottom: 12px;
}
.step-combined-card summary {
    font-size: 10pt;
    font-weight: 800;
    color: #8C5338;
    cursor: pointer;
    outline: none;
    list-style: none;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.step-combined-card summary::-webkit-details-marker {
    display: none;
}
.step-combined-card summary::after {
    content: "▼";
    font-size: 8pt;
    color: #8C5338;
    transition: transform 0.2s;
}
.step-combined-card[open] summary::after {
    transform: rotate(180deg);
}

.step-subitem-title {
    font-size: 9.5pt;
    font-weight: 800;
    margin-bottom: 3px;
    display: flex;
    align-items: center;
    gap: 4px;
}
.step-subitem-body {
    font-size: 9pt;
    color: #2B2118;
    line-height: 1.35;
    font-weight: 600;
}

/* PIONOWA LISTA PRZYCISKÓW NA DOLE KARTY */
.step-action-vertical-bar {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 14px;
    margin-bottom: 10px;
}

.step-action-vertical-btn {
    background-color: #C3CBB5;
    border: 1.5px solid #ACB79C;
    border-radius: 16px;
    padding: 10px 14px;
    text-align: center;
    text-decoration: none !important;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    transition: background-color 0.15s ease;
}
.step-action-vertical-btn:hover {
    background-color: #B5BEA5;
}
.step-action-vertical-btn span:first-child { font-size: 13pt; }
.step-action-vertical-btn span:last-child { font-size: 9.5pt; font-weight: 800; color: #2B2118; }

/* PRZYCISK NAWIGUJ W WIERSZU */
.timeline-nav-btn {
    flex-shrink: 0;
    background-color: #EFE4CA;
    border: 1.5px solid #D8C8A6;
    border-radius: 14px;
    padding: 6px 10px;
    text-align: center;
    text-decoration: none !important;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    margin-left: 8px;
    margin-top: 2px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.03);
    z-index: 3;
}
.timeline-nav-btn:hover {
    background-color: #E5D8B8;
}
.timeline-nav-btn span:first-child {
    font-size: 14pt;
    color: #8C5338;
}
.timeline-nav-btn span:last-child {
    font-size: 8.5pt;
    font-weight: 800;
    color: #2B2118;
}

/* DOSTĘP DO DROGI I PRZEJAZDÓW */
.timeline-transit-row {
    position: relative;
    display: flex;
    justify-content: center;
    margin: -6px 0 10px 0;
    z-index: 3;
}

/* Pasek nawigacji dolnej */
.bottom-nav-container {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background-color: #EFE8D6;
    border-top: 1.5px solid #D6CEBC;
    padding: 10px 16px;
    display: flex;
    justify-content: space-around;
    gap: 12px;
    z-index: 99999;
    box-shadow: 0 -4px 15px rgba(0, 0, 0, 0.05);
}
.bottom-nav-btn {
    flex: 1;
    background-color: transparent;
    color: #8A7B70;
    padding: 6px 0;
    text-align: center;
    border-radius: 14px;
    font-size: 11px;
    font-weight: 800;
    text-decoration: none;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
}
.bottom-nav-btn.active {
    color: #8C5338;
    font-weight: 900;
}

/* Pływający kontener AI */
.floating-ai-container {
    position: fixed;
    bottom: 75px;
    left: 8px;
    right: 8px;
    max-width: 520px;
    margin: 0 auto;
    z-index: 999998;
}

.custom-nav-bar {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    width: 100%;
    margin-bottom: 0.4rem;
}
.custom-nav-btn {
    flex: 1;
    background-color: #FAF8F2;
    border: 1.5px solid #D6D2C4;
    color: #2B2118;
    padding: 8px 4px;
    text-align: center;
    border-radius: 16px;
    font-size: 11px;
    font-weight: 800;
    text-decoration: none;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
}

/* Przyciski globalne */
.stButton > button {
    background-color: #2E251E !important;
    color: #FFFFFF !important;
    border: none !important;
    font-weight: 800 !important;
    border-radius: 20px !important;
    padding: 0.5rem 1rem !important;
    min-height: 44px !important;
    font-size: 10.5pt !important;
}

.note-card {
    background-color: #FAF8F2;
    border: 1.5px solid #D8D2BC;
    border-radius: 18px;
    padding: 14px;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

if "flash_toast" in st.session_state and st.session_state["flash_toast"]:
    st.toast(st.session_state["flash_toast"], icon="🧭")
    st.session_state["flash_toast"] = None

DOMEK_LAT = 35.5914
DOMEK_LON = 24.0918
SKLEP_LAT = 35.586222
SKLEP_LON = 24.091861

# --- FUNKCJA POBIERANIA CZASÓW DOJAZDU PRZEZ OSRM ---
@st.cache_data(ttl=86400)
def oblicz_czas_przejazdu_osrm(lat1, lon1, lat2, lon2):
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'CretAiApp/1.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            if 'routes' in data and len(data['routes']) > 0:
                duration_sec = data['routes'][0]['duration']
                minuty = int(round(duration_sec / 60))
                if minuty < 60:
                    return f"~{minuty} min", minuty
                godziny = minuty // 60
                reszta = minuty % 60
                return f"~{godziny}h {reszta}m", minuty
    except:
        pass
    return "~25 min", 25

def sparsuj_wspolrzedne(wsp_str):
    if not wsp_str or ',' not in str(wsp_str):
        return None, None
    try:
        parts = str(wsp_str).split(',')
        return float(parts[0].strip()), float(parts[1].strip())
    except:
        return None, None

def sparsuj_godzine_minuty(czas_str):
    if not czas_str:
        return None
    m = re.search(r'(\d{1,2}):(\d{2})', str(czas_str))
    if m:
        return int(m.group(1)), int(m.group(2))
    return None

def klucz_sortowania_okienka(okienko_str):
    res = sparsuj_godzine_minuty(okienko_str)
    if res:
        return res[0] * 60 + res[1]
    return 9999

# --- FORMATOWANIE DATY PO POLSKU ---
DNI_TYGODNIA_PL = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
MIESIACE_PL = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]

def formatuj_date_pl(data_obj):
    if not isinstance(data_obj, (date, datetime)):
        return str(data_obj)
    dzien = data_obj.day
    miesiac = MIESIACE_PL[data_obj.month - 1]
    rok = data_obj.year
    dzien_tyg = DNI_TYGODNIA_PL[data_obj.weekday()]
    return f"{dzien} {miesiac} {rok} ({dzien_tyg})"

# --- AUTOMATYCZNY SILNIK PRZELICZANIA I SYNCHRONIZACJI LOGISTYKI ---
def przelicz_i_zsynchronizuj_wycieczke(id_wycieczki):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, krok_wycieczki, wspolrzedne, okienko_zwiedzania, nazwa FROM krok_wycieczki WHERE id_wycieczki = ?', (str(id_wycieczki),))
    kroki = cursor.fetchall()
    
    if not kroki:
        conn.close()
        return

    kroki.sort(key=lambda x: klucz_sortowania_okienka(x[3]))

    krok_ids = [k[0] for k in kroki]
    if krok_ids:
        placeholders = ','.join(['?'] * len(krok_ids))
        cursor.execute(f'DELETE FROM czasy_dojazdu WHERE id_kroku_z IN ({placeholders}) OR id_kroku_do IN ({placeholders})', krok_ids + krok_ids)

    for idx in range(len(kroki) - 1):
        k1_id, _, k1_wsp, _, _ = kroki[idx]
        k2_id, _, k2_wsp, _, _ = kroki[idx + 1]
        
        lat1, lon1 = sparsuj_wspolrzedne(k1_wsp)
        lat2, lon2 = sparsuj_wspolrzedne(k2_wsp)
        
        if lat1 is not None and lon1 is not None and lat2 is not None and lon2 is not None:
            tekst_dojazdu, minuty = oblicz_czas_przejazdu_osrm(lat1, lon1, lat2, lon2)
            szacowany_postoj = 15
            cursor.execute('''
                INSERT INTO czasy_dojazdu (id_kroku_z, id_kroku_do, czas_przejazdu, szacowany_czas_postoju)
                VALUES (?, ?, ?, ?)
            ''', (k1_id, k2_id, tekst_dojazdu, szacowany_postoj))

    pierwsze_okienko = kroki[0][3] or "07:00 - 07:30"
    ostatnie_okienko = kroki[-1][3] or "18:00 - 18:30"

    if "-" in pierwsze_okienko:
        start_1 = sparsuj_godzine_minuty(pierwsze_okienko.split('-')[1]) or (7, 30)
    else:
        start_1 = sparsuj_godzine_minuty(pierwsze_okienko) or (7, 30)

    koniec_n = sparsuj_godzine_minuty(ostatnie_okienko.split('-')[0]) or (18, 0)

    dt_start = datetime(2026, 1, 1, start_1[0], start_1[1])
    dt_wyjazd = dt_start
    dt_pobudka = dt_wyjazd - timedelta(minutes=90)
    dt_powrot = datetime(2026, 1, 1, koniec_n[0], koniec_n[1])

    roznica_sek = (dt_powrot - dt_wyjazd).total_seconds()
    czas_trwania_h = round(max(roznica_sek / 3600.0, 0.5), 1)

    str_pobudka = dt_pobudka.strftime("%H:%M")
    str_wyjazd = dt_wyjazd.strftime("%H:%M")
    str_powrot = dt_powrot.strftime("%H:%M")

    cursor.execute('''
        UPDATE wycieczka 
        SET pobudka = ?, czas_wyjazdu = ?, szacowana_godzina_powrotu = ?, calkowity_czas_wycieczki_godziny = ?, czas_powrotu_do_domku = NULL
        WHERE id = ?
    ''', (str_pobudka, str_wyjazd, str_powrot, str(czas_trwania_h), str(id_wycieczki)))

    conn.commit()
    conn.close()

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
            czas_powrotu_do_domku TEXT DEFAULT NULL,
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
        CREATE TABLE IF NOT EXISTS czasy_dojazdu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_kroku_z INTEGER,
            id_kroku_do INTEGER,
            czas_przejazdu TEXT,
            szacowany_czas_postoju INTEGER,
            FOREIGN KEY (id_kroku_z) REFERENCES krok_wycieczki(id) ON DELETE CASCADE,
            FOREIGN KEY (id_kroku_do) REFERENCES krok_wycieczki(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posilki_kroku (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_kroku INTEGER,
            rodzaj_posilku TEXT CHECK(rodzaj_posilku IN ('śniadanie', 'obiad', 'kolacja', 'przekąska')),
            miejsce TEXT CHECK(miejsce IN ('w domku', 'w kroku', 'restauracja', 'po drodze')),
            opis TEXT,
            FOREIGN KEY (id_kroku) REFERENCES krok_wycieczki(id) ON DELETE CASCADE
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
            "10.0",
            "17:30",
            "06:00",
            "07:30",
            domyslna_data
        ))

        kroki_w1 = [
            ("1", "0", "Nasz Domek (Start)", f"{DOMEK_LAT}, {DOMEK_LON}", "07:00 - 07:30", "07:30", "Brak", "Spokojna baza", "Poziom energii, prosta rada (np. 'Światło dzienne, spokojna muzyka').", "Niski", "Ciepła atmosfera w domku", "Nasz domek wypadowy w Stavros."),
            ("1", "1", "Pałac w Knossos", "35.2980, 25.1631", "09:00 - 11:30", "11:30", "BEZWZGLĘDNIE EWAKUOWAĆ SIĘ PRZED 12:00! Tłumy i upał.", "Brak - rygor czasowy.", "Poziom tłumu (Niski), szacowany czas zwiedzania.", "Wysoki (tłumy, brak cienia, duchota)", "Użycie aplikacji 3D na iPadzie jako kotwica uwagi, szybka ewakuacja w razie buntu.", "Legendarska stolica minojskiej Krety z ruinami pałacu króla Minosa."),
            ("1", "2", "Cretaquarium", "35.3326, 25.2825", "13:30 - 15:30", "15:30", "Unikać godzin szczytu.", "Kawiarnia obok", "Poziom stymulacji sensorycznej (Umiarkowany - półmrok, chłód).", "Średni (pogłos w halach, tłum)", "Słuchawki wygłuszające, powolne tempo, półmrok przy akwariach.", "Jedno z największych oceanariów w basenie Morza Śródziemnego."),
            ("1", "3", "Nasz Domek (Powrót)", f"{DOMEK_LAT}, {DOMEK_LON}", "16:00 - 19:00", "19:00", "Brak", "Pełny relaks", "Poziom energii na koniec dnia, prosta rada (np. 'Wyciszenie w drodze').", "Niski", "Kolacja domowa i odpoczynek", "Koniec wyprawy w naszej bazie.")
        ]
        cursor.executemany('''
            INSERT INTO krok_wycieczki (id_wycieczki, krok_wycieczki, nazwa, wspolrzedne, okienko_zwiedzania, godzina_ewakuacji, czerwona_strefa_ostrzezenie, strefa_luzu_i_regeneracji, podsumowanie_taktyki, potencjal_meltdownu, strategie_meltdown, opis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', kroki_w1)

        cursor.execute("SELECT id FROM krok_wycieczki WHERE id_wycieczki = '1' ORDER BY id ASC")
        db_krok_ids = [r[0] for r in cursor.fetchall()]
        if len(db_krok_ids) >= 4:
            cursor.execute("INSERT INTO posilki_kroku (id_kroku, rodzaj_posilku, miejsce, opis) VALUES (?, 'śniadanie', 'w domku', 'Domowe śniadanie')", (db_krok_ids[0],))
            cursor.execute("INSERT INTO posilki_kroku (id_kroku, rodzaj_posilku, miejsce, opis) VALUES (?, 'obiad', 'w kroku', 'Poziom regeneracji (Wysoki), dostępność strefy wyciszenia, czas dojazdu do restauracji (np. 5 min spacerem).')", (db_krok_ids[1],))
            cursor.execute("INSERT INTO posilki_kroku (id_kroku, rodzaj_posilku, miejsce, opis) VALUES (?, 'kolacja', 'w domku', 'Kolacja po powrocie')", (db_krok_ids[3],))

        conn.commit()
        przelicz_i_zsynchronizuj_wycieczke("1")
    conn.close()

init_db()

# --- FUNKCJE OBSŁUGI ZAKUPÓW PRZEZ QUERY PARAMS ---
if "action" in st.query_params and st.query_params["action"] == "add_zakup":
    k_id = st.query_params.get("krok_id")
    p_name = st.query_params.get("prod_name")
    p_qty = st.query_params.get("prod_qty", "1")
    if k_id and p_name:
        dodaj_produkt_zakupow(int(k_id), str(p_name), str(p_qty))
        st.session_state["flash_toast"] = f"🛒 Dodano: {p_name}"
    st.query_params.clear()
    st.query_params["tab"] = "route"
    if k_id:
        st.query_params["expand"] = str(k_id)
    st.rerun()

# --- FUNKCJE ZARZĄDZANIA USTAWIENIAMI I KLUCZAMI API ---
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

def sprawdź_pogodę_w_locie(szerokosc_geograficzna, dlugosc_geograficzna, data_wspolrzedne="dzisiaj"):
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

def pobierz_szczegoly_pogody_dla_godziny(wspolrzedne, planowana_data, okienko_czasowe):
    if not planowana_data or not str(planowana_data).strip():
        return None
    try:
        parts = str(wspolrzedne).split(',')
        lat = float(parts[0].strip())
        lon = float(parts[1].strip())
    except:
        return None

    prognoza_dnia = pobierz_prognoze_pogody(lat, lon, str(planowana_data))
    if not prognoza_dnia:
        return None

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
        ostrzezenia.append(f"🔥 Ekstremalny upał! Maksymalna temperatura sięgnie {max_temp}°C.")

    border_col = '#DC5050' if ostrzezenia else '#D8D2BC'
    title_col = '#DC5050' if ostrzezenia else '#8A7B70'

    st.markdown(f'<div style="background-color: #FAF8F2; border: 1.5px solid {border_col}; border-radius: 20px; padding: 14px; margin-bottom: 12px;"><div style="font-size: 9pt; font-weight: 900; color: {title_col}; margin-bottom: 4px; text-transform: uppercase;">🌤️ Pogoda na trasie ({planowana_data})</div><div style="font-size: 10.5pt; color: #2B2118; font-weight: 700;">Temperatura: <b>{min_temp}°C do {max_temp}°C</b></div></div>', unsafe_allow_html=True)

    if ostrzezenia:
        for ost in ostrzezenia:
            st.markdown(f'<div style="color: #DC5050; font-weight: 800; font-size: 9.5pt; margin-top: 2px;">{ost}</div>', unsafe_allow_html=True)

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

# --- FUNKCJE OBSŁUGI NOTATEK, MIEJSC, WYCIECZEK, KROKÓW I ZAKUPÓW ---
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
    st.markdown("### 📌 Notatki i Zadania")
    df_notatki = pobierz_notatki(id_wycieczki=id_wycieczki, id_miejsca=id_miejsca)
    
    with st.expander("➕ Dodaj nową notatkę"):
        with st.form(key=f"form_add_note_{id_wycieczki}_{id_miejsca}", clear_on_submit=True):
            nt_tytul = st.text_input("Tytuł (opcjonalnie)")
            nt_typ = st.selectbox(
                "Typ notatki", 
                options=["text", "link", "list"], 
                format_func=lambda x: {"text": "📝 Tekst", "link": "🔗 Link", "list": "📋 Checklista"}[x]
            )
            nt_zawartosc = st.text_area("Treść notatki")
            submitted = st.form_submit_button("💾 Zapisz notatkę", use_container_width=True)
            if submitted and nt_zawartosc:
                dodaj_notatke(zawartosc=nt_zawartosc, typ_notatki=nt_typ, id_wycieczki=id_wycieczki, id_miejsca=id_miejsca, tytul=nt_tytul)
                st.session_state["flash_toast"] = "💾 Dodano notatkę!"
                st.rerun()

    if not df_notatki.empty:
        for _, note in df_notatki.iterrows():
            st.markdown(f'<div class="note-card"><div style="font-weight: 800; font-size: 10.5pt; color: #2B2118; margin-bottom: 4px;">📌 {note.get("tytul") or "Notatka"}</div><div style="font-size: 9.5pt; color: #4A3E36;">{note["zawartosc"]}</div></div>', unsafe_allow_html=True)

def edytuj_wycieczke(id, tytul_wycieczki=None, calosciowy_opis_wycieczki=None, calosciowa_taktyka_dnia=None, 
                     calkowity_czas_wycieczki_godziny=None, szacowana_godzina_powrotu=None, 
                     pobudka=None, czas_wyjazdu=None, planowana_data=None):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    if tytul_wycieczki is not None:
        cursor.execute('UPDATE wycieczka SET tytul_wycieczki = ? WHERE id = ?', (tytul_wycieczki, str(id)))
    if calosciowy_opis_wycieczki is not None:
        cursor.execute('UPDATE wycieczka SET calosciowy_opis_wycieczki = ? WHERE id = ?', (calosciowy_opis_wycieczki, str(id)))
    if calosciowa_taktyka_dnia is not None:
        cursor.execute('UPDATE wycieczka SET calosciowa_taktyka_dnia = ? WHERE id = ?', (calosciowa_taktyka_dnia, str(id)))
    if planowana_data is not None:
        cursor.execute('UPDATE wycieczka SET planowana_data = ? WHERE id = ?', (planowana_data, str(id)))
    conn.commit()
    conn.close()
    przelicz_i_zsynchronizuj_wycieczke(str(id))
    return f"Wycieczka #{id} została zaktualizowana."

def dodaj_krok_wycieczki(id_wycieczki, krok_wycieczki, nazwa, wspolrzedne="35.3,24.5", 
                         okienko_zwiedzania="10:00 - 12:00", godzina_ewakuacji="12:00", 
                         czerwona_strefa_ostrzezenie="Unikać upału", strefa_luzu_i_regeneracji="Cień", 
                         podsumowanie_taktyki="Spokojne tempo", potencjal_meltdownu="Średni", 
                         strategie_meltdown="Okulary i woda", opis="Brak opisu"):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO krok_wycieczki (
            id_wycieczki, krok_wycieczki, nazwa, wspolrzedne, 
            okienko_zwiedzania, godzina_ewakuacji, czerwona_strefa_ostrzezenie, 
            strefa_luzu_i_regeneracji, podsumowanie_taktyki, potencjal_meltdownu, 
            strategie_meltdown, opis
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        str(id_wycieczki), str(krok_wycieczki), str(nazwa), str(wspolrzedne), 
        str(okienko_zwiedzania), str(godzina_ewakuacji), str(czerwona_strefa_ostrzezenie), 
        str(strefa_luzu_i_regeneracji), str(podsumowanie_taktyki), 
        str(potencjal_meltdownu), str(strategie_meltdown), str(opis)
    ))
    conn.commit()
    conn.close()
    przelicz_i_zsynchronizuj_wycieczke(str(id_wycieczki))
    return f"Dodano krok {nazwa} do wycieczki."

def edytuj_krok_wycieczki(id_wycieczki, krok_wycieczki, nazwa=None, wspolrzedne=None,
                          okienko_zwiedzania=None, godzina_ewakuacji=None, czerwona_strefa_ostrzezenie=None, 
                          strefa_luzu_i_regeneracji=None, podsumowanie_taktyki=None, 
                          potencjal_meltdownu=None, strategie_meltdown=None, opis=None):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM krok_wycieczki WHERE id_wycieczki = ? AND (krok_wycieczki = ? OR nazwa LIKE ?)', (str(id_wycieczki), str(krok_wycieczki), f"%{krok_wycieczki}%"))
    res = cursor.fetchone()
    if not res:
        conn.close()
        return "Nie znaleziono kroku wycieczki."
    krok_row_id = res[0]
    
    pola = {
        "nazwa": nazwa, "wspolrzedne": wspolrzedne, "okienko_zwiedzania": okienko_zwiedzania,
        "godzina_ewakuacji": godzina_ewakuacji, "czerwona_strefa_ostrzezenie": czerwona_strefa_ostrzezenie,
        "strefa_luzu_i_regeneracji": strefa_luzu_i_regeneracji, "podsumowanie_taktyki": podsumowanie_taktyki,
        "potencjal_meltdownu": potencjal_meltdownu, "strategie_meltdown": strategie_meltdown, "opis": opis
    }
    for col, val in pola.items():
        if val is not None:
            cursor.execute(f'UPDATE krok_wycieczki SET {col} = ? WHERE id = ?', (val, krok_row_id))
            
    conn.commit()
    conn.close()
    przelicz_i_zsynchronizuj_wycieczke(str(id_wycieczki))
    return f"Zaktualizowano krok wycieczki #{id_wycieczki}."

def usun_krok_wycieczki(id_wycieczki, krok_wycieczki):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, nazwa FROM krok_wycieczki WHERE id_wycieczki = ? AND (krok_wycieczki = ? OR nazwa LIKE ?)', 
                   (str(id_wycieczki), str(krok_wycieczki), f"%{krok_wycieczki}%"))
    krok_to_del = cursor.fetchone()
    if not krok_to_del:
        conn.close()
        return "Nie znaleziono takiego kroku w harmonogramie wycieczki."
    
    krok_id, nazwa = krok_to_del
    if "domek" in nazwa.lower():
        conn.close()
        return f"BLOKADA: Krok '{nazwa}' to baza wypadowa (Domek) i jest nieusuwalny!"

    cursor.execute('DELETE FROM krok_wycieczki WHERE id = ?', (krok_id,))
    conn.commit()
    conn.close()
    przelicz_i_zsynchronizuj_wycieczke(str(id_wycieczki))
    return f"Usunięto krok '{nazwa}'."

def pobierz_posilki_dla_kroku(id_kroku):
    conn = sqlite3.connect('cretai.db')
    df = pd.read_sql('SELECT * FROM posilki_kroku WHERE id_kroku = ?', conn, params=(str(id_kroku),))
    conn.close()
    return df

def dodaj_posilek_do_kroku(id_kroku, rodzaj_posilku, miejsce="w kroku", opis=""):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO posilki_kroku (id_kroku, rodzaj_posilku, miejsce, opis)
        VALUES (?, ?, ?, ?)
    ''', (str(id_kroku), str(rodzaj_posilku), str(miejsce), str(opis)))
    conn.commit()
    conn.close()
    return f"Dodano posiłek ({rodzaj_posilku}) do kroku."

def usun_posilek_kroku(posilek_id):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM posilki_kroku WHERE id = ?', (posilek_id,))
    conn.commit()
    conn.close()
    return "Usunięto posiłek."

def pobierz_zakupy_dla_kroku(id_kroku):
    conn = sqlite3.connect('cretai.db')
    df = pd.read_sql('SELECT * FROM zakupy WHERE id_kroku = ?', conn, params=(str(id_kroku),))
    conn.close()
    return df

def dodaj_produkt_zakupow(id_kroku, nazwa_produktu, ilosc="1"):
    conn = sqlite3.connect('cretai.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO zakupy (id_kroku, nazwa_produktu, ilosc, kupione) VALUES (?, ?, ?, 0)', (str(id_kroku), nazwa_produktu, str(ilosc)))
    conn.commit()
    conn.close()
    return f"Dodano produkt '{nazwa_produktu}'."

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
    tekst += f"- Lokalizacja naszego DOMEK: {DOMEK_LAT}, {DOMEK_LON}\n"
    tekst += f"- Lokalizacja SKLEP: {SKLEP_LAT}, {SKLEP_LON}\n"
    conn = sqlite3.connect('cretai.db')
    try:
        miejsca_df = pd.read_sql('SELECT numer_miejsca, nazwa, typ, czas_dojazdu FROM miejsca', conn)
        wycieczki_df = pd.read_sql('SELECT id, tytul_wycieczki, calosciowy_opis_wycieczki, pobudka, czas_wyjazdu, szacowana_godzina_powrotu, planowana_data FROM wycieczka', conn)
        kroki_df = pd.read_sql('SELECT id, id_wycieczki, krok_wycieczki, nazwa, wspolrzedne, okienko_zwiedzania, godzina_ewakuacji FROM krok_wycieczki', conn)
    except:
        miejsca_df, wycieczki_df, kroki_df = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    conn.close()

    if not kroki_df.empty:
        kroki_df['sort_key'] = kroki_df['okienko_zwiedzania'].apply(klucz_sortowania_okienka)
        kroki_df = kroki_df.sort_values(by='sort_key').drop(columns=['sort_key'])

    if not wycieczki_df.empty:
        for _, w in wycieczki_df.iterrows():
            tekst += f"- Wycieczka #{w['id']}: {w['tytul_wycieczki']} | Data: {w.get('planowana_data', '')}\n"
    if not kroki_df.empty:
        for _, k in kroki_df.iterrows():
            tekst += f"- Krok (W#{k['id_wycieczki']}): {k['nazwa']} | Czas: {k['okienko_zwiedzania']}\n"
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
    domek_icon_html = '<div style="background-color:#2E251E;color:#FFFFFF;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:14px;border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.2);">🏠</div>'
    domek_icon = folium.DivIcon(html=domek_icon_html, icon_size=(28, 28), icon_anchor=(14, 14))
    folium.Marker([DOMEK_LAT, DOMEK_LON], icon=domek_icon, tooltip="Nasz Domek").add_to(m)

# --- FUNCTION CALLING DLA ASYSTENTA AI ---
cretai_tools = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="dodaj_notatke",
        description="Dodaje notatkę do wycieczki lub miejsca.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "zawartosc": types.Schema(type=types.Type.STRING, description="Treść notatki"),
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
        description="Aktualizuje parametry wycieczki.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                "tytul_wycieczki": types.Schema(type=types.Type.STRING, description="Tytuł"),
                "calosciowy_opis_wycieczki": types.Schema(type=types.Type.STRING, description="Opis"),
                "calosciowa_taktyka_dnia": types.Schema(type=types.Type.STRING, description="Taktyka"),
                "planowana_data": types.Schema(type=types.Type.STRING, description="RRRR-MM-DD"),
            },
            required=["id"]
        ),
    ),
    types.FunctionDeclaration(
        name="dodaj_krok_wycieczki",
        description="Dodaje krok do wycieczki.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                "krok_wycieczki": types.Schema(type=types.Type.STRING, description="Numer kroku"),
                "nazwa": types.Schema(type=types.Type.STRING, description="Nazwa miejsca"),
                "wspolrzedne": types.Schema(type=types.Type.STRING, description="GPS"),
                "okienko_zwiedzania": types.Schema(type=types.Type.STRING, description="np. '10:00 - 12:00'"),
                "godzina_ewakuacji": types.Schema(type=types.Type.STRING, description="np. '12:00'"),
                "czerwona_strefa_ostrzezenie": types.Schema(type=types.Type.STRING, description="Ostrzeżenie o upale/tłumie"),
                "strefa_luzu_i_regeneracji": types.Schema(type=types.Type.STRING, description="Strefa wyciszenia"),
                "podsumowanie_taktyki": types.Schema(type=types.Type.STRING, description="Taktyka"),
                "opis": types.Schema(type=types.Type.STRING, description="Opis"),
            },
            required=["id_wycieczki", "krok_wycieczki", "nazwa"]
        ),
    ),
    types.FunctionDeclaration(
        name="usun_krok_wycieczki",
        description="Usuwa krok z wycieczki.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                "krok_wycieczki": types.Schema(type=types.Type.STRING, description="Numer lub nazwa kroku"),
            },
            required=["id_wycieczki", "krok_wycieczki"]
        ),
    )
])

def wykonaj_narzedzie_bazy(call_name, args):
    if call_name == "dodaj_notatke":
        return dodaj_notatke(**args)
    elif call_name == "edytuj_wycieczke":
        return edytuj_wycieczke(**args)
    elif call_name == "dodaj_krok_wycieczki":
        return dodaj_krok_wycieczki(**args)
    elif call_name == "usun_krok_wycieczki":
        return usun_krok_wycieczki(**args)
    return "Wykonano."

# --- W PANELU BOCZNYM: USTAWIENIA I PROFILE ---
with st.sidebar:
    st.markdown("### 👤 Profil Użytkownika")
    dostepni_uzytkownicy = ["Rodzic 1", "Rodzic 2", "Rodzic 3", "Rodzic 4"]
    aktualny_uzytkownik = st.selectbox("Wybierz swój profil", options=dostepni_uzytkownicy, index=0)
    st.markdown("---")
    
    st.header("⚙️ Ustawienia Asystenta")
    zapisany_klucz, zapisany_dostawca, zapisany_model = pobierz_ustawienia_z_db(aktualny_uzytkownik)
    
    dostawcy_ai = ["Google Gemini", "Anthropic Claude"]
    dostawca_index = dostawcy_ai.index(zapisany_dostawca) if zapisany_dostawca in dostawcy_ai else 0
    wybrany_dostawca = st.selectbox("Dostawca AI", options=dostawcy_ai, index=dostawca_index)
    
    if wybrany_dostawca == "Google Gemini":
        dostepne_modele = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.6-flash"]
    else:
        dostepne_modele = ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"]
    
    model_index = dostepne_modele.index(zapisany_model) if zapisany_model in dostepne_modele else 0
    wybrany_model = st.selectbox("Model AI", options=dostepne_modele, index=model_index)
    
    api_key_input = st.text_input(f"Klucz API ({wybrany_dostawca})", value=zapisany_klucz, type="password", key=f"api_key_{aktualny_uzytkownik}")
    if api_key_input != zapisany_klucz or wybrany_dostawca != zapisany_dostawca or wybrany_model != zapisany_model:
        zapisz_ustawienia_w_db(aktualny_uzytkownik, api_key_input, wybrany_dostawca, wybrany_model)

    st.markdown("---")
    st.markdown("### 🧭 Szybka Nawigacja")
    st.markdown(f"""
<div class="custom-nav-bar">
<a href="https://www.google.com/maps/search/?api=1&query={SKLEP_LAT},{SKLEP_LON}" target="_blank" class="custom-nav-btn"><span>🛒</span><span>Sklep</span></a>
<a href="https://www.google.com/maps/search/?api=1&query={DOMEK_LAT},{DOMEK_LON}" target="_blank" class="custom-nav-btn"><span>🏠</span><span>Domek</span></a>
</div>
""", unsafe_allow_html=True)

# --- GLOBALNY ASYSTENT AI ---
def renderuj_globalny_czat_ai(uzytkownik):
    st.markdown('<div class="floating-ai-container">', unsafe_allow_html=True)
    with st.expander(f"💬 Asystent AI ({uzytkownik})", expanded=False):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"<span style='font-size: 9pt; font-weight: 800;'>🧠 TRYB ADHD • {uzytkownik}</span>", unsafe_allow_html=True)
        with col2:
            if st.button("🗑️ Wyczyść", key=f"btn_clear_{uzytkownik}", use_container_width=True):
                wyczysc_historie_czatu_w_db(uzytkownik)
                st.session_state["flash_toast"] = "🗑️ Wyczyszczono czat."
                st.rerun()

        if not api_key_input:
            st.warning(f"Wprowadź klucz API w menu bocznym.")
            st.markdown('</div>', unsafe_allow_html=True)
            return

        dzisiaj_str = date.today().strftime("%Y-%m-%d")
        zewnetrzny_kontekst = wczytaj_kontekst_zewnetrzny()
        system_prompt = f"Jesteś asystentem podróży CretAi na Krecie. Dziś: {dzisiaj_str}.\n{zewnetrzny_kontekst}"
        
        chat_historia_z_db = pobierz_historie_czatu_z_db(uzytkownik)
        chat_container = st.container(height=200)
        with chat_container:
            for message in chat_historia_z_db:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"] if isinstance(message["content"], str) else "")

        prompt = st.chat_input(f"Pytanie do AI...", key=f"chat_input_{uzytkownik}")
        if prompt:
            zapisz_wiadomosc_w_db(uzytkownik, "user", prompt)
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)
                with st.chat_message("assistant"):
                    try:
                        if wybrany_dostawca == "Google Gemini":
                            client = genai.Client(api_key=api_key_input)
                            aktualna_historia_db = pobierz_historie_czatu_z_db(uzytkownik)
                            contents = [item["raw_content"] for item in aktualna_historia_db if "raw_content" in item]
                            response = client.models.generate_content(
                                model=wybrany_model,
                                contents=contents,
                                config=types.GenerateContentConfig(tools=[cretai_tools], system_instruction=system_prompt)
                            )
                            assistant_reply = response.text if hasattr(response, "text") and response.text else "Zaktualizowano."
                        else:
                            client_c = anthropic.Anthropic(api_key=api_key_input)
                            resp = client_c.messages.create(
                                model=wybrany_model,
                                max_tokens=1024,
                                system=system_prompt,
                                messages=[{"role": "user", "content": prompt}]
                            )
                            assistant_reply = "".join([b.text for b in resp.content if hasattr(b, "text")])
                        zapisz_wiadomosc_w_db(uzytkownik, "model", assistant_reply)
                        st.markdown(assistant_reply)
                    except Exception as e:
                        st.error(f"Błąd: {e}")
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

if "tab" in st.query_params:
    st.session_state.active_tab = st.query_params["tab"]
elif "active_tab" not in st.session_state:
    st.session_state.active_tab = "route"

if "place" in st.query_params:
    st.session_state.active_place_id = st.query_params["place"]
    st.session_state.active_tab = "zabytek"

if "active_place_id" not in st.session_state:
    st.session_state.active_place_id = None

COLORS = {'must have': '#DC5050', 'nice to have': '#E28C32', 'others': '#5B8FB9', 'activity': '#6D8257', 'shop': '#9D79BC', 'plaża': '#4EA8A8'}
DEFAULT_COLOR = '#8A7B70'

df_miejsca = pobierz_wszystkie_miejsca()
wycieczki_options = pobierz_skrocone_opcje_wycieczek()

# ==========================================
# GŁÓWNY WIDOK WYCIECZKI (Z PEŁNĄ LOGISTYKĄ I TIMELINE)
# ==========================================
def renderuj_karte_wycieczki(wycieczka_id, pokaz_mape=False, pokaz_pogode=False):
    conn = sqlite3.connect('cretai.db')
    wycieczka_row = pd.read_sql('SELECT * FROM wycieczka WHERE id = ?', conn, params=(str(wycieczka_id),))
    kroki_df = pd.read_sql('SELECT * FROM krok_wycieczki WHERE id_wycieczki = ?', conn, params=(str(wycieczka_id),))
    czasy_dojazdu_df = pd.read_sql('SELECT * FROM czasy_dojazdu', conn)
    conn.close()
    
    if wycieczka_row.empty:
        st.info("Brak danych wycieczki.")
        return

    if not kroki_df.empty:
        kroki_df['sort_key'] = kroki_df['okienko_zwiedzania'].apply(klucz_sortowania_okienka)
        kroki_df = kroki_df.sort_values(by='sort_key').drop(columns=['sort_key'])

    w_gen = wycieczka_row.iloc[0]
    planowana_data_val = w_gen.get('planowana_data', '')
    
    dzisiaj = date.today()
    try:
        parsed_date = datetime.strptime(str(planowana_data_val), "%Y-%m-%d").date() if planowana_data_val else dzisiaj
    except:
        parsed_date = dzisiaj

    formatted_date_str = formatuj_date_pl(parsed_date)

    st.markdown(f'<div class="trip-top-section"><div class="trip-main-title">Twoja wycieczka</div><div class="trip-date-subtitle"><span>{formatted_date_str}</span><span style="font-size: 10pt;">▼</span></div></div>', unsafe_allow_html=True)

    with st.expander("📅 Zmień datę wycieczki", expanded=False):
        def zapisz_date_callback():
            wybrana_data = st.session_state[f"date_input_{wycieczka_id}"]
            str_data = wybrana_data.strftime("%Y-%m-%d")
            edytuj_wycieczke(wycieczka_id, planowana_data=str_data)
            st.session_state["flash_toast"] = f"📅 Zmieniono datę: {str_data}"

        st.date_input(
            "Wybierz inną datę", 
            value=parsed_date, 
            min_value=dzisiaj, 
            key=f"date_input_{wycieczka_id}", 
            label_visibility="collapsed",
            on_change=zapisz_date_callback
        )

    if pokaz_pogode:
        renderuj_podsumowanie_pogody_wycieczki(kroki_df, planowana_data_val)

    pobudka_val = w_gen.get('pobudka', '06:00') if pd.notna(w_gen.get('pobudka')) else '06:00'
    wyjazd_val = w_gen.get('czas_wyjazdu', '07:30') if pd.notna(w_gen.get('czas_wyjazdu')) else '07:30'
    powrot_val = w_gen.get('szacowana_godzina_powrotu', '17:33') if pd.notna(w_gen.get('szacowana_godzina_powrotu')) else '17:33'
    czas_trwania = f"{w_gen['calkowity_czas_wycieczki_godziny']} godz." if pd.notna(w_gen.get('calkowity_czas_wycieczki_godziny')) else "—"

    st.markdown(f"""
    <div class="overview-card">
        <div class="overview-card-title"><span>🧭</span> LOGISTYKA DNIA</div>
        <div class="logistics-grid">
            <div class="logistics-pill">
                <div class="logistics-pill-title">⏰ Pobudka</div>
                <div class="logistics-pill-value">{pobudka_val}</div>
            </div>
            <div class="logistics-pill">
                <div class="logistics-pill-title">🚗 Wyjazd</div>
                <div class="logistics-pill-value">{wyjazd_val}</div>
            </div>
            <div class="logistics-pill">
                <div class="logistics-pill-title">🏠 Powrót do Domku</div>
                <div class="logistics-pill-value">{powrot_val}</div>
            </div>
            <div class="logistics-pill">
                <div class="logistics-pill-title">⏱️ Czas trwania trasy</div>
                <div class="logistics-pill-value">{czas_trwania}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if pd.notna(w_gen.get('calosciowy_opis_wycieczki')) and str(w_gen['calosciowy_opis_wycieczki']).strip():
        st.markdown(f"""
        <div class="overview-card">
            <div class="overview-card-title">📝 Cel wycieczki</div>
            <div class="overview-card-text">{w_gen['calosciowy_opis_wycieczki']}</div>
        </div>
        """, unsafe_allow_html=True)

    if pd.notna(w_gen.get('calosciowa_taktyka_dnia')) and str(w_gen['calosciowa_taktyka_dnia']).strip():
        st.markdown(f"""
        <details class="overview-details-card">
            <summary>🧠 TAKTYKA DNIA</summary>
            <div style="margin-top: 10px; border-top: 1px solid #D1C7AE; padding-top: 8px;">
                <div class="overview-card-text">{w_gen['calosciowa_taktyka_dnia']}</div>
            </div>
        </details>
        """, unsafe_allow_html=True)

    if pokaz_mape:
        punkty_trasy, surowe_wspolrzedne = [], []
        for _, k in kroki_df.iterrows():
            coords = str(k['wspolrzedne'])
            if ',' in coords:
                try:
                    parts = coords.split(',')
                    lat, lon = float(parts[0].strip()), float(parts[1].strip())
                    punkty_trasy.append((lat, lon, str(k['krok_wycieczki']), str(k['nazwa'])))
                    surowe_wspolrzedne.append((lat, lon))
                except:
                    pass
        if punkty_trasy:
            srodek_lat = sum([p[0] for p in punkty_trasy]) / len(punkty_trasy)
            srodek_lon = sum([p[1] for p in punkty_trasy]) / len(punkty_trasy)
            m_trasa = folium.Map(location=[srodek_lat, srodek_lon], zoom_start=10, tiles="CartoDB positron")
            for lat, lon, krok, nazwa in punkty_trasy:
                is_d = "Domek" in nazwa
                icon_bg = "#2E251E" if is_d else "#C06C4E"
                icon_sym = "🏠" if is_d else krok
                icon_html = f'<div style="background-color:{icon_bg};color:white;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:900;border:2px solid white;">{icon_sym}</div>'
                folium.Marker([lat, lon], icon=folium.DivIcon(html=icon_html, icon_size=(26, 26), icon_anchor=(13, 13)), tooltip=nazwa).add_to(m_trasa)
            trasa_po_drogach = pobierz_trase_osrm(surowe_wspolrzedne)
            if trasa_po_drogach:
                folium.PolyLine(trasa_po_drogach, color="#8C5338", weight=4, opacity=0.9).add_to(m_trasa)
            st_folium(m_trasa, width="100%", height=220, returned_objects=[])

    st.markdown('<div class="day-plan-container"><div class="day-plan-heading">Plan na dzień</div><div class="timeline-wrapper">', unsafe_allow_html=True)
    
    current_expanded_param = st.query_params.get("expand")
    
    total_steps = len(kroki_df)
    for idx, (_, k) in enumerate(kroki_df.iterrows()):
        krok_row_id = int(k['id'])
        nazwa = str(k['nazwa'])
        okienko = str(k.get('okienko_zwiedzania', ''))
        krok_num = str(k['krok_wycieczki'])
        wspolrzedne = str(k.get('wspolrzedne', ''))
        coords_clean = wspolrzedne.replace(" ", "")
        
        godzina_start = okienko.split("-")[0].strip() if "-" in okienko else (okienko if okienko else "08:00")
        godzina_koniec = okienko.split("-")[1].strip() if "-" in okienko else str(k.get('godzina_ewakuacji', '')).strip()
        
        is_first = (idx == 0)
        is_last = (idx == total_steps - 1)
        
        if is_first:
            badge_symbol = "🛏️"
            tytul_wyswietlany = "Pobudka"
            badge_class = "badge-pobudka"
            has_nav = False
        elif is_last:
            badge_symbol = "🚩"
            tytul_wyswietlany = "Powrót / Zakończenie"
            badge_class = "badge-powrot"
            has_nav = False
        elif "obiad" in nazwa.lower() or "lunch" in nazwa.lower() or "jedzenie" in nazwa.lower() or "przerwa" in nazwa.lower():
            badge_symbol = "🍴"
            tytul_wyswietlany = nazwa
            badge_class = "badge-obiad"
            has_nav = False
        else:
            badge_symbol = krok_num if (krok_num and krok_num != "0") else str(idx)
            tytul_wyswietlany = nazwa
            badge_class = "badge-miejsce"
            has_nav = bool(coords_clean and ',' in coords_clean)

        df_pos = pobierz_posilki_dla_kroku(k['id'])
        opis_tekst = ""
        if not df_pos.empty:
            posiłki_str = []
            for _, prow in df_pos.iterrows():
                p_rodzaj = str(prow.get('rodzaj_posilku', '')).strip().lower()
                if p_rodzaj in ['śniadanie', 'obiad', 'kolacja']:
                    posiłki_str.append(p_rodzaj.capitalize())
                elif p_rodzaj == 'przekąska':
                    posiłki_str.append("Przekąska")
            if posiłki_str:
                opis_tekst = f"<span style='color:#8C5338; font-weight:700;'>🍲 {' / '.join(posiłki_str)}</span>"

        is_expanded = (current_expanded_param == str(krok_row_id))
        toggle_expand_url = f"?tab=route" if is_expanded else f"?tab=route&expand={krok_row_id}"

        nav_btn_html = ""
        if has_nav:
            gps_url = f"https://www.google.com/maps/search/?api=1&query={coords_clean}"
            nav_btn_html = f'<a href="{gps_url}" target="_blank" class="timeline-nav-btn" title="Nawiguj"><span>🧭</span><span>Nawiguj</span></a>'

        time_end_html = f'<span class="timeline-time-end">do {godzina_koniec}</span>' if (godzina_koniec and godzina_koniec != godzina_start) else ''

        row_html = (
            f'<div class="timeline-row">'
            f'<div class="timeline-time">'
            f'<span class="timeline-time-start">{godzina_start}</span>'
            f'{time_end_html}'
            f'</div>'
            f'<div class="timeline-center-col">'
            f'<a href="{toggle_expand_url}" target="_self" class="timeline-icon-badge {badge_class}" title="Kliknij, aby rozwinąć/zwinąć szczegóły">{badge_symbol}</a>'
            f'</div>'
            f'<div class="timeline-content-col">'
            f'<div class="timeline-item-title">{tytul_wyswietlany}</div>'
            f'<div class="timeline-item-desc">{opis_tekst}</div>'
            f'</div>'
            f'{nav_btn_html}'
            f'</div>'
        )
        st.markdown(row_html, unsafe_allow_html=True)

        if is_expanded:
            google_search_url = f"https://www.google.com/search?q={nazwa} Kreta"
            sklep_maps_url = f"https://www.google.com/maps/search/supermarket/@{coords_clean},15z" if coords_clean else "#"
            resto_maps_url = f"https://www.google.com/maps/search/restaurant/@{coords_clean},15z" if coords_clean else "#"

            pogoda_kroku = pobierz_szczegoly_pogody_dla_godziny(k['wspolrzedne'], planowana_data_val, okienko)
            pogoda_html = ""
            if pogoda_kroku:
                pogoda_html = (
                    f'<div style="background-color: #FAF8F2; border: 1.5px solid #D8D2BC; border-radius: 16px; padding: 10px 14px; margin-bottom: 12px; text-align: center;">'
                    f'<div style="font-size: 8.5pt; font-weight: 800; color: #8C5338; text-transform: uppercase; margin-bottom: 3px;">☀️ PROGNOZA POGODY ({pogoda_kroku["data"]})</div>'
                    f'<div style="font-size: 10.5pt; font-weight: 800; color: #2B2118;">{pogoda_kroku["temp"]}°C (odczuwalna {pogoda_kroku["feel"]}°C), {pogoda_kroku["desc"]} 💨 {pogoda_kroku["wind"]} km/h | ☀️ UV {pogoda_kroku["uv"]}</div>'
                    f'</div>'
                )

            opis_glowny = str(k.get('opis', '')).strip()
            opis_glowny_html = f'<div class="step-desc-bubble">{opis_glowny}</div>' if (opis_glowny and opis_glowny != "None") else ""

            ewakuacja_val = str(k.get('godzina_ewakuacji', '')).strip()
            evac_html = ""
            if ewakuacja_val and ewakuacja_val != "None" and ewakuacja_val != "Brak":
                evac_html = (
                    f'<div class="step-evac-pill">'
                    f'<div class="step-evac-pill-title">🚨 Godzina ewakuacji</div>'
                    f'<div class="step-evac-pill-val">{ewakuacja_val}</div>'
                    f'</div>'
                )

            ostrzezenie_val = str(k.get('czerwona_strefa_ostrzezenie', '')).strip()
            warn_html = ""
            if ostrzezenie_val and ostrzezenie_val != "None" and ostrzezenie_val != "Brak":
                warn_html = (
                    f'<div class="step-warn-box">'
                    f'<div class="step-warn-title">⚠️ Ostrzeżenie (Czerwona strefa)</div>'
                    f'<div class="step-warn-text">{ostrzezenie_val}</div>'
                    f'</div>'
                )

            taktyka_val = k.get("podsumowanie_taktyki", "Brak szczegółów taktyki")
            regen_val = k.get("strefa_luzu_i_regeneracji", "Brak strefy regeneracji")

            df_zakupy = pobierz_zakupy_dla_kroku(k['id'])
            zakupy_items_html = ""
            if df_zakupy.empty:
                zakupy_items_html = "<div style='font-size: 8.5pt; color: #8C827A; font-style: italic; margin-bottom: 8px;'>Brak zaplanowanych zakupów w tym punkcie.</div>"
            else:
                for _, z in df_zakupy.iterrows():
                    z_id = z['id']
                    z_nazwa = z['nazwa_produktu']
                    z_ilosc = z['ilosc']
                    z_kupione = bool(z['kupione'])
                    check_icon = "☑️" if z_kupione else "⬜"
                    ilosc_txt = f" ({z_ilosc})" if z_ilosc and z_ilosc != "1" else ""
                    zakupy_items_html += f"<div style='font-size: 9pt; color: #2B2118; font-weight: 700; margin-bottom: 4px;'>{check_icon} {z_nazwa}{ilosc_txt}</div>"

            details_html = (
                f'<div class="step-details-card">'
                f'<div style="font-size: 10pt; font-weight: 800; color: #8C5338; margin-bottom: 8px;">🕒 {okienko} | 📌 {nazwa}</div>'
                f'{pogoda_html}'
                f'{opis_glowny_html}'
                f'{evac_html}'
                f'{warn_html}'
                f'<details class="step-combined-card">'
                f'<summary>🎯 Taktyka & Regeneracja</summary>'
                f'<div style="margin-top: 10px; border-top: 1px solid #D1C7AE; padding-top: 8px;">'
                f'<div class="step-subitem-title" style="color: #8C5338;">🎯 Taktyka: Wyciszenie</div>'
                f'<div class="step-subitem-body">{taktyka_val}</div>'
                f'<div class="step-subitem-title" style="color: #6D8257; margin-top: 8px;">🌿 Regeneracja: Strefa luzu</div>'
                f'<div class="step-subitem-body">{regen_val}</div>'
                f'</div>'
                f'</details>'
                f'<details class="step-combined-card">'
                f'<summary>🛒 Zakupy</summary>'
                f'<div style="margin-top: 10px; border-top: 1px solid #D1C7AE; padding-top: 8px;">'
                f'{zakupy_items_html}'
                f'</div>'
                f'</details>'
                f'<div class="step-action-vertical-bar">'
                f'<a href="{google_search_url}" target="_blank" class="step-action-vertical-btn"><span>🔍</span><span>Google</span></a>'
                f'<a href="{sklep_maps_url}" target="_blank" class="step-action-vertical-btn"><span>🛒</span><span>Sklep</span></a>'
                f'<a href="{resto_maps_url}" target="_blank" class="step-action-vertical-btn"><span>🍽️</span><span>Resto</span></a>'
                f'</div>'
                f'</div>'
            )
            st.markdown(details_html, unsafe_allow_html=True)

            with st.expander("➕ Dodaj pozycję zakupową"):
                with st.form(key=f"form_inline_zakup_{krok_row_id}"):
                    p_nazwa = st.text_input("Nazwa produktu", placeholder="np. Woda, owoce")
                    p_ilosc = st.text_input("Ilość", value="1")
                    if st.form_submit_button("💾 Zapisz produkt", use_container_width=True):
                        if p_nazwa.strip():
                            dodaj_produkt_zakupow(int(krok_row_id), p_nazwa.strip(), p_ilosc.strip())
                            st.session_state["flash_toast"] = "🛒 Dodano produkt!"
                            st.rerun()

        if idx < len(kroki_df) - 1:
            k2_row_id = int(kroki_df.iloc[idx + 1]['id'])
            match_row = czasy_dojazdu_df[(czasy_dojazdu_df['id_kroku_z'] == krok_row_id) & (czasy_dojazdu_df['id_kroku_do'] == k2_row_id)]
            if not match_row.empty:
                czas_dojazdu_dalej = match_row.iloc[0]['czas_przejazdu']
                postoj_val = match_row.iloc[0]['szacowany_czas_postoju']
                if pd.notna(czas_dojazdu_dalej) and str(czas_dojazdu_dalej).strip() != "":
                    st.markdown(f'<div class="timeline-transit-row"><div style="background-color: #EFE8D6; border: 1.5px solid #D6CEBC; border-radius: 20px; padding: 4px 14px; font-size: 8.5pt; font-weight: 800; display: flex; align-items: center; gap: 6px; color: #8C5338;"><span>🚗</span> Dojazd: <span style="color: #2B2118;">{czas_dojazdu_dalej}</span> | ⏱️ Postój: <span style="color: #2B2118;">{postoj_val} min</span></div></div>', unsafe_allow_html=True)

    st.markdown('</div></div>', unsafe_allow_html=True)
    renderuj_sekcje_notatek(id_wycieczki=wycieczka_id)

# --- DOLNY PASEK NAWIGACJI: Miejsca / Wycieczki / Trasa Dnia ---
active_zabytek = "active" if st.session_state.active_tab == "zabytek" else ""
active_map = "active" if st.session_state.active_tab == "map" else ""
active_route = "active" if st.session_state.active_tab == "route" else ""

st.markdown(f"""
<div class="bottom-nav-container">
<a href="?tab=zabytek" target="_self" class="bottom-nav-btn {active_zabytek}"><span>🏛️</span><span>Miejsca</span></a>
<a href="?tab=map" target="_self" class="bottom-nav-btn {active_map}"><span>🗺️</span><span>Wycieczki</span></a>
<a href="?tab=route" target="_self" class="bottom-nav-btn {active_route}"><span>🚗</span><span>Trasa Dnia</span></a>
</div>
""", unsafe_allow_html=True)

# --- ROUTING ZAKŁADEK ---
if st.session_state.active_tab == "route":
    aktualne_id = pobierz_aktywna_wycieczke_id()
    renderuj_karte_wycieczki(aktualne_id, pokaz_mape=False, pokaz_pogode=True)

elif st.session_state.active_tab == "map":
    st.markdown("""
<div class="adventure-header">
<div style="font-size:24px;">🗺️</div>
<div><div class="adventure-title-text">CretAi • Mapa Trasy</div></div>
</div>
""", unsafe_allow_html=True)
    
    opcje_wycieczek_lista = ["-- Wybierz wycieczkę lub mapę miejsc --"] + wycieczki_options
    wybrana_mapa_sb = st.selectbox("", options=opcje_wycieczek_lista, key="map_wycieczka_select", label_visibility="collapsed")
    
    if wybrana_mapa_sb == "-- Wybierz wycieczkę lub mapę miejsc --":
        m_all = folium.Map(location=[35.3, 24.5], zoom_start=9, tiles="CartoDB positron")
        dodaj_marker_domku(m_all)
        for _, row in df_miejsca.iterrows():
            coords = str(row['wspolrzedne'])
            if ',' in coords:
                try:
                    parts = coords.split(',')
                    lat, lon = float(parts[0].strip()), float(parts[1].strip())
                    num = str(row['numer_miejsca'])
                    icon_html = f'<div style="background-color:#C06C4E;color:white;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:900;border:2px solid white;">{num}</div>'
                    folium.Marker([lat, lon], icon=folium.DivIcon(html=icon_html, icon_size=(26, 26), icon_anchor=(13, 13)), tooltip=row['nazwa']).add_to(m_all)
                except:
                    pass
        st_folium(m_all, width="100%", height=340)
    else:
        if wybrana_mapa_sb:
            wybrana_id = wybrana_mapa_sb.split(". ")[0]
            renderuj_karte_wycieczki(wybrana_id, pokaz_mape=True, pokaz_pogode=False)

elif st.session_state.active_tab == "zabytek":
    st.markdown("""
<div class="adventure-header">
<div style="font-size:24px;">🏛️</div>
<div><div class="adventure-title-text">CretAi • Baza Miejsc</div></div>
</div>
""", unsafe_allow_html5=True)
    
    miejsca_opcje_lista = [f"{r['numer_miejsca']}. {r['nazwa']}" for _, r in df_miejsca.iterrows()]
    selected_option = st.selectbox("Wybierz miejsce:", options=[None] + miejsca_opcje_lista, format_func=lambda x: "Wybierz atrakcję..." if x is None else x)
    
    if selected_option:
        numer_m = selected_option.split(".")[0].strip()
        p_row = df_miejsca[df_miejsca['numer_miejsca'] == numer_m]
        if not p_row.empty:
            p = p_row.iloc[0]
            st.markdown(f"### {p['nazwa']}")
            st.write(p['opis'])
            st.markdown(f"**🧠 Trudność ADHD:** {p.get('trudnosc_adhd', 'Średnia')}")
            st.markdown(f"**🛡️ Strategia:** {p.get('strategie_meltdown', 'Brak')}")
            renderuj_sekcje_notatek(id_miejsca=numer_m)

renderuj_globalny_czat_ai(aktualny_uzytkownik)
