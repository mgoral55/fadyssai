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

# --- 1. KONFIGURACJA STRONY I DESIGN SYSTEM: DUCH PRZYGODY (DARK + NEONY) ---
st.set_page_config(page_title="OdyssAi - Kreta", layout="centered", page_icon="🧭")

st.markdown("""
    <style>
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 90px !important;
        max-width: 600px;
    }
    .stApp {
        background-color: #0b1329;
        color: #f8fafc;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    [data-testid="stSidebar"] {
        background-color: #111e38;
        color: #f8fafc !important;
        border-right: 1px solid #1e293b;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
        color: #f8fafc !important;
    }
    h3 {
        color: #38bdf8;
        font-size: 1.15rem;
        font-weight: 700;
        margin-top: 0.5rem;
        margin-bottom: 0.25rem;
    }
    
    /* Belka tytułowa z wektorowym SVG logiem */
    .adventure-header {
        background: linear-gradient(135deg, #111e38 0%, #1e293b 100%);
        border: 1.5px solid #38bdf8;
        border-radius: 12px;
        padding: 8px 12px;
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 8px;
        box-shadow: 0 4px 15px rgba(56, 189, 248, 0.15);
    }
    .adventure-title-text {
        font-size: 1.1rem;
        font-weight: 800;
        color: #f8fafc;
        letter-spacing: 0.03em;
        text-transform: uppercase;
    }
    .adventure-subtitle {
        font-size: 0.75rem;
        color: #38bdf8;
        font-weight: 600;
    }

    /* Pasek nawigacji dolnej */
    .bottom-nav-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background-color: rgba(17, 30, 56, 0.95);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-top: 1px solid rgba(56, 189, 248, 0.2);
        padding: 8px 12px;
        display: flex;
        justify-content: space-around;
        gap: 6px;
        z-index: 99999;
        box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.4);
    }
    .bottom-nav-btn {
        flex: 1;
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: #94a3b8;
        padding: 8px 0;
        text-align: center;
        border-radius: 10px;
        font-size: 20px;
        text-decoration: none;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .bottom-nav-btn:hover {
        background-color: rgba(56, 189, 248, 0.15);
        color: #38bdf8;
        border-color: rgba(56, 189, 248, 0.4);
    }
    .bottom-nav-btn.active {
        background-color: #38bdf8;
        color: #0b1329;
        border-color: #38bdf8;
        font-weight: bold;
        box-shadow: 0 0 12px rgba(56, 189, 248, 0.5);
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
        border: 1px solid #334155;
        color: #f8fafc;
        padding: 6px 0;
        text-align: center;
        border-radius: 8px;
        font-size: 16px;
        text-decoration: none;
    }
    .custom-nav-btn:hover {
        background-color: #1e293b;
        border-color: #38bdf8;
        color: #38bdf8;
    }

    .logistics-card {
        background-color: #111e38;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 10px;
        text-align: left;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        margin-bottom: 4px;
    }
    .logistics-title {
        font-size: 8.5pt;
        font-weight: 700;
        color: #94a3b8;
        margin-bottom: 2px;
        text-transform: uppercase;
    }
    .logistics-value {
        font-size: 11pt;
        font-weight: 800;
        color: #f8fafc;
    }

    .net-box {
        background-color: #111e38;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 6px;
    }
    .net-box-evac {
        background-color: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.3);
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 6px;
    }
    .net-box-regen {
        background-color: rgba(34, 197, 94, 0.1);
        border: 1px solid rgba(34, 197, 94, 0.3);
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 6px;
    }
    .net-box-warn {
        background-color: rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.3);
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 6px;
    }
    .net-title {
        font-size: 8.5pt;
        font-weight: 700;
        color: #94a3b8;
        margin-bottom: 2px;
        text-transform: uppercase;
    }
    .net-title-evac {
        font-size: 8.5pt;
        font-weight: 700;
        color: #f87171;
        margin-bottom: 2px;
        text-transform: uppercase;
    }
    .net-title-regen {
        font-size: 8.5pt;
        font-weight: 700;
        color: #4ade80;
        margin-bottom: 2px;
        text-transform: uppercase;
    }
    .net-title-warn {
        font-size: 8.5pt;
        font-weight: 700;
        color: #fbbf24;
        margin-bottom: 2px;
        text-transform: uppercase;
    }
    .net-text {
        font-size: 10pt;
        color: #cbd5e1;
        line-height: 1.35;
    }
    .stButton > button {
        background-color: #111e38 !important;
        color: #f8fafc !important;
        border: 1.5px solid #334155 !important;
        font-weight: 700 !important;
        border-radius: 8px !important;
        padding: 0.4rem 0.8rem !important;
    }
    .stButton > button:hover {
        background-color: #38bdf8 !important;
        color: #0b1329 !important;
        border-color: #38bdf8 !important;
    }
    [data-testid="stExpander"] {
        border: 1px solid #1e293b !important;
        border-radius: 10px !important;
        background-color: #111e38 !important;
        margin-bottom: 6px !important;
    }
    </style>
""", unsafe_allow_html=True)

DOMEK_LAT = 35.5914
DOMEK_LON = 24.0918

