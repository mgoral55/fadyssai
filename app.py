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
import math
import base64
import time as py_time
from datetime import datetime, date, time, timedelta

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# --- 0. BAZA DANYCH (CONCURRENCY & WAL) ---
def get_db():
    conn = sqlite3.connect('cretai.db', timeout=30.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA busy_timeout = 30000;')
    return conn

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

/* Zapobieganie zoomowaniu w iOS Safari i dopasowanie mobilne */
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

div[data-testid="stPopover"] { width: 100% !important; }
div[data-testid="stPopover"] > button, div[data-testid="stPopover"] > button:disabled, div[data-testid="stPopover"] > button[aria-expanded], div[data-testid="stPopover"] > button:focus, div[data-testid="stPopover"] > button:active { background-color: #F6F0DD !important; color: #2B2118 !important; border: 1.5px solid #E2DEC8 !important; border-radius: 20px !important; padding: 14px 8px !important; min-height: 64px !important; box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important; width: 100% !important; display: flex !important; align-items: center !important; justify-content: center !important; }
div[data-testid="stPopover"] > button * { color: #2B2118 !important; font-weight: 900 !important; font-size: 1.05rem !important; }
div[data-testid="stPopover"] > button:hover { border-color: #8C5338 !important; background-color: #EFE8D1 !important; }

[data-testid="stExpander"] { border: 1.5px solid #E2DEC8 !important; border-radius: 20px !important; background-color: #F6F0DD !important; margin-bottom: 6px !important; box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important; overflow: hidden !important; }
[data-testid="stExpander"] summary { font-size: 9.5pt !important; font-weight: 800 !important; color: #2B2118 !important; padding: 10px 14px !important; }
[data-testid="stExpander"] summary:hover { color: #8C5338 !important; }
[data-testid="stExpander"] summary svg { fill: #8C5338 !important; color: #8C5338 !important; }
[data-testid="stExpander"] [data-testid="stExpanderDetails"] { background-color: #F6F0DD !important; border-top: 1px solid #D1C7AE !important; padding: 10px 12px !important; }

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

.badge-pobudka, .badge-wyjazd, .badge-powrot { background-color: #94A77E !important; }
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

div[data-testid="stCheckbox"] { margin-bottom: 4px !important; background-color: #B4C29D !important; border: none !important; border-radius: 0px !important; padding: 0px !important; box-shadow: none !important; accent-color: #8C5338 !important; }
div[data-testid="stCheckbox"] label { font-size: 9pt !important; font-weight: 700 !important; color: #2B2118 !important; }

/* Mobilny Pływający Asystent AI */
.floating-ai-container { position: fixed; bottom: 10px; left: 6px; right: 6px; max-width: 520px; margin: 0 auto; z-index: 999998; }
.custom-nav-bar { display: flex; justify-content: space-between; gap: 6px; width: 100%; }
.custom-nav-btn { flex: 1; background-color: #FAF8F2; border: 1.5px solid #D6D2C4; color: #2B2118; padding: 7px 3px; text-align: center; border-radius: 14px; font-size: 10.5px; font-weight: 800; text-decoration: none; display: flex; flex-direction: column; align-items: center; gap: 2px; }

.stButton > button { background-color: #2E251E !important; color: #FFFFFF !important; border: none !important; font-weight: 800 !important; border-radius: 18px !important; padding: 0.4rem 0.8rem !important; min-height: 40px !important; font-size: 9.5pt !important; box-shadow: 0 3px 8px rgba(0,0,0,0.08) !important; }
div[class*="st-key-btn_add_shop_"] button, div[class*="st-key-btn_add_market_"] button { height: 40px !important; min-height: 40px !important; max-height: 40px !important; font-size: 8.5pt !important; font-weight: 800 !important; border-radius: 14px !important; margin-bottom: 4px !important; display: flex !important; align-items: center !important; justify-content: center !important; text-align: center !important; }
div[class*="st-key-btn_add_shop_"] button:disabled, div[class*="st-key-btn_add_market_"] button:disabled { background-color: #D6CEBA !important; color: #73695F !important; border: 1.5px solid #C4BC9E !important; opacity: 0.85 !important; cursor: not-allowed !important; box-shadow: none !important; }
.note-card { background-color: #F4EFE6; border: 1.5px solid #D8D2BC; border-radius: 16px; padding: 12px; margin-bottom: 8px; }

/* Optymalizacja dymków czatu na telefonie */
[data-testid="stChatMessage"] { padding: 8px 10px !important; margin-bottom: 6px !important; border-radius: 14px !important; font-size: 9.5pt !important; }
[data-testid="stChatMessageContent"] p { font-size: 9.5pt !important; line-height: 1.35 !important; margin-bottom: 0 !important; }
</style>
""", unsafe_allow_html=True)

if "flash_toast" in st.session_state and st.session_state["flash_toast"]:
    st.toast(st.session_state["flash_toast"], icon="🧭")
    st.session_state["flash_toast"] = None

DOMEK_LAT, DOMEK_LON = 35.5914, 24.0918
SKLEP_LAT, SKLEP_LON = 35.586222, 24.091861

# --- OBSŁUGA LOGO ---
def pobierz_logo_b64(sciezka_pliku="logo.png"):
    if os.path.exists(sciezka_pliku):
        try:
            with open(sciezka_pliku, "rb") as f:
                return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
        except:
            return None
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
    except:
        weekday = date.today().weekday()
    return LAIKI_SCHEDULE.get(weekday), weekday

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
    if "must" in t: return "Must have"
    if "nice" in t: return "Nice to have"
    if any(w in t for w in ["plaż", "plaz", "beach"]): return "Plaża"
    if any(w in t for w in ["activ", "aktywn", "wąwóz", "wawoz", "sport"]): return "Activity"
    if any(w in t for w in ["shop", "sklep", "zakup", "market", "rynek", "targ"]): return "Shop"
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
        with urllib.request.urlopen(req, timeout=0.3) as response:
            data = json.loads(response.read().decode())
            if 'routes' in data and len(data['routes']) > 0:
                minuty = zaokraglij_do_5_minut(int(round(data['routes'][0]['duration'] / 60)))
                if minuty < 60: return f"~{minuty} min", minuty
                godziny, reszta = minuty // 60, minuty % 60
                return (f"~{godziny}h", minuty) if reszta == 0 else (f"~{godziny}h {reszta}m", minuty)
    except:
        pass
    
    try:
        dist_km = math.sqrt(((lat2 - lat1) * 111.0)**2 + ((lon2 - lon1) * 85.0)**2) * 1.3
        est_min = zaokraglij_do_5_minut(max(int(round((dist_km / 45.0) * 60)), 10))
        return (f"~{est_min} min", est_min) if est_min < 60 else (f"~{est_min // 60}h {est_min % 60}m", est_min)
    except:
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
    except:
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
        except:
            total = 30
    return max(total, 15)

DNI_TYGODNIA_PL = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
MIESIACE_PL = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]

def sformatuj_date_pl(data_str):
    try:
        dt = datetime.strptime(str(data_str), "%Y-%m-%d").date() if data_str else date.today()
    except:
        dt = date.today()
    return dt, dt.day, MIESIACE_PL[dt.month - 1], DNI_TYGODNIA_PL[dt.weekday()]

def wczytaj_pliki_regul(katalog="rule", plik_glowny="SYSTEM_RULES_KRETA_ADHD.md"):
    if os.path.exists(plik_glowny):
        try:
            with open(plik_glowny, 'r', encoding='utf-8') as f:
                return f"\n--- SYSTEM RULES (GŁÓWNY PLIK REGUŁ) ---\n{f.read().strip()}\n"
        except:
            pass

    if not os.path.exists(katalog):
        return ""
    tresc, znaleziono = "\n--- REGUŁY ---\n", False
    for plik in sorted(os.listdir(katalog)):
        sciezka = os.path.join(katalog, plik)
        if os.path.isfile(sciezka) and plik.lower().endswith(('.txt', '.md', '.json', '.rule', '.csv')):
            try:
                with open(sciezka, 'r', encoding='utf-8') as f:
                    tresc += f"[{plik}]:\n{f.read().strip()}\n\n"
                    znaleziono = True
            except:
                pass
    return tresc if znaleziono else ""

def formatuj_posilki_kroku(df_pos):
    if df_pos.empty:
        return ""
    posiłki_str = []
    for _, prow in df_pos.iterrows():
        p_rodzaj = str(prow.get('rodzaj_posilku', '')).strip().lower()
        p_godz = str(prow.get('sugerowana_godzina', '')).strip()
        p_miejsce = str(prow.get('miejsce', '')).strip().lower()
        if p_rodzaj in ['śniadanie', 'obiad', 'kolacja']:
            nazwa_p = p_rodzaj.capitalize()
            posiłki_str.append(f"{nazwa_p} ok {p_godz}" if (p_miejsce != 'w domku' and p_godz and p_godz not in ['None', 'Brak']) else nazwa_p)
    return f"<span style='color:#8C5338; font-weight:700;'>🍲 {' / '.join(posiłki_str)}</span>" if posiłki_str else ""

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

def znajdz_id_kroku_w_db(cursor, id_wycieczki, identyfikator):
    query = '''
        SELECT id, nazwa FROM krok_wycieczki 
        WHERE id_wycieczki = ? AND (
            id = ? OR 
            krok_wycieczki = ? OR 
            nazwa LIKE ? OR 
            ? LIKE ('%' || nazwa || '%')
        )
    '''
    cursor.execute(query, (str(id_wycieczki), str(identyfikator), str(identyfikator), f"%{identyfikator}%", str(identyfikator)))
    return cursor.fetchone()

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
        return pd.read_sql('SELECT * FROM miejsca', conn)

def pobierz_aktywna_wycieczke_id():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT aktualne_id_wycieczki FROM aktywna_wycieczka WHERE id = 1')
        res = cursor.fetchone()
    return str(res[0]) if res else "1"

def szukaj_miejsca_w_bazie(nazwa_zapytania):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT numer_miejsca, nazwa, wspolrzedne, orientacyjny_czas, godziny_otwarcia, 
                   konieczna_akcja, ochrona_slonce, potencjal_meltdownu, strategie_meltdown, opis
            FROM miejsca 
            WHERE nazwa LIKE ? OR numer_miejsca = ?
        ''', (f"%{nazwa_zapytania}%", str(nazwa_zapytania)))
        row = cursor.fetchone()
        if row:
            return {
                "numer_miejsca": row[0], "nazwa": row[1], "wspolrzedne": row[2], "orientacyjny_czas": row[3],
                "godziny_otwarcia": row[4], "konieczna_akcja": row[5], "ochrona_slonce": row[6],
                "potencjal_meltdownu": row[7], "strategie_meltdown": row[8], "opis": row[9]
            }
    return None

# --- STRAŻNIK AuDHD: WALIDATOR PRZED MUTACJĄ W BAZIE ---
def sprawdz_ryzyka_audhd_dla_kroku(id_wycieczki, nazwa_nowego_miejsca, planowane_okienko):
    miejsce_info = szukaj_miejsca_w_bazie(nazwa_nowego_miejsca)
    nazwa_l = str(nazwa_nowego_miejsca).lower()
    
    # 1. Walidacja okna upału (11:30 - 15:30)
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
                    f"💡 PROPOZYCJA: Zaplanuj tę atrakcję z samego rana (np. 08:00–10:00) lub w tych godzinach wybierz klimatyzowane Cretaquarium, jaskinię lub obiad w tawernie w cieniu."
                )

    # 2. Walidacja luki żywieniowej (Zasada 3.5h)
    with get_db() as conn:
        kroki = conn.cursor().execute(
            'SELECT okienko_zwiedzania, nazwa FROM krok_wycieczki WHERE id_wycieczki = ? ORDER BY CAST(krok_wycieczki AS INTEGER) ASC',
            (str(id_wycieczki),)
        ).fetchall()
    
    if kroki and g_start:
        ostatni_krok = kroki[-1]
        g_prev = sparsuj_godzine_minuty(ostatni_krok[0].split("-")[-1].strip())
        if g_prev:
            prev_dec = g_prev[0] + g_prev[1] / 60.0
            if (godz_dec - prev_dec) > 3.5:
                return False, (
                    f"⛔ ODMOWA: Czas od poprzedniego punktu przekracza 3.5 godziny bez zaplanowanego posiłku. "
                    f"Dzieci z AuDHD wejdą w stan silnego przebodźcowania i głodu (Hangry). "
                    f"💡 PROPOZYCJA: Zaplanuj przerwę na obiad / Safe Snack lub postój w tawernie przed wejściem do '{nazwa_nowego_miejsca}'."
                )

    return True, ""

def przelicz_i_zsynchronizuj_wycieczke(id_wycieczki, force_pobudka_str=None, force_wyjazd_str=None, force_powrot_str=None):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT szacowany_czas_ogarniania_rano, pobudka, czas_wyjazdu FROM wycieczka WHERE id = ?', (str(id_wycieczki),))
        row_og = cursor.fetchone()
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
        dur_def = 25 if any(w in nazwa_l for w in ["sklep", "market", "zakup", "apteka", "rynek", "targ"]) else (90 if ("plaż" in nazwa_l or "beach" in nazwa_l) else (30 if (idx == 0 or idx == len(kroki) - 1) else 60))
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
            cursor.execute('UPDATE krok_wycieczki SET okienko_zwiedzania = ? WHERE id = ?', (f"{s_str} - {e_str}", kroki[i][0]))
            cursor.execute('UPDATE posilki_kroku SET sugerowana_godzina = ? WHERE id_kroku = ?', (s_str, kroki[i][0]))
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

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS miejsca (
            numer_miejsca TEXT PRIMARY KEY, nazwa TEXT, nazwa_angielska TEXT, opis TEXT, wspolrzedne TEXT, typ TEXT,
            czas_dojazdu TEXT, godziny_otwarcia TEXT, najlepsza_pora TEXT, orientacyjny_czas TEXT, koszt TEXT,
            konieczna_akcja TEXT, zaplecze_gastro TEXT, ile_jedzenia TEXT, trudnosc_adhd TEXT, potencjal_meltdownu TEXT,
            strategie_meltdown TEXT, ochrona_slonce TEXT, najlepiej_polaczyc TEXT, zadania_dla_dzieci TEXT,
            odwiedzone INTEGER DEFAULT 0, Base TEXT DEFAULT 'false'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wycieczka (
            id TEXT PRIMARY KEY, tytul_wycieczki TEXT, calosciowy_opis_wycieczki TEXT, calosciowa_taktyka_dnia TEXT,
            calkowity_czas_wycieczki_godziny TEXT, szacowana_godzina_powrotu TEXT, pobudka TEXT, czas_wyjazdu TEXT,
            planowana_data TEXT, czas_powrotu_do_domku TEXT DEFAULT NULL, szacowany_czas_ogarniania_rano TEXT DEFAULT '0.5h', odbyta INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notatki (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_wycieczki TEXT, id_miejsca TEXT, tytul TEXT, zawartosc TEXT NOT NULL,
            typ_notatki TEXT CHECK(typ_notatki IN ('text', 'link', 'list')) DEFAULT 'text', data_utworzenia TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_wycieczki) REFERENCES wycieczka(id) ON DELETE CASCADE, FOREIGN KEY (id_miejsca) REFERENCES miejsca(numer_miejsca) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS czat_historia (
            id INTEGER PRIMARY KEY AUTOINCREMENT, uzytkownik TEXT, rola TEXT, tresc TEXT, data_utworzenia TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS uzytkownik_ustawienia (
            uzytkownik TEXT PRIMARY KEY, api_key TEXT, dostawca_ai TEXT DEFAULT 'Google Gemini', model_ai TEXT DEFAULT 'gemini-3.5-flash-lite'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS krok_wycieczki (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_wycieczki TEXT, krok_wycieczki TEXT, nazwa TEXT, wspolrzedne TEXT,
            okienko_zwiedzania TEXT, godzina_ewakuacji TEXT, czerwona_strefa_ostrzezenie TEXT, strefa_luzu_i_regeneracji TEXT,
            podsumowanie_taktyki TEXT, potencjal_meltdownu TEXT, strategie_meltdown TEXT, opis TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS czasy_dojazdu (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_kroku_z INTEGER, id_kroku_do INTEGER, czas_przejazdu TEXT, szacowany_czas_postoju INTEGER DEFAULT 0,
            FOREIGN KEY (id_kroku_z) REFERENCES krok_wycieczki(id) ON DELETE CASCADE, FOREIGN KEY (id_kroku_do) REFERENCES krok_wycieczki(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posilki_kroku (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_kroku INTEGER, rodzaj_posilku TEXT CHECK(rodzaj_posilku IN ('śniadanie', 'obiad', 'kolacja', 'przekąska')),
            miejsce TEXT CHECK(miejsce IN ('w domku', 'w kroku', 'restauracja', 'po drodze')), sugerowana_godzina TEXT, opis TEXT,
            FOREIGN KEY (id_kroku) REFERENCES krok_wycieczki(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS zakupy (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_wycieczki TEXT, id_kroku INTEGER, nazwa_produktu TEXT NOT NULL, ilosc TEXT, kupione INTEGER DEFAULT 0,
            FOREIGN KEY (id_wycieczki) REFERENCES wycieczka(id) ON DELETE CASCADE, FOREIGN KEY (id_kroku) REFERENCES krok_wycieczki(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute("PRAGMA table_info(zakupy)")
    if "id_wycieczki" not in [col[1] for col in cursor.fetchall()]:
        cursor.execute("ALTER TABLE zakupy ADD COLUMN id_wycieczki TEXT")

    cursor.execute('''
        UPDATE zakupy 
        SET id_wycieczki = (SELECT id_wycieczki FROM krok_wycieczki WHERE krok_wycieczki.id = zakupy.id_kroku)
        WHERE id_wycieczki IS NULL AND id_kroku IS NOT NULL
    ''')
    cursor.execute('CREATE TABLE IF NOT EXISTS zadania_dzieci_status (klucz_zadania TEXT PRIMARY KEY, ukonczone INTEGER DEFAULT 0)')
    cursor.execute('CREATE TABLE IF NOT EXISTS aktywna_wycieczka (id INTEGER PRIMARY KEY CHECK (id = 1), aktualne_id_wycieczki TEXT)')
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
                    str(row.get('numer miejsca', '')), str(row.get('nazwa', '')), str(row.get('nazwa angielska', '')), str(row.get('Opis', '')),
                    str(row.get('współrzędne', '')), str(row.get('typ', '')), str(row.get('czas dojazdu ze Stravros', '')), str(row.get('godziny otwarcia', '')),
                    str(row.get('najlepsza pora zwiedzania', '')), str(row.get('orientacyjny czas zwiedzania', '')), str(row.get('koszt zwiedzania dla rodziny 2+2', '')),
                    str(row.get('Konieczna akcja', '')), str(row.get('Zaplecze gastronomiczne', '')), str(row.get('Ile jedzenia', '')), str(row.get('Poziom trudności ADHD', '')),
                    str(row.get('Potencjał meltdownu', '')), str(row.get('Strategie na meltdown', '')), str(row.get('Ochrona przed słońcem', '')), str(row.get('Najlepiej połączyć z', '')),
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
            "1", "Mity i Oceaniczne Głębiny: Pałac w Knossos & Cretaquarium",
            "Wyprawa łącząca mityczną historię starożytnej Krety z podwodnym światem głębin w klimatyzowanym akwarium oraz relaksem nad jeziorem Kournas.",
            "Żelazna kontrola czasu rano w Knossos, obiad w Cretaquarium i popołudniowe wyciszenie nad jeziorem.",
            "10.0", "17:30", "06:00", "06:30", domyslna_data, "0.5h"
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

def przelacz_status_miejsca(numer_miejsca, aktualny_stan):
    nowy_stan = 0 if aktualny_stan else 1
    with get_db() as conn:
        conn.cursor().execute('UPDATE miejsca SET odwiedzone = ? WHERE numer_miejsca = ?', (nowy_stan, str(numer_miejsca)))
        conn.commit()
    return nowy_stan

def przelacz_status_wycieczki(id_wycieczki, aktualny_stan):
    nowy_stan = 0 if aktualny_stan else 1
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE wycieczka SET odbyta = ? WHERE id = ?', (nowy_stan, str(id_wycieczki)))
        cursor.execute('SELECT krok_wycieczki, nazwa FROM krok_wycieczki WHERE id_wycieczki = ?', (str(id_wycieczki),))
        kroki = cursor.fetchall()
        cursor.execute('SELECT numer_miejsca, nazwa FROM miejsca')
        wszystkie_miejsca = cursor.fetchall()
        
        for k_num, k_nazwa in kroki:
            if not k_nazwa or "domek" in k_nazwa.lower():
                continue
            k_clean = re.sub(r'[^\w\s]', '', str(k_nazwa).lower()).strip()
            for m_id, m_nazwa in wszystkie_miejsca:
                m_clean = re.sub(r'[^\w\s]', '', str(m_nazwa).lower()).strip()
                if str(k_num) == str(m_id) or m_clean in k_clean or k_clean in m_clean:
                    cursor.execute('UPDATE miejsca SET odwiedzone = ? WHERE numer_miejsca = ?', (nowy_stan, m_id))
        conn.commit()
    return nowy_stan

@st.dialog("Potwierdzenie statusu wycieczki")
def potwierdz_zakonczenie_wycieczki_dialog(wycieczka_id, tytul, stan_akt):
    akcja_txt = "cofnąć status ukończenia wycieczki (powiązane miejsca zostaną odznaczone)" if stan_akt else "oznaczyć wycieczkę jako ukończoną (powiązane miejsca zostaną automatycznie oznaczone jako odwiedzone)"
    st.markdown(f"Czy na pewno chcesz {akcja_txt} dla: **{tytul}**?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Tak", use_container_width=True):
            przelacz_status_wycieczki(wycieczka_id, stan_akt)
            st.session_state["flash_toast"] = "🏁 Zaktualizowano status wycieczki i miejsc!"
            st.rerun()
    with col2:
        if st.button("Anuluj", use_container_width=True):
            st.rerun()

@st.dialog("Potwierdzenie statusu miejsca")
def potwierdz_odwiedzenie_dialog(num_m, nazwa_m, stan_akt):
    akcja_txt = "cofnąć oznaczenie jako odwiedzone" if stan_akt else "oznaczyć jako odwiedzone"
    st.markdown(f"Czy na pewno chcesz {akcja_txt} miejsce: **{nazwa_m}**?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Tak", use_container_width=True):
            przelacz_status_miejsca(num_m, stan_akt)
            st.session_state["flash_toast"] = "✅ Zaktualizowano status miejsca!"
            st.rerun()
    with c2:
        if st.button("Anuluj", use_container_width=True):
            st.rerun()

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
            rynek_info, _ = pobierz_dane_rynku_dla_daty(planowana_data)
            if rynek_info:
                cursor.execute('SELECT id FROM krok_wycieczki WHERE id_wycieczki = ? AND (nazwa LIKE "%Rynek w Chanii%" OR nazwa LIKE "%Targ w Chanii%")', (str(id),))
                for r_id in cursor.fetchall():
                    cursor.execute('UPDATE krok_wycieczki SET nazwa = "Rynek w Chanii", wspolrzedne = ? WHERE id = ?', (rynek_info['coords'], r_id[0]))
        if szacowany_czas_ogarniania_rano is not None:
            cursor.execute('UPDATE wycieczka SET szacowany_czas_ogarniania_rano = ? WHERE id = ?', (szacowany_czas_ogarniania_rano, str(id)))
        if czas_wyjazdu is not None:
            cursor.execute('UPDATE wycieczka SET czas_wyjazdu = ? WHERE id = ?', (czas_wyjazdu, str(id)))
        conn.commit()
    
    przelicz_i_zsynchronizuj_wycieczke(str(id), force_wyjazd_str=czas_wyjazdu if czas_wyjazdu else None)
    return f"Wycieczka #{id} została zaktualizowana i przeliczona."

def dodaj_krok_wycieczki(id_wycieczki, nazwa_z_bazy="", okienko_zwiedzania="12:00 - 13:00", podsumowanie_taktyki="Brak"):
    miejsce_info = szukaj_miejsca_w_bazie(nazwa_z_bazy)
    if not miejsce_info:
        return f"⛔ BŁĄD: Nie znaleziono miejsca '{nazwa_z_bazy}' w lokalnej bazie miejsc!"

    # STRAŻNIK AuDHD
    bezpieczny, powod_odmowy = sprawdz_ryzyka_audhd_dla_kroku(id_wycieczki, miejsce_info['nazwa'], okienko_zwiedzania)
    if not bezpieczny:
        return powod_odmowy

    nazwa, wspolrzedne = miejsce_info['nazwa'], miejsce_info['wspolrzedne']
    godzina_ewakuacji = miejsce_info['konieczna_akcja'] or "Brak"
    czerwona_strefa = miejsce_info['ochrona_slonce'] or "Brak"
    strefa_luzu = miejsce_info['strategie_meltdown'] or "Spokojna strefa"
    opis = miejsce_info['opis'] or ""

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, krok_wycieczki, nazwa FROM krok_wycieczki WHERE id_wycieczki = ? ORDER BY CAST(krok_wycieczki AS INTEGER) ASC', (str(id_wycieczki),))
        istniejace = cursor.fetchall()

        if istniejace and ("domek" in istniejace[-1][2].lower() or "powrót" in istniejace[-1][2].lower()):
            cursor.execute('UPDATE krok_wycieczki SET krok_wycieczki = ? WHERE id = ?', (str(len(istniejace)), istniejace[-1][0]))
            target_krok_num = str(len(istniejace) - 1)
        else:
            target_krok_num = str(len(istniejace))

        cursor.execute('''
            INSERT INTO krok_wycieczki (id_wycieczki, krok_wycieczki, nazwa, wspolrzedne, okienko_zwiedzania, godzina_ewakuacji, czerwona_strefa_ostrzezenie, strefa_luzu_i_regeneracji, podsumowanie_taktyki, opis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (str(id_wycieczki), target_krok_num, str(nazwa), str(wspolrzedne), str(okienko_zwiedzania), str(godzina_ewakuacji), str(czerwona_strefa), str(strefa_luzu), str(podsumowanie_taktyki), str(opis)))
        conn.commit()
    
    przelicz_i_zsynchronizuj_wycieczke(str(id_wycieczki))
    return f"Pomyślnie pobrano z bazy i dodano miejsce '{nazwa}' do wycieczki #{id_wycieczki} oraz przeliczono harmonogram."

def wstaw_krok_specjalny(id_wycieczki, nazwa, wspolrzedne, okienko_def, strefa_luzu, taktyka, opis, pozycja="start", sprawdz_offset=False):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, krok_wycieczki, nazwa FROM krok_wycieczki WHERE id_wycieczki = ? ORDER BY CAST(krok_wycieczki AS INTEGER) ASC', (str(id_wycieczki),))
        istniejace = cursor.fetchall()
        
        has_sklep_rano = any("sklep" in str(r[2]).lower() and int(r[1]) == 1 for r in istniejace)
        has_sklep_wieczor = any("sklep" in str(r[2]).lower() and int(r[1]) == max(len(istniejace)-2, 1) for r in istniejace)

        if pozycja == "start":
            target_idx = (2 if has_sklep_rano else 1) if sprawdz_offset else 1
            for row in istniejace:
                if int(row[1]) >= target_idx:
                    cursor.execute('UPDATE krok_wycieczki SET krok_wycieczki = ? WHERE id = ?', (str(int(row[1]) + 1), row[0]))
            target_krok_num = target_idx
        else:
            if istniejace and ("domek" in istniejace[-1][2].lower() or "powrót" in istniejace[-1][2].lower()):
                offset = (2 if has_sklep_wieczor else 1) if sprawdz_offset else 1
                target_idx = len(istniejace) - offset
                for row in istniejace:
                    if int(row[1]) >= target_idx:
                        cursor.execute('UPDATE krok_wycieczki SET krok_wycieczki = ? WHERE id = ?', (str(int(row[1]) + 1), row[0]))
                target_krok_num = target_idx
            else:
                target_krok_num = len(istniejace)

        cursor.execute('''
            INSERT INTO krok_wycieczki (id_wycieczki, krok_wycieczki, nazwa, wspolrzedne, okienko_zwiedzania, godzina_ewakuacji, czerwona_strefa_ostrzezenie, strefa_luzu_i_regeneracji, podsumowanie_taktyki, opis)
            VALUES (?, ?, ?, ?, ?, 'Brak', 'Brak', ?, ?, ?)
        ''', (str(id_wycieczki), str(target_krok_num), nazwa, wspolrzedne, okienko_def, strefa_luzu, taktyka, opis))
        conn.commit()

    przelicz_i_zsynchronizuj_wycieczke(str(id_wycieczki))
    return f"Dodano '{nazwa}' i przeliczono harmonogram."

def dodaj_sklep_przy_domku_do_wycieczki(id_wycieczki, pozycja="koniec"):
    return wstaw_krok_specjalny(
        id_wycieczki=id_wycieczki, nazwa="Sklep przy domku", wspolrzedne=f"{SKLEP_LAT}, {SKLEP_LON}",
        okienko_def='07:00 - 07:20', strefa_luzu='Klimatyzowany sklep, szybkie zakupy', taktyka='Szybkie zakupy bez zwłoki',
        opis='', pozycja=pozycja, sprawdz_offset=False
    )

def dodaj_rynek_w_chanii_do_wycieczki(id_wycieczki, pozycja="start"):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT planowana_data FROM wycieczka WHERE id = ?', (str(id_wycieczki),))
        row_w = cursor.fetchone()
        plan_data = row_w[0] if row_w and row_w[0] else date.today().strftime("%Y-%m-%d")

    rynek_info, _ = pobierz_dane_rynku_dla_daty(plan_data)
    if not rynek_info:
        return "Dzisiaj w Chanii nie ma targu miejskiego (Laiki)."

    return wstaw_krok_specjalny(
        id_wycieczki=id_wycieczki, nazwa="Rynek w Chanii", wspolrzedne=rynek_info['coords'],
        okienko_def='08:00 - 08:35', strefa_luzu='Gwarny targ na świeżym powietrzu', taktyka='Lokalne owoce, oliwki i sery',
        opis='', pozycja=pozycja, sprawdz_offset=True
    )

def edytuj_krok_wycieczki(id_wycieczki, krok_wycieczki, nazwa=None, wspolrzedne=None, okienko_zwiedzania=None, 
                          godzina_ewakuacji=None, czerwona_strefa_ostrzezenie=None, strefa_luzu_i_regeneracji=None, 
                          podsumowanie_taktyki=None, opis=None):
    with get_db() as conn:
        cursor = conn.cursor()
        res = znajdz_id_kroku_w_db(cursor, id_wycieczki, krok_wycieczki)
        if not res:
            return f"Nie znaleziono kroku '{krok_wycieczki}' w wycieczce #{id_wycieczki}."
        krok_id, stary_nazwa = res[0], res[1]
        
        # STRAŻNIK AuDHD przy edycji godzin
        if okienko_zwiedzania:
            bezpieczny, powod_odmowy = sprawdz_ryzyka_audhd_dla_kroku(id_wycieczki, nazwa or stary_nazwa, okienko_zwiedzania)
            if not bezpieczny:
                return powod_odmowy

        pola = {
            "nazwa": nazwa, "wspolrzedne": wspolrzedne, "okienko_zwiedzania": okienko_zwiedzania,
            "godzina_ewakuacji": godzina_ewakuacji, "czerwona_strefa_ostrzezenie": czerwona_strefa_ostrzezenie,
            "strefa_luzu_i_regeneracji": strefa_luzu_i_regeneracji, "podsumowanie_taktyki": podsumowanie_taktyki, "opis": opis
        }
        for col, val in pola.items():
            if val is not None:
                cursor.execute(f'UPDATE krok_wycieczki SET {col} = ? WHERE id = ?', (val, krok_id))
        conn.commit()
    
    przelicz_i_zsynchronizuj_wycieczke(str(id_wycieczki))
    return f"Zaktualizowano krok i automatycznie przeliczono godziny całej wycieczki #{id_wycieczki}."

def usun_krok_wycieczki(id_wycieczki, krok_wycieczki):
    with get_db() as conn:
        cursor = conn.cursor()
        res = znajdz_id_kroku_w_db(cursor, id_wycieczki, krok_wycieczki)
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
    except:
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
        except:
            pass

    dopasowana_godzina, min_diff = None, 999
    for h in hourly_list:
        try:
            diff = abs(int(h.get('time', '0')) // 100 - target_hour)
            if diff < min_diff:
                min_diff, dopasowana_godzina = diff, h
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

cretai_tools = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="szukaj_miejsca_w_bazie",
                description="Wyszukuje miejsce WYŁĄCZNIE w lokalnej bazie danych miejsc po nazwie. Zwraca szczegóły i współrzędne.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "nazwa_zapytania": types.Schema(type=types.Type.STRING, description="Nazwa miejsca, np. 'Spinalonga', 'Knossos'"),
                    },
                    required=["nazwa_zapytania"]
                ),
            ),
            types.FunctionDeclaration(
                name="sprawdz_pogode",
                description="Pobiera prognozę pogody (temperaturę, odczuwalną, wiatr, indeks UV) dla podanych współrzędnych i daty.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "wspolrzedne": types.Schema(type=types.Type.STRING, description="Koordynaty np. '35.2980, 25.1631'"),
                        "planowana_data": types.Schema(type=types.Type.STRING, description="Data w formacie RRRR-MM-DD"),
                        "okienko_czasowe": types.Schema(type=types.Type.STRING, description="Okienko np. '12:00 - 14:00'"),
                    },
                    required=["wspolrzedne", "planowana_data"]
                ),
            ),
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
                        "planowana_data": types.Schema(type=types.Type.STRING, description="RRRR-MM-DD"),
                        "czas_wyjazdu": types.Schema(type=types.Type.STRING, description="Godzina wyjazdu, np. '06:30'"),
                    },
                    required=["id"]
                ),
            ),
            types.FunctionDeclaration(
                name="dodaj_krok_wycieczki",
                description="Dodaje miejsce z lokalnej bazy miejsc do wycieczki po jego nazwie z bazy.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                        "nazwa_z_bazy": types.Schema(type=types.Type.STRING, description="Dokładna nazwa miejsca z bazy miejsc (np. 'Spinalonga')"),
                        "okienko_zwiedzania": types.Schema(type=types.Type.STRING, description="Okienko czasu np. '13:00 - 14:30'"),
                        "podsumowanie_taktyki": types.Schema(type=types.Type.STRING, description="Taktyka"),
                    },
                    required=["id_wycieczki", "nazwa_z_bazy"]
                ),
            ),
            types.FunctionDeclaration(
                name="edytuj_krok_wycieczki",
                description="Edytuje parametry kroku wycieczki i przelicza godziny trasy.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                        "krok_wycieczki": types.Schema(type=types.Type.STRING, description="ID kroku, numer lub nazwa"),
                        "okienko_zwiedzania": types.Schema(type=types.Type.STRING, description="Okienko np. '10:00 - 13:00'"),
                    },
                    required=["id_wycieczki", "krok_wycieczki"]
                ),
            ),
            types.FunctionDeclaration(
                name="usun_krok_wycieczki",
                description="Usuwa wskazany krok z wycieczki.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
                        "krok_wycieczki": types.Schema(type=types.Type.STRING, description="ID z bazy, numer lub nazwa"),
                    },
                    required=["id_wycieczki", "krok_wycieczki"]
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
                        "id_kroku": types.Schema(type=types.Type.STRING, description="ID kroku lub None"),
                        "ilosc": types.Schema(type=types.Type.STRING, description="Ilość"),
                    },
                    required=["id_wycieczki", "nazwa_produktu"]
                ),
            )
        ]
    )
]

NARZEDZIA_DISPATCHER = {
    "szukaj_miejsca_w_bazie": lambda args: str(szukaj_miejsca_w_bazie(**args)) if szukaj_miejsca_w_bazie(**args) else "Brak miejsca w bazie.",
    "sprawdz_pogode": lambda args: str(pobierz_szczegoly_pogody_dla_godziny(**args)),
    "dodaj_notatke": lambda args: dodaj_notatke(**args),
    "edytuj_wycieczke": lambda args: edytuj_wycieczke(**args),
    "dodaj_krok_wycieczki": lambda args: dodaj_krok_wycieczki(**args),
    "edytuj_krok_wycieczki": lambda args: edytuj_krok_wycieczki(**args),
    "usun_krok_wycieczki": lambda args: usun_krok_wycieczki(**args),
    "dodaj_produkt_zakupow": lambda args: dodaj_produkt_zakupow(**args),
}

def wykonaj_narzedzie_bazy(call_name, args):
    handler = NARZEDZIA_DISPATCHER.get(call_name)
    return handler(args) if handler else "Wykonano."

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
    return [czysta for l in re.split(r'(?:[\r\n;]+|(?:\s*\d+[\.\)]\s+))', s) if (czysta := re.sub(r'^[\s\*\-\•\d\.\)]+', '', l.strip()).strip())]

def pobierz_grupy_zadan_dla_wycieczki(wycieczka_id, kroki_df, df_miejsca_ref):
    grupy = [("🚗 Zadania na drogę", [
        "Wypatruj przez okno kóz i policz, ile ich zobaczysz na zboczach gór.",
        "Znajdź najciekawszy kształt chmury podczas jazdy samochodem.",
        "Kto pierwszy zauważy morze na horyzoncie, zdobywa punkt nawigatora!"
    ], f"w_{wycieczka_id}_droga")]

    miejsca_dict = {}
    if not df_miejsca_ref.empty:
        for _, mr in df_miejsca_ref.iterrows():
            miejsca_dict[str(mr['numer_miejsca'])] = str(mr.get('zadania_dla_dzieci', ''))
            miejsca_dict[str(mr['nazwa']).lower()] = str(mr.get('zadania_dla_dzieci', ''))

    for _, k in kroki_df.iterrows():
        nazwa, knum, k_id = str(k['nazwa']), str(k['krok_wycieczki']), str(k['id'])
        if "domek" in nazwa.lower():
            continue
        
        raw_z = miejsca_dict.get(knum) or miejsca_dict.get(nazwa.lower(), "")
        zad_miejsca = sparsuj_liste_zadan(raw_z)
        if zad_miejsca:
            grupy.append((f"📍 {nazwa}", list(dict.fromkeys(zad_miejsca)), f"w_{wycieczka_id}_krok_{k_id}"))

    return grupy

def pobierz_ustawienia_z_db(uzytkownik):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT api_key, dostawca_ai, model_ai FROM uzytkownik_ustawienia WHERE uzytkownik = ?', (uzytkownik,))
        res = cursor.fetchone()
    return (res[0] or "", res[1] or "Google Gemini", res[2] or "gemini-3.5-flash-lite") if res else ("", "Google Gemini", "gemini-3.5-flash-lite")

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
    dostepni_uzytkownicy = ["Magda", "Michał", "Jurek", "Julia"]
    
    # Zapamiętywanie profilu w adresie URL telefonu
    domyslny_user = "Magda"
    if "user" in st.query_params and st.query_params["user"] in dostepni_uzytkownicy:
        domyslny_user = st.query_params["user"]
    elif "last_selected_user" in st.session_state and st.session_state["last_selected_user"] in dostepni_uzytkownicy:
        domyslny_user = st.session_state["last_selected_user"]

    index_profilu = dostepni_uzytkownicy.index(domyslny_user)
    
    aktualny_uzytkownik = st.selectbox("Wybierz swój profil", options=dostepni_uzytkownicy, index=index_profilu, key="sb_user_profile")
    
    if st.query_params.get("user") != aktualny_uzytkownik:
        st.query_params["user"] = aktualny_uzytkownik
        st.session_state["last_selected_user"] = aktualny_uzytkownik

    st.markdown("---")
    
    st.header("⚙️ Ustawienia Asystenta")
    zapisany_klucz, zapisany_dostawca, zapisany_model = pobierz_ustawienia_z_db(aktualny_uzytkownik)
    dostawcy_ai = ["Google Gemini", "Anthropic Claude"]
    dostawca_index = dostawcy_ai.index(zapisany_dostawca) if zapisany_dostawca in dostawcy_ai else 0
    wybrany_dostawca = st.selectbox("Dostawca AI", options=dostawcy_ai, index=dostawca_index)
    
    dostepne_modele = ["gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.6-pro"] if wybrany_dostawca == "Google Gemini" else ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"]
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

def renderuj_podsumowanie_pogody_wycieczki(kroki_df, planowana_data):
    if not planowana_data or not str(planowana_data).strip() or kroki_df.empty:
        return

    ostrzezenia, max_temp, min_temp, opis_pogody_zbiorczy = [], -99, 99, set()
    for _, k in kroki_df.iterrows():
        lat, lon = sparsuj_wspolrzedne(k['wspolrzedne'])
        if lat is not None and lon is not None:
            prognoza = pobierz_prognoze_pogody(lat, lon, str(planowana_data))
            if prognoza and 'hourly' in prognoza:
                for h in prognoza['hourly']:
                    t = int(h.get('tempC', 20))
                    max_temp = max(max_temp, t)
                    min_temp = min(min_temp, t)
                    opis_pogody_zbiorczy.add(h.get('weatherDesc', [{}])[0].get('value', '').lower())

    for desc in opis_pogody_zbiorczy:
        if any(w in desc for w in ['rain', 'deszcz', 'shower']):
            ostrzezenia.append("🌧️ Prognozowane opady deszczu na trasie!")
        if any(w in desc for w in ['storm', 'thunder', 'burza']):
            ostrzezenia.append("⚡ Ryzyko burz na trasie wycieczki!")

    if max_temp >= 32:
        ostrzezenia.append(f"🔥 Ekstremalny upał! Maksymalna temperatura sięgnie {max_temp}°C.")

    st.markdown(f'<div class="section-unified-header">🌤️ Pogoda na trasie</div><div style="font-size: 10pt; color: #2B2118; font-weight: 700; margin-bottom: 10px;">Temperatura: <b>{min_temp}°C do {max_temp}°C</b></div>', unsafe_allow_html=True)
    for ost in ostrzezenia:
        st.markdown(f'<div style="color: #DC5050; font-weight: 800; font-size: 9pt; margin-top: 2px;">{ost}</div>', unsafe_allow_html=True)

def pobierz_historie_czatu_z_db(uzytkownik):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT rola, tresc FROM czat_historia WHERE uzytkownik = ? ORDER BY id ASC', (uzytkownik,))
        rows = cursor.fetchall()
    return [{"role": rola, "content": tresc, "raw_content": types.Content(role=rola, parts=[types.Part.from_text(text=tresc)])} for rola, tresc in rows]

def zapisz_wiadomosc_w_db(uzytkownik, rola, tresc):
    with get_db() as conn:
        conn.cursor().execute('INSERT INTO czat_historia (uzytkownik, rola, tresc) VALUES (?, ?, ?)', (uzytkownik, rola, tresc))
        conn.commit()

def wyczysc_historie_czatu_w_db(uzytkownik):
    with get_db() as conn:
        conn.cursor().execute('DELETE FROM czat_historia WHERE uzytkownik = ?', (uzytkownik,))
        conn.commit()

def pobierz_notatki(id_wycieczki=None, id_miejsca=None):
    with get_db() as conn:
        if id_wycieczki:
            return pd.read_sql('SELECT * FROM notatki WHERE id_wycieczki = ?', conn, params=(str(id_wycieczki),))
        elif id_miejsca:
            return pd.read_sql('SELECT * FROM notatki WHERE id_miejsca = ?', conn, params=(str(id_miejsca),))
    return pd.DataFrame()

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

def pobierz_skrocone_opcje_wycieczek(pokaz_ukonczone=False):
    with get_db() as conn:
        query = 'SELECT id, tytul_wycieczki, odbyta FROM wycieczka'
        if not pokaz_ukonczone:
            query += ' WHERE odbyta = 0'
        df_w = pd.read_sql(query, conn)
    if df_w.empty:
        return []
    opcje = []
    for _, row in df_w.iterrows():
        wid, pelny, odbyta = str(row['id']), str(row['tytul_wycieczki']), bool(row.get('odbyta', 0))
        skrocony = pelny.split(':')[0] if ':' in pelny else pelny
        if len(skrocony) > 35:
            skrocony = skrocony[:35] + "..."
        opcje.append(f"{wid}. {skrocony} (ukończona)" if odbyta else f"{wid}. {skrocony}")
    return opcje

def pobierz_wycieczki_dla_miejsca(numer_miejsca, nazwa_miejsca):
    with get_db() as conn:
        query = '''
            SELECT DISTINCT w.id, w.tytul_wycieczki, k.krok_wycieczki, k.okienko_zwiedzania
            FROM wycieczka w
            JOIN krok_wycieczki k ON w.id = k.id_wycieczki
            WHERE k.krok_wycieczki = ? OR k.nazwa LIKE ? OR ? LIKE ('%' || k.nazwa || '%')
        '''
        return pd.read_sql(query, conn, params=(str(numer_miejsca), f"%{nazwa_miejsca}%", str(nazwa_miejsca)))

def wczytaj_kontekst_zewnetrzny(aktywne_id_wycieczki="1"):
    tekst = f"CretAi Assistant • Kreta\nBaza/Domek: {DOMEK_LAT}, {DOMEK_LON} | Sklep: {SKLEP_LAT}, {SKLEP_LON}\n"
    tekst += wczytaj_pliki_regul()
    
    with get_db() as conn:
        try:
            wycieczka_df = pd.read_sql('SELECT id, tytul_wycieczki, planowana_data, szacowany_czas_ogarniania_rano, czas_wyjazdu FROM wycieczka WHERE id = ?', conn, params=(str(aktywne_id_wycieczki),))
            kroki_df = pd.read_sql('SELECT id, krok_wycieczki, nazwa, okienko_zwiedzania FROM krok_wycieczki WHERE id_wycieczki = ? ORDER BY CAST(krok_wycieczki AS INTEGER) ASC', conn, params=(str(aktywne_id_wycieczki),))
            miejsca_df = pd.read_sql('SELECT numer_miejsca, nazwa FROM miejsca', conn)
        except:
            wycieczka_df, kroki_df, miejsca_df = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    if not wycieczka_df.empty:
        w = wycieczka_df.iloc[0]
        tekst += f"\nAktualna Wycieczka #{w['id']}: {w['tytul_wycieczki']} (Data: {w.get('planowana_data', '')}, Wyjazd: {w.get('czas_wyjazdu', '')})\nKroki:\n"
    if not kroki_df.empty:
        for _, k in kroki_df.iterrows():
            tekst += f"- ID DB:{k['id']} | #{k['krok_wycieczki']} {k['nazwa']} ({k['okienko_zwiedzania']})\n"
            
    if not miejsca_df.empty:
        tekst += "\nDOSTĘPNA BAZA MIEJSC (nazwy do dodania przez narzędzia):\n"
        for _, m in miejsca_df.iterrows():
            tekst += f"- #{m['numer_miejsca']} {m['nazwa']}\n"
    return tekst

def dodaj_marker_domku(m):
    domek_icon_html = '<div style="background-color:#2E251E;color:#FFFFFF;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:14px;border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.2);">🏠</div>'
    folium.Marker([DOMEK_LAT, DOMEK_LON], icon=folium.DivIcon(html=domek_icon_html, icon_size=(28, 28), icon_anchor=(14, 14)), tooltip="Nasz Domek").add_to(m)

# --- BEZPIECZNY LOKALNY PARSER INTENTÓW ---
def sprobuj_wykonac_komende_lokalnie(prompt, id_wycieczki):
    p = prompt.strip().lower()
    m_zakup = re.search(r'^(?:kup|kupić|dodaj do zakup[oó]w|dopisz)\s+([^,]+)', p)
    if m_zakup and not any(w in p for w in ["krok", "miejsce", "atrakcj", "godzin", "wyjazd", "start"]):
        prod = m_zakup.group(1).strip()
        dodaj_produkt_zakupow(id_wycieczki, prod)
        return f"⚡ Dodano **{prod}** do listy zakupów wycieczki."
    return None

def renderuj_globalny_czat_ai(uzytkownik, inline=False):
    if not inline:
        st.markdown('<div class="floating-ai-container">', unsafe_allow_html=True)
    with st.expander(f"💬 Asystent AI ({uzytkownik})", expanded=False):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"<div style='font-size: 8.5pt; font-weight: 800; padding-top: 6px;'>🧠 TRYB AuDHD • {uzytkownik}</div>", unsafe_allow_html=True)
        with col2:
            if st.button("🗑️ Czyść", key=f"btn_clear_{uzytkownik}_{'inline' if inline else 'float'}", use_container_width=True):
                wyczysc_historie_czatu_w_db(uzytkownik)
                st.session_state["flash_toast"] = "🗑️ Wyczyszczono czat."
                st.rerun()

        chat_historia_z_db = pobierz_historie_czatu_z_db(uzytkownik)
        chat_container = st.container(height=190)
        with chat_container:
            for message in chat_historia_z_db:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"] if isinstance(message["content"], str) else "")

        prompt = st.chat_input(f"Napisz np. 'wyjazd o 7:30', 'kup woda'...", key=f"chat_input_{uzytkownik}_{'inline' if inline else 'float'}")
        if prompt:
            zapisz_wiadomosc_w_db(uzytkownik, "user", prompt)
            akt_wyc_id = pobierz_aktywna_wycieczke_id()

            odpowiedz_lokalna = sprobuj_wykonac_komende_lokalnie(prompt, akt_wyc_id)

            if odpowiedz_lokalna:
                zapisz_wiadomosc_w_db(uzytkownik, "model", odpowiedz_lokalna)
                st.session_state["flash_toast"] = "⚡ Zaktualizowano listę zakupów!"
                st.rerun()

            if not api_key_input:
                st.warning("⚠️ Wprowadź klucz API w menu bocznym, aby korzystać z zaawansowanego doradcy AI.")
                if not inline:
                    st.markdown('</div>', unsafe_allow_html=True)
                return

            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)
                with st.chat_message("assistant"):
                    assistant_reply = ""
                    dzisiaj_str = date.today().strftime("%Y-%m-%d")
                    zewnetrzny_kontekst = wczytaj_kontekst_zewnetrzny(akt_wyc_id)
                    
                    system_prompt = f"""Jesteś inteligentnym planerem i strażnikiem AuDHD/ADHD na Krecie (CretAi).
Rozmawiasz z użytkownikiem, który ma na imię: {uzytkownik}.
Dzisiejsza data: {dzisiaj_str}.
{zewnetrzny_kontekst}

ZASADA OSOBOWEGO I DIREKTYWNEGO TONU:
Zwracaj się do użytkownika po imieniu w sposób bardzo personalny, dopasowany do jakości jego pomysłu:
- Na powitanie lub w normalnych wiadomościach używaj jego imienia (np. "Witaj {uzytkownik}", "Cześć {uzytkownik}").
- Gdy propozycja rodzica jest zła (narusza lekko zasady, np. zła pora, małe ryzyko): zwracaj się bezpośrednio (np. "To zły pomysł, {uzytkownik}").
- Gdy propozycja rodzica jest bardzo zła / katastrofalna dla dzieci z AuDHD (np. pełne słońce w upale 11:30-15:30, głód >4h, brak cienia): reaguj kategorycznie i ostrzegawczo (np. "To bardzo zły pomysł, {uzytkownik}").

ZASADA NACZELNA (STRAŻNIK AuDHD):
Zanim wykonasz JAKIEKOLWIEK działania na bazie danych (narzędzia CRUD), ZAWSZE sprawdź:
1. Upał i słońce w oknie 11:30–15:30 – zakaz planowania odsłoniętych ruin i miejsc bez cienia w tych godzinach!
2. Luki żywieniowe – zakaz przerw dłuższych niż 3.5h bez posiłku/przekąski.
3. Bufor poranny – minimalny czas w domku rano.
Jeśli którekolwiek z wymagań jest niespełnione, ODMÓW wykonania polecenia, wyjaśnij ryzyko fizjologiczne/sensoryczne dla dzieci i zaproponuj lepszą, bezpieczną alternatywę."""

                    try:
                        with st.status("🧭 Analizuję bezpieczeństwo i trasę AuDHD...", expanded=False) as status:
                            if wybrany_dostawca == "Google Gemini":
                                client = genai.Client(api_key=api_key_input)
                                contents = [
                                    types.Content(
                                        role="model" if m["role"] in ["assistant", "model"] else "user",
                                        parts=[types.Part.from_text(text=m["content"])]
                                    )
                                    for m in chat_historia_z_db[-4:]
                                ]
                                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=prompt)]))
                                executed_actions = []

                                config = types.GenerateContentConfig(
                                    tools=cretai_tools,
                                    system_instruction=system_prompt,
                                    temperature=0.1,
                                    max_output_tokens=1024
                                )

                                for loop_idx in range(3):
                                    try:
                                        response = client.models.generate_content(
                                            model=wybrany_model,
                                            contents=contents,
                                            config=config
                                        )
                                    except Exception as api_err:
                                        if "429" in str(api_err):
                                            py_time.sleep(2.0)
                                            response = client.models.generate_content(
                                                model=wybrany_model,
                                                contents=contents,
                                                config=config
                                            )
                                        else:
                                            raise api_err

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
                                            call_name, args = call.name, call.args
                                            wynik_bazy = wykonaj_narzedzie_bazy(call_name, args)
                                            executed_actions.append(wynik_bazy)
                                            function_responses_parts.append(
                                                types.Part.from_function_response(name=call_name, response={"result": str(wynik_bazy)})
                                            )
                                        contents.append(types.Content(role="user", parts=function_responses_parts))
                                        py_time.sleep(0.5)
                                    else:
                                        if candidate and candidate.content and candidate.content.parts:
                                            assistant_reply = "".join([p_text.text for p_text in candidate.content.parts if hasattr(p_text, "text") and p_text.text])
                                        elif hasattr(response, 'text') and response.text:
                                            assistant_reply = response.text
                                        break
                                
                                if not assistant_reply.strip() and executed_actions:
                                    assistant_reply = f"✅ **Zaktualizowano plan w bazie dla Ciebie, {uzytkownik}:**\n* " + "\n* ".join(executed_actions)

                            else:
                                client_c = anthropic.Anthropic(api_key=api_key_input)
                                resp = client_c.messages.create(
                                    model=wybrany_model,
                                    max_tokens=1024,
                                    system=system_prompt,
                                    messages=[{"role": "user", "content": prompt}]
                                )
                                assistant_reply = "".join([b.text for b in resp.content if hasattr(b, "text")])

                            status.update(label="✅ Gotowe!", state="complete")

                        if not assistant_reply:
                            assistant_reply = f"✅ Zrealizowano, {uzytkownik}."

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
if "show_visited_places" not in st.session_state:
    st.session_state.show_visited_places = False
if "show_completed_trips" not in st.session_state:
    st.session_state.show_completed_trips = False

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

def render_timeline_row_simple(time_start, badge_icon, badge_class, title, desc, nav_btn_html="", time_end=""):
    time_end_markup = f'<span class="timeline-time-end">{time_end}</span>' if time_end else ''
    return (
        f'<div class="timeline-step-row-wrapper">'
        f'<div class="timeline-row-frameless">'
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

def renderuj_karte_wycieczki(wycieczka_id, df_wszystkie_miejsca_ref, pokaz_mape=False, pokaz_pogode=False):
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
    
    st.markdown(f'<div class="trip-top-section"><div class="trip-main-title">{tytul_wycieczki}</div></div>', unsafe_allow_html=True)
    if st.button(f"📅 Planowana data: {dzien_val} {miesiac_val} ({dzien_tyg_val}) ▾", key="btn_date_picker", use_container_width=True):
        edit_date_dialog(wycieczka_id, parsed_date)

    if pokaz_pogode:
        renderuj_podsumowanie_pogody_wycieczki(kroki_df, planowana_data_val)

    if pd.notna(w_gen.get('calosciowy_opis_wycieczki')) and str(w_gen['calosciowy_opis_wycieczki']).strip():
        st.markdown(f"""
        <div style="margin-top: 4px; margin-bottom: 10px;">
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
        st.markdown('<div style="text-align: center; font-size: 7.5pt; font-weight: 800; color: #8C5338; text-transform: uppercase; margin-bottom: 3px;">⏰ Pobudka</div>', unsafe_allow_html=True)
        with st.popover(pobudka_val, use_container_width=True):
            g_pob = sparsuj_godzine_minuty(pobudka_val) or (6, 0)
            t_pob = st.time_input("Nowa godzina pobudki", value=time(g_pob[0], g_pob[1]), step=300, key=f"ti_pob_{wycieczka_id}")
            if st.button("💾 Zapisz", key=f"btn_save_pob_{wycieczka_id}", use_container_width=True):
                przelicz_i_zsynchronizuj_wycieczke(str(wycieczka_id), force_pobudka_str=t_pob.strftime("%H:%M"))
                st.session_state["flash_toast"] = "⏱️ Zaktualizowano godzinę pobudki!"
                st.rerun()

    with col_log2:
        st.markdown('<div style="text-align: center; font-size: 7.5pt; font-weight: 800; color: #8C5338; text-transform: uppercase; margin-bottom: 3px;">🎒 Wyjazd za</div>', unsafe_allow_html=True)
        with st.popover(ogarnianie_val, use_container_width=True):
            nowy_czas_ogarniania = st.text_input("Szacowany czas rano", value=ogarnianie_val, key=f"ti_ogarnianie_{wycieczka_id}")
            if st.button("💾 Zapisz", key=f"btn_save_ogarnianie_{wycieczka_id}", use_container_width=True):
                edytuj_wycieczke(wycieczka_id, szacowany_czas_ogarniania_rano=nowy_czas_ogarniania)
                st.session_state["flash_toast"] = "⏱️ Zaktualizowano czas do wyjazdu!"
                st.rerun()

    with col_log3:
        st.markdown('<div style="text-align: center; font-size: 7.5pt; font-weight: 800; color: #8C5338; text-transform: uppercase; margin-bottom: 3px;">🏠 Powrót</div>', unsafe_allow_html=True)
        with st.popover(powrot_val, use_container_width=True):
            g_pow = sparsuj_godzine_minuty(powrot_val) or (17, 33)
            t_pow = st.time_input("Nowa godzina powrotu", value=time(g_pow[0], g_pow[1]), step=300, key=f"ti_pow_{wycieczka_id}")
            if st.button("💾 Zapisz", key=f"btn_save_pow_{wycieczka_id}", use_container_width=True):
                przelicz_i_zsynchronizuj_wycieczke(str(wycieczka_id), force_powrot_str=t_pow.strftime("%H:%M"))
                st.session_state["flash_toast"] = "⏱️ Zaktualizowano godzinę powrotu!"
                st.rerun()

    if pd.notna(w_gen.get('calosciowa_taktyka_dnia')) and str(w_gen['calosciowa_taktyka_dnia']).strip():
        st.markdown('<div class="section-unified-header">🧠 Taktyka</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <details class="overview-details-card" style="margin-top: 4px;">
            <summary style="font-weight: normal !important;">🧠 Taktyka dnia</summary>
            <div style="margin-top: 8px; border-top: 1px solid #D1C7AE; padding-top: 6px;">
                <div class="section-body-text" style="margin-bottom: 0;">{w_gen['calosciowa_taktyka_dnia']}</div>
            </div>
        </details>
        """, unsafe_allow_html=True)

    st.markdown('<div class="section-unified-header">🗺️ Plan na dzień</div>', unsafe_allow_html=True)

    total_steps = len(kroki_df)
    timeline_full_html = ['<div class="timeline-master-container">', '<div class="timeline-master-continuous-line"></div>']
    
    baza_miejsc_dict = {}
    if not df_wszystkie_miejsca_ref.empty:
        for _, mrow in df_wszystkie_miejsca_ref.iterrows():
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
        
        is_first, is_last = (idx == 0), (idx == total_steps - 1)
        lat_parsed, lon_parsed = sparsuj_wspolrzedne(wspolrzedne)
        nav_btn_html = f'<a href="https://www.google.com/maps/search/?api=1&query={coords_clean}" target="_blank" class="timeline-nav-btn" title="Nawiguj"><span>🧭</span><span>Nawiguj</span></a>' if (lat_parsed is not None and lon_parsed is not None) else ""

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
        elif any(w in nazwa_lower for w in ["obiad", "lunch", "jedzenie", "przekąska"]):
            detected_icon = "🍴"
        elif "plaż" in nazwa_lower or "beach" in nazwa_lower:
            detected_icon = "🏖️"
        else:
            matched_typ = baza_miejsc_dict.get(krok_num)
            if not matched_typ:
                for k_name_db, k_typ_db in baza_miejsc_dict.items():
                    if len(k_name_db) > 3 and k_name_db in nazwa_lower:
                        matched_typ = k_typ_db
                        break
            kat = kategoryzuj_typ(matched_typ) if matched_typ else kategoryzuj_typ(nazwa_lower)
            detected_icon = pobierz_ikonke_kategorii(kat)

        badge_symbol = detected_icon if detected_icon is not None else (krok_num if (krok_num and krok_num != "0") else str(idx))
        is_in_places_db = ("numer_miejsca" in k and pd.notna(k.get("numer_miejsca"))) or (krok_num in baza_miejsc_dict)
        is_custom_flat = not is_first and not is_last and (
            not is_in_places_db or 
            any(w in nazwa_lower for w in ["sklep", "market", "zakup", "apteka", "postój", "parking", "kawa", "cafe", "toaleta", "punkt widokowy", "widok", "rynek", "targ"])
        )

        df_pos_kroku = posilki_wszystkie_df[posilki_wszystkie_df['id_kroku'] == krok_row_id]
        posilki_tekst = formatuj_posilki_kroku(df_pos_kroku)

        if is_first:
            timeline_full_html.append(render_timeline_row_simple(godzina_start, "⏰", "badge-pobudka", "Pobudka", posilki_tekst if posilki_tekst else f"Czas do wyjazdu: {ogarnianie_val}"))
            godzina_wyjazdu_wyswietl = godzina_koniec if godzina_koniec else wyjazd_val
            timeline_full_html.append(render_timeline_row_simple(godzina_wyjazdu_wyswietl, "🚗", "badge-wyjazd", "Wyjazd", ""))

        elif is_last:
            nav_domek = f'<a href="https://www.google.com/maps/search/?api=1&query={DOMEK_LAT},{DOMEK_LON}" target="_blank" class="timeline-nav-btn" title="Nawiguj"><span>🧭</span><span>Nawiguj</span></a>'
            timeline_full_html.append(render_timeline_row_simple(godzina_start, "🏠", "badge-powrot", "Powrót do domku", posilki_tekst if posilki_tekst else "Wypoczynek i relaks", nav_btn_html=nav_domek))
        
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

            timeline_full_html.append(render_timeline_row_simple(
                time_start=godzina_start,
                badge_icon=badge_symbol,
                badge_class="badge-pobudka",
                title=tytul_kroku_display,
                desc=opis_kroku_cust,
                nav_btn_html=nav_btn_html,
                time_end=f"do {godzina_koniec}" if (godzina_koniec and godzina_koniec != godzina_start) else ""
            ))

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

            details_inner_html = (
                f'<div class="step-details-card">'
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
                f'<div class="timeline-item-title">{nazwa}</div>'
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
        has_shop_start = any("sklep" in str(r['nazwa']).lower() and int(r['krok_wycieczki']) == 1 for _, r in kroki_df.iterrows())
        has_shop_end = any("sklep" in str(r['nazwa']).lower() and int(r['krok_wycieczki']) == max(len(kroki_df)-2, 1) for _, r in kroki_df.iterrows())
        has_market_start = any(("rynek" in str(r['nazwa']).lower() or "targ" in str(r['nazwa']).lower()) and int(r['krok_wycieczki']) <= 2 for _, r in kroki_df.iterrows())
        has_market_end = any(("rynek" in str(r['nazwa']).lower() or "targ" in str(r['nazwa']).lower()) and int(r['krok_wycieczki']) >= max(len(kroki_df)-3, 1) for _, r in kroki_df.iterrows())

        rynek_dla_daty, _ = pobierz_dane_rynku_dla_daty(planowana_data_val)
        rynek_czynny = (rynek_dla_daty is not None)

        col_qs_am, col_qs_pm = st.columns(2)
        with col_qs_am:
            st.markdown("<div style='font-size: 7.5pt; font-weight: 800; color: #5D7A60; text-transform: uppercase; margin-bottom: 4px;'>🌅 Po wyjeździe</div>", unsafe_allow_html=True)
            if st.button("✓ Sklep dodany" if has_shop_start else "🛒 Sklep rano", key=f"btn_add_shop_am_{wycieczka_id}", use_container_width=True, disabled=has_shop_start):
                dodaj_sklep_przy_domku_do_wycieczki(wycieczka_id, pozycja="start")
                st.session_state["flash_toast"] = "🌅 Dodano Sklep po wyjeździe!"
                st.rerun()
            
            btn_market_am_label = "✓ Rynek dodany" if has_market_start else ("🛒 Rynek rano" if rynek_czynny else "🛒 Rynek (nieczynny)")
            if st.button(btn_market_am_label, key=f"btn_add_market_am_{wycieczka_id}", use_container_width=True, disabled=(has_market_start or not rynek_czynny), help=f"Lokalizacja: {rynek_dla_daty['opis_miejsca']}" if rynek_czynny else "Dziś brak targu w Chanii"):
                dodaj_rynek_w_chanii_do_wycieczki(wycieczka_id, pozycja="start")
                st.session_state["flash_toast"] = f"🌅 Dodano Rynek w Chanii ({rynek_dla_daty['dzien_pl']})!"
                st.rerun()

        with col_qs_pm:
            st.markdown("<div style='font-size: 7.5pt; font-weight: 800; color: #8C5338; text-transform: uppercase; margin-bottom: 4px;'>🌇 Przed powrotem</div>", unsafe_allow_html=True)
            if st.button("✓ Sklep dodany" if has_shop_end else "🛒 Sklep powrót", key=f"btn_add_shop_pm_{wycieczka_id}", use_container_width=True, disabled=has_shop_end):
                dodaj_sklep_przy_domku_do_wycieczki(wycieczka_id, pozycja="koniec")
                st.session_state["flash_toast"] = "🌇 Dodano Sklep przed powrotem!"
                st.rerun()
            
            btn_market_pm_label = "✓ Rynek dodany" if has_market_end else ("🛒 Rynek powrót" if rynek_czynny else "🛒 Rynek (nieczynny)")
            if st.button(btn_market_pm_label, key=f"btn_add_market_pm_{wycieczka_id}", use_container_width=True, disabled=(has_market_end or not rynek_czynny), help=f"Lokalizacja: {rynek_dla_daty['opis_miejsca']}" if rynek_czynny else "Dziś brak targu w Chanii"):
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
            st.markdown("<div style='font-size: 8.5pt; color: #8C827A; font-style: italic;'>Brak zadań dla tej wycieczki.</div>", unsafe_allow_html=True)

    czy_odbyta = bool(w_gen.get('odbyta', 0))
    st.markdown('<div class="section-unified-header">🏁 Status Wycieczki</div>', unsafe_allow_html=True)
    if st.button("✓ Wycieczka ukończona (cofnij)" if czy_odbyta else "🏁 Oznacz całą wycieczkę jako ukończoną", key=f"btn_finish_trip_{wycieczka_id}", use_container_width=True):
        potwierdz_zakonczenie_wycieczki_dialog(wycieczka_id, tytul_wycieczki, czy_odbyta)

    st.markdown('<div class="section-unified-header">🤖 Asystent AI</div>', unsafe_allow_html=True)
    renderuj_globalny_czat_ai(aktualny_uzytkownik, inline=True)

if st.session_state.active_tab == "route":
    render_adventure_header("CretAi • Aktualna Wycieczka")
    renderuj_karte_wycieczki(pobierz_aktywna_wycieczke_id(), df_miejsca, pokaz_mape=False, pokaz_pogode=True)

elif st.session_state.active_tab == "map":
    render_adventure_header("CretAi • Nasze wycieczki")
    
    st.session_state.show_completed_trips = st.checkbox("Pokaż ukończone wycieczki", value=st.session_state.show_completed_trips)
    wycieczki_options_filtrowane = pobierz_skrocone_opcje_wycieczek(pokaz_ukonczone=st.session_state.show_completed_trips)
    opcje_wycieczek_lista = [None] + wycieczki_options_filtrowane
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
            kolor = "#A8A29E" if bool(row.get('odwiedzone', 0)) else pobierz_kolor_kategorii(kategoryzuj_typ(row.get('typ')))
            map_coords_lookup[(round(lat, 4), round(lon, 4))] = (num, nazwa)
            
            icon_html = f'<div style="background-color:{kolor};color:white;border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:900;border:2px solid white;cursor:pointer;box-shadow:0 2px 5px rgba(0,0,0,0.2);">{num}</div>'
            folium.Marker([lat, lon], icon=folium.DivIcon(html=icon_html, icon_size=(24, 24), icon_anchor=(12, 12)), tooltip=f"#{num} {nazwa}").add_to(m_all)
            
    map_out = st_folium(m_all, width=None, height=300, returned_objects=["last_object_clicked"], key="map_all_trips_view")
    if map_out and map_out.get("last_object_clicked"):
        c_lat, c_lng = map_out["last_object_clicked"].get("lat"), map_out["last_object_clicked"].get("lng")
        if c_lat is not None and c_lng is not None:
            matched_place = map_coords_lookup.get((round(c_lat, 4), round(c_lng, 4)))
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
            st.markdown(f'<div style="font-size: 10.5pt; font-weight: 900; color: #2B2118; margin-bottom: 3px;">📍 {nr_m}. {nazwa_m}</div><div style="font-size: 9pt; font-weight: 800; color: #8C5338; margin-bottom: 6px;">🗺️ Występuje w wycieczkach:</div>', unsafe_allow_html=True)
            if df_przypisane.empty:
                st.markdown("<div style='font-size: 8.5pt; color: #8C827A; font-style: italic; margin-bottom: 3px;'>Nie jest przypisany</div>", unsafe_allow_html=True)
            else:
                for _, row_trip in df_przypisane.iterrows():
                    w_id, w_tytul = str(row_trip['id']), str(row_trip['tytul_wycieczki'])
                    skrocony = w_tytul.split(':')[0] if ':' in w_tytul else w_tytul
                    if st.button(f"🧭 {w_id}. {skrocony}", key=f"btn_go_to_trip_{w_id}_{nr_m}", use_container_width=True):
                        st.session_state["selected_trip_from_click"] = w_id
                        st.rerun()

    if wybrana_mapa_sb is not None:
        renderuj_karte_wycieczki(wybrana_mapa_sb.split(". ")[0], df_miejsca, pokaz_mape=True, pokaz_pogode=False)

elif st.session_state.active_tab == "zabytek":
    render_adventure_header("CretAi • Baza Miejsc")
    
    all_cats = list(CATEGORIES_CONFIG.keys())
    active_cat = st.session_state.selected_category
    
    cat_style_rules = [
        """
        div[data-testid="stHorizontalBlock"] { display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important; gap: 4px !important; margin-bottom: 0px !important; }
        div[data-testid="stHorizontalBlock"] > div { flex: 1 1 0px !important; min-width: 0 !important; }
        """
    ]

    for cat_name, conf in CATEGORIES_CONFIG.items():
        is_sel = (active_cat == cat_name or active_cat is None)
        bg = conf["color"] if is_sel else "#E0DCCE"
        border = conf["color"] if is_sel else "#C8C2B0"
        opacity = "1.0" if is_sel else "0.45"
        text_c = "#FAF8F2" if is_sel else "#2F241D"
        cat_style_rules.append(f"""
        div.st-key-btn_cat_filter_{conf['slug']} button {{
            background-color: {bg} !important; color: {text_c} !important; border: 1.5px solid {border} !important;
            opacity: {opacity} !important; height: 30px !important; border-radius: 9px !important; width: 100% !important; font-size: 8.5pt !important;
        }}
        """)

    st.markdown(f"<style>{''.join(cat_style_rules)}</style>", unsafe_allow_html=True)

    cols_row1 = st.columns(3, gap="small")
    for idx, cat_name in enumerate(all_cats[:3]):
        slug = CATEGORIES_CONFIG[cat_name]["slug"]
        with cols_row1[idx]:
            if st.button(f"✓ {cat_name}" if active_cat == cat_name else cat_name, key=f"btn_cat_filter_{slug}", use_container_width=True):
                st.session_state.selected_category = None if active_cat == cat_name else cat_name
                st.rerun()

    cols_row2 = st.columns(3, gap="small")
    for idx, cat_name in enumerate(all_cats[3:]):
        slug = CATEGORIES_CONFIG[cat_name]["slug"]
        with cols_row2[idx]:
            if st.button(f"✓ {cat_name}" if active_cat == cat_name else cat_name, key=f"btn_cat_filter_{slug}", use_container_width=True):
                st.session_state.selected_category = None if active_cat == cat_name else cat_name
                st.rerun()

    st.markdown("<div style='margin-top: 4px;'></div>", unsafe_allow_html=True)
    st.checkbox(
        "Pokaż odwiedzone miejsca", 
        value=st.session_state.get("show_visited_places", False), 
        key="show_visited_places",
        on_change=lambda: st.session_state.update(show_visited_places=st.session_state.show_visited_places)
    )

    df_miejsca_filtrowane = df_miejsca.copy()
    if not df_miejsca_filtrowane.empty:
        df_miejsca_filtrowane['kategoria_normalizowana'] = df_miejsca_filtrowane['typ'].apply(kategoryzuj_typ)
        if st.session_state.selected_category is not None:
            df_miejsca_filtrowane = df_miejsca_filtrowane[df_miejsca_filtrowane['kategoria_normalizowana'] == st.session_state.selected_category]
        if not st.session_state.show_visited_places:
            df_miejsca_filtrowane = df_miejsca_filtrowane[df_miejsca_filtrowane['odwiedzone'] == 0]

    m_miejsca = folium.Map(location=[35.2401, 24.8093], zoom_start=8, tiles="CartoDB positron")
    dodaj_marker_domku(m_miejsca)

    marker_coords_dict = {}
    if not df_miejsca_filtrowane.empty:
        for _, row in df_miejsca_filtrowane.iterrows():
            lat, lon = sparsuj_wspolrzedne(row.get('wspolrzedne'))
            if lat is not None and lon is not None:
                num = str(row.get('numer_miejsca', ''))
                kolor = "#A8A29E" if bool(row.get('odwiedzone', 0)) else pobierz_kolor_kategorii(row.get('kategoria_normalizowana', 'Other'))
                marker_coords_dict[(round(lat, 4), round(lon, 4))] = num
                icon_html = f'<div style="background-color:{kolor};color:#FFFFFF;border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:900;border:2px solid #FFFFFF;box-shadow:0 2px 5px rgba(0,0,0,0.25);">{num}</div>'
                folium.Marker([lat, lon], icon=folium.DivIcon(html=icon_html, icon_size=(24, 24), icon_anchor=(12, 12))).add_to(m_miejsca)

    map_key = f"map_places_view_{st.session_state.show_visited_places}_{st.session_state.selected_category}"
    map_output = st_folium(m_miejsca, width=None, height=290, returned_objects=["last_object_clicked"], key=map_key)

    if map_output and map_output.get("last_object_clicked"):
        c_lat, c_lng = map_output["last_object_clicked"].get("lat"), map_output["last_object_clicked"].get("lng")
        if c_lat is not None and c_lng is not None:
            clicked_id = marker_coords_dict.get((round(c_lat, 4), round(c_lng, 4)))
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
        key=f"place_selectbox_selector_{st.session_state.show_visited_places}",
        label_visibility="collapsed"
    )
    
    docelowy_nr = selected_option.split(".")[0].strip() if selected_option else st.session_state.active_place_id
    if selected_option:
        st.session_state.active_place_id = docelowy_nr

    if docelowy_nr:
        p_row = df_miejsca[df_miejsca['numer_miejsca'] == str(docelowy_nr)]
        if not p_row.empty:
            p = p_row.iloc[0]
            kat_p = kategoryzuj_typ(p.get('typ'))
            kolor_p = pobierz_kolor_kategorii(kat_p)
            coords_p = str(p.get('wspolrzedne', '')).replace(" ", "")
            czy_odwiedzone = bool(p.get('odwiedzone', 0))

            st.markdown(f"""
            <div class="overview-card" style="margin-top: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
                    <div style="font-size: 13pt; font-weight: 900; color: #2B2118; line-height: 1.2;">{p.get('numer_miejsca')}. {p.get('nazwa')}</div>
                    <span style="background-color: {kolor_p}; color: #FAF8F2; font-size: 8pt; font-weight: 800; padding: 2px 8px; border-radius: 10px;">{kat_p}</span>
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
                <summary>🧠 SPECYFIKA AuDHD & SENSORYKA</summary>
                <div style="margin-top: 8px; border-top: 1px solid #D1C7AE; padding-top: 6px;">
                    <div style="font-size: 9pt; color: #2B2118; margin-bottom: 4px;"><b>Potencjał meltdownu:</b> {p.get('potencjal_meltdownu', 'Średni')}</div>
                    <div style="font-size: 9pt; color: #2B2118;"><b>Strategia zaradcza:</b> {p.get('strategie_meltdown', 'Brak')}</div>
                </div>
            </details>
            """, unsafe_allow_html=True)

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

            if st.button("✓ Miejsce odwiedzone" if czy_odwiedzone else "🎯 Oznacz jako odwiedzone", key=f"btn_toggle_vis_{docelowy_nr}", use_container_width=True):
                potwierdz_odwiedzenie_dialog(docelowy_nr, p.get('nazwa'), czy_odwiedzone)

            renderuj_sekcje_notatek(id_miejsca=str(docelowy_nr))

if st.session_state.active_tab != "route":
    renderuj_globalny_czat_ai(aktualny_uzytkownik)
