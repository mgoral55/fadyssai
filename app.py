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
from datetime import datetime, date, time, timedelta

# Próba zaimportowania Anthropic SDK dla Claude'a
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# --- 0. BEZPIECZNE POŁĄCZENIE Z BAZĄ DANYCH (CONCURRENCY & WAL) ---
def get_db():
    conn = sqlite3.connect('cretai.db', timeout=30.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA busy_timeout = 30000;')
    return conn

# --- 1. KONFIGURACJA STRONY I DESIGN SYSTEM ---
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
    padding-top: 1.0rem !important;
    padding-bottom: 140px !important;
    max-width: 540px;
}
.stApp {
    background-color: #B4C29D !important;
    color: #2F241D !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

/* PASEK BOCZNY */
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

/* INPUTY, COMBOBOXY I WIDGETY BASEWEB */
input, textarea, .stChatInput textarea {
    background-color: #FAF8F2 !important;
    color: #2B2118 !important;
    border: 1.5px solid #D6D2C4 !important;
    border-radius: 16px !important;
}
::placeholder {
    color: #8C827A !important;
}

/* STYLIZACJA SELEKTORÓW, TIMEPICKERÓW I BASEWEB */
div[data-baseweb="select"],
div[data-baseweb="select"] > div,
div[data-baseweb="select"] * {
    background-color: #FAF8F2 !important;
    color: #2B2118 !important;
    fill: #2B2118 !important;
}
div[data-baseweb="select"] > div {
    border: 1.5px solid #D6D2C4 !important;
    border-radius: 16px !important;
}
div[data-baseweb="popover"],
div[data-baseweb="popover"] > div,
ul[role="listbox"],
li[role="option"] {
    background-color: #FAF8F2 !important;
    color: #2B2118 !important;
}
li[role="option"]:hover,
li[aria-selected="true"] {
    background-color: #EFE8D1 !important;
    color: #8C5338 !important;
}
div[data-baseweb="input"],
div[data-baseweb="input"] > div,
div[data-baseweb="input"] input {
    background-color: #FAF8F2 !important;
    color: #2B2118 !important;
    border-color: #D6D2C4 !important;
}

/* WYMUSZENIE POZIOMEGO UKŁADU KOLUMN STREAMLITA DLA LOGISTYKI */
div[data-testid="stHorizontalBlock"] {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    gap: 8px !important;
}
div[data-testid="stHorizontalBlock"] > div {
    flex: 1 1 0px !important;
    min-width: 0 !important;
}

/* PRZYCISK DATY */
div.st-key-btn_date_picker button {
    background-color: #F6F0DD !important;
    color: #2B2118 !important;
    border: 1.5px solid #E2DEC8 !important;
    border-radius: 20px !important;
    padding: 14px 16px !important;
    min-height: 52px !important;
    font-size: 1.02rem !important;
    font-weight: 800 !important;
    width: 100% !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;
}
div.st-key-btn_date_picker button:hover {
    border-color: #8C5338 !important;
    background-color: #EFE8D1 !important;
}

/* PRZYCISKI POPOVER LOGISTYKI */
div[data-testid="stPopover"] {
    width: 100% !important;
}
div[data-testid="stPopover"] > button,
div[data-testid="stPopover"] > button:disabled,
div[data-testid="stPopover"] > button[aria-expanded],
div[data-testid="stPopover"] > button:focus,
div[data-testid="stPopover"] > button:active {
    background-color: #F6F0DD !important;
    color: #2B2118 !important;
    border: 1.5px solid #E2DEC8 !important;
    border-radius: 20px !important;
    padding: 18px 10px !important;
    min-height: 72px !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;
    width: 100% !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
div[data-testid="stPopover"] > button * {
    color: #2B2118 !important;
    font-weight: 900 !important;
    font-size: 1.15rem !important;
}
div[data-testid="stPopover"] > button:hover {
    border-color: #8C5338 !important;
    background-color: #EFE8D1 !important;
}

/* EXPANDER OGÓLNY / TAKTYKA DNIA */
[data-testid="stExpander"] {
    border: 1.5px solid #E2DEC8 !important;
    border-radius: 24px !important;
    background-color: #F6F0DD !important;
    margin-bottom: 6px !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;
    overflow: hidden !important;
}
[data-testid="stExpander"] summary {
    font-size: 10pt !important;
    font-weight: 800 !important;
    color: #2B2118 !important;
}
[data-testid="stExpander"] summary:hover {
    color: #8C5338 !important;
}
[data-testid="stExpander"] summary svg {
    fill: #8C5338 !important;
    color: #8C5338 !important;
}
[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    background-color: #F6F0DD !important;
    border-top: 1px solid #D1C7AE !important;
    padding: 12px 14px !important;
}

/* NAWIGACJA GÓRNA */
.top-sticky-nav-container {
    position: sticky;
    top: 0;
    z-index: 999;
    background-color: #B4C29D;
    padding: 8px 0 12px 0;
    margin-bottom: 8px;
    border-bottom: 1.5px solid rgba(255, 255, 255, 0.2);
}
.custom-top-nav-bar {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    width: 100%;
}
.custom-top-nav-btn {
    flex: 1;
    background-color: #EFE8D6;
    border: 1.5px solid #D6CEBC;
    color: #8A7B70;
    padding: 8px 4px;
    text-align: center;
    border-radius: 14px;
    font-size: 11px;
    font-weight: 800;
    text-decoration: none;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.03);
}
.custom-top-nav-btn.active {
    background-color: #F6F0DD;
    color: #8C5338;
    border-color: #C8C0AC;
    font-weight: 900;
}

/* Belka nagłówkowa */
.adventure-header {
    background: #2E251E;
    border: none;
    border-radius: 20px;
    padding: 12px 16px;
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
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
    padding: 4px 4px 6px 4px;
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

div.st-key-btn_date_picker {
    margin-bottom: 12px !important;
}

/* UJEDNOLICONE NAGŁÓWKI SEKCJI */
.section-unified-header {
    font-size: 1.25rem !important;
    font-weight: 800 !important;
    color: #2B2118 !important;
    margin-top: 16px !important;
    margin-bottom: 8px !important;
    display: flex;
    align-items: center;
    gap: 8px;
}

.section-body-text {
    font-size: 9.5pt;
    color: #2B2118;
    font-weight: 600;
    line-height: 1.4;
    margin-bottom: 12px;
}

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
    color: #2B2118;
    cursor: pointer;
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
}

/* OŚ CZASU */
.timeline-master-container {
    position: relative;
    display: flex;
    flex-direction: column;
    width: 100%;
    margin-bottom: 16px;
}

.timeline-master-continuous-line {
    position: absolute;
    left: 94px;
    top: 32px;
    bottom: 32px;
    width: 3.5px;
    background-color: rgba(0, 0, 0, 0.25) !important;
    transform: translateX(-50%);
    z-index: 1 !important;
    pointer-events: none;
}

.timeline-step-row-wrapper {
    position: relative;
    width: 100%;
    z-index: 2;
}

.timeline-row-frameless {
    position: relative;
    display: flex;
    align-items: center;
    min-height: 56px;
    background-color: transparent !important;
    border: none !important;
    padding: 6px 12px;
    box-sizing: border-box;
}

.timeline-step-expander {
    position: relative;
    background-color: #F6F0DD;
    border: 1.5px solid #E2DEC8;
    border-radius: 20px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.03);
    overflow: hidden;
    box-sizing: border-box;
}
.timeline-step-expander summary {
    list-style: none !important;
    cursor: pointer;
    padding: 10px 12px;
    background-color: #F6F0DD;
    border-radius: 20px;
    display: block;
}
.timeline-step-expander summary::-webkit-details-marker,
.timeline-step-expander summary::marker {
    display: none !important;
}
.timeline-step-expander[open] summary {
    border-bottom: 1.5px solid #E2DEC8;
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
}

.timeline-row-inner {
    position: relative;
    display: flex;
    align-items: center;
    min-height: 44px;
    width: 100%;
}

.timeline-time {
    position: relative;
    width: 58px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
    z-index: 2;
}
.timeline-time-start {
    font-size: 11pt;
    font-weight: 900;
    color: #2B2118;
}
.timeline-time-end {
    font-size: 8.5pt;
    font-weight: 700;
    color: #8C5338;
    margin-top: 2px;
}

.timeline-center-col {
    position: relative;
    width: 48px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: 8px;
}

.timeline-icon-badge-static {
    position: relative;
    width: 38px;
    height: 38px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13pt;
    font-weight: 900;
    color: #FFFFFF !important;
    border: 2.5px solid #FFFFFF !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.15);
    z-index: 5 !important;
    opacity: 1 !important;
}