def init_db():
    conn = sqlite3.connect('odyssai.db')
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
            odbyta INTEGER DEFAULT 0
        )
    ''')

    try:
        cursor.execute("ALTER TABLE miejsca ADD COLUMN odwiedzone INTEGER DEFAULT 0")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE miejsca ADD COLUMN Base TEXT DEFAULT 'false'")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE wycieczka ADD COLUMN odbyta INTEGER DEFAULT 0")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE wycieczka ADD COLUMN pobudka TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE wycieczka ADD COLUMN czas_wyjazdu TEXT")
    except:
        pass

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
        cursor.execute('''
            INSERT INTO wycieczka (id, tytul_wycieczki, calosciowy_opis_wycieczki, calosciowa_taktyka_dnia, calkowity_czas_wycieczki_godziny, szacowana_godzina_powrotu, pobudka, czas_wyjazdu, odbyta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
        ''', (
            "1",
            "Mity i Oceaniczne Głębiny: Pałac w Knossos & Cretaquarium",
            "Wyprawa łącząca mityczną historię starożytnej Krety z podwodnym światem głębin w klimatyzowanym akwarium oraz relaksem nad jeziorem Kournas.",
            "Żelazna kontrola czasu rano w Knossos, obiad w Cretaquarium i popołudniowe wyciszenie nad jeziorem.",
            "12.0",
            "18:30",
            "07:00",
            "07:30"
        ))

        kroki_w1 = [
            ("1", "1", "Pałac w Knossos", "35.2980, 25.1631", "08:00 - 09:45", "09:45", "BEZWZGLĘDNIE EWAKUOWAĆ SIĘ PRZED 10:00! Tłumy i upał.", "Brak - rygor czasowy.", "Szybkie wejście na otwarcie o 8:00.", "Wysoki (tłumy, brak cienia, duchota)", "Użycie aplikacji 3D na iPadzie jako kotwica uwagi, szybka ewakuacja w razie buntu.", "Legendarna stolica minojskiej Krety z ruinami pałacu króla Minosa."),
            ("1", "2", "Cretaquarium", "35.3326, 25.2825", "10:10 - 12:00", "12:00", "Unikać godzin szczytu (11:00 - 15:00).", "Średnia - kawiarnia obok.", "Wyciszenie sensoryczne w klimatyzowanym półmroku.", "Średni (pogłos w betonowych halach, tłum)", "Słuchawki wygłuszające, powolne tempo, półmrok przy akwariach.", "Jedno z największych i najnowocześniejszych oceanariów w basenie Morza Śródziemnego.")
        ]
        cursor.executemany('''
            INSERT INTO krok_wycieczki (id_wycieczki, krok_wycieczki, nazwa, wspolrzedne, okienko_zwiedzania, godzina_ewakuacji, czerwona_strefa_ostrzezenie, strefa_luzu_i_regeneracji, podsumowanie_taktyki, potencjal_meltdownu, strategie_meltdown, opis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', kroki_w1)

        cursor.execute("INSERT INTO checklist (id_wycieczki, typ) VALUES ('1', 'sprzęt')")
        ch1_s = cursor.lastrowid
        cursor.executemany("INSERT INTO checklist_item (id_checklisty, nazwa, ilosc) VALUES (?, ?, ?)", [
            (ch1_s, "iPad + aplikacja 3D", "1"),
            (ch1_s, "Okulary przeciwsłoneczne", "4")
        ])

        cursor.execute("INSERT INTO checklist (id_wycieczki, typ) VALUES ('1', 'jedzenie')")
        ch1_j = cursor.lastrowid
        cursor.executemany("INSERT INTO checklist_item (id_checklisty, nazwa, ilosc) VALUES (?, ?, ?)", [
            (ch1_j, "Woda 0.5L", "4"),
            (ch1_j, "Musy owocowe", "6")
        ])

        cursor.execute('''
            INSERT INTO wycieczka (id, tytul_wycieczki, calosciowy_opis_wycieczki, calosciowa_taktyka_dnia, calkowity_czas_wycieczki_godziny, szacowana_godzina_powrotu, pobudka, czas_wyjazdu, odbyta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
        ''', (
            "2",
            "Wyspa Łez i Sekretne Zatoki: Spinalonga & Agios Nikolaos",
            "Malownicza wyprawa na historyczną wyspę-twierdzę Spinalonga z rejsem statkiem z Eloundy oraz popołudniowym relaksem i kawą nad malowniczym jeziorem Voulismeni w Agios Nikolaos.",
            "Wczesny wyjazd na parking w Elounda, rejs na Spinalongę przed największym upałem, a po obiedzie spacer wokół jeziora w Agios Nikolaos.",
            "10.5",
            "17:00",
            "07:30",
            "08:00"
        ))

        kroki_w2 = [
            ("2", "1", "Elounda - Port i Rejs na Spinalongę", "35.2575, 25.7314", "09:00 - 11:30", "11:30", "Silne słońce na łodzi i na wyspie. Konieczne nakrycia głowy!", "Odpoczynek w cieniu kawiarni w porcie Elounda.", "Spokojny rejs tradycyjną łodzią i zwiedzanie historycznej twierdzy.", "Średni (długi rejs, nasłonecznienie)", "Okulary przeciwsłoneczne, woda z lodem w termosie, czapka.", "Dawna wenecka twierdza i późniejsza kolonia trędowatych z niezwykłą atmosferą."),
            ("2", "2", "Agios Nikolaos & Jezioro Voulismeni", "35.1915, 25.7171", "12:50 - 15:30", "15:30", "Dużo turystów wokół jeziora w godzinach popołudniowych.", "Kawiarnie nad brzegiem jeziora z widokiem na klify.", "Niespieszny obiad i lody nad wodą.", "Niski (przyjemny spacer, dużo miejsc do zatrzymania)", "Lody jako nagroda, swobodne tempo.", "Urokliwe miasteczko wokół bezdennego jeziora połączonego z morzem wąskim kanałem.")
        ]
        cursor.executemany('''
            INSERT INTO krok_wycieczki (id_wycieczki, krok_wycieczki, nazwa, wspolrzedne, okienko_zwiedzania, godzina_ewakuacji, czerwona_strefa_ostrzezenie, strefa_luzu_i_regeneracji, podsumowanie_taktyki, potencjal_meltdownu, strategie_meltdown, opis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', kroki_w2)

        cursor.execute("INSERT INTO checklist (id_wycieczki, typ) VALUES ('2', 'sprzęt')")
        ch2_s = cursor.lastrowid
        cursor.executemany("INSERT INTO checklist_item (id_checklisty, nazwa, ilosc) VALUES (?, ?, ?)", [
            (ch2_s, "Nakrycie głowy / czapka", "4"),
            (ch2_s, "Krem z filtrem UV 50+", "1")
        ])

        cursor.execute("INSERT INTO checklist (id_wycieczki, typ) VALUES ('2', 'jedzenie')")
        ch2_j = cursor.lastrowid
        cursor.executemany("INSERT INTO checklist_item (id_checklisty, nazwa, ilosc) VALUES (?, ?, ?)", [
            (ch2_j, "Zimna woda w termosie", "2"),
            (ch2_j, "Batony energetyczne", "4")
        ])

        conn.commit()
    conn.close()

init_db()

def oznacz_wycieczke_i_miejsca_jako_odbyte(id_wycieczki):
    conn = sqlite3.connect('odyssai.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE wycieczka SET odbyta = 1 WHERE id = ?', (str(id_wycieczki),))
    
    cursor.execute('SELECT krok_wycieczki FROM krok_wycieczki WHERE id_wycieczki = ?', (str(id_wycieczki),))
    kroki = cursor.fetchall()
    
    for k in kroki:
        numer_miejsca = k[0]
        cursor.execute('UPDATE miejsca SET odwiedzone = 1 WHERE numer_miejsca = ?', (str(numer_miejsca),))
        
    conn.commit()
    conn.close()
    return f"Wycieczka #{id_wycieczki} oraz powiązane z nią miejsca zostały oznaczone jako odbyte!"

def aktualizuj_miejsce(numer_miejsca, opis=None, konieczna_akcja=None):
    conn = sqlite3.connect('odyssai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT Base FROM miejsca WHERE numer_miejsca = ?', (str(numer_miejsca),))
    res = cursor.fetchone()
    if res and str(res[0]).lower() == 'true':
        conn.close()
        return f"OSTRZEŻENIE: Miejsce nr {numer_miejsca} pochodzi z bazy bazowej (CSV) i ma flagę Base=true. Modyfikacja zablokowana!"

    if opis:
        cursor.execute('UPDATE miejsca SET opis = ? WHERE numer_miejsca = ?', (opis, str(numer_miejsca)))
    if konieczna_akcja:
        cursor.execute('UPDATE miejsca SET konieczna_akcja = ? WHERE numer_miejsca = ?', (konieczna_akcja, str(numer_miejsca)))
    conn.commit()
    conn.close()
    return f"Miejsce nr {numer_miejsca} zostało zaktualizowane!"

def usun_miejsce(numer_miejsca):
    conn = sqlite3.connect('odyssai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT Base FROM miejsca WHERE numer_miejsca = ?', (str(numer_miejsca),))
    res = cursor.fetchone()
    if res and str(res[0]).lower() == 'true':
        conn.close()
        return f"OSTRZEŻENIE: Miejsce nr {numer_miejsca} pochodzi z bazy bazowej (CSV) i ma flagę Base=true. Usuwanie zablokowane!"
    
    cursor.execute('DELETE FROM miejsca WHERE numer_miejsca = ?', (str(numer_miejsca),))
    conn.commit()
    conn.close()
    return f"Miejsce nr {numer_miejsca} zostało usunięte."

def utworz_nowa_wycieczke(id, tytul_wycieczki, calosciowy_opis_wycieczki, calosciowa_taktyka_dnia, calkowity_czas_wycieczki_godziny, szacowana_godzina_powrotu, pobudka, czas_wyjazdu):
    conn = sqlite3.connect('odyssai.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO wycieczka (id, tytul_wycieczki, calosciowy_opis_wycieczki, calosciowa_taktyka_dnia, calkowity_czas_wycieczki_godziny, szacowana_godzina_powrotu, pobudka, czas_wyjazdu, odbyta)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
    ''', (str(id), tytul_wycieczki, calosciowy_opis_wycieczki, calosciowa_taktyka_dnia, str(calkowity_czas_wycieczki_godziny), szacowana_godzina_powrotu, pobudka, czas_wyjazdu))
    conn.commit()
    conn.close()
    return f"Nowa wycieczka '{tytul_wycieczki}' (ID: {id}) została utworzona!"

def edytuj_wycieczke(id, tytul_wycieczki=None, calosciowy_opis_wycieczki=None, calosciowa_taktyka_dnia=None, szacowana_godzina_powrotu=None, pobudka=None, czas_wyjazdu=None):
    conn = sqlite3.connect('odyssai.db')
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
    conn.commit()
    conn.close()
    return f"Wycieczka #{id} została zaktualizowana."

def usun_wycieczke(id_wycieczki):
    conn = sqlite3.connect('odyssai.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM wycieczka WHERE id = ?', (str(id_wycieczki),))
    cursor.execute('DELETE FROM krok_wycieczki WHERE id_wycieczki = ?', (str(id_wycieczki),))
    cursor.execute('SELECT id FROM checklist WHERE id_wycieczki = ?', (str(id_wycieczki),))
    chl_rows = cursor.fetchall()
    for row in chl_rows:
        cursor.execute('DELETE FROM checklist_item WHERE id_checklisty = ?', (row[0],))
    cursor.execute('DELETE FROM checklist WHERE id_wycieczki = ?', (str(id_wycieczki),))
    conn.commit()
    conn.close()
    return f"Wycieczka #{id_wycieczki} została usunięta."

def dodaj_krok_do_wycieczki(id_wycieczki, krok_wycieczki, nazwa, wspolrzedne, okienko_zwiedzania, godzina_ewakuacji, czerwona_strefa_ostrzezenie, strefa_luzu_i_regeneracji, podsumowanie_taktyki, potencjal_meltdownu, strategie_meltdown, opis):
    conn = sqlite3.connect('odyssai.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO krok_wycieczki (
            id_wycieczki, krok_wycieczki, nazwa, wspolrzedne, okienko_zwiedzania, 
            godzina_ewakuacji, czerwona_strefa_ostrzezenie, 
            strefa_luzu_i_regeneracji, podsumowanie_taktyki, potencjal_meltdownu, 
            strategie_meltdown, opis
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (str(id_wycieczki), str(krok_wycieczki), nazwa, wspolrzedne, okienko_zwiedzania, godzina_ewakuacji, czerwona_strefa_ostrzezenie, strefa_luzu_i_regeneracji, podsumowanie_taktyki, potencjal_meltdownu, strategie_meltdown, opis))
    conn.commit()
    conn.close()
    return f"Dodano krok nr {krok_wycieczki} ({nazwa}) do wycieczki #{id_wycieczki}!"

def edytuj_krok_w_wycieczce(id_wycieczki, krok_wycieczki, nazwa=None, okienko_zwiedzania=None, godzina_ewakuacji=None, czerwona_strefa_ostrzezenie=None, strefa_luzu_i_regeneracji=None, podsumowanie_taktyki=None, potencjal_meltdownu=None, strategie_meltdown=None, opis=None):
    conn = sqlite3.connect('odyssai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM krok_wycieczki WHERE id_wycieczki = ? AND (krok_wycieczki = ? OR nazwa LIKE ?)', (str(id_wycieczki), str(krok_wycieczki), f"%{krok_wycieczki}%"))
    res = cursor.fetchone()
    if not res:
        conn.close()
        return f"Nie znaleziono kroku."
    krok_row_id = res[0]
    if nazwa:
        cursor.execute('UPDATE krok_wycieczki SET nazwa = ? WHERE id = ?', (nazwa, krok_row_id))
    if okienko_zwiedzania:
        cursor.execute('UPDATE krok_wycieczki SET okienko_zwiedzania = ? WHERE id = ?', (okienko_zwiedzania, krok_row_id))
    if godzina_ewakuacji:
        cursor.execute('UPDATE krok_wycieczki SET godzina_ewakuacji = ? WHERE id = ?', (godzina_ewakuacji, krok_row_id))
    if czerwona_strefa_ostrzezenie:
        cursor.execute('UPDATE krok_wycieczki SET czerwona_strefa_ostrzezenie = ? WHERE id = ?', (czerwona_strefa_ostrzezenie, krok_row_id))
    if strefa_luzu_i_regeneracji:
        cursor.execute('UPDATE krok_wycieczki SET strefa_luzu_i_regeneracji = ? WHERE id = ?', (strefa_luzu_i_regeneracji, krok_row_id))
    if podsumowanie_taktyki:
        cursor.execute('UPDATE krok_wycieczki SET podsumowanie_taktyki = ? WHERE id = ?', (podsumowanie_taktyki, krok_row_id))
    if potencjal_meltdownu:
        cursor.execute('UPDATE krok_wycieczki SET potencjal_meltdownu = ? WHERE id = ?', (potencjal_meltdownu, krok_row_id))
    if strategie_meltdown:
        cursor.execute('UPDATE krok_wycieczki SET strategie_meltdown = ? WHERE id = ?', (strategie_meltdown, krok_row_id))
    if opis:
        cursor.execute('UPDATE krok_wycieczki SET opis = ? WHERE id = ?', (opis, krok_row_id))
    conn.commit()
    conn.close()
    return f"Krok {krok_wycieczki} zaktualizowany."

def usun_krok_z_wycieczki(id_wycieczki, krok_wycieczki):
    conn = sqlite3.connect('odyssai.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM krok_wycieczki WHERE id_wycieczki = ? AND (krok_wycieczki = ? OR nazwa LIKE ?)', (str(id_wycieczki), str(krok_wycieczki), f"%{krok_wycieczki}%"))
    conn.commit()
    conn.close()
    return f"Usunięto krok."

def dodaj_element_checklisty(id_wycieczki, typ, nazwa, ilosc="1"):
    conn = sqlite3.connect('odyssai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM checklist WHERE id_wycieczki = ? AND typ = ?', (str(id_wycieczki), typ))
    res = cursor.fetchone()
    if res:
        chl_id = res[0]
    else:
        cursor.execute('INSERT INTO checklist (id_wycieczki, typ) VALUES (?, ?)', (str(id_wycieczki), typ))
        chl_id = cursor.lastrowid
    cursor.execute('INSERT INTO checklist_item (id_checklisty, nazwa, ilosc) VALUES (?, ?, ?)', (chl_id, nazwa, str(ilosc)))
    conn.commit()
    conn.close()
    return f"Dodano do checklisty."

def edytuj_element_checklisty(id_wycieczki, typ, stara_nazwa, nowa_nazwa=None, nowa_ilosc=None):
    conn = sqlite3.connect('odyssai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM checklist WHERE id_wycieczki = ? AND typ = ?', (str(id_wycieczki), typ))
    res = cursor.fetchone()
    if not res:
        conn.close()
        return f"Nie znaleziono checklisty."
    chl_id = res[0]
    cursor.execute('SELECT id FROM checklist_item WHERE id_checklisty = ? AND nazwa LIKE ?', (chl_id, f"%{stara_nazwa}%"))
    item_res = cursor.fetchone()
    if not item_res:
        conn.close()
        return f"Nie znaleziono elementu."
    item_id = item_res[0]
    if nowa_nazwa:
        cursor.execute('UPDATE checklist_item SET nazwa = ? WHERE id = ?', (nowa_nazwa, item_id))
    if nowa_ilosc:
        cursor.execute('UPDATE checklist_item SET ilosc = ? WHERE id = ?', (str(nowa_ilosc), item_id))
    conn.commit()
    conn.close()
    return f"Zaktualizowano element."

def usun_element_checklisty(id_wycieczki, typ, nazwa):
    conn = sqlite3.connect('odyssai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM checklist WHERE id_wycieczki = ? AND typ = ?', (str(id_wycieczki), typ))
    res = cursor.fetchone()
    if not res:
        conn.close()
        return f"Nie znaleziono."
    chl_id = res[0]
    cursor.execute('DELETE FROM checklist_item WHERE id_checklisty = ? AND nazwa LIKE ?', (chl_id, f"%{nazwa}%"))
    conn.commit()
    conn.close()
    return f"Usunięto element."

def pobierz_wszystkie_miejsca():
    conn = sqlite3.connect('odyssai.db')
    df = pd.read_sql('SELECT * FROM miejsca', conn)
    conn.close()
    return df

def pobierz_aktywna_wycieczke_id():
    conn = sqlite3.connect('odyssai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT aktualne_id_wycieczki FROM aktywna_wycieczka WHERE id = 1')
    res = cursor.fetchone()
    conn.close()
    return str(res[0]) if res else "1"

def ustaw_aktywna_wycieczke_id(wycieczka_id):
    conn = sqlite3.connect('odyssai.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE aktywna_wycieczka SET aktualne_id_wycieczki = ? WHERE id = 1', (str(wycieczka_id),))
    conn.commit()
    conn.close()

def pobierz_skrocone_opcje_wycieczek():
    conn = sqlite3.connect('odyssai.db')
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
    tekst = "Jesteś asystentem podróży OdyssAi na Kretę.\n--- BAZA DANYCH SQLITE ---\n"
    conn = sqlite3.connect('odyssai.db')
    try:
        miejsca_df = pd.read_sql('SELECT numer_miejsca, nazwa, typ, czas_dojazdu, orientacyjny_czas, koszt, konieczna_akcja, odwiedzone, Base FROM miejsca', conn)
        wycieczki_df = pd.read_sql('SELECT id, tytul_wycieczki, calosciowy_opis_wycieczki, calosciowa_taktyka_dnia, odbyta FROM wycieczka', conn)
        kroki_df = pd.read_sql('SELECT id_wycieczki, krok_wycieczki, nazwa, okienko_zwiedzania FROM krok_wycieczki', conn)
        checklisty_df = pd.read_sql('SELECT c.id_wycieczki, c.typ, i.nazwa, i.ilosc FROM checklist c JOIN checklist_item i ON c.id = i.id_checklisty', conn)
    except:
        miejsca_df = pd.DataFrame()
        wycieczki_df = pd.DataFrame()
        kroki_df = pd.DataFrame()
        checklisty_df = pd.DataFrame()
    conn.close()

    if not miejsca_df.empty:
        tekst += "Miejsca:\n"
        for _, r in miejsca_df.iterrows():
            tekst += f"- Nr {r['numer_miejsca']}: {r['nazwa']} (Typ: {r['typ']}, Odwiedzone: {r['odwiedzone']}, Dojazd: {r['czas_dojazdu']})\n"
    if not wycieczki_df.empty:
        tekst += "\nWycieczki:\n"
        for _, w in wycieczki_df.iterrows():
            if int(w.get('odbyta', 0)) == 1:
                continue
            tekst += f"- Wycieczka #{w['id']}: {w['tytul_wycieczki']} | Opis: {w['calosciowy_opis_wycieczki']}\n"
    return tekst

def pobierz_trase_osrm(punkty):
    if len(punkty) < 2:
        return []
    wsp_str = ";".join([f"{p[1]},{p[0]}" for p in punkty])
    url = f"http://router.project-osrm.org/route/v1/driving/{wsp_str}?overview=full&geometries=geojson"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'OdyssAiApp/1.0'})
        with urllib.request.urlopen(req, timeout=2) as response:
            data = json.loads(response.read().decode())
            if 'routes' in data and len(data['routes']) > 0:
                geojson_coords = data['routes'][0]['geometry']['coordinates']
                return [[c[1], c[0]] for c in geojson_coords]
    except:
        pass
    return [[p[0], p[1]] for p in punkty]

def dodaj_marker_domku(m):
    domek_icon_html = '<div style="background-color:#38bdf8;color:#0b1329;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:14px;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);">🏠</div>'
    domek_icon = folium.DivIcon(html=domek_icon_html, icon_size=(28, 28), icon_anchor=(14, 14))
    folium.Marker([DOMEK_LAT, DOMEK_LON], icon=domek_icon, tooltip="Nasz Domek").add_to(m)

@st.dialog("🎒 Checklista Wycieczki")
def pokaz_checklistu_popup(wycieczka_id):
    conn = sqlite3.connect('odyssai.db')
    checklisty_df = pd.read_sql('SELECT * FROM checklist WHERE id_wycieczki = ?', conn, params=(str(wycieczka_id),))
    items_df = pd.DataFrame()
    if not checklisty_df.empty:
        ids_chl = tuple(checklisty_df['id'].tolist())
        if len(ids_chl) == 1:
            items_df = pd.read_sql('SELECT * FROM checklist_item WHERE id_checklisty = ?', conn, params=(ids_chl[0],))
        else:
            placeholders = ','.join(['?'] * len(ids_chl))
            items_df = pd.read_sql(f'SELECT * FROM checklist_item WHERE id_checklisty IN ({placeholders})', conn, params=ids_chl)
    conn.close()

    if checklisty_df.empty or items_df.empty:
        st.info("Brak zdefiniowanej checklisty.")
    else:
        for _, chl in checklisty_df.iterrows():
            typ_chl = chl['typ'].capitalize()
            chl_id = chl['id']
            powiazane_itemy = items_df[items_df['id_checklisty'] == chl_id]
            if not powiazane_itemy.empty:
                st.markdown(f"**📌 {typ_chl}:**")
                for _, itm in powiazane_itemy.iterrows():
                    ilosc_val = itm['ilosc']
                    ilosc_str = f" *({ilosc_val})*" if pd.notna(ilosc_val) and ilosc_val != "1" else ""
                    st.checkbox(f"{itm['nazwa']}{ilosc_str}", key=f"chk_pop_{itm['id']}")