.badge-pobudka { background-color: #94A77E !important; }
.badge-wyjazd  { background-color: #94A77E !important; }
.badge-miejsce { background-color: #C06C4E !important; }
.badge-obiad { background-color: #B56749 !important; }
.badge-powrot { background-color: #94A77E !important; }

.timeline-content-col {
    position: relative;
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    z-index: 2;
}
.timeline-item-title {
    font-size: 12.5pt;
    font-weight: 900;
    color: #2B2118;
}
.timeline-item-desc {
    font-size: 9.5pt;
    color: #4A3E36;
}

.timeline-nav-btn {
    position: relative;
    flex-shrink: 0;
    width: auto;
    min-width: 50px;
    height: 48px;
    background-color: transparent !important;
    border: none !important;
    border-radius: 14px;
    text-align: center;
    text-decoration: none !important;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1px;
    margin-left: 8px;
    padding: 0 4px;
    z-index: 2;
}
.timeline-nav-btn span:first-child { font-size: 13pt; color: #8C5338; }
.timeline-nav-btn span:last-child { font-size: 7.5pt; font-weight: 800; color: #2B2118; }

.timeline-step-expander .timeline-expander-body {
    position: relative;
    padding: 12px 14px;
    background-color: #F6F0DD !important;
    z-index: 3;
}

.step-details-card {
    position: relative;
    background-color: #EDE8D6 !important;
    border: 1.5px solid #D6CEBA;
    border-radius: 18px;
    padding: 14px;
    margin-bottom: 8px;
    z-index: 3;
}
.step-desc-bubble {
    background-color: #E2DAC4;
    border-radius: 16px;
    padding: 12px 14px;
    font-size: 10pt;
    color: #2B2118;
    font-weight: 600;
    margin-bottom: 10px;
}
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
}
.step-warn-text {
    font-size: 9pt;
    font-weight: 700;
    color: #2B2118;
}

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
}

.step-subitem-title {
    font-size: 9.5pt;
    font-weight: 800;
    margin-bottom: 3px;
}
.step-subitem-body {
    font-size: 9pt;
    color: #2B2118;
    font-weight: 600;
}

.step-action-vertical-bar {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 14px;
    margin-bottom: 4px;
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
}
.step-action-vertical-btn span:first-child { font-size: 13pt; }
.step-action-vertical-btn span:last-child { font-size: 9.5pt; font-weight: 800; color: #2B2118; }

.timeline-transit-spacer {
    position: relative;
    width: 100%;
    min-height: 28px;
    display: flex;
    align-items: center;
    margin: 4px 0;
    z-index: 2;
}

.timeline-transit-text {
    margin-left: 118px;
    font-size: 9pt;
    font-weight: 800;
    color: #2B2118;
    display: flex;
    align-items: center;
    gap: 6px;
    z-index: 2;
    background: transparent;
    border: none;
    padding: 0;
}

div[data-testid="stCheckbox"] {
    margin-bottom: 6px !important;
    background-color: #FAF8F2 !important;
    border: 1.2px solid #E2DEC8 !important;
    border-radius: 14px !important;
    padding: 8px 12px !important;
    accent-color: #8C5338 !important;
}
div[data-testid="stCheckbox"] label {
    font-size: 9.5pt !important;
    font-weight: 700 !important;
    color: #2B2118 !important;
}

.floating-ai-container {
    position: fixed;
    bottom: 15px;
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
    background-color: #F4EFE6;
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

CATEGORIES_CONFIG = {
    "Must have": {"color": "#B35446", "slug": "must_have", "icon": "🏛️"},
    "Nice to have": {"color": "#C47C48", "slug": "nice_to_have", "icon": "✨"},
    "Plaża": {"color": "#4A7C8F", "slug": "plaza", "icon": "🏖️"},
    "Activity": {"color": "#C6934B", "slug": "activity", "icon": "🧗"},
    "Shop": {"color": "#7D5871", "slug": "shop", "icon": "🛒"},
    "Other": {"color": "#5D7A60", "slug": "other", "icon": None}
}

def kategoryzuj_typ(typ_str):
    if not typ_str or pd.isna(typ_str):
        return "Other"
    t = str(typ_str).lower().strip()
    if "must" in t:
        return "Must have"
    elif "nice" in t:
        return "Nice to have"
    elif "plaż" in t or "plaz" in t or "beach" in t:
        return "Plaża"
    elif "activ" in t or "aktywn" in t or "wąwóz" in t or "wawoz" in t or "sport" in t:
        return "Activity"
    elif "shop" in t or "sklep" in t or "zakup" in t or "market" in t:
        return "Shop"
    else:
        return "Other"

def pobierz_kolor_kategorii(kategoria):
    return CATEGORIES_CONFIG.get(kategoria, CATEGORIES_CONFIG["Other"])["color"]

def pobierz_ikonke_kategorii(kategoria):
    return CATEGORIES_CONFIG.get(kategoria, CATEGORIES_CONFIG["Other"]).get("icon")

def zaokraglij_do_5_minut(minuty):
    return int(round(minuty / 5.0) * 5)

@st.cache_data(ttl=86400)
def oblicz_czas_przejazdu_osrm(lat1, lon1, lat2, lon2):
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'CretAiApp/1.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            if 'routes' in data and len(data['routes']) > 0:
                duration_sec = data['routes'][0]['duration']
                surowe_minuty = int(round(duration_sec / 60))
                minuty = zaokraglij_do_5_minut(surowe_minuty)
                if minuty < 60:
                    return f"~{minuty} min", minuty
                godziny = minuty // 60
                reszta = minuty % 60
                if reszta == 0:
                    return f"~{godziny}h", minuty
                return f"~{godziny}h {reszta}m", minuty
    except:
        pass
    return "~25 min", 25

def sparsuj_wspolrzedne(wsp_str):
    if not wsp_str or pd.isna(wsp_str):
        return None, None
    s = str(wsp_str).replace(' ', '').replace(';', ',')
    if ',' not in s:
        return None, None
    try:
        parts = s.split(',')
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

def oblicz_czas_trwania_okienka(okienko_str, domyslny_czas=45):
    if not okienko_str or "-" not in str(okienko_str):
        return domyslny_czas
    try:
        czesci = str(okienko_str).split("-")
        g1 = sparsuj_godzine_minuty(czesci[0])
        g2 = sparsuj_godzine_minuty(czesci[1])
        if g1 and g2:
            m1 = g1[0] * 60 + g1[1]
            m2 = g2[0] * 60 + g2[1]
            diff = m2 - m1
            return max(diff, 15)
    except:
        pass
    return domyslny_czas

def sparsuj_czas_ogarniania_na_minuty(czas_str):
    if not czas_str:
        return 30
    s = str(czas_str).lower()
    g_match = re.search(r'(\d+(?:\.\d+)?)\s*h', s)
    m_match = re.search(r'(\d+)\s*m', s)
    
    godziny = float(g_match.group(1)) if g_match else 0.0
    minuty = int(m_match.group(1)) if m_match else 0
    total = int(round(godziny * 60)) + minuty
    
    if total == 0:
        try:
            total = int(float(s) * 60) if '.' in s else int(s)
        except:
            total = 30
    return max(total, 15)

DNI_TYGODNIA_PL = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
MIESIACE_PL = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]

def wczytaj_pliki_regul(katalog="rule"):
    if not os.path.exists(katalog):
        return ""
    tresc_regul = "\n--- REGUŁY Z FOLDERU RULE ---\n"
    znaleziono = False
    for plik in sorted(os.listdir(katalog)):
        sciezka = os.path.join(katalog, plik)
        if os.path.isfile(sciezka) and plik.lower().endswith(('.txt', '.md', '.json', '.rule', '.csv')):
            try:
                with open(sciezka, 'r', encoding='utf-8') as f:
                    tresc_regul += f"\n[Plik: {plik}]\n{f.read()}\n"
                    znaleziono = True
            except:
                try:
                    with open(sciezka, 'r', encoding='cp1250') as f:
                        tresc_regul += f"\n[Plik: {plik}]\n{f.read()}\n"
                        znaleziono = True
                except:
                    pass
    return tresc_regul if znaleziono else ""

def przelicz_i_zsynchronizuj_wycieczke(id_wycieczki, anchor_krok_id=None, anchor_koniec_str=None, anchor_start_str=None, force_pobudka_str=None, force_wyjazd_str=None, force_powrot_str=None):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT szacowany_czas_ogarniania_rano, pobudka, czas_wyjazdu FROM wycieczka WHERE id = ?', (str(id_wycieczki),))
        row_ogarnianie = cursor.fetchone()
        surowy_ogarniania = row_ogarnianie[0] if row_ogarnianie else '0.5h'
        pobudka_z_bazy = row_ogarnianie[1] if row_ogarnianie and row_ogarnianie[1] else '06:00'
        minuty_ogarniania = sparsuj_czas_ogarniania_na_minuty(surowy_ogarniania)

        cursor.execute('SELECT id_kroku_z, id_kroku_do, szacowany_czas_postoju FROM czasy_dojazdu WHERE szacowany_czas_postoju IS NOT NULL')
        istniejace_postoje = {(row[0], row[1]): row[2] for row in cursor.fetchall()}

        cursor.execute('SELECT id, krok_wycieczki, wspolrzedne, okienko_zwiedzania, nazwa FROM krok_wycieczki WHERE id_wycieczki = ? ORDER BY CAST(krok_wycieczki AS INTEGER) ASC, id ASC', (str(id_wycieczki),))
        kroki = cursor.fetchall()
    
    if not kroki:
        return

    dojazdy_minuty = []
    dojazdy_tekst = []
    postoje_na_trasie_minuty = []
    
    for idx in range(len(kroki) - 1):
        k1_id = kroki[idx][0]
        k2_id = kroki[idx + 1][0]
        k1_wsp = kroki[idx][2]
        k2_wsp = kroki[idx + 1][2]
        lat1, lon1 = sparsuj_wspolrzedne(k1_wsp)
        lat2, lon2 = sparsuj_wspolrzedne(k2_wsp)
        minuty_przejazdu = 25
        tekst_dojazdu = "~25 min"
        if lat1 is not None and lon1 is not None and lat2 is not None and lon2 is not None:
            tekst_dojazdu, minuty_przejazdu = oblicz_czas_przejazdu_osrm(lat1, lon1, lat2, lon2)
        
        bufor_postoju = istniejace_postoje.get((k1_id, k2_id), 0)
        dojazdy_minuty.append(minuty_przejazdu)
        dojazdy_tekst.append(tekst_dojazdu)
        postoje_na_trasie_minuty.append(bufor_postoju)

    czasy_pobytu = []
    for idx, k in enumerate(kroki):
        is_f = (idx == 0)
        is_l = (idx == len(kroki) - 1)
        nazwa_lower = str(k[4]).lower()
        
        if "sklep" in nazwa_lower or "market" in nazwa_lower or "zakup" in nazwa_lower or "apteka" in nazwa_lower:
            domyslny_czas = 25
        elif "plaż" in nazwa_lower or "beach" in nazwa_lower:
            domyslny_czas = 90
        elif is_f or is_l:
            domyslny_czas = 30
        else:
            domyslny_czas = 60

        dur = oblicz_czas_trwania_okienka(k[3], domyslny_czas=domyslny_czas)
        czasy_pobytu.append(dur)

    start_times = [None] * len(kroki)
    end_times = [None] * len(kroki)

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
            czas_odcinka = dojazdy_minuty[i] + postoje_na_trasie_minuty[i]
            end_times[i] = start_times[i + 1] - timedelta(minutes=czas_odcinka)
            start_times[i] = end_times[i] - timedelta(minutes=czasy_pobytu[i])

        start_times[0] = dt_pob
        end_times[0] = start_times[1] - timedelta(minutes=(dojazdy_minuty[0] + postoje_na_trasie_minuty[0]))
    elif force_wyjazd_str:
        g_wyj = sparsuj_godzine_minuty(force_wyjazd_str) or (6, 30)
        dt_wyj = datetime(2026, 1, 1, g_wyj[0], g_wyj[1])
        
        dt_pob = dt_wyj - timedelta(minutes=minuty_ogarniania)
        pobudka_z_bazy = dt_pob.strftime("%H:%M")
        
        start_times[0] = dt_pob
        end_times[0] = dt_wyj
        
        cur_dt = dt_wyj
        for i in range(1, len(kroki)):
            czas_odcinka = dojazdy_minuty[i - 1] + postoje_na_trasie_minuty[i - 1]
            start_times[i] = cur_dt + timedelta(minutes=czas_odcinka)
            end_times[i] = start_times[i] + timedelta(minutes=czasy_pobytu[i])
            cur_dt = end_times[i]
    else:
        cur_dt = dt_wyj
        for i in range(len(kroki)):
            if i == 0:
                start_times[i] = dt_pob
                end_times[i] = dt_wyj
            else:
                start_times[i] = cur_dt
                end_times[i] = cur_dt + timedelta(minutes=czasy_pobytu[i])
            if i < len(kroki) - 1:
                czas_odcinka = dojazdy_minuty[i] + postoje_na_trasie_minuty[i]
                cur_dt = end_times[i] + timedelta(minutes=czas_odcinka)

    with get_db() as conn:
        cursor = conn.cursor()
        krok_ids = [k[0] for k in kroki]
        if krok_ids:
            placeholders = ','.join(['?'] * len(krok_ids))
            cursor.execute(f'DELETE FROM czasy_dojazdu WHERE id_kroku_z IN ({placeholders}) OR id_kroku_do IN ({placeholders})', krok_ids + krok_ids)

        for i in range(len(kroki)):
            s_str = start_times[i].strftime("%H:%M")
            e_str = end_times[i].strftime("%H:%M")
            nowe_okienko = f"{s_str} - {e_str}"
            cursor.execute('UPDATE krok_wycieczki SET okienko_zwiedzania = ? WHERE id = ?', (nowe_okienko, kroki[i][0]))
            
            cursor.execute('UPDATE posilki_kroku SET sugerowana_godzina = ? WHERE id_kroku = ?', (s_str, kroki[i][0]))

            if i < len(kroki) - 1:
                cursor.execute('''
                    INSERT INTO czasy_dojazdu (id_kroku_z, id_kroku_do, czas_przejazdu, szacowany_czas_postoju)
                    VALUES (?, ?, ?, ?)
                ''', (kroki[i][0], kroki[i + 1][0], dojazdy_tekst[i], postoje_na_trasie_minuty[i]))

        dt_wyjazd = end_times[0]
        dt_powrot = start_times[-1]
        roznica_sek = (dt_powrot - dt_wyjazd).total_seconds()
        czas_trwania_h = round(max(roznica_sek / 3600.0, 0.5), 1)

        cursor.execute('''
            UPDATE wycieczka 
            SET pobudka = ?, czas_wyjazdu = ?, szacowana_godzina_powrotu = ?, calkowity_czas_wycieczki_godziny = ?, czas_powrotu_do_domku = NULL
            WHERE id = ?
        ''', (pobudka_z_bazy, dt_wyjazd.strftime("%H:%M"), dt_powrot.strftime("%H:%M"), str(czas_trwania_h), str(id_wycieczki)))
        conn.commit()

def init_db():
    conn = get_db()
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
            szacowany_czas_ogarniania_rano TEXT DEFAULT '0.5h',
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
            szacowany_czas_postoju INTEGER DEFAULT 0,
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
            sugerowana_godzina TEXT,
            opis TEXT,
            FOREIGN KEY (id_kroku) REFERENCES krok_wycieczki(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS zakupy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_wycieczki TEXT,
            id_kroku INTEGER,
            nazwa_produktu TEXT NOT NULL,
            ilosc TEXT,
            kupione INTEGER DEFAULT 0,
            FOREIGN KEY (id_wycieczki) REFERENCES wycieczka(id) ON DELETE CASCADE,
            FOREIGN KEY (id_kroku) REFERENCES krok_wycieczki(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute("PRAGMA table_info(zakupy)")
    cols_zakupy = [col[1] for col in cursor.fetchall()]
    if "id_wycieczki" not in cols_zakupy:
        cursor.execute("ALTER TABLE zakupy ADD COLUMN id_wycieczki TEXT")

    cursor.execute('''
        UPDATE zakupy 
        SET id_wycieczki = (SELECT id_wycieczki FROM krok_wycieczki WHERE krok_wycieczki.id = zakupy.id_kroku)
        WHERE id_wycieczki IS NULL AND id_kroku IS NOT NULL
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS zadania_dzieci_status (
            klucz_zadania TEXT PRIMARY KEY,
            ukonczone INTEGER DEFAULT 0
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
        cursor.execute('SELECT COUNT(*) FROM miejsca')
        if cursor.fetchone()[0] == 0:
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
            INSERT INTO wycieczka (id, tytul_wycieczki, calosciowy_opis_wycieczki, calosciowa_taktyka_dnia, calkowity_czas_wycieczki_godziny, szacowana_godzina_powrotu, pobudka, czas_wyjazdu, planowana_data, szacowany_czas_ogarniania_rano, odbyta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        ''', (
            "1",
            "Mity i Oceaniczne Głębiny: Pałac w Knossos & Cretaquarium",
            "Wyprawa łącząca mityczną historię starożytnej Krety z podwodnym światem głębin w klimatyzowanym akwarium oraz relaksem nad jeziorem Kournas.",
            "Żelazna kontrola czasu rano w Knossos, obiad w Cretaquarium i popołudniowe wyciszenie nad jeziorem.",
            "10.0",
            "17:30",
            "06:00",
            "06:30",
            domyslna_data,
            "0.5h"
        ))

        kroki_w1 = [
            ("1", "0", "Nasz Domek (Start)", f"{DOMEK_LAT}, {DOMEK_LON}", "06:00 - 06:30", "Brak", "Brak", "Spokojna baza", "Poziom energii, prosta rada (np. 'Światło dzienne, spokojna muzyka').", "Niski", "Ciepła atmosfera w domku", "Nasz domek wypadowy w Stavros."),
            ("1", "1", "Pałac w Knossos", "35.2980, 25.1631", "08:00 - 10:30", "11:30", "BEZWZGLĘDNIE EWAKUOWAĆ SIĘ PRZED 12:00! Tłumy i upał.", "Brak - rygor czasowy.", "Poziom tłumu (Niski), szacowany czas zwiedzania.", "Wysoki (tłumy, brak cienia, duchota)", "Użycie aplikacji 3D na iPadzie jako kotwica uwagi, szybka ewakuacja w razie buntu.", "Legendarska stolica minojskiej Krety z ruinami pałacu króla Minosa."),
            ("1", "2", "Cretaquarium", "35.3326, 25.2825", "12:30 - 14:30", "Brak", "Unikać godzin szczytu.", "Kawiarnia obok", "Poziom stymulacji sensorycznej (Umiarkowany - półmrok, chłód).", "Średni (pogłos w halach, tłum)", "Słuchawki wygłuszające, powolne tempo, półmrok przy akwariach.", "Jedno z największych oceanariów w basenie Morza Śródziemnego."),
            ("1", "3", "Nasz Domek (Powrót)", f"{DOMEK_LAT}, {DOMEK_LON}", "15:00 - 18:00", "Brak", "Brak", "Pełny relaks", "Poziom energii na koniec dnia, prosta rada (np. 'Wyciszenie w drodze').", "Niski", "Kolacja domowa i odpoczynek", "Koniec wyprawy w naszej bazie.")
        ]
        cursor.executemany('''
            INSERT INTO krok_wycieczki (id_wycieczki, krok_wycieczki, nazwa, wspolrzedne, okienko_zwiedzania, godzina_ewakuacji, czerwona_strefa_ostrzezenie, strefa_luzu_i_regeneracji, podsumowanie_taktyki, potencjal_meltdownu, strategie_meltdown, opis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', kroki_w1)

        cursor.execute("SELECT id FROM krok_wycieczki WHERE id_wycieczki = '1' ORDER BY id ASC")
        db_krok_ids = [r[0] for r in cursor.fetchall()]
        if len(db_krok_ids) >= 4:
            cursor.execute("INSERT INTO posilki_kroku (id_kroku, rodzaj_posilku, miejsce, sugerowana_godzina, opis) VALUES (?, 'śniadanie', 'w domku', '06:00', 'Domowe śniadanie')", (db_krok_ids[0],))
            cursor.execute("INSERT INTO posilki_kroku (id_kroku, rodzaj_posilku, miejsce, sugerowana_godzina, opis) VALUES (?, 'obiad', 'w kroku', '12:00', 'Poziom regeneracji (Wysoki), dostępność strefy wyciszenia.')", (db_krok_ids[1],))
            cursor.execute("INSERT INTO posilki_kroku (id_kroku, rodzaj_posilku, miejsce, sugerowana_godzina, opis) VALUES (?, 'kolacja', 'w domku', '18:00', 'Kolacja po powrocie')", (db_krok_ids[3],))

        conn.commit()
    conn.close()
    przelicz_i_zsynchronizuj_wycieczke("1")

init_db()

def edytuj_wycieczke(id, tytul_wycieczki=None, calosciowy_opis_wycieczki=None, calosciowa_taktyka_dnia=None, 
                     planowana_data=None, szacowany_czas_ogarniania_rano=None, czas_wyjazdu=None):
    with get_db() as conn:
        cursor = conn.cursor()
        if tytul_wycieczki is not None:
            cursor.execute('UPDATE wycieczka SET tytul_wycieczki = ? WHERE id = ?', (tytul_wycieczki, str(id)))
        if calosciowy_opis_wycieczki is not None:
            cursor.execute('UPDATE wycieczka SET calosciowy_opis_wycieczki = ? WHERE id = ?', (calosciowy_opis_wycieczki, str(id)))
        if calosciowa_taktyka_dnia is not None:
            cursor.execute('UPDATE wycieczka SET calosciowa_taktyka_dnia = ? WHERE id = ?', (calosciowa_taktyka_dnia, str(id)))
        if planowana_data is not None:
            cursor.execute('UPDATE wycieczka SET planowana_data = ? WHERE id = ?', (planowana_data, str(id)))
        if szacowany_czas_ogarniania_rano is not None:
            cursor.execute('UPDATE wycieczka SET szacowany_czas_ogarniania_rano = ? WHERE id = ?', (szacowany_czas_ogarniania_rano, str(id)))
        if czas_wyjazdu is not None:
            cursor.execute('UPDATE wycieczka SET czas_wyjazdu = ? WHERE id = ?', (czas_wyjazdu, str(id)))
        conn.commit()
    
    przelicz_i_zsynchronizuj_wycieczke(str(id), force_wyjazd_str=czas_wyjazdu if czas_wyjazdu else None)
    return f"Wycieczka #{id} została zaktualizowana i przeliczona."

def dodaj_krok_wycieczki(id_wycieczki, krok_wycieczki=None, nazwa="", wspolrzedne=None, 
                         okienko_zwiedzania="10:00 - 10:30", godzina_ewakuacji="Brak", 
                         czerwona_strefa_ostrzezenie="Brak", strefa_luzu_i_regeneracji="Spokojna strefa", 
                         podsumowanie_taktyki="Brak", opis="Brak"):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, krok_wycieczki, nazwa FROM krok_wycieczki WHERE id_wycieczki = ? ORDER BY CAST(krok_wycieczki AS INTEGER) ASC', (str(id_wycieczki),))
        istniejace = cursor.fetchall()

        wsp_val = str(wspolrzedne).strip() if wspolrzedne is not None and str(wspolrzedne).strip() and str(wspolrzedne).lower() != 'none' else ""

        if istniejace and ("domek" in istniejace[-1][2].lower() or "powrót" in istniejace[-1][2].lower()):
            ostatni_id = istniejace[-1][0]
            nowy_numer_kroku = len(istniejace) - 1
            nowy_numer_domku = len(istniejace)
            
            cursor.execute('UPDATE krok_wycieczki SET krok_wycieczki = ? WHERE id = ?', (str(nowy_numer_domku), ostatni_id))
            target_krok_num = str(nowy_numer_kroku)
        else:
            target_krok_num = str(len(istniejace))

        cursor.execute('''
            INSERT INTO krok_wycieczki (id_wycieczki, krok_wycieczki, nazwa, wspolrzedne, okienko_zwiedzania, godzina_ewakuacji, czerwona_strefa_ostrzezenie, strefa_luzu_i_regeneracji, podsumowanie_taktyki, opis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (str(id_wycieczki), target_krok_num, str(nazwa), wsp_val, str(okienko_zwiedzania), str(godzina_ewakuacji), str(czerwona_strefa_ostrzezenie), str(strefa_luzu_i_regeneracji), str(podsumowanie_taktyki), str(opis)))
        conn.commit()
    
    przelicz_i_zsynchronizuj_wycieczke(str(id_wycieczki))
    return f"Dodano krok '{nazwa}' do wycieczki #{id_wycieczki} i automatycznie przeliczono cały łańcuch godzin."

def edytuj_krok_wycieczki(id_wycieczki, krok_wycieczki, nazwa=None, wspolrzedne=None, okienko_zwiedzania=None, 
                          godzina_ewakuacji=None, czerwona_strefa_ostrzezenie=None, strefa_luzu_i_regeneracji=None, 
                          podsumowanie_taktyki=None, opis=None, godzina_wyjazdu_do=None, godzina_dotarcia_na=None):
    with get_db() as conn:
        cursor = conn.cursor()
        query = '''
            SELECT id, nazwa FROM krok_wycieczki 
            WHERE id_wycieczki = ? AND (
                id = ? OR 
                krok_wycieczki = ? OR 
                nazwa LIKE ? OR 
                ? LIKE ('%' || nazwa || '%')
            )
        '''
        cursor.execute(query, (str(id_wycieczki), str(krok_wycieczki), str(krok_wycieczki), f"%{krok_wycieczki}%", str(krok_wycieczki)))
        res = cursor.fetchone()
        if not res:
            return f"Nie znaleziono kroku '{krok_wycieczki}' w wycieczce #{id_wycieczki}."
        krok_id = res[0]
        
        pola = {
            "nazwa": nazwa, "wspolrzedne": wspolrzedne, "okienko_zwiedzania": okienko_zwiedzania,
            "godzina_ewakuacji": godzina_ewakuacji, "czerwona_strefa_ostrzezenie": czerwona_strefa_ostrzezenie,
            "strefa_luzu_i_regeneracji": strefa_luzu_i_regeneracji, "podsumowanie_taktyki": podsumowanie_taktyki, "opis": opis
        }
        for col, val in pola.items():
            if val is not None:
                cursor.execute(f'UPDATE krok_wycieczki SET {col} = ? WHERE id = ?', (val, krok_id))
        conn.commit()
    
    przelicz_i_zsynchronizuj_wycieczke(
        str(id_wycieczki), 
        anchor_krok_id=krok_id, 
        anchor_koniec_str=godzina_wyjazdu_do,
        anchor_start_str=godzina_dotarcia_na
    )
    return f"Zaktualizowano krok i automatycznie przeliczono godziny całej wycieczki #{id_wycieczki}."

def usun_krok_wycieczki(id_wycieczki, krok_wycieczki):
    with get_db() as conn:
        cursor = conn.cursor()
        query = '''
            SELECT id, nazwa FROM krok_wycieczki 
            WHERE id_wycieczki = ? AND (
                id = ? OR 
                krok_wycieczki = ? OR 
                nazwa LIKE ? OR 
                ? LIKE ('%' || nazwa || '%')
            )
        '''
        cursor.execute(query, (str(id_wycieczki), str(krok_wycieczki), str(krok_wycieczki), f"%{krok_wycieczki}%", str(krok_wycieczki)))
        res = cursor.fetchone()
        if not res:
            return f"Nie znaleziono kroku '{krok_wycieczki}' do usunięcia."
            
        krok_id, nazwa = res
        if "domek" in nazwa.lower() and ("start" in nazwa.lower() or "powrót" in nazwa.lower() or "baza" in nazwa.lower()):
            return "BLOKADA: Baza wypadowa (Domek) jest nieusuwalna! Możesz usuwać wyłącznie atrakcje, sklepy i plaże na trasie."
        
        cursor.execute('DELETE FROM posilki_kroku WHERE id_kroku = ?', (krok_id,))
        cursor.execute('DELETE FROM zakupy WHERE id_kroku = ?', (krok_id,))
        cursor.execute('DELETE FROM czasy_dojazdu WHERE id_kroku_z = ? OR id_kroku_do = ?', (krok_id, krok_id))
        cursor.execute('DELETE FROM krok_wycieczki WHERE id = ?', (krok_id,))

        cursor.execute('SELECT id, nazwa, okienko_zwiedzania FROM krok_wycieczki WHERE id_wycieczki = ?', (str(id_wycieczki),))
        pozostale = cursor.fetchall()
        pozostale.sort(key=lambda x: klucz_sortowania_okienka(x[2]))
        
        for idx, (row_id, _, _) in enumerate(pozostale):
            cursor.execute('UPDATE krok_wycieczki SET krok_wycieczki = ? WHERE id = ?', (str(idx), row_id))
        conn.commit()

    przelicz_i_zsynchronizuj_wycieczke(str(id_wycieczki))
    return f"Pomyślnie usunięto krok '{nazwa}' i automatycznie zsynchronizowano harmonogram wycieczki #{id_wycieczki}."

def zmien_czas_postoju_na_trasie(id_wycieczki, krok_z, krok_do, minuty_postoju):
    with get_db() as conn:
        cursor = conn.cursor()
        
        def find_id(k_val):
            cursor.execute('SELECT id FROM krok_wycieczki WHERE id_wycieczki = ? AND (id = ? OR krok_wycieczki = ? OR nazwa LIKE ?)', (str(id_wycieczki), str(k_val), str(k_val), f"%{k_val}%"))
            r = cursor.fetchone()
            return r[0] if r else None

        id_z = find_id(krok_z)
        id_do = find_id(krok_do)
        
        if not id_z or not id_do:
            return "Nie znaleziono wskazanych kroków trasy."
            
        cursor.execute('UPDATE czasy_dojazdu SET szacowany_czas_postoju = ? WHERE id_kroku_z = ? AND id_kroku_do = ?', (int(minuty_postoju), id_z, id_do))
        conn.commit()
    
    przelicz_i_zsynchronizuj_wycieczke(str(id_wycieczki))
    return f"Zaktualizowano bufor postoju na trasie do {minuty_postoju} minut i przeliczono harmonogram."

def dodaj_notatke(zawartosc, typ_notatki='text', id_wycieczki=None, id_miejsca=None, tytul=None):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO notatki (id_wycieczki, id_miejsca, tytul, zawartosc, typ_notatki)
            VALUES (?, ?, ?, ?, ?)
        ''', (str(id_wycieczki) if id_wycieczki else None, str(id_miejsca) if id_miejsca else None, tytul, zawartosc, typ_notatki))
        conn.commit()
    return "Dodano notatkę!"

def dodaj_produkt_zakupow(id_wycieczki, nazwa_produktu, id_kroku=None, ilosc="1"):
    with get_db() as conn:
        cursor = conn.cursor()
        krok_val = str(id_kroku) if id_kroku not in [None, "", "None", "null"] else None
        cursor.execute('''
            INSERT INTO zakupy (id_wycieczki, id_kroku, nazwa_produktu, ilosc, kupione) 
            VALUES (?, ?, ?, ?, 0)
        ''', (str(id_wycieczki), krok_val, nazwa_produktu, str(ilosc)))
        conn.commit()
    lokalizacja = f"kroku #{krok_val}" if krok_val else "całej wycieczki"
    return f"Dodano produkt '{nazwa_produktu}' do listy zakupów ({lokalizacja})."

def zmien_status_zakupu(zakup_id, kupione):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE zakupy SET kupione = ? WHERE id = ?', (1 if kupione else 0, int(zakup_id)))
        conn.commit()

def pobierz_zakupy_dla_kroku(id_kroku):
    with get_db() as conn:
        df = pd.read_sql('SELECT * FROM zakupy WHERE id_kroku = ? ORDER BY id ASC', conn, params=(str(id_kroku),))
    return df

def pobierz_zakupy_dla_wycieczki(id_wycieczki):
    with get_db() as conn:
        df = pd.read_sql('SELECT * FROM zakupy WHERE id_wycieczki = ? ORDER BY id ASC', conn, params=(str(id_wycieczki),))
    return df

# Deklaracja narzędzi bazy danych CRUD oraz natywnego Google Search
cretai_tools = [
    types.Tool(
        function_declarations=[
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
                description="Aktualizuje parametry wycieczki, w tym szacowany czas do wyjazdu (np. '0.5h', '45m') oraz godzinę wyjazdu (np. '06:30'). Zmiana czasu do wyjazdu automatycznie przelicza cały harmonogram.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "id": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                        "tytul_wycieczki": types.Schema(type=types.Type.STRING, description="Tytuł"),
                        "calosciowy_opis_wycieczki": types.Schema(type=types.Type.STRING, description="Opis"),
                        "calosciowa_taktyka_dnia": types.Schema(type=types.Type.STRING, description="Taktyka"),
                        "planowana_data": types.Schema(type=types.Type.STRING, description="RRRR-MM-DD"),
                        "szacowany_czas_ogarniania_rano": types.Schema(type=types.Type.STRING, description="Szacowany czas do wyjazdu, np. '0.5h', '1h', '45m'"),
                        "czas_wyjazdu": types.Schema(type=types.Type.STRING, description="Godzina wyjazdu z domku, np. '06:30'"),
                    },
                    required=["id"]
                ),
            ),
            types.FunctionDeclaration(
                name="dodaj_krok_wycieczki",
                description="Dodaje krok do wycieczki (np. sklep przy trasie, aptekę, punkt widokowy, kawiarnię lub dowolne inne miejsce spoza listy). Jeśli brak współrzędnych, parametr 'wspolrzedne' pozostaw pusty lub None. Backend automatycznie wstawia punkt przed powrotem do bazy i przelicza godziny!",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                        "krok_wycieczki": types.Schema(type=types.Type.STRING, description="Numer kroku (opcjonalny, backend ustala go sam)"),
                        "nazwa": types.Schema(type=types.Type.STRING, description="Nazwa miejsca / 'Sklep przy trasie' / 'Apteka' itp."),
                        "wspolrzedne": types.Schema(type=types.Type.STRING, description="GPS jako 'lat, lon' (np. '35.586222, 24.091861') lub None/pusty string, gdy brak koordynatów"),
                        "okienko_zwiedzania": types.Schema(type=types.Type.STRING, description="Orientacyjny czas pobytu, np. '17:00 - 17:25'"),
                        "godzina_ewakuacji": types.Schema(type=types.Type.STRING, description="KRYTYCZNA godzina graniczna przed upałem/tłumem lub 'Brak'"),
                        "czerwona_strefa_ostrzezenie": types.Schema(type=types.Type.STRING, description="Ostrzeżenie o upale/tłumie lub 'Brak'"),
                        "strefa_luzu_i_regeneracji": types.Schema(type=types.Type.STRING, description="Strefa wyciszenia"),
                        "podsumowanie_taktyki": types.Schema(type=types.Type.STRING, description="Taktyka"),
                        "opis": types.Schema(type=types.Type.STRING, description="Opis"),
                    },
                    required=["id_wycieczki", "nazwa"]
                ),
            ),
            types.FunctionDeclaration(
                name="edytuj_krok_wycieczki",
                description="Edytuje parametry kroku wycieczki. Obsługuje precyzyjnie godziny wyjazdu 'do...' oraz godziny dotarcia 'na...'. Backend kaskadowo przeliczy godziny wszystkich punktów!",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                        "krok_wycieczki": types.Schema(type=types.Type.STRING, description="ID z bazy (DB_ID), numer kroku lub nazwa atrakcji"),
                        "okienko_zwiedzania": types.Schema(type=types.Type.STRING, description="Nowe okienko pobytu, np. '10:00 - 13:00'"),
                        "godzina_wyjazdu_do": types.Schema(type=types.Type.STRING, description="Sztywna godzina WYJAZDU/ZAKOŃCZENIA pobytu w tym miejscu, gdy użytkownik mówi 'chcę być w X do godziny HH:MM'"),
                        "godzina_dotarcia_na": types.Schema(type=types.Type.STRING, description="Sztywna godzina PRZYJAZDU/STARTU pobytu w tym miejscu, gdy użytkownik mówi 'chcę dojechać/dotrzeć do X na/do godziny HH:MM'"),
                        "podsumowanie_taktyki": types.Schema(type=types.Type.STRING, description="Taktyka"),
                        "godzina_ewakuacji": types.Schema(type=types.Type.STRING, description="Godzina krytyczna lub 'Brak'"),
                    },
                    required=["id_wycieczki", "krok_wycieczki"]
                ),
            ),
            types.FunctionDeclaration(
                name="usun_krok_wycieczki",
                description="Usuwa wskazany krok / atrakcję / sklep z wycieczki i natychmiast przelicza cały harmonogram. Używaj ZAWSZE, gdy użytkownik prosi o usunięcie, pominięcie lub wykasowanie punktu.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki (np. '1')"),
                        "krok_wycieczki": types.Schema(type=types.Type.STRING, description="ID z bazy (DB_ID), numer kroku lub nazwa usuwanego punktu (np. 'Cretaquarium', 'Sklep', '2')"),
                    },
                    required=["id_wycieczki", "krok_wycieczki"]
                ),
            ),
            types.FunctionDeclaration(
                name="zmien_czas_postoju_na_trasie",
                description="Zmienia bufor postoju na trasie między dwoma punktami (np. dodatkowy postój na kawę/toaletę) i przelicza godziny trasy.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                        "krok_z": types.Schema(type=types.Type.STRING, description="Numer lub nazwa kroku startowego odcinka"),
                        "krok_do": types.Schema(type=types.Type.STRING, description="Numer lub nazwa kroku docelowego odcinka"),
                        "minuty_postoju": types.Schema(type=types.Type.INTEGER, description="Liczba minut postoju na trasie (np. 20, 30)"),
                    },
                    required=["id_wycieczki", "krok_z", "krok_do", "minuty_postoju"]
                ),
            ),
            types.FunctionDeclaration(
                name="dodaj_produkt_zakupow",
                description="Dodaje produkt do listy zakupów wycieczki. Może być przypisany do całej wycieczki (id_kroku=None) lub do konkretnego kroku na trasie (np. Sklepu lub atrakcji). PAMIĘTAJ: Nigdy nie przypisuj zakupów do Domku/Bazy.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki (np. '1')"),
                        "nazwa_produktu": types.Schema(type=types.Type.STRING, description="Nazwa produktu zakupowego"),
                        "id_kroku": types.Schema(type=types.Type.STRING, description="Opcjonalne DB_ID kroku wycieczki. Jeśli zakup ogólny dla wycieczki, pozostaw None."),
                        "ilosc": types.Schema(type=types.Type.STRING, description="Ilość/opakowanie, np. '1 kg', '12 sztuk', '400g'"),
                    },
                    required=["id_wycieczki", "nazwa_produktu"]
                ),
            )
        ]
    ),
    types.Tool(
        google_search=types.GoogleSearch()
    )
]

def wykonaj_narzedzie_bazy(call_name, args):
    if call_name == "dodaj_notatke":
        return dodaj_notatke(**args)
    elif call_name == "edytuj_wycieczke":
        return edytuj_wycieczke(**args)
    elif call_name == "dodaj_krok_wycieczki":
        return dodaj_krok_wycieczki(**args)
    elif call_name == "edytuj_krok_wycieczki":
        return edytuj_krok_wycieczki(**args)
    elif call_name == "usun_krok_wycieczki":
        return usun_krok_wycieczki(**args)
    elif call_name == "zmien_czas_postoju_na_trasie":
        return zmien_czas_postoju_na_trasie(**args)
    elif call_name == "dodaj_produkt_zakupow":
        return dodaj_produkt_zakupow(**args)
    return "Wykonano."

def pobierz_status_zadania(klucz_zadania):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT ukonczone FROM zadania_dzieci_status WHERE klucz_zadania = ?', (str(klucz_zadania),))
        res = cursor.fetchone()
    return bool(res[0]) if res else False

def zapisz_status_zadania(klucz_zadania, ukonczone):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO zadania_dzieci_status (klucz_zadania, ukonczone) VALUES (?, ?)', (str(klucz_zadania), 1 if ukonczone else 0))
        conn.commit()

def sparsuj_liste_zadan(surowy_tekst):
    if not surowy_tekst or pd.isna(surowy_tekst):
        return []
    s = str(surowy_tekst).strip()
    if not s or s.lower() in ['nan', 'none', 'brak']:
        return []
    
    linie = re.split(r'(?:[\r\n;]+|(?:\s*\d+[\.\)]\s+))', s)
    wynik = []
    for l in linie:
        czysta = l.strip()
        if not czysta:
            continue
        czysta = re.sub(r'^[\s\*\-\•\d\.\)]+', '', czysta).strip()
        if czysta:
            wynik.append(czysta)
    return wynik

def pobierz_grupy_zadan_dla_wycieczki(wycieczka_id, kroki_df):
    grupy = []
    
    zadania_w_drodze = [
        "Wypatruj przez okno kóz i policz, ile ich zobaczysz na zboczach gór.",
        "Znajdź najciekawszy kształt chmury podczas jazdy samochodem.",
        "Kto pierwszy zauważy morze na horyzoncie, zdobywa punkt nawigatora!"
    ]
    grupy.append(("🚗 Zadania na drogę", zadania_w_drodze, f"w_{wycieczka_id}_droga"))

    with get_db() as conn:
        cursor = conn.cursor()
        for _, k in kroki_df.iterrows():
            nazwa = str(k['nazwa'])
            knum = str(k['krok_wycieczki'])
            k_id = str(k['id'])
            
            if "domek" in nazwa.lower():
                continue
                
            query = 'SELECT zadania_dla_dzieci FROM miejsca WHERE numer_miejsca = ? OR nazwa LIKE ? OR ? LIKE ("%" || nazwa || "%")'
            cursor.execute(query, (str(knum), f"%{nazwa}%", str(nazwa)))
            rows = cursor.fetchall()
            
            zad_miejsca = []
            for r in rows:
                if r and r[0]:
                    zad_miejsca.extend(sparsuj_liste_zadan(r[0]))
            
            zad_miejsca = list(dict.fromkeys(zad_miejsca))
            if zad_miejsca:
                grupy.append((f"📍 {nazwa}", zad_miejsca, f"w_{wycieczka_id}_krok_{k_id}"))

    return grupy

def pobierz_ustawienia_z_db(uzytkownik):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT api_key, dostawca_ai, model_ai FROM uzytkownik_ustawienia WHERE uzytkownik = ?', (uzytkownik,))
        res = cursor.fetchone()
    if res:
        return res[0] or "", res[1] or "Google Gemini", res[2] or "gemini-3.1-flash-lite"
    return "", "Google Gemini", "gemini-3.1-flash-lite"

def zapisz_ustawienia_w_db(uzytkownik, api_key, dostawca_ai, model_ai):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO uzytkownik_ustawienia (uzytkownik, api_key, dostawca_ai, model_ai) 
            VALUES (?, ?, ?, ?)
        ''', (uzytkownik, api_key, dostawca_ai, model_ai))
        conn.commit()

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
        lat, lon = sparsuj_wspolrzedne(k['wspolrzedne'])
        if lat is not None and lon is not None:
            prognoza = pobierz_prognoze_pogody(lat, lon, str(planowana_data))
            if prognoza and 'hourly' in prognoza:
                for h in prognoza['hourly']:
                    t = int(h.get('tempC', 20))
                    if t > max_temp: max_temp = t
                    if t < min_temp: min_temp = t
                    desc = h.get('weatherDesc', [{}])[0].get('value', '').lower()
                    opis_pogody_zbiorczy.add(desc)

    for desc in opis_pogody_zbiorczy:
        if 'rain' in desc or 'deszcz' in desc or 'shower' in desc:
            ostrzezenia.append("🌧️ Prognozowane opady deszczu na trasie!")
        if 'storm' in desc or 'thunder' in desc or 'burza' in desc:
            ostrzezenia.append("⚡ Ryzyko burz na trasie wycieczki!")

    if max_temp >= 32:
        ostrzezenia.append(f"🔥 Ekstremalny upał! Maksymalna temperatura sięgnie {max_temp}°C.")

    st.markdown(f'<div class="section-unified-header">🌤️ Pogoda na trasie</div><div style="font-size: 10.5pt; color: #2B2118; font-weight: 700; margin-bottom: 12px;">Temperatura: <b>{min_temp}°C do {max_temp}°C</b></div>', unsafe_allow_html=True)

    if ostrzezenia:
        for ost in ostrzezenia:
            st.markdown(f'<div style="color: #DC5050; font-weight: 800; font-size: 9.5pt; margin-top: 2px;">{ost}</div>', unsafe_allow_html=True)

def pobierz_historie_czatu_z_db(uzytkownik):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT rola, tresc FROM czat_historia WHERE uzytkownik = ? ORDER BY id ASC', (uzytkownik,))
        rows = cursor.fetchall()
    
    history = []
    for rola, tresc in rows:
        raw_content = types.Content(role=rola, parts=[types.Part.from_text(text=tresc)])
        history.append({"role": rola, "content": tresc, "raw_content": raw_content})
    return history

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
            df = pd.read_sql('SELECT * FROM notatki WHERE id_wycieczki = ?', conn, params=(str(id_wycieczki),))
        elif id_miejsca:
            df = pd.read_sql('SELECT * FROM notatki WHERE id_miejsca = ?', conn, params=(str(id_miejsca),))
        else:
            df = pd.DataFrame()
    return df

def renderuj_sekcje_notatek(id_wycieczki=None, id_miejsca=None):
    st.markdown('<div class="section-unified-header">📌 Notatki</div>', unsafe_allow_html=True)
    df_notatki = pobierz_notatki(id_wycieczki=id_wycieczki, id_miejsca=id_miejsca)

    if not df_notatki.empty:
        for _, note in df_notatki.iterrows():
            st.markdown(f'<div class="note-card"><div style="font-weight: 800; font-size: 10.5pt; color: #2B2118; margin-bottom: 4px;">📌 {note.get("tytul") or "Notatka"}</div><div style="font-size: 9.5pt; color: #4A3E36;">{note["zawartosc"]}</div></div>', unsafe_allow_html=True)

    with st.expander("➕ Dodaj nową notatkę", expanded=False):
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

def pob_posilki_dla_kroku(id_kroku):
    with get_db() as conn:
        df = pd.read_sql('SELECT * FROM posilki_kroku WHERE id_kroku = ?', conn, params=(str(id_kroku),))
    return df

def pobierz_wszystkie_miejsca():
    with get_db() as conn:
        df = pd.read_sql('SELECT * FROM miejsca', conn)
    return df

def pobierz_aktywna_wycieczke_id():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT aktualne_id_wycieczki FROM aktywna_wycieczka WHERE id = 1')
        res = cursor.fetchone()
    return str(res[0]) if res else "1"

def pobierz_skrocone_opcje_wycieczek():
    with get_db() as conn:
        df_w = pd.read_sql('SELECT id, tytul_wycieczki FROM wycieczka WHERE odbyta = 0', conn)
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

def pobierz_wycieczki_dla_miejsca(numer_miejsca, nazwa_miejsca):
    with get_db() as conn:
        query = '''
            SELECT DISTINCT w.id, w.tytul_wycieczki, k.krok_wycieczki, k.okienko_zwiedzania
            FROM wycieczka w
            JOIN krok_wycieczki k ON w.id = k.id_wycieczki
            WHERE k.krok_wycieczki = ? OR k.nazwa LIKE ? OR ? LIKE ('%' || k.nazwa || '%')
        '''
        df = pd.read_sql(query, conn, params=(str(numer_miejsca), f"%{nazwa_miejsca}%", str(nazwa_miejsca)))
    return df

def wczytaj_kontekst_zewnetrzny():
    tekst = f"Jesteś asystentem podróży CretAi na Kretę.\n"
    tekst += f"- Lokalizacja naszego DOMEK: {DOMEK_LAT}, {DOMEK_LON}\n"
    tekst += f"- Lokalizacja SKLEP (Sklep przy domku): {SKLEP_LAT}, {SKLEP_LON}\n"
    tekst += wczytaj_pliki_regul("rule")
    
    with get_db() as conn:
        try:
            wycieczki_df = pd.read_sql('SELECT id, tytul_wycieczki, calosciowy_opis_wycieczki, pobudka, czas_wyjazdu, szacowana_godzina_powrotu, planowana_data, szacowany_czas_ogarniania_rano FROM wycieczka', conn)
            kroki_df = pd.read_sql('SELECT id, id_wycieczki, krok_wycieczki, nazwa, wspolrzedne, okienko_zwiedzania, godzina_ewakuacji FROM krok_wycieczki ORDER BY CAST(krok_wycieczki AS INTEGER) ASC', conn)
        except:
            wycieczki_df, kroki_df = pd.DataFrame(), pd.DataFrame()

    if not wycieczki_df.empty:
        for _, w in wycieczki_df.iterrows():
            tekst += f"- Wycieczka #{w['id']}: {w['tytul_wycieczki']} | Data: {w.get('planowana_data', '')} | Czas do wyjazdu: {w.get('szacowany_czas_ogarniania_rano', '0.5h')} | Wyjazd: {w.get('czas_wyjazdu', '')}\n"
    if not kroki_df.empty:
        for _, k in kroki_df.iterrows():
            tekst += f"- Krok (W#{k['id_wycieczki']}): ID DB: {k['id']} | #{k['krok_wycieczki']}. {k['nazwa']} | Czas: {k['okienko_zwiedzania']}\n"
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

def renderuj_globalny_czat_ai(uzytkownik, inline=False):
    if not inline:
        st.markdown('<div class="floating-ai-container">', unsafe_allow_html=True)
    with st.expander(f"💬 Asystent AI ({uzytkownik})", expanded=False):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"<span style='font-size: 9pt; font-weight: 800;'>🧠 TRYB ADHD • {uzytkownik}</span>", unsafe_allow_html=True)
        with col2:
            if st.button("🗑️ Wyczyść", key=f"btn_clear_{uzytkownik}_{'inline' if inline else 'float'}", use_container_width=True):
                wyczysc_historie_czatu_w_db(uzytkownik)
                st.session_state["flash_toast"] = "🗑️ Wyczyszczono czat."
                st.rerun()

        if not api_key_input:
            st.warning(f"Wprowadź klucz API w menu bocznym.")
            if not inline:
                st.markdown('</div>', unsafe_allow_html=True)
            return

        dzisiaj_str = date.today().strftime("%Y-%m-%d")
        zewnetrzny_kontekst = wczytaj_kontekst_zewnetrzny()
        system_prompt = f"""Jesteś asystentem podróży CretAi na Kretę, pomagającym zarządzać wycieczką objazdową z dziećmi i rodzicami z ADHD. Dziś: {dzisiaj_str}.
{zewnetrzny_kontekst}
- ZASADA DODAWANIA MIEJSC SPOZA LISTY (SKLEPY, APTEKI, PUNKTY WIDOKOWE, POSTOJE ITD.):
  1. Gdy użytkownik prosi o dodanie nowego miejsca, sklepu lub postoju spoza głównej bazy miejsc, a NIE PODAŁ współrzędnych GPS:
     - Zapytaj go krótko: "Czy masz współrzędne GPS lub pinezkę dla [Nazwa punktu]? Jeśli nie, mogę dodać ten punkt jako postój orientacyjny bez przycisku nawigacji."
     - Jeśli użytkownik wprost odpowie podając współrzędne -> dodaj krok z parametrem `wspolrzedne='lat, lon'`.
     - Jeśli użytkownik odpowie "nie mam", "dodaj bez", "jedziemy na oko" lub w pierwszym poleceniu wyraźnie zażąda dodania bez współrzędnych -> natychmiast wywołaj `dodaj_krok_wycieczki(..., wspolrzedne=None)` (wtedy aplikacja nie wyświetli przycisku nawigacji i ustawi zielone tło).
  2. Jeśli użytkownik od razu w pierwszym pytaniu podał współrzędne (lub chodzi o znany Sklep przy domku: {SKLEP_LAT}, {SKLEP_LON}) -> dodaj od razu bez dopytywania.
  3. Domyślny czas postoju dla sklepów, marketów, aptek, szybkich postojów: 15-25 min.
  4. Dla punktów spoza listy parametr `godzina_ewakuacji` i `czerwona_strefa_ostrzezenie` ZAWSZE ustawiaj na 'Brak'.
- ZASADA CZASU DO WYJAZDU: Wycieczka posiada parametr `szacowany_czas_ogarniania_rano` (domyślnie '0.5h', wyświetlany jako Czas do wyjazdu) oraz `czas_wyjazdu`. Pobudka i wyjazd są ściśle powiązane tym czasem. Gdy użytkownik mówi 'wyjeżdżamy o 07:00' lub zmienia czas do wyjazdu, backend automatycznie przelicza wyjazd i cały harmonogram wycieczki.
- ZASADA USUWANIA KROKÓW: Gdy użytkownik prosi o usunięcie, wykasowanie, pominięcie lub rezygnację z atrakcji/sklepu (np. 'usuń Cretaquarium', 'nie jedziemy do akwarium', 'skasuj krok 2'), ZAWSZE natychmiast wywołaj `usun_krok_wycieczki(id_wycieczki='1', krok_wycieczki='nazwa lub numer')`.
- ZASADA LISTY ZAKUPÓW:
  1. Możesz dodawać zakupy ogólne dla całej wycieczki za pomocą funkcji `dodaj_produkt_zakupow(id_wycieczki, nazwa_produktu, ilosc)` bez podawania `id_kroku` lub podając `id_kroku=None`.
  2. Jeśli zakupy dotyczą konkretnego punktu trasy (np. Sklepu lub atrakcji), podaj właściwe `id_kroku`. PAMIĘTAJ: Nigdy nie przypisuj zakupów do Domku (bazy startowej/końcowej).
- ZASADA CZASU I HARMONOGRAMU (KASKADOWE PRZELICZANIE):
  1. Gdy użytkownik mówi: 'chcę być w X do godziny HH:MM' (np. 'chcę być w Knossos do 12:00'), oznacza to GODZINĘ WYJAZDU z tego punktu. Wywołaj `edytuj_krok_wycieczki(id_wycieczki, krok_wycieczki, godzina_wyjazdu_do='12:00')`.
  2. Gdy użytkownik mówi: 'chcę dotrzeć/dojechać do X na/do godziny HH:MM' (np. 'chcę dotrzeć do Knossos na 10:00'), oznacza to GODZINĘ PRZYJAZDU. Wywołaj `edytuj_krok_wycieczki(id_wycieczki, krok_wycieczki, godzina_dotarcia_na='10:00')`.
  3. Gdy użytkownik prosi o zmianę postoju w trasie (np. 'dodaj 30 min na kawę w drodze'), wywołaj `zmien_czas_postoju_na_trasie(id_wycieczki, krok_z, krok_do, minuty_postoju)`.
  4. Backend automatycznie przelicza cały łańcuch godzin, synchronizuje dojazdy OSRM oraz czyta z bazy czasy postojów w trasie.
  5. REGUŁA NA CZAS POBYTU W PUNKTACH:
     - Duże atrakcje / Pałace / Parki: 90-120 min.
     - Plaże / Wypoczynek: 90-150 min.
     - Punkty widokowe / Zdjęcia: 20-30 min.
     - Sklepy / Markety: 20-25 min.
  6. POJĘCIE 'godzina_ewakuacji': To wyłącznie krytyczna granica termiczna/sensoryczna (np. '11:30' przed upałem w ruinach). Dla sklepów, plaż czy punktów bez zagrożenia ZAWSZE podawaj 'Brak'."""
        
        chat_historia_z_db = pobierz_historie_czatu_z_db(uzytkownik)
        chat_container = st.container(height=200)
        with chat_container:
            for message in chat_historia_z_db:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"] if isinstance(message["content"], str) else "")

        prompt = st.chat_input(f"Pytanie do AI...", key=f"chat_input_{uzytkownik}_{'inline' if inline else 'float'}")
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

                            for _ in range(5):
                                response = client.models.generate_content(
                                    model=wybrany_model,
                                    contents=contents,
                                    config=types.GenerateContentConfig(
                                        tools=cretai_tools,
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
                                    contents.append(model_content)
                                    calls = response.function_calls if response.function_calls else [p.function_call for p in model_content.parts if p.function_call]
                                    
                                    function_responses_parts = []
                                    for call in calls:
                                        args = call.args
                                        call_name = call.name
                                        wynik_bazy = wykonaj_narzedzie_bazy(call_name, args)
                                        function_responses_parts.append(
                                            types.Part.from_function_response(name=call_name, response={"result": wynik_bazy})
                                        )
                                    contents.append(types.Content(role="user", parts=function_responses_parts))
                                else:
                                    text_parts = [p.text for p in candidate.content.parts if hasattr(p, "text") and p.text] if candidate and candidate.content and candidate.content.parts else []
                                    assistant_reply = "".join(text_parts) if text_parts else (response.text if hasattr(response, "text") else "Zaktualizowano bazę danych.")
                                    
                                    if candidate and hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                                        gm = candidate.grounding_metadata
                                        if hasattr(gm, 'grounding_chunks') and gm.grounding_chunks:
                                            links = []
                                            for chunk in gm.grounding_chunks:
                                                if hasattr(chunk, 'web') and chunk.web:
                                                    links.append(f"[{chunk.web.title}]({chunk.web.uri})")
                                            if links:
                                                assistant_reply += "\n\n🌐 **Źródła:** " + ", ".join(links[:3])
                                    break
                        else:
                            client_c = anthropic.Anthropic(api_key=api_key_input)
                            resp = client_c.messages.create(
                                model=wybrany_model,
                                max_tokens=1024,
                                system=system_prompt,
                                messages=[{"role": "user", "content": prompt}]
                            )
                            assistant_reply = "".join([b.text for b in resp.content if hasattr(b, "text")])

                        if not assistant_reply:
                            assistant_reply = "Operacja wykonana i zsynchronizowana w harmonogramie."

                        zapisz_wiadomosc_w_db(uzytkownik, "model", assistant_reply)
                        st.markdown(assistant_reply)
                    except Exception as e:
                        st.error(f"Błąd: {e}")
            st.rerun()

    if not inline:
        st.markdown('</div>', unsafe_allow_html=True)

if "tab" in st.query_params:
    st.session_state.active_tab = st.query_params["tab"]
elif "active_tab" not in st.session_state:
    st.session_state.active_tab = "route"

if "place" in st.query_params:
    st.session_state.active_place_id = str(st.query_params["place"])
    st.session_state.active_tab = "zabytek"

if "active_place_id" not in st.session_state:
    st.session_state.active_place_id = None

if "map_tab_selected_place" not in st.session_state:
    st.session_state.map_tab_selected_place = None

if "selected_category" not in st.session_state:
    st.session_state.selected_category = None

df_miejsca = pobierz_wszystkie_miejsca()
wycieczki_options = pobierz_skrocone_opcje_wycieczek()

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

def renderuj_karte_wycieczki(wycieczka_id, pokaz_mape=False, pokaz_pogode=False):
    with get_db() as conn:
        wycieczka_row = pd.read_sql('SELECT * FROM wycieczka WHERE id = ?', conn, params=(str(wycieczka_id),))
        kroki_df = pd.read_sql('SELECT * FROM krok_wycieczki WHERE id_wycieczki = ? ORDER BY CAST(krok_wycieczki AS INTEGER) ASC', conn, params=(str(wycieczka_id),))
        czasy_dojazdu_df = pd.read_sql('SELECT * FROM czasy_dojazdu', conn)
        df_wszystkie_miejsca = pd.read_sql('SELECT numer_miejsca, nazwa, typ FROM miejsca', conn)
    
    if wycieczka_row.empty:
        st.info("Brak danych wycieczki.")
        return

    w_gen = wycieczka_row.iloc[0]
    tytul_wycieczki = w_gen.get('tytul_wycieczki', 'Wycieczka')
    planowana_data_val = w_gen.get('planowana_data', '')
    
    dzisiaj = date.today()
    try:
        parsed_date = datetime.strptime(str(planowana_data_val), "%Y-%m-%d").date() if planowana_data_val else dzisiaj
    except:
        parsed_date = dzisiaj

    dzien_val = parsed_date.day
    miesiac_val = MIESIACE_PL[parsed_date.month - 1]
    dzien_tyg_val = DNI_TYGODNIA_PL[parsed_date.weekday()]
    
    st.markdown(f'<div class="trip-top-section"><div class="trip-main-title">{tytul_wycieczki}</div></div>', unsafe_allow_html=True)

    data_label = f"📅 Planowana data: {dzien_val} {miesiac_val} ({dzien_tyg_val}) ▾"
    if st.button(data_label, key="btn_date_picker", use_container_width=True):
        edit_date_dialog(wycieczka_id, parsed_date)

    if pokaz_pogode:
        renderuj_podsumowanie_pogody_wycieczki(kroki_df, planowana_data_val)

    if pd.notna(w_gen.get('calosciowy_opis_wycieczki')) and str(w_gen['calosciowy_opis_wycieczki']).strip():
        st.markdown(f"""
        <div style="margin-top: 4px; margin-bottom: 12px;">
            <div class="section-unified-header">📝 Cel wycieczki</div>
            <div class="section-body-text">{w_gen['calosciowy_opis_wycieczki']}</div>
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
        st.markdown('<div style="text-align: center; font-size: 8pt; font-weight: 800; color: #8C5338; text-transform: uppercase; margin-bottom: 4px;">⏰ Pobudka</div>', unsafe_allow_html=True)
        with st.popover(pobudka_val, use_container_width=True):
            g_pob = sparsuj_godzine_minuty(pobudka_val) or (6, 0)
            t_pob = st.time_input("Nowa godzina pobudki", value=time(g_pob[0], g_pob[1]), step=300, key=f"ti_pob_{wycieczka_id}")
            if st.button("💾 Zapisz", key=f"btn_save_pob_{wycieczka_id}", use_container_width=True):
                przelicz_i_zsynchronizuj_wycieczke(str(wycieczka_id), force_pobudka_str=t_pob.strftime("%H:%M"))
                st.session_state["flash_toast"] = "⏱️ Zaktualizowano godzinę pobudki!"
                st.rerun()

    with col_log2:
        st.markdown('<div style="text-align: center; font-size: 8pt; font-weight: 800; color: #8C5338; text-transform: uppercase; margin-bottom: 4px;">🎒 Czas do wyjazdu</div>', unsafe_allow_html=True)
        with st.popover(ogarnianie_val, use_container_width=True):
            nowy_czas_ogarniania = st.text_input("Szacowany czas rano", value=ogarnianie_val, key=f"ti_ogarnianie_{wycieczka_id}")
            if st.button("💾 Zapisz", key=f"btn_save_ogarnianie_{wycieczka_id}", use_container_width=True):
                edytuj_wycieczke(wycieczka_id, szacowany_czas_ogarniania_rano=nowy_czas_ogarniania)
                st.session_state["flash_toast"] = "⏱️ Zaktualizowano czas do wyjazdu!"
                st.rerun()

    with col_log3:
        st.markdown('<div style="text-align: center; font-size: 8pt; font-weight: 800; color: #8C5338; text-transform: uppercase; margin-bottom: 4px;">🏠 Powrót</div>', unsafe_allow_html=True)
        with st.popover(powrot_val, use_container_width=True):
            g_pow = sparsuj_godzine_minuty(powrot_val) or (17, 33)
            t_pow = st.time_input("Nowa godzina powrotu", value=time(g_pow[0], g_pow[1]), step=300, key=f"ti_pow_{wycieczka_id}")
            if st.button("💾 Zapisz", key=f"btn_save_pow_{wycieczka_id}", use_container_width=True):
                przelicz_i_zsynchronizuj_wycieczke(str(wycieczka_id), force_powrot_str=t_pow.strftime("%H:%M"))
                st.session_state["flash_toast"] = "⏱️ Zaktualizowano godzinę powrotu!"
                st.rerun()

    # --- SEKCJA TAKTYKA ---
    if pd.notna(w_gen.get('calosciowa_taktyka_dnia')) and str(w_gen['calosciowa_taktyka_dnia']).strip():
        st.markdown('<div class="section-unified-header">🧠 Taktyka</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <details class="overview-details-card" style="margin-top: 6px;">
            <summary style="font-weight: normal !important;">🧠 Taktyka dnia</summary>
            <div style="margin-top: 10px; border-top: 1px solid #D1C7AE; padding-top: 8px;">
                <div class="section-body-text" style="margin-bottom: 0;">{w_gen['calosciowa_taktyka_dnia']}</div>
            </div>
        </details>
        """, unsafe_allow_html=True)

    st.markdown('<div class="section-unified-header">🗺️ Plan na dzień</div>', unsafe_allow_html=True)

    total_steps = len(kroki_df)
    timeline_full_html = [
        '<div class="timeline-master-container">',
        '<div class="timeline-master-continuous-line"></div>'
    ]
    
    baza_miejsc_dict = {}
    if not df_wszystkie_miejsca.empty:
        for _, mrow in df_wszystkie_miejsca.iterrows():
            baza_miejsc_dict[str(mrow['numer_miejsca'])] = str(mrow['typ'])
            baza_miejsc_dict[str(mrow['nazwa']).lower()] = str(mrow['typ'])

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
        
        is_first = (idx == 0)
        is_last = (idx == total_steps - 1)
        
        lat_parsed, lon_parsed = sparsuj_wspolrzedne(wspolrzedne)
        has_nav = (lat_parsed is not None and lon_parsed is not None)
        nav_btn_html = ""
        if has_nav:
            gps_url = f"https://www.google.com/maps/search/?api=1&query={coords_clean}"
            nav_btn_html = f'<a href="{gps_url}" target="_blank" class="timeline-nav-btn" title="Nawiguj"><span>🧭</span><span>Nawiguj</span></a>'

        # Wykrycie typu miejsca i dopasowanie ikony
        matched_typ = baza_miejsc_dict.get(krok_num)
        if not matched_typ:
            for k_name_db, k_typ_db in baza_miejsc_dict.items():
                if len(k_name_db) > 3 and k_name_db in nazwa_lower:
                    matched_typ = k_typ_db
                    break

        kat = kategoryzuj_typ(matched_typ) if matched_typ else kategoryzuj_typ(nazwa_lower)
        icon_from_cat = pobierz_ikonke_kategorii(kat)

        # Precyzyjne dopasowanie emoji kontekstowych
        if "sklep" in nazwa_lower or "market" in nazwa_lower or "zakup" in nazwa_lower:
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
        elif "obiad" in nazwa_lower or "lunch" in nazwa_lower or "jedzenie" in nazwa_lower or "przekąska" in nazwa_lower:
            detected_icon = "🍴"
        elif "plaż" in nazwa_lower or "beach" in nazwa_lower:
            detected_icon = "🏖️"
        elif icon_from_cat is not None:
            detected_icon = icon_from_cat
        else:
            detected_icon = None

        badge_symbol = detected_icon if detected_icon is not None else (krok_num if (krok_num and krok_num != "0") else str(idx))

        is_in_places_db = matched_typ is not None
        is_custom_flat = not is_first and not is_last and (
            not is_in_places_db or 
            any(w in nazwa_lower for w in ["sklep", "market", "zakup", "apteka", "postój", "parking", "kawa", "cafe", "toaleta", "punkt widokowy", "widok"])
        )

        if is_first:
            # 1. KROK: POBUDKA
            df_pos = pob_posilki_dla_kroku(k['id'])
            opis_tekst_pob = ""
            if not df_pos.empty:
                posiłki_str = []
                for _, prow in df_pos.iterrows():
                    p_rodzaj = str(prow.get('rodzaj_posilku', '')).strip().lower()
                    p_godz = str(prow.get('sugerowana_godzina', '')).strip()
                    p_miejsce = str(prow.get('miejsce', '')).strip().lower()
                    if p_rodzaj in ['śniadanie', 'obiad', 'kolacja']:
                        nazwa_p = p_rodzaj.capitalize()
                        if p_miejsce != 'w domku' and p_godz and p_godz != 'None' and p_godz != 'Brak':
                            posiłki_str.append(f"{nazwa_p} ok {p_godz}")
                        else:
                            posiłki_str.append(nazwa_p)
                if posiłki_str:
                    opis_tekst_pob = f"<span style='color:#8C5338; font-weight:700;'>🍲 {' / '.join(posiłki_str)}</span>"

            row_pobudka = (
                f'<div class="timeline-step-row-wrapper">'
                f'<div class="timeline-row-frameless">'
                f'<div class="timeline-row-inner">'
                f'<div class="timeline-time"><span class="timeline-time-start">{godzina_start}</span></div>'
                f'<div class="timeline-center-col"><div class="timeline-icon-badge-static badge-pobudka">⏰</div></div>'
                f'<div class="timeline-content-col">'
                f'<div class="timeline-item-title">Pobudka</div>'
                f'<div class="timeline-item-desc">{opis_tekst_pob if opis_tekst_pob else f"Czas do wyjazdu: {ogarnianie_val}"}</div>'
                f'</div>'
                f'</div>'
                f'</div>'
                f'</div>'
            )
            timeline_full_html.append(row_pobudka)

            # 2. KROK: WYJAZD
            godzina_wyjazdu_wyswietl = godzina_koniec if godzina_koniec else wyjazd_val
            row_wyjazd = (
                f'<div class="timeline-step-row-wrapper">'
                f'<div class="timeline-row-frameless">'
                f'<div class="timeline-row-inner">'
                f'<div class="timeline-time"><span class="timeline-time-start">{godzina_wyjazdu_wyswietl}</span></div>'
                f'<div class="timeline-center-col"><div class="timeline-icon-badge-static badge-wyjazd">🚗</div></div>'
                f'<div class="timeline-content-col">'
                f'<div class="timeline-item-title">Wyjazd</div>'
                f'<div class="timeline-item-desc"></div>'
                f'</div>'
                f'</div>'
                f'</div>'
                f'</div>'
            )
            timeline_full_html.append(row_wyjazd)

        elif is_last:
            df_pos = pob_posilki_dla_kroku(k['id'])
            opis_tekst = ""
            if not df_pos.empty:
                posiłki_str = []
                for _, prow in df_pos.iterrows():
                    p_rodzaj = str(prow.get('rodzaj_posilku', '')).strip().lower()
                    p_godz = str(prow.get('sugerowana_godzina', '')).strip()
                    p_miejsce = str(prow.get('miejsce', '')).strip().lower()
                    if p_rodzaj in ['śniadanie', 'obiad', 'kolacja']:
                        nazwa_p = p_rodzaj.capitalize()
                        if p_miejsce != 'w domku' and p_godz and p_godz != 'None' and p_godz != 'Brak':
                            posiłki_str.append(f"{nazwa_p} ok {p_godz}")
                        else:
                            posiłki_str.append(nazwa_p)
                if posiłki_str:
                    opis_tekst = f"<span style='color:#8C5338; font-weight:700;'>🍲 {' / '.join(posiłki_str)}</span>"

            gps_url = f"https://www.google.com/maps/search/?api=1&query={DOMEK_LAT},{DOMEK_LON}"
            nav_btn_html_domek = f'<a href="{gps_url}" target="_blank" class="timeline-nav-btn" title="Nawiguj"><span>🧭</span><span>Nawiguj</span></a>'

            row_html = (
                f'<div class="timeline-step-row-wrapper">'
                f'<div class="timeline-row-frameless">'
                f'<div class="timeline-row-inner">'
                f'<div class="timeline-time"><span class="timeline-time-start">{godzina_start}</span></div>'
                f'<div class="timeline-center-col"><div class="timeline-icon-badge-static badge-powrot">🏠</div></div>'
                f'<div class="timeline-content-col">'
                f'<div class="timeline-item-title">Powrót do domku</div>'
                f'<div class="timeline-item-desc">{opis_tekst if opis_tekst else "Wypoczynek i relaks"}</div>'
                f'</div>'
                f'{nav_btn_html_domek}'
                f'</div>'
                f'</div>'
                f'</div>'
            )
            timeline_full_html.append(row_html)
        
        elif is_custom_flat:
            # PŁASKI, ZIELONY, NIEROZWIJALNY KROK SPOZA LISTY
            opis_kroku_cust = str(k.get('opis', '')).strip()
            if opis_kroku_cust in ["Brak", "None", ""]:
                opis_kroku_cust = ""

            row_custom = (
                f'<div class="timeline-step-row-wrapper">'
                f'<div class="timeline-row-frameless">'
                f'<div class="timeline-row-inner">'
                f'<div class="timeline-time">'
                f'<span class="timeline-time-start">{godzina_start}</span>'
                f'{(f"<span class=\'timeline-time-end\'>do {godzina_koniec}</span>") if (godzina_koniec and godzina_koniec != godzina_start) else ""}'
                f'</div>'
                f'<div class="timeline-center-col"><div class="timeline-icon-badge-static badge-pobudka">{badge_symbol}</div></div>'
                f'<div class="timeline-content-col">'
                f'<div class="timeline-item-title">{nazwa}</div>'
                f'<div class="timeline-item-desc">{opis_kroku_cust}</div>'
                f'</div>'
                f'{nav_btn_html}'
                f'</div>'
                f'</div>'
                f'</div>'
            )
            timeline_full_html.append(row_custom)

        else:
            badge_class = "badge-obiad" if "🍴" in str(badge_symbol) else "badge-miejsce"

            df_pos = pob_posilki_dla_kroku(k['id'])
            opis_tekst = ""
            if not df_pos.empty:
                posiłki_str = []
                for _, prow in df_pos.iterrows():
                    p_rodzaj = str(prow.get('rodzaj_posilku', '')).strip().lower()
                    p_godz = str(prow.get('sugerowana_godzina', '')).strip()
                    p_miejsce = str(prow.get('miejsce', '')).strip().lower()
                    if p_rodzaj in ['śniadanie', 'obiad', 'kolacja']:
                        nazwa_p = p_rodzaj.capitalize()
                        if p_miejsce != 'w domku' and p_godz and p_godz != 'None' and p_godz != 'Brak':
                            posiłki_str.append(f"{nazwa_p} ok {p_godz}")
                        else:
                            posiłki_str.append(nazwa_p)
                if posiłki_str:
                    opis_tekst = f"<span style='color:#8C5338; font-weight:700;'>🍲 {' / '.join(posiłki_str)}</span>"

            center_col_html = (
                f'<div class="timeline-center-col">'
                f'<div class="timeline-icon-badge-static {badge_class}">{badge_symbol}</div>'
                f'</div>'
            )

            time_end_html = f'<span class="timeline-time-end">do {godzina_koniec}</span>' if (godzina_koniec and godzina_koniec != godzina_start) else ''

            sklep_maps_url = f"https://www.google.com/maps/search/supermarket/@{coords_clean},15z" if coords_clean else "#"
            resto_maps_url = f"https://www.google.com/maps/search/restaurant/@{coords_clean},15z" if coords_clean else "#"

            pogoda_kroku = pobierz_szczegoly_pogody_dla_godziny(k['wspolrzedne'], planowana_data_val, okienko)
            pogoda_html = ""
            if pogoda_kroku:
                pogoda_html = (
                    f'<div style="background-color: #FAF8F2; border: 1.5px solid #D8D2BC; border-radius: 16px; padding: 10px 14px; margin-bottom: 12px; text-align: center;">'
                    f'<div style="font-size: 8.5pt; font-weight: 800; color: #8C5338; text-transform: uppercase; margin-bottom: 3px;">☀️ POGODA ({pogoda_kroku["data"]})</div>'
                    f'<div style="font-size: 10.5pt; font-weight: 800; color: #2B2118;">{pogoda_kroku["temp"]}°C (odcz. {pogoda_kroku["feel"]}°C), {pogoda_kroku["desc"]} 💨 {pogoda_kroku["wind"]} km/h | UV {pogoda_kroku["uv"]}</div>'
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

            details_inner_html = (
                f'<div class="step-details-card">'
                f'{pogoda_html}'
                f'{opis_glowny_html}'
                f'{evac_html}'
                f'{warn_html}'
                f'<details class="step-combined-card">'
                f'<summary>🎯 Taktyka & Regeneracja</summary>'
                f'<div style="margin-top: 10px; border-top: 1px solid #D1C7AE; padding-top: 8px;">'
                f'<div class="step-subitem-title" style="color: #8C5338;">🎯 Taktyka</div>'
                f'<div class="step-subitem-body">{taktyka_val}</div>'
                f'<div class="step-subitem-title" style="color: #6D8257; margin-top: 8px;">🌿 Regeneracja</div>'
                f'<div class="step-subitem-body">{regen_val}</div>'
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
                f'<div class="timeline-time">'
                f'<span class="timeline-time-start">{godzina_start}</span>'
                f'{time_end_html}'
                f'</div>'
                f'{center_col_html}'
                f'<div class="timeline-content-col">'
                f'<div class="timeline-item-title">{nazwa}</div>'
                f'<div class="timeline-item-desc">{opis_tekst}</div>'
                f'</div>'
                f'{nav_btn_html}'
                f'</div>'
                f'</summary>'
                f'<div class="timeline-expander-body">'
                f'{details_inner_html}'
                f'</div>'
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
                    if postoj_val is not None and int(postoj_val) > 0:
                        transit_html = f'<div class="timeline-transit-text">🚗 {czas_dojazdu_dalej} | + {postoj_val}m</div>'
                    else:
                        transit_html = f'<div class="timeline-transit-text">🚗 {czas_dojazdu_dalej}</div>'

            spacer_html = (
                f'<div class="timeline-transit-spacer">'
                f'{transit_html}'
                f'</div>'
            )
            timeline_full_html.append(spacer_html)

    timeline_full_html.append('</div>')
    
    full_timeline_string = "".join(timeline_full_html)

    # Wstrzyknięcie kart zakupów dla poszczególnych kroków (z pominięciem domku)
    for _, k in kroki_df.iterrows():
        nazwa_kroku = str(k['nazwa']).lower()
        if "domek" in nazwa_kroku:
            continue

        krok_row_id = int(k['id'])
        ph = f"###SHOPPING_LIST_PLACEHOLDER_{krok_row_id}###"
        if ph in full_timeline_string:
            df_zak = pobierz_zakupy_dla_kroku(krok_row_id)
            if not df_zak.empty:
                zak_items_html = []
                for _, zrow in df_zak.iterrows():
                    z_id = zrow['id']
                    z_nazwa = str(zrow['nazwa_produktu'])
                    z_ilosc = str(zrow['ilosc']) if pd.notna(zrow['ilosc']) and str(zrow['ilosc']).strip() else ""
                    z_kup = bool(zrow['kupione'])
                    
                    strike_style = "text-decoration: line-through; opacity: 0.6;" if z_kup else ""
                    checked_attr = "checked" if z_kup else ""
                    ilosc_badge = f'<span style="font-size: 8pt; background: #D1C7AE; color: #2B2118; padding: 2px 6px; border-radius: 8px; font-weight: 800; margin-left: auto;">{z_ilosc}</span>' if z_ilosc else ""
                    
                    zak_items_html.append(
                        f'<div style="display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid rgba(0,0,0,0.05);">'
                        f'<input type="checkbox" {checked_attr} disabled style="accent-color: #8C5338; width: 16px; height: 16px;">'
                        f'<span style="font-size: 9.5pt; font-weight: 700; color: #2B2118; {strike_style}">{z_nazwa}</span>'
                        f'{ilosc_badge}'
                        f'</div>'
                    )

                card_zakupy_html = (
                    f'<details class="step-combined-card" style="margin-top: 8px; margin-bottom: 8px;">'
                    f'<summary>🛒 Lista zakupów ({len(df_zak)})</summary>'
                    f'<div style="margin-top: 10px; border-top: 1px solid #D1C7AE; padding-top: 8px;">'
                    f'{"".join(zak_items_html)}'
                    f'</div>'
                    f'</details>'
                )
                full_timeline_string = full_timeline_string.replace(ph, card_zakupy_html)
            else:
                full_timeline_string = full_timeline_string.replace(ph, "")

    st.markdown(full_timeline_string, unsafe_allow_html=True)

    # Centralna sekcja i rozwijana karta: Zakupy Dnia
    st.markdown('<div class="section-unified-header">🛒 Zakupy Dnia</div>', unsafe_allow_html=True)
    df_wszystkie_zakupy = pobierz_zakupy_dla_wycieczki(wycieczka_id)

    with st.expander("🛒 Lista zakupów", expanded=False):
        # 1. Formularz szybkiego dodawania pozycji (całkowity brak Domku w opcjach)
        with st.form(key=f"form_add_shopping_item_{wycieczka_id}", clear_on_submit=True):
            st.markdown("<div style='font-size: 9.5pt; font-weight: 800; color: #8C5338; margin-bottom: 4px;'>➕ Dodaj nową pozycję do listy</div>", unsafe_allow_html=True)
            col_nazwa, col_ilosc = st.columns([2, 1])
            with col_nazwa:
                nowy_prod = st.text_input("Produkt", placeholder="np. Woda 1.5L, Owoce, Plastry", label_visibility="collapsed")
            with col_ilosc:
                nowa_ilosc = st.text_input("Ilość", placeholder="Ilość (np. 6 szt)", label_visibility="collapsed")

            # Przygotowanie opcji przypisania: Cała wycieczka (ogólne) lub konkretny krok poza Domkiem
            opcje_przypisania = [("📦 Cała wycieczka (ogólne)", None)]
            for _, k_row in kroki_df.iterrows():
                nazwa_k = str(k_row['nazwa'])
                if "domek" not in nazwa_k.lower():
                    opcje_przypisania.append((f"📍 Krok {k_row['krok_wycieczki']}: {nazwa_k}", int(k_row['id'])))

            wybrany_target = st.selectbox(
                "Przypisz do:",
                options=opcje_przypisania,
                format_func=lambda x: x[0]
            )

            btn_add_item = st.form_submit_button("➕ Dodaj do listy", use_container_width=True)
            if btn_add_item and nowy_prod.strip():
                dodaj_produkt_zakupow(
                    id_wycieczki=wycieczka_id,
                    nazwa_produktu=nowy_prod.strip(),
                    id_kroku=wybrany_target[1],
                    ilosc=nowa_ilosc.strip() if nowa_ilosc.strip() else "1"
                )
                st.session_state["flash_toast"] = f"🛒 Dodano: {nowy_prod.strip()}"
                st.rerun()

        st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)

        # 2. Wyświetlanie elementów checklisty
        if df_wszystkie_zakupy.empty:
            st.markdown("<div style='font-size: 9pt; color: #8C827A; font-style: italic; margin-top: 6px;'>Lista zakupów jest pusta. Dodaj produkty powyżej!</div>", unsafe_allow_html=True)
        else:
            # A) Zakupy ogólne na całą wycieczkę
            ogolne_zakupy = df_wszystkie_zakupy[df_wszystkie_zakupy['id_kroku'].isna() | (df_wszystkie_zakupy['id_kroku'] == '')]
            if not ogolne_zakupy.empty:
                st.markdown("<div style='font-size: 9.5pt; font-weight: 800; color: #8C5338; margin: 8px 0 4px 0;'>📦 Na całą wycieczkę:</div>", unsafe_allow_html=True)
                for _, zrow in ogolne_zakupy.iterrows():
                    z_id = zrow['id']
                    z_nazwa = str(zrow['nazwa_produktu'])
                    z_ilosc = f" ({zrow['ilosc']})" if pd.notna(zrow['ilosc']) and str(zrow['ilosc']).strip() else ""
                    z_kup = bool(zrow['kupione'])
                    
                    nowy_status = st.checkbox(f"{z_nazwa}{z_ilosc}", value=z_kup, key=f"cb_zakup_main_{z_id}")
                    if nowy_status != z_kup:
                        zmien_status_zakupu(z_id, nowy_status)
                        st.rerun()

            # B) Zakupy przypisane do konkretnych kroków (z pominięciem domku)
            for _, k in kroki_df.iterrows():
                if "domek" in str(k['nazwa']).lower():
                    continue

                k_id = int(k['id'])
                zakupy_kroku = df_wszystkie_zakupy[df_wszystkie_zakupy['id_kroku'] == k_id]
                if not zakupy_kroku.empty:
                    st.markdown(f"<div style='font-size: 9.5pt; font-weight: 800; color: #8C5338; margin: 10px 0 4px 0;'>📍 {k['nazwa']}:</div>", unsafe_allow_html=True)
                    for _, zrow in zakupy_kroku.iterrows():
                        z_id = zrow['id']
                        z_nazwa = str(zrow['nazwa_produktu'])
                        z_ilosc = f" ({zrow['ilosc']})" if pd.notna(zrow['ilosc']) and str(zrow['ilosc']).strip() else ""
                        z_kup = bool(zrow['kupione'])
                        
                        nowy_status = st.checkbox(f"{z_nazwa}{z_ilosc}", value=z_kup, key=f"cb_zakup_krok_view_{z_id}")
                        if nowy_status != z_kup:
                            zmien_status_zakupu(z_id, nowy_status)
                            st.rerun()

    # --- SEKCJA NOTATKI (PRZENIESIONA NAD ZADANIA DLA DZIECI) ---
    renderuj_sekcje_notatek(id_wycieczki=wycieczka_id)

    # --- SEKCJA ZADANIA DLA DZIECI ---
    st.markdown('<div class="section-unified-header">🎯 Zadania dla dzieci</div>', unsafe_allow_html=True)
    grupy_zadan = pobierz_grupy_zadan_dla_wycieczki(wycieczka_id, kroki_df)
    
    with st.expander("🎯 Zadania", expanded=False):
        if grupy_zadan:
            for tytul_grupy, lista_zadan, prefix in grupy_zadan:
                if not lista_zadan:
                    continue
                with st.expander(tytul_grupy, expanded=False):
                    for idx, zad in enumerate(lista_zadan):
                        klucz = f"{prefix}_task_{idx}"
                        stan = pobierz_status_zadania(klucz)
                        nowy_stan = st.checkbox(
                            zad,
                            value=stan,
                            key=f"cb_{klucz}"
                        )
                        if nowy_stan != stan:
                            zapisz_status_zadania(klucz, nowy_stan)
                            st.rerun()
        else:
            st.markdown("<div style='font-size: 9pt; color: #8C827A; font-style: italic;'>Brak zadań dla tej wycieczki.</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-unified-header">🤖 Asystent AI</div>', unsafe_allow_html=True)
    renderuj_globalny_czat_ai(aktualny_uzytkownik, inline=True)

if st.session_state.active_tab == "route":
    st.markdown("""
<div class="adventure-header">
<div style="font-size:24px;">🚗</div>
<div><div class="adventure-title-text">CretAi • Aktualna Wycieczka</div></div>
</div>
""", unsafe_allow_html=True)
    aktualne_id = pobierz_aktywna_wycieczke_id()
    renderuj_karte_wycieczki(aktualne_id, pokaz_mape=False, pokaz_pogode=True)

elif st.session_state.active_tab == "map":
    st.markdown("""
<div class="adventure-header">
<div style="font-size:24px;">🗺️</div>
<div><div class="adventure-title-text">CretAi • Nasze wycieczki</div></div>
</div>
""", unsafe_allow_html=True)
    
    opcje_wycieczek_lista = [None] + wycieczki_options
    selected_idx = 0
    if "selected_trip_from_click" in st.session_state and st.session_state["selected_trip_from_click"]:
        for i, opt in enumerate(opcje_wycieczek_lista):
            if opt and opt.startswith(f"{st.session_state['selected_trip_from_click']}."):
                selected_idx = i
                break
        st.session_state["selected_trip_from_click"] = None

    wybrana_mapa_sb = st.selectbox(
        "", 
        options=opcje_wycieczek_lista, 
        index=selected_idx, 
        format_func=lambda x: "**Wybierz wycieczkę**" if x is None else x,
        key="map_wycieczka_select", 
        label_visibility="collapsed"
    )

    m_all = folium.Map(location=[35.2401, 24.8093], zoom_start=8, tiles="CartoDB positron")
    dodaj_marker_domku(m_all)
    
    map_coords_lookup = {}
    for _, row in df_miejsca.iterrows():
        lat, lon = sparsuj_wspolrzedne(row.get('wspolrzedne'))
        if lat is not None and lon is not None:
            num = str(row.get('numer_miejsca', ''))
            nazwa = str(row.get('nazwa', ''))
            kat = kategoryzuj_typ(row.get('typ'))
            kolor = pobierz_kolor_kategorii(kat)
            map_coords_lookup[(round(lat, 4), round(lon, 4))] = (num, nazwa)
            
            icon_html = f'<div style="background-color:{kolor};color:white;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:900;border:2px solid white;cursor:pointer;box-shadow:0 2px 5px rgba(0,0,0,0.2);">{num}</div>'
            folium.Marker([lat, lon], icon=folium.DivIcon(html=icon_html, icon_size=(26, 26), icon_anchor=(13, 13)), tooltip=f"#{num} {nazwa}").add_to(m_all)
            
    map_out = st_folium(m_all, width=None, height=340, returned_objects=["last_object_clicked"], key="map_all_trips_view")
    
    if map_out and map_out.get("last_object_clicked"):
        c_lat = map_out["last_object_clicked"].get("lat")
        c_lng = map_out["last_object_clicked"].get("lng")
        if c_lat is not None and c_lng is not None:
            key_l = (round(c_lat, 4), round(c_lng, 4))
            matched_place = map_coords_lookup.get(key_l)
            if not matched_place:
                for (mlat, mlon), data_tuple in map_coords_lookup.items():
                    if abs(mlat - c_lat) < 0.005 and abs(mlon - c_lng) < 0.005:
                        matched_place = data_tuple
                        break
            if matched_place and st.session_state.map_tab_selected_place != matched_place:
                st.session_state.map_tab_selected_place = matched_place
                st.rerun()

    if st.session_state.map_tab_selected_place:
        nr_m, nazwa_m = st.session_state.map_tab_selected_place
        df_przypisane = pobierz_wycieczki_dla_miejsca(nr_m, nazwa_m)
        
        with st.container():
            st.markdown('<div class="trip-box-marker"></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="font-size: 11pt; font-weight: 900; color: #2B2118; margin-bottom: 4px;">📍 {nr_m}. {nazwa_m}</div><div style="font-size: 9.5pt; font-weight: 800; color: #8C5338; margin-bottom: 8px;">🗺️ Występuje w wycieczkach:</div>', unsafe_allow_html=True)
            
            if df_przypisane.empty:
                st.markdown("<div style='font-size: 9pt; color: #8C827A; font-style: italic; margin-bottom: 4px;'>Nie jest przypisany</div>", unsafe_allow_html=True)
            else:
                for _, row_trip in df_przypisane.iterrows():
                    w_id = str(row_trip['id'])
                    w_tytul = str(row_trip['tytul_wycieczki'])
                    skrocony = w_tytul.split(':')[0] if ':' in w_tytul else w_tytul
                    if st.button(f"🧭 {w_id}. {skrocony}", key=f"btn_go_to_trip_{w_id}_{nr_m}", use_container_width=True):
                        st.session_state["selected_trip_from_click"] = w_id
                        st.rerun()

    if wybrana_mapa_sb is not None:
        wybrana_id = wybrana_mapa_sb.split(". ")[0]
        renderuj_karte_wycieczki(wybrana_id, pokaz_mape=True, pokaz_pogode=False)

elif st.session_state.active_tab == "zabytek":
    st.markdown("""
<div class="adventure-header">
<div style="font-size:24px;">🏛️</div>
<div><div class="adventure-title-text">CretAi • Baza Miejsc</div></div>
</div>
""", unsafe_allow_html=True)
    
    all_cats = list(CATEGORIES_CONFIG.keys())
    active_cat = st.session_state.selected_category
    
    button_styles = ["""
    div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 6px !important;
        margin-bottom: 0px !important;
    }
    div[data-testid="stHorizontalBlock"] > div {
        flex: 1 1 0px !important;
        min-width: 0 !important;
    }
    """]

    for cat_name, conf in CATEGORIES_CONFIG.items():
        is_selected = (active_cat == cat_name)
        is_all_active = (active_cat is None)
        slug = conf["slug"]
        
        bg_col = conf["color"] if (is_selected or is_all_active) else "#E0DCCE"
        border_col = conf["color"] if (is_selected or is_all_active) else "#C8C2B0"
        opacity = "1.0" if (is_selected or is_all_active) else "0.45"
        text_col = "#FAF8F2" if (is_selected or is_all_active) else "#2F241D"
        
        button_styles.append(f"""
        div.st-key-btn_cat_filter_{slug} button {{
            background-color: {bg_col} !important;
            color: {text_col} !important;
            border: 1.5px solid {border_col} !important;
            opacity: {opacity} !important;
            height: 32px !important;
            border-radius: 10px !important;
            width: 100% !important;
        }}
        """)

    st.markdown(f"<style>{''.join(button_styles)}</style>", unsafe_allow_html=True)

    cols_row1 = st.columns(3, gap="small")
    for idx, cat_name in enumerate(all_cats[:3]):
        slug = CATEGORIES_CONFIG[cat_name]["slug"]
        with cols_row1[idx]:
            btn_label = f"✓ {cat_name}" if active_cat == cat_name else cat_name
            if st.button(btn_label, key=f"btn_cat_filter_{slug}", use_container_width=True):
                st.session_state.selected_category = None if active_cat == cat_name else cat_name
                st.rerun()

    cols_row2 = st.columns(3, gap="small")
    for idx, cat_name in enumerate(all_cats[3:]):
        slug = CATEGORIES_CONFIG[cat_name]["slug"]
        with cols_row2[idx]:
            btn_label = f"✓ {cat_name}" if active_cat == cat_name else cat_name
            if st.button(btn_label, key=f"btn_cat_filter_{slug}", use_container_width=True):
                st.session_state.selected_category = None if active_cat == cat_name else cat_name
                st.rerun()

    df_miejsca_filtrowane = df_miejsca.copy()
    if not df_miejsca_filtrowane.empty:
        df_miejsca_filtrowane['kategoria_normalizowana'] = df_miejsca_filtrowane['typ'].apply(kategoryzuj_typ)
        if st.session_state.selected_category is not None:
            df_miejsca_filtrowane = df_miejsca_filtrowane[df_miejsca_filtrowane['kategoria_normalizowana'] == st.session_state.selected_category]

    m_miejsca = folium.Map(location=[35.2401, 24.8093], zoom_start=8, tiles="CartoDB positron")
    dodaj_marker_domku(m_miejsca)

    marker_coords_dict = {}
    if not df_miejsca_filtrowane.empty:
        for _, row in df_miejsca_filtrowane.iterrows():
            lat, lon = sparsuj_wspolrzedne(row.get('wspolrzedne'))
            if lat is not None and lon is not None:
                num = str(row.get('numer_miejsca', ''))
                kat = row.get('kategoria_normalizowana', 'Other')
                kolor = pobierz_kolor_kategorii(kat)
                marker_coords_dict[(round(lat, 4), round(lon, 4))] = num
                
                icon_html = f'<div style="background-color:{kolor};color:#FFFFFF;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:900;border:2px solid #FFFFFF;box-shadow:0 2px 5px rgba(0,0,0,0.25);">{num}</div>'
                folium.Marker([lat, lon], icon=folium.DivIcon(html=icon_html, icon_size=(26, 26), icon_anchor=(13, 13))).add_to(m_miejsca)

    map_output = st_folium(m_miejsca, width=None, height=320, returned_objects=["last_object_clicked"], key="map_places_view")

    if map_output and map_output.get("last_object_clicked"):
        c_lat = map_output["last_object_clicked"].get("lat")
        c_lng = map_output["last_object_clicked"].get("lng")
        if c_lat is not None and c_lng is not None:
            key_lookup = (round(c_lat, 4), round(c_lng, 4))
            clicked_id = marker_coords_dict.get(key_lookup)
            if clicked_id and st.session_state.active_place_id != str(clicked_id):
                st.session_state.active_place_id = str(clicked_id)
                st.query_params["place"] = str(clicked_id)
                st.rerun()

    miejsca_opcje_lista = [f"{r['numer_miejsca']}. {r['nazwa']}" for _, r in df_miejsca_filtrowane.iterrows()]
    domyslny_indeks = 0
    if st.session_state.active_place_id:
        for idx, opt in enumerate(miejsca_opcje_lista):
            if opt.startswith(f"{st.session_state.active_place_id}."):
                domyslny_indeks = idx + 1
                break

    selected_option = st.selectbox(
        "",
        options=[None] + miejsca_opcje_lista,
        index=domyslny_indeks,
        format_func=lambda x: "🔍 Wybierz z listy..." if x is None else x,
        key="place_selectbox_selector",
        label_visibility="collapsed"
    )
    
    docelowy_nr = selected_option.split(".")[0].strip() if selected_option else (st.session_state.active_place_id)
    if selected_option:
        st.session_state.active_place_id = docelowy_nr

    if docelowy_nr:
        p_row = df_miejsca[df_miejsca['numer_miejsca'] == str(docelowy_nr)]
        if not p_row.empty:
            p = p_row.iloc[0]
            kat_p = kategoryzuj_typ(p.get('typ'))
            kolor_p = pobierz_kolor_kategorii(kat_p)
            coords_p = str(p.get('wspolrzedne', '')).replace(" ", "")

            st.markdown(f"""
            <div class="overview-card" style="margin-top: 10px;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                    <div style="font-size: 15pt; font-weight: 900; color: #2B2118; line-height: 1.2;">{p.get('numer_miejsca')}. {p.get('nazwa')}</div>
                    <span style="background-color: {kolor_p}; color: #FAF8F2; font-size: 8.5pt; font-weight: 800; padding: 3px 10px; border-radius: 12px;">{kat_p}</span>
                </div>
                <div class="overview-card-text">{p.get('opis', '')}</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown(f"""
            <div class="overview-card">
                <div class="overview-card-title"><span>ℹ️</span> INFORMACJE PRAKTYCZNE</div>
                <div class="logistics-grid">
                    <div class="logistics-pill">
                        <div class="logistics-pill-title">🚗 Czas dojazdu</div>
                        <div class="logistics-pill-value" style="font-size: 10pt;">{p.get('czas_dojazdu', '—')}</div>
                    </div>
                    <div class="logistics-pill">
                        <div class="logistics-pill-title">⏱️ Czas na miejscu</div>
                        <div class="logistics-pill-value" style="font-size: 10pt;">{p.get('orientacyjny_czas', '—')}</div>
                    </div>
                    <div class="logistics-pill">
                        <div class="logistics-pill-title">💶 Koszt (2+2)</div>
                        <div class="logistics-pill-value" style="font-size: 10pt;">{p.get('koszt', '—')}</div>
                    </div>
                    <div class="logistics-pill">
                        <div class="logistics-pill-title">🕒 Godziny otwarcia</div>
                        <div class="logistics-pill-value" style="font-size: 10pt;">{p.get('godziny_otwarcia', '—')}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown(f"""
            <div class="overview-card">
                <div class="overview-card-title"><span>📊</span> POZIOM TRUDNOŚCI</div>
                <div class="overview-card-text">{p.get('trudnosc_adhd', 'Średni')}</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown(f"""
            <div class="overview-card">
                <div class="overview-card-title"><span>☀️</span> OCHRONA PRZED SŁOŃCEM</div>
                <div class="overview-card-text">{p.get('ochrona_slonce', 'Standardowa')}</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown(f"""
            <details class="overview-details-card">
                <summary>🧠 SPECYFIKA ADHD & SENSORYKA</summary>
                <div style="margin-top: 10px; border-top: 1px solid #D1C7AE; padding-top: 8px;">
                    <div style="font-size: 9.5pt; color: #2B2118; margin-bottom: 6px;"><b>Potencjał meltdownu:</b> {p.get('potencjal_meltdownu', 'Średni')}</div>
                    <div style="font-size: 9.5pt; color: #2B2118;"><b>Strategia zaradcza:</b> {p.get('strategie_meltdown', 'Brak')}</div>
                </div>
            </details>
            """, unsafe_allow_html=True)

            zadania_miejsca = sparsuj_liste_zadan(p.get('zadania_dla_dzieci', ''))
            if zadania_miejsca:
                with st.expander("🎯 Zadania dla dzieci", expanded=False):
                    for idx, zad in enumerate(zadania_miejsca):
                        klucz = f"place_{docelowy_nr}_task_{idx}"
                        stan = pobierz_status_zadania(klucz)
                        nowy_stan = st.checkbox(
                            zad,
                            value=stan,
                            key=f"cb_{klucz}"
                        )
                        if nowy_stan != stan:
                            zapisz_status_zadania(klucz, nowy_stan)
                            st.rerun()

            if coords_p and ',' in coords_p:
                st.markdown(f"""
                <div class="step-action-vertical-bar">
                    <a href="https://www.google.com/maps/search/?api=1&query={coords_p}" target="_blank" class="step-action-vertical-btn"><span>🧭</span><span>Nawiguj do tego miejsca</span></a>
                    <a href="https://www.google.com/search?q={p['nazwa']} Kreta" target="_blank" class="step-action-vertical-btn"><span>🔍</span><span>Szukaj w Google</span></a>
                </div>
                """, unsafe_allow_html=True)

            renderuj_sekcje_notatek(id_miejsca=str(docelowy_nr))

if st.session_state.active_tab != "route":
    renderuj_globalny_czat_ai(aktualny_uzytkownik)