# Narzędzia AI
aktualizuj_tool = types.FunctionDeclaration(
    name="aktualizuj_miejsce",
    description="Aktualizuje informacje o miejscu na Krecie.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "numer_miejsca": types.Schema(type=types.Type.STRING, description="Numer miejsca"),
            "opis": types.Schema(type=types.Type.STRING, description="Nowy opis"),
            "konieczna_akcja": types.Schema(type=types.Type.STRING, description="Nowa akcja"),
        },
        required=["numer_miejsca"]
    ),
)
usun_miejsce_tool = types.FunctionDeclaration(
    name="usun_miejsce",
    description="Usuwa miejsce z bazy.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={"numer_miejsca": types.Schema(type=types.Type.STRING)},
        required=["numer_miejsca"]
    ),
)
utworz_nowa_wycieczke_tool = types.FunctionDeclaration(
    name="utworz_nowa_wycieczke",
    description="Tworzy nową wycieczkę.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id": types.Schema(type=types.Type.STRING),
            "tytul_wycieczki": types.Schema(type=types.Type.STRING),
            "calosciowy_opis_wycieczki": types.Schema(type=types.Type.STRING),
            "calosciowa_taktyka_dnia": types.Schema(type=types.Type.STRING),
            "calkowity_czas_wycieczki_godziny": types.Schema(type=types.Type.STRING),
            "szacowana_godzina_powrotu": types.Schema(type=types.Type.STRING),
            "pobudka": types.Schema(type=types.Type.STRING),
            "czas_wyjazdu": types.Schema(type=types.Type.STRING),
        },
        required=["id", "tytul_wycieczki", "calosciowy_opis_wycieczki", "calosciowa_taktyka_dnia"]
    ),
)
edytuj_wycieczke_tool = types.FunctionDeclaration(
    name="edytuj_wycieczke",
    description="Edytuje parametry wycieczki.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id": types.Schema(type=types.Type.STRING),
            "tytul_wycieczki": types.Schema(type=types.Type.STRING),
            "calosciowy_opis_wycieczki": types.Schema(type=types.Type.STRING),
            "calosciowa_taktyka_dnia": types.Schema(type=types.Type.STRING),
            "szacowana_godzina_powrotu": types.Schema(type=types.Type.STRING),
            "pobudka": types.Schema(type=types.Type.STRING),
            "czas_wyjazdu": types.Schema(type=types.Type.STRING),
        },
        required=["id"]
    ),
)
usun_wycieczke_tool = types.FunctionDeclaration(
    name="usun_wycieczke",
    description="Usuwa wycieczkę.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={"id_wycieczki": types.Schema(type=types.Type.STRING)},
        required=["id_wycieczki"]
    ),
)
dodaj_krok_tool = types.FunctionDeclaration(
    name="dodaj_krok_do_wycieczki",
    description="Dodaje krok do wycieczki.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id_wycieczki": types.Schema(type=types.Type.STRING),
            "krok_wycieczki": types.Schema(type=types.Type.STRING),
            "nazwa": types.Schema(type=types.Type.STRING),
            "wspolrzedne": types.Schema(type=types.Type.STRING),
            "okienko_zwiedzania": types.Schema(type=types.Type.STRING),
            "godzina_ewakuacji": types.Schema(type=types.Type.STRING),
            "czerwona_strefa_ostrzezenie": types.Schema(type=types.Type.STRING),
            "strefa_luzu_i_regeneracji": types.Schema(type=types.Type.STRING),
            "podsumowanie_taktyki": types.Schema(type=types.Type.STRING),
            "potencjal_meltdownu": types.Schema(type=types.Type.STRING),
            "strategie_meltdown": types.Schema(type=types.Type.STRING),
            "opis": types.Schema(type=types.Type.STRING),
        },
        required=["id_wycieczki", "krok_wycieczki", "nazwa", "wspolrzedne"]
    ),
)
edytuj_krok_tool = types.FunctionDeclaration(
    name="edytuj_krok_w_wycieczce",
    description="Edytuje krok wycieczki.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id_wycieczki": types.Schema(type=types.Type.STRING),
            "krok_wycieczki": types.Schema(type=types.Type.STRING),
            "nazwa": types.Schema(type=types.Type.STRING),
            "okienko_zwiedzania": types.Schema(type=types.Type.STRING),
            "godzina_ewakuacji": types.Schema(type=types.Type.STRING),
            "czerwona_strefa_ostrzezenie": types.Schema(type=types.Type.STRING),
            "strefa_luzu_i_regeneracji": types.Schema(type=types.Type.STRING),
            "podsumowanie_taktyki": types.Schema(type=types.Type.STRING),
            "potencjal_meltdownu": types.Schema(type=types.Type.STRING),
            "strategie_meltdown": types.Schema(type=types.Type.STRING),
            "opis": types.Schema(type=types.Type.STRING),
        },
        required=["id_wycieczki", "krok_wycieczki"]
    ),
)
usun_krok_tool = types.FunctionDeclaration(
    name="usun_krok_z_wycieczki",
    description="Usuwa krok wycieczki.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id_wycieczki": types.Schema(type=types.Type.STRING),
            "krok_wycieczki": types.Schema(type=types.Type.STRING),
        },
        required=["id_wycieczki", "krok_wycieczki"]
    ),
)
dodaj_checklist_tool = types.FunctionDeclaration(
    name="dodaj_element_checklisty",
    description="Dodaje element do checklisty.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id_wycieczki": types.Schema(type=types.Type.STRING),
            "typ": types.Schema(type=types.Type.STRING),
            "nazwa": types.Schema(type=types.Type.STRING),
            "ilosc": types.Schema(type=types.Type.STRING),
        },
        required=["id_wycieczki", "typ", "nazwa"]
    ),
)
edytuj_checklist_tool = types.FunctionDeclaration(
    name="edytuj_element_checklisty",
    description="Edytuje element checklisty.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id_wycieczki": types.Schema(type=types.Type.STRING),
            "typ": types.Schema(type=types.Type.STRING),
            "stara_nazwa": types.Schema(type=types.Type.STRING),
            "nowa_nazwa": types.Schema(type=types.Type.STRING),
            "nowa_ilosc": types.Schema(type=types.Type.STRING),
        },
        required=["id_wycieczki", "typ", "stara_nazwa"]
    ),
)
usun_checklist_tool = types.FunctionDeclaration(
    name="usun_element_checklisty",
    description="Usuwa element z checklisty.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id_wycieczki": types.Schema(type=types.Type.STRING),
            "typ": types.Schema(type=types.Type.STRING),
            "nazwa": types.Schema(type=types.Type.STRING),
        },
        required=["id_wycieczki", "typ", "nazwa"]
    ),
)

odyssai_tools = types.Tool(function_declarations=[
    aktualizuj_tool, usun_miejsce_tool, utworz_nowa_wycieczke_tool, edytuj_wycieczke_tool, 
    usun_wycieczke_tool, dodaj_krok_tool, edytuj_krok_tool, usun_krok_tool, 
    dodaj_checklist_tool, edytuj_checklist_tool, usun_checklist_tool
])

def renderuj_sekcje_czatu_ai(klucz_unikalny_sufiks):
    st.markdown("---")
    st.markdown("### 💬 Asystent AI OdyssAi")
    
    if not gemini_api_key:
        st.info("👈 Wprowadź klucz API Google Gemini w menu bocznym, aby uruchomić czat.")
        return

    client = genai.Client(api_key=gemini_api_key)
    zewnetrzny_kontekst = wczytaj_kontekst_zewnetrzny()
    
    system_prompt = f"""Jesteś inteligentnym asystentem podróży OdyssAi na Kretę.
{zewnetrzny_kontekst}
- Masz wgląd w bazę danych. Chronisz miejsca z flagą Base = true."""

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for message in st.session_state.chat_history:
        role = message["role"]
        content = message["content"]
        with st.chat_message(role):
            if isinstance(content, str):
                st.markdown(content)
            elif hasattr(content, "parts"):
                for p in content.parts:
                    if hasattr(p, "text") and p.text:
                        st.markdown(p.text)

    if st.button("🗑️ Nowy czat", key=f"btn_new_chat_{klucz_unikalny_sufiks}", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

    prompt = st.chat_input("Zapytaj o plany, zmień trasę...", key=f"chat_input_{klucz_unikalny_sufiks}")
    if prompt:
        user_content = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
        st.session_state.chat_history.append({"role": "user", "content": prompt, "raw_content": user_content})
        
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                contents = [item["raw_content"] for item in st.session_state.chat_history if "raw_content" in item]
                if not contents:
                    contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]

                with st.spinner(f"Analizuję plan (model: {wybrany_model})..."):
                    response = client.models.generate_content(
                        model=wybrany_model,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            tools=[odyssai_tools],
                            system_instruction=system_prompt
                        )
                    )

                assistant_reply = ""
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
                        if call_name == "aktualizuj_miejsce":
                            wynik_bazy = aktualizuj_miejsce(**args)
                        elif call_name == "usun_miejsce":
                            wynik_bazy = usun_miejsce(**args)
                        elif call_name == "utworz_nowa_wycieczke":
                            wynik_bazy = utworz_nowa_wycieczke(**args)
                        elif call_name == "edytuj_wycieczke":
                            wynik_bazy = edytuj_wycieczke(**args)
                        elif call_name == "usun_wycieczke":
                            wynik_bazy = usun_wycieczke(**args)
                        elif call_name == "dodaj_krok_do_wycieczki":
                            wynik_bazy = dodaj_krok_do_wycieczki(**args)
                        elif call_name == "edytuj_krok_w_wycieczce":
                            wynik_bazy = edytuj_krok_w_wycieczce(**args)
                        elif call_name == "usun_krok_z_wycieczki":
                            wynik_bazy = usun_krok_z_wycieczki(**args)
                        elif call_name == "dodaj_element_checklisty":
                            wynik_bazy = dodaj_element_checklisty(**args)
                        elif call_name == "edytuj_element_checklisty":
                            wynik_bazy = edytuj_element_checklisty(**args)
                        elif call_name == "usun_element_checklisty":
                            wynik_bazy = usun_element_checklisty(**args)
                        else:
                            wynik_bazy = "Wykonano."
                        
                        follow_up = client.models.generate_content(
                            model=wybrany_model,
                            contents=contents + [
                                model_content,
                                types.Content(role="user", parts=[types.Part.from_function_response(name=call_name, response={"result": wynik_bazy})])
                            ],
                            config=types.GenerateContentConfig(tools=[odyssai_tools])
                        )
                        fu_cand = follow_up.candidates[0] if follow_up.candidates else None
                        if fu_cand and fu_cand.content and fu_cand.content.parts:
                            text_parts = [p.text for p in fu_cand.content.parts if hasattr(p, "text") and p.text]
                            assistant_reply = "".join(text_parts) if text_parts else "Operacja zakończona."
                            st.session_state.chat_history.append({"role": "assistant", "content": assistant_reply, "raw_content": fu_cand.content})
                        else:
                            assistant_reply = "Zaktualizowano bazę."
                else:
                    text_parts = [p.text for p in candidate.content.parts if hasattr(p, "text") and p.text] if candidate and candidate.content and candidate.content.parts else []
                    assistant_reply = "".join(text_parts) if text_parts else (response.text if hasattr(response, "text") else "Brak odpowiedzi.")
                    st.session_state.chat_history.append({"role": "assistant", "content": assistant_reply, "raw_content": candidate.content if candidate else types.Content(role="model", parts=[types.Part.from_text(text=assistant_reply)])})
            except Exception as e:
                assistant_reply = f"Błąd: {e}"
                st.session_state.chat_history.append({"role": "assistant", "content": assistant_reply, "raw_content": types.Content(role="model", parts=[types.Part.from_text(text=assistant_reply)])})

            st.markdown(assistant_reply)
            st.rerun()

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

def renderuj_karte_wycieczki(wycieczka_id, pokaz_mape=True):
    conn = sqlite3.connect('odyssai.db')
    wycieczka_row = pd.read_sql('SELECT * FROM wycieczka WHERE id = ?', conn, params=(str(wycieczka_id),))
    kroki_df = pd.read_sql('SELECT * FROM krok_wycieczki WHERE id_wycieczki = ?', conn, params=(str(wycieczka_id),))
    conn.close()
    
    if not wycieczka_row.empty:
        w_gen = wycieczka_row.iloc[0]
        tytul_w = str(w_gen['tytul_wycieczki'])
        
        st.markdown(f"""
        <div style="background-color:#111e38; padding:10px 12px; border:1px solid #1e293b; border-radius:10px; text-align:center; font-size:11pt; font-weight:800; text-transform:uppercase; margin-bottom:8px; color:#38bdf8;">
            {tytul_w}
        </div>
        """, unsafe_allow_html=True)

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
                        icon_html = f'<div style="background-color:#38bdf8;color:#0b1329;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:bold;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);">{krok}</div>'
                        icon = folium.DivIcon(html=icon_html, icon_size=(26, 26), icon_anchor=(13, 13))
                        folium.Marker([lat, lon], icon=icon, tooltip=f"Krok {krok}: {nazwa}").add_to(m_trasa)
                    
                trasa_po_drogach = pobierz_trase_osrm(surowe_wspolrzedne)
                if trasa_po_drogach:
                    folium.PolyLine(trasa_po_drogach, color="#38bdf8", weight=4, opacity=0.8).add_to(m_trasa)
                    
                st_folium(m_trasa, width="100%", height=240, returned_objects=[])

            st.markdown("---")

        pobudka_val = w_gen.get('pobudka', '07:00') if pd.notna(w_gen.get('pobudka')) else '07:00'
        wyjazd_val = w_gen.get('czas_wyjazdu', '07:30') if pd.notna(w_gen.get('czas_wyjazdu')) else '07:30'
        powrot_val = w_gen.get('szacowana_godzina_powrotu', '17:00')
        czas_trwania = f"{w_gen['calkowity_czas_wycieczki_godziny']} godz."

        st.markdown(f"""
        <div style="background-color:#111e38; border:1px solid #1e293b; border-radius:10px; padding:10px; margin-bottom:10px;">
            <div style="font-size:9.5pt; font-weight:700; color:#38bdf8; margin-bottom:6px; display:flex; align-items:center; gap:6px;">
                <span>🧭</span> LOGISTYKA DNIA
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px;">
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
            <div style="background-color:#111e38; border:1px solid #1e293b; border-radius:10px; padding:10px; margin-bottom:10px;">
                <div style="font-size:9.5pt; font-weight:700; color:#38bdf8; margin-bottom:4px;">📝 Cel wycieczki</div>
                <div style="color:#cbd5e1; font-size:10pt;">{w_gen['calosciowy_opis_wycieczki']}</div>
            </div>
            """, unsafe_allow_html=True)

        if pd.notna(w_gen['calosciowa_taktyka_dnia']) and str(w_gen['calosciowa_taktyka_dnia']).strip() != "":
            st.markdown(f"""
            <div style="background-color:#111e38; padding:10px; border:1px solid #1e293b; border-radius:10px; margin-bottom:10px;">
                <span style="font-size:9.5pt; font-weight:700; color:#38bdf8;">🧠 TAKTYKA DNIA:</span><br>
                <span style="color:#cbd5e1; font-size:10pt;">{w_gen['calosciowa_taktyka_dnia']}</span>
            </div>
            """, unsafe_allow_html=True)

        if st.button("🎒 Sprawdź checklistę", use_container_width=True):
            pokaz_checklistu_popup(wycieczka_id)

        st.markdown("<h3>Szczegółowy plan</h3>", unsafe_allow_html=True)
        
        for _, k in kroki_df.iterrows():
            krok_num = str(k['krok_wycieczki'])
            krok_nazwa = str(k['nazwa'])
            okienko = str(k.get('okienko_zwiedzania', ''))
            
            pasujące_miejsce = df_miejsca[df_miejsca['numer_miejsca'] == krok_num]
            miejsce_id_cel = str(pasujące_miejsce.iloc[0]['numer_miejsca']) if not pasujące_miejsce.empty else "1"
            
            google_search_url = f"https://www.google.com/search?q={krok_nazwa} Kreta"
            gps_maps_url = f"https://www.google.com/maps/search/?api=1&query={k['wspolrzedne']}"
            coords_clean = str(k['wspolrzedne']).replace(" ", "")
            sklep_maps_url = f"https://www.google.com/maps/search/supermarket/@{coords_clean},15z"
            resto_maps_url = f"https://www.google.com/maps/search/restaurant/@{coords_clean},15z"

            warn_html = f'<div class="net-box-warn"><div class="net-title-warn">⚠️ Ostrzeżenie</div><div class="net-text" style="color:#fbbf24; font-weight:600;">{k["czerwona_strefa_ostrzezenie"]}</div></div>' if pd.notna(k.get('czerwona_strefa_ostrzezenie')) and str(k['czerwona_strefa_ostrzezenie']).strip() != "" else ""
            desc_html = f'<div style="margin-top: 6px; background-color:rgba(255,255,255,0.03); border:1px solid #1e293b; border-radius:8px; padding:8px; font-size:9.5pt; color:#cbd5e1;">{k["opis"]}</div>' if pd.notna(k.get('opis')) and str(k.get('opis')).strip() != "" else ""

            tytul_expandera = f"🕒 {okienko}  |  📌 {krok_nazwa}" if okienko else f"📌 {krok_nazwa}"

            with st.expander(tytul_expandera):
                card_html = f'''<div style="background-color:#111e38; padding:4px;"><div style="display:flex; align-items:center; gap:6px; margin-bottom:6px;"><div style="background-color:#f43f5e; color:white; border-radius:50%; width:24px; height:24px; display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:9.5pt;">{krok_num}</div><span style="font-size:11pt; font-weight:800; color:#38bdf8;">{krok_nazwa}</span></div>{desc_html}<div style="display: flex; gap: 6px; margin-top: 8px; margin-bottom: 8px;"><a href="{gps_maps_url}" target="_blank" class="custom-nav-btn" style="padding:4px 0; font-size:15px;" title="GPS">📍</a><a href="{google_search_url}" target="_blank" class="custom-nav-btn" style="padding:4px 0; font-size:15px;" title="Google">🔍</a><a href="{sklep_maps_url}" target="_blank" class="custom-nav-btn" style="padding:4px 0; font-size:15px;" title="Sklep">🛒</a><a href="{resto_maps_url}" target="_blank" class="custom-nav-btn" style="padding:4px 0; font-size:15px;" title="Restauracja">🍽️</a><a href="?tab=zabytek&place={miejsce_id_cel}" target="_self" class="custom-nav-btn" style="padding:4px 0; font-size:15px;" title="Opis">📝</a></div><div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 6px;"><div class="net-box" style="margin-bottom:0;"><div class="net-title">⏱️ Harmonogram</div><div style="font-size:10.5pt; font-weight:700; color:#f8fafc;">{k["okienko_zwiedzania"]}</div></div><div class="net-box-evac" style="margin-bottom:0;"><div class="net-title-evac">🚨 Ewakuacja</div><div style="font-size:10.5pt; font-weight:700; color:#f87171;">{k.get("godzina_ewakuacji", "Brak")}</div></div></div><div class="net-box"><div class="net-title">🎯 Taktyka</div><div class="net-text">{k["podsumowanie_taktyki"]}</div></div><div class="net-box-regen" style="margin-bottom:0;"><div class="net-title-regen">🌿 Regeneracja</div><div class="net-text" style="color:#4ade80;">{k["strefa_luzu_i_regeneracji"]}</div></div>{warn_html}</div>'''
                st.markdown(card_html, unsafe_allow_html=True)

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button(f"🎯 Ustaw aktywną", key=f"btn_akt_{wycieczka_id}", use_container_width=True):
                ustaw_aktywna_wycieczke_id(wycieczka_id)
                st.success("Ustawiono!")
                st.rerun()
        with col_btn2:
            is_odbyta = int(w_gen.get('odbyta', 0)) == 1
            if is_odbyta:
                st.markdown('<div style="background-color:rgba(34,197,94,0.1); color:#4ade80; padding:6px; border-radius:8px; text-align:center; font-weight:bold; border:1px solid rgba(34,197,94,0.3); font-size:9.5pt;">✨ Przebyta</div>', unsafe_allow_html=True)
            else:
                if st.button(f"✅ Oznacz przebytą", key=f"btn_odbyte_{wycieczka_id}", use_container_width=True):
                    oznacz_wycieczke_i_miejsca_jako_odbyte(wycieczka_id)
                    st.success("Oznaczono!")
                    st.rerun()

domek_maps_url = "https://www.google.com/maps/search/?api=1&query=35.5914,24.0918"
sklep_maps_url = "https://www.google.com/maps/search/?api=1&query=35.586222,24.091861"
active_chat_sidebar = "active" if st.session_state.active_tab == "chat" else ""

with st.sidebar:
    st.markdown("### 🧭 Szybka Nawigacja")
    st.markdown(f"""
        <div class="custom-nav-bar">
            <a href="{sklep_maps_url}" target="_blank" class="custom-nav-btn" title="Sklep">🛒</a>
            <a href="{domek_maps_url}" target="_blank" class="custom-nav-btn" title="Domek">🏠</a>
            <a href="?tab=chat" target="_self" class="custom-nav-btn {active_chat_sidebar}" title="Asystent AI">💬</a>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.header("⚙️ Ustawienia Asystenta")
    gemini_api_key = st.text_input("Klucz API Google Gemini", type="password", key="api_key_input")
    
    dostepne_modele = [
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.6-flash"
    ]
    wybrany_model = st.selectbox("Wybierz model AI", options=dostepne_modele, index=0)
    st.markdown("---")

active_zabytek = "active" if st.session_state.active_tab == "zabytek" else ""
active_map = "active" if st.session_state.active_tab == "map" else ""
active_route = "active" if st.session_state.active_tab == "route" else ""

st.markdown(f"""
    <div class="bottom-nav-container">
        <a href="?tab=zabytek" target="_self" class="bottom-nav-btn {active_zabytek}">🏛️</a>
        <a href="?tab=map" target="_self" class="bottom-nav-btn {active_map}">🗺️</a>
        <a href="?tab=route" target="_self" class="bottom-nav-btn {active_route}">🚗</a>
    </div>
""", unsafe_allow_html=True)

st.markdown("<div style='margin-bottom: 50px;'></div>", unsafe_allow_html=True)

if st.session_state.active_tab == "chat":
    m_chat = folium.Map(location=[35.3, 24.5], zoom_start=9, tiles="CartoDB dark_matter")
    dodaj_marker_domku(m_chat)
    
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
                
                icon_html = f'<div style="background-color:{bg_color};color:white;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:bold;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);">{num}</div>'
                icon = folium.DivIcon(html=icon_html, icon_size=(26, 26), icon_anchor=(13, 13))
                folium.Marker([lat, lon], icon=icon, tooltip=f"{num}. {name}").add_to(m_chat)
            except:
                pass
    st_folium(m_chat, width="100%", height=300, returned_objects=[])
    renderuj_sekcje_czatu_ai("tab_chat")

elif st.session_state.active_tab == "zabytek":
    svg_logo = """
    <svg width="40" height="40" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="100" height="100" rx="20" fill="#0b1329"/>
        <path d="M30 65C30 50 45 45 50 35C55 45 70 50 70 65" stroke="#38bdf8" stroke-width="6" stroke-linecap="round"/>
        <circle cx="50" cy="30" r="12" fill="#2dd4bf"/>
        <path d="M42 45L58 45" stroke="#f43f5e" stroke-width="6" stroke-linecap="round"/>
    </svg>
    """
    svg_base64 = base64.b64encode(svg_logo.encode("utf-8")).decode("utf-8")

    st.markdown(f"""
        <div class="adventure-header">
            <img src="data:image/svg+xml;base64,{svg_base64}" style="width:40px;height:40px;border-radius:8px;">
            <div>
                <div class="adventure-title-text">OdyssAi • Kreta</div>
                <div class="adventure-subtitle">Przewodnik wyprawy z duchem przygody</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    list_options_zabytek = ["-- Wybierz miejsce z listy lub mapy --"] + list(df_miejsca['numer_miejsca'].astype(str) + ". " + df_miejsca['nazwa'])
    curr_zabytek_idx = 0
    if st.session_state.active_place_id and st.session_state.active_place_id.isdigit():
        matching_z = [i for i, opt in enumerate(list_options_zabytek) if opt.startswith(st.session_state.active_place_id + ".")]
        if matching_z:
            curr_zabytek_idx = matching_z[0]

    wybrany_zabytek_main = st.selectbox("Wybierz miejsce:", options=list_options_zabytek, index=curr_zabytek_idx, key="main_zabytek_sb")
    if wybrany_zabytek_main != "-- Wybierz miejsce z listy lub mapy --":
        chosen_id_m = wybrany_zabytek_main.split(". ")[0]
        if chosen_id_m != st.session_state.active_place_id:
            st.session_state.active_place_id = chosen_id_m
            st.rerun()

    # --- POPRAWKA UX: Szczegóły miejsca wyświetlane od razu POD selectboxem (z automatu widoczne na telefonie) ---
    if st.session_state.active_place_id:
        place_row = df_miejsca[df_miejsca['numer_miejsca'] == str(st.session_state.active_place_id)]
        
        if not place_row.empty:
            p = place_row.iloc[0]
            numer_m = str(p['numer_miejsca'])
            tytul_miejsca = f"{numer_m}. {str(p['nazwa']).upper()}"
            google_search_url = f"https://www.google.com/search?q={p['nazwa']} Kreta"
            
            st.markdown(f"""
            <div id="selected-place-details" style="background-color: #111e38; border: 2px solid #38bdf8; border-radius: 12px; padding: 14px; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(56,189,248,0.2);">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                    <span style="font-size: 13pt; font-weight: 800; color: #38bdf8;">{tytul_miejsca}</span>
                    <a href="{google_search_url}" target="_blank" style="text-decoration: none; font-size: 16px; background-color: #1e293b; border: 1px solid #334155; border-radius: 50%; width: 34px; height: 34px; display: flex; align-items: center; justify-content: center; color: #f8fafc;" title="Szukaj w Google">🔍</a>
                </div>
            """, unsafe_allow_html=True)

            is_visited = int(p.get('odwiedzone', 0)) == 1
            if is_visited:
                st.markdown("""
                <div style="text-align: center; margin-bottom: 8px;">
                    <span style="background-color: rgba(34,197,94,0.1); color: #4ade80; padding: 3px 10px; border-radius: 10px; font-weight: bold; border: 1px solid rgba(34,197,94,0.3); font-size: 9.5pt;">
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
                <div style="display: flex; align-items: center; justify-content: space-between; margin: 10px 0 8px 0;">
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <div style="background-color: #38bdf8; color: #0b1329; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items:center; justify-content:center; font-size: 11px; font-weight: bold;">📍</div>
                        <span style="font-size: 9pt; font-weight: 700; color: #94a3b8; text-transform: uppercase;">Lokalizacja GPS</span>
                    </div>
                    <a href="{gps_maps_url}" target="_blank" style="background-color: #38bdf8; color: #0b1329; padding: 4px 12px; border-radius: 16px; font-size: 9pt; font-weight: 700; text-decoration: none;">NAWIGUJ ➔</a>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px;">
                    <div style="background-color: #0b1329; border: 1px solid #1e293b; border-radius: 8px; padding: 8px;">
                        <div style="font-size: 8pt; font-weight: 600; color: #94a3b8; text-transform: uppercase; margin-bottom: 2px;">Dojazd (Stravros)</div>
                        <div style="font-size: 10pt; font-weight: 700; color: #f8fafc;">{p['czas_dojazdu']}</div>
                    </div>
                    <div style="background-color: #0b1329; border: 1px solid #1e293b; border-radius: 8px; padding: 8px;">
                        <div style="font-size: 8pt; font-weight: 600; color: #94a3b8; text-transform: uppercase; margin-bottom: 2px;">Godziny otwarcia</div>
                        <div style="font-size: 10pt; font-weight: 700; color: #f8fafc;">{p['godziny_otwarcia']}</div>
                    </div>
                    <div style="background-color: #0b1329; border: 1px solid #1e293b; border-radius: 8px; padding: 8px;">
                        <div style="font-size: 8pt; font-weight: 600; color: #94a3b8; text-transform: uppercase; margin-bottom: 2px;">Najlepsza pora</div>
                        <div style="font-size: 9.5pt; font-weight: 700; color: #f8fafc;">{p['najlepsza_pora']}</div>
                    </div>
                    <div style="background-color: #0b1329; border: 1px solid #1e293b; border-radius: 8px; padding: 8px;">
                        <div style="font-size: 8pt; font-weight: 600; color: #94a3b8; text-transform: uppercase; margin-bottom: 2px;">Czas zwiedzania</div>
                        <div style="font-size: 10pt; font-weight: 700; color: #f8fafc;">{p['orientacyjny_czas']}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            koszt_val = p.get('koszt', '')
            if pd.notna(koszt_val) and str(koszt_val).strip() != "":
                st.markdown(f"""
                <div style="background-color: #111e38; border: 1px solid #1e293b; border-radius: 10px; padding: 10px; margin-bottom: 8px; display: flex; align-items: flex-start; gap: 8px;">
                    <div style="font-size: 16px;">💶👥</div>
                    <div>
                        <div style="font-size: 8.5pt; font-weight: 600; color: #94a3b8; text-transform: uppercase; margin-bottom: 2px;">Koszt dla rodziny 2+2:</div>
                        <div style="font-size: 10pt; color: #f8fafc; font-weight: 500;">{koszt_val}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            akcja_val = p.get('konieczna_akcja', '')
            if pd.notna(akcja_val) and str(akcja_val).strip() != "Brak" and str(akcja_val).strip() != "":
                st.markdown(f"""
                <div style="background-color: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); border-radius: 10px; padding: 10px; margin-bottom: 8px; display: flex; align-items: flex-start; gap: 8px;">
                    <div style="font-size: 16px;">⚠️</div>
                    <div>
                        <div style="font-size: 8.5pt; font-weight: 600; color: #f87171; text-transform: uppercase; margin-bottom: 2px;">Konieczna akcja</div>
                        <div style="font-size: 10pt; color: #f8fafc; font-weight: 500;">{akcja_val}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            adhd_val = p.get('trudnosc_adhd', '')
            meltdown_val = p.get('potencjal_meltdownu', '')
            strategie_val = p.get('strategie_meltdown', '')

            html_wyzwania = f"""<div style="background-color: #111e38; border: 1px solid #1e293b; border-radius: 10px; padding: 12px; margin-top: 8px; margin-bottom: 8px;"><div style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;"><span style="font-size: 16px;">🐂</span><span style="font-size: 10pt; font-weight: 800; color: #38bdf8; text-transform: uppercase;">Wyzwania & Rady ADHD</span></div><div style="margin-bottom: 8px;"><div style="font-size: 8.5pt; font-weight: 600; color: #94a3b8; text-transform: uppercase; margin-bottom: 2px;">🧠 Trudności ADHD:</div><div style="font-size: 9.5pt; color: #cbd5e1; line-height: 1.35;">{adhd_val}</div></div><div style="margin-bottom: 8px;"><div style="font-size: 8.5pt; font-weight: 600; color: #f87171; text-transform: uppercase; margin-bottom: 2px;">⚡ Potencjał meltdownu:</div><div style="font-size: 9.5pt; color: #cbd5e1; line-height: 1.35;">{meltdown_val}</div></div><div><div style="font-size: 8.5pt; font-weight: 600; color: #4ade80; text-transform: uppercase; margin-bottom: 2px;">🛡️ Strategie ratunkowe:</div><div style="font-size: 9.5pt; color: #cbd5e1; line-height: 1.35;">{strategie_val}</div></div></div>"""
            st.markdown(html_wyzwania, unsafe_allow_html=True)
            
            if pd.notna(p['zadania_dla_dzieci']) and str(p['zadania_dla_dzieci']).strip() != "":
                with st.expander("🧒 Zadania dla dzieci w tym miejscu"):
                    renderuj_zadania_dzieci_expander(p['zadania_dla_dzieci'], p['numer_miejsca'])
            
            polaczenie_tekst = str(p['najlepiej_polaczyc'])
            def zamien_na_link(match):
                nr_miejsca = match.group(1)
                return f'<a href="?tab=zabytek&place={nr_miejsca}" target="_self" style="color: #38bdf8; font-weight: bold; text-decoration: underline;">Miejsce {nr_miejsca}</a>'
            
            polaczenie_przetworzone = re.sub(r'Miejsce\s+(\d+)', zamien_na_link, polaczenie_tekst, flags=re.IGNORECASE)
            st.markdown(f"**🔗 Najlepiej połączyć z:** {polaczenie_przetworzone}", unsafe_allow_html=True)

    # Mapa przeniesiona pod karty szczegółów
    st.markdown("---")
    st.markdown("### 🗺️ Mapa lokalizacji")
    m = folium.Map(location=[35.3, 24.5], zoom_start=9, tiles="CartoDB dark_matter")
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
                
                icon_html = f'<div style="background-color:{bg_color};color:white;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:bold;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);">{num}</div>'
                icon = folium.DivIcon(html=icon_html, icon_size=(26, 26), icon_anchor=(13, 13))
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

    renderuj_sekcje_czatu_ai("tab_zabytek")

elif st.session_state.active_tab == "map":
    st.markdown("""
        <div class="adventure-header">
            <div style="font-size:24px;">🗺️</div>
            <div>
                <div class="adventure-title-text">OdyssAi • Mapa Wypraw</div>
                <div class="adventure-subtitle">Eksploruj szlaki i punkty strategiczne</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    opcje_wycieczek_lista = ["-- Wybierz wycieczkę lub zobacz mapę wszystkich miejsc --"] + wycieczki_options
    wybrana_mapa_sb = st.selectbox("", options=opcje_wycieczek_lista, key="map_wycieczka_select", label_visibility="collapsed")
    
    if "last_clicked_place_info" in st.session_state and st.session_state.last_clicked_place_info:
        st.markdown(st.session_state.last_clicked_place_info)

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
                    
                    icon_html = f'<div style="background-color:{bg_color};color:white;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:bold;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);">{num}</div>'
                    icon = folium.DivIcon(html=icon_html, icon_size=(26, 26), icon_anchor=(13, 13))
                    folium.Marker([lat, lon], icon=icon, tooltip=f"{num}. {name}").add_to(m_all)
                except:
                    pass
        
        map_all_data = st_folium(m_all, width="100%", height=340)
        
        if map_all_data and map_all_data.get("last_object_clicked_tooltip"):
            clicked_tooltip = map_all_data["last_object_clicked_tooltip"]
            if "." in clicked_tooltip:
                klikniety_numer_miejsca = clicked_tooltip.split(".")[0].strip()
                
                conn = sqlite3.connect('odyssai.db')
                powiazane_kroki = pd.read_sql('''
                    SELECT DISTINCT k.id_wycieczki, w.tytul_wycieczki 
                    FROM krok_wycieczki k 
                    JOIN wycieczka w ON k.id_wycieczki = w.id 
                    WHERE (k.krok_wycieczki = ? OR k.nazwa LIKE ?) AND w.odbyta = 0
                ''', conn, params=(klikniety_numer_miejsca, f"%{clicked_tooltip.split('.')[1].strip()}%"))
                conn.close()
                
                info_tekst = ""
                if not powiazane_kroki.empty:
                    info_tekst = f"📌 Miejsce **{clicked_tooltip}** znajduje się w aktywnych wycieczkach:\n"
                    for _, row_w in powiazane_kroki.iterrows():
                        info_tekst += f"- **Wycieczka #{row_w['id_wycieczki']}**: {row_w['tytul_wycieczki']}\n"
                else:
                    info_tekst = f"📌 Miejsce **{clicked_tooltip}** nie jest obecnie przypisane do żadnej aktywnej wycieczki."
                
                if st.session_state.get("last_clicked_text") != clicked_tooltip:
                    st.session_state.last_clicked_text = clicked_tooltip
                    st.session_state.last_clicked_place_info = info_tekst
                    st.rerun()
    else:
        if "last_clicked_place_info" in st.session_state:
            st.session_state.last_clicked_text = None
            st.session_state.last_clicked_place_info = None
            
        if wybrana_mapa_sb:
            wybrana_id = wybrana_mapa_sb.split(". ")[0]
            st.markdown("---")
            renderuj_karte_wycieczki(wybrana_id, pokaz_mape=True)

    renderuj_sekcje_czatu_ai("tab_map")

elif st.session_state.active_tab == "route":
    st.markdown("""
        <div class="adventure-header">
            <div style="font-size:24px;">🚗</div>
            <div>
                <div class="adventure-title-text">OdyssAi • Trasa Dnia</div>
                <div class="adventure-subtitle">Kontrola misji w czasie rzeczywistym</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    aktualne_id = pobierz_aktywna_wycieczke_id()
    
    conn = sqlite3.connect('odyssai.db')
    curr_w_check = pd.read_sql('SELECT odbyta FROM wycieczka WHERE id = ?', conn, params=(str(aktualne_id),))
    conn.close()
    
    if not curr_w_check.empty and int(curr_w_check.iloc[0]['odbyta']) == 1:
        st.info("✨ Aktualnie ustawiona wycieczka została ukończona.")
    else:
        renderuj_karte_wycieczki(aktualne_id, pokaz_mape=False)

    renderuj_sekcje_czatu_ai("tab_route")
