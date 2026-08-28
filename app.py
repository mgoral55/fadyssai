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

# --- 1. KONFIGURACJA STRONY I STYL PERGAMINU (MOBILE FIRST / UX ADHD) ---
st.set_page_config(page_title="Fadyssai - Kreta", layout="centered", page_icon="🧭")

st.markdown("""
    <style>
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 70px !important;
    }
    .stApp {
        background-color: #f4ecdf;
        color: #3b2f2f;
    }
    [data-testid="stSidebar"] {
        background-color: #e6ded1;
        color: #3b2f2f !important;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
        color: #3b2f2f !important;
    }
    h3 {
        color: #663223;
        font-family: Georgia, serif;
    }
    .bottom-nav-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background-color: #e6ded1;
        border-top: 2px solid #b89b82;
        padding: 8px 12px;
        display: flex;
        justify-content: space-around;
        gap: 6px;
        z-index: 99999;
        box-shadow: 0 -2px 10px rgba(0,0,0,0.15);
    }
    .bottom-nav-btn {
        flex: 1;
        background-color: #fcf8f2;
        border: 1px solid #b89b82;
        color: #663223;
        padding: 8px 0;
        text-align: center;
        border-radius: 8px;
        font-size: 20px;
        text-decoration: none;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        cursor: pointer;
    }
    .bottom-nav-btn:hover {
        background-color: #d4c8b8;
        border-color: #663223;
    }
    .bottom-nav-btn.active {
        background-color: #b89b82;
        color: white;
        border-color: #663223;
    }
    .custom-nav-bar {
        display: flex;
        justify-content: space-between;
        gap: 6px;
        width: 100%;
        margin-bottom: 0.5rem;
    }
    .custom-nav-btn {
        flex: 1;
        background-color: #e6ded1;
        border: 1px solid #b89b82;
        color: #663223;
        padding: 6px 0;
        text-align: center;
        border-radius: 8px;
        font-size: 18px;
        text-decoration: none;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        cursor: pointer;
    }
    .custom-nav-btn:hover {
        background-color: #d4c8b8;
        border-color: #663223;
    }
    .custom-nav-btn.active {
        background-color: #b89b82;
        color: white;
        border-color: #663223;
    }
    .sidebar-nav-bar {
        display: flex;
        justify-content: space-between;
        gap: 4px;
        width: 100%;
        margin-bottom: 0.5rem;
    }
    .sidebar-nav-btn {
        flex: 1;
        background-color: #e6ded1;
        border: 1px solid #b89b82;
        color: #663223;
        padding: 6px 0;
        text-align: center;
        border-radius: 6px;
        font-size: 16px;
        text-decoration: none;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        cursor: pointer;
    }
    .sidebar-nav-btn:hover {
        background-color: #d4c8b8;
        border-color: #663223;
    }
    .sidebar-nav-btn.active {
        background-color: #b89b82;
        color: white;
        border-color: #663223;
    }
    .logistics-card {
        background-color: #fcf8f2;
        border: 1.5px solid #b89b82;
        border-radius: 12px;
        padding: 12px;
        text-align: left;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        margin-bottom: 8px;
    }
    .logistics-title {
        font-size: 9pt;
        font-weight: bold;
        color: #8c6a53;
        margin-bottom: 4px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .logistics-value {
        font-size: 12pt;
        font-weight: bold;
        color: #3b2f2f;
    }
    .net-box {
        background-color: #fcf8f2;
        border: 1.5px solid #b89b82;
        border-radius: 12px;
        padding: 12px;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .net-box-evac {
        background-color: #fdf2f2;
        border: 1.5px solid #f5c6cb;
        border-radius: 12px;
        padding: 12px;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .net-box-regen {
        background-color: #f2f9f4;
        border: 1.5px solid #c3e6cb;
        border-radius: 12px;
        padding: 12px;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .net-box-warn {
        background-color: #fcf0f0;
        border: 1.5px solid #f8d7da;
        border-radius: 12px;
        padding: 12px;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .net-title {
        font-size: 9pt;
        font-weight: bold;
        color: #8c6a53;
        margin-bottom: 4px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .net-title-evac {
        font-size: 9pt;
        font-weight: bold;
        color: #a71d2a;
        margin-bottom: 4px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .net-title-regen {
        font-size: 9pt;
        font-weight: bold;
        color: #155724;
        margin-bottom: 4px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .net-title-warn {
        font-size: 9pt;
        font-weight: bold;
        color: #721c24;
        margin-bottom: 4px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .net-text {
        font-size: 10.5pt;
        color: #3b2f2f;
    }
    .antique-header {
        background: linear-gradient(to right, #d4c8b8, #e6ded1, #d4c8b8);
        border: 2px solid #b89b82;
        border-radius: 8px;
        padding: 12px 16px;
        text-align: center;
        color: #663223;
        font-family: Georgia, serif;
        font-size: 18px;
        font-weight: bold;
        box-shadow: 0 2px 5px rgba(0,0,0,0.15);
        margin-bottom: 10px;
        letter-spacing: 1px;
    }
    .stButton > button {
        background-color: #e6ded1 !important;
        color: #5c2c16 !important;
        border: 1px solid #8c6a53 !important;
        font-weight: 600 !important;
    }
    .stButton > button:hover {
        background-color: #d4c8b8 !important;
        color: #3b1c0e !important;
        border-color: #5c2c16 !important;
    }
    iframe {
        margin-top: -10px !important;
    }
    [data-testid="stSidebar"] input {
        background-color: #fcf8f2 !important;
        color: #3b2f2f !important;
        border: 1px solid #b89b82 !important;
    }
    [data-testid="stChatMessage"] {
        background-color: #e6ded1 !important;
        border: 1px solid #b89b82 !important;
        border-radius: 12px !important;
        color: #3b2f2f !important;
    }
    [data-testid="stChatMessage"] p, [data-testid="stChatMessage"] span, [data-testid="stChatMessage"] div {
        color: #3b2f2f !important;
    }
    .stChatInputContainer {
        background-color: #e6ded1 !important;
        border-radius: 12px !important;
        border: 1px solid #b89b82 !important;
    }
    .stChatInputContainer textarea {
        color: #3b2f2f !important;
        background-color: #fcf8f2 !important;
    }
    </style>
""", unsafe_allow_html=True)

DOMEK_LAT = 35.5914
DOMEK_LON = 24.0918

def init_db():
    conn = sqlite3.connect('fadyssai.db')
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
    conn = sqlite3.connect('fadyssai.db')
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
    conn = sqlite3.connect('fadyssai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT Base FROM miejsca WHERE numer_miejsca = ?', (str(numer_miejsca),))
    res = cursor.fetchone()
    if res and str(res[0]).lower() == 'true':
        conn.close()
        return f"OSTRZEŻENIE: Miejsce nr {numer_miejsca} pochodzi z bazy bazowej (CSV) i ma ustawioną flagę Base=true. Modyfikacja tego miejsca przez AI jest zablokowana!"

    if opis:
        cursor.execute('UPDATE miejsca SET opis = ? WHERE numer_miejsca = ?', (opis, str(numer_miejsca)))
    if konieczna_akcja:
        cursor.execute('UPDATE miejsca SET konieczna_akcja = ? WHERE numer_miejsca = ?', (konieczna_akcja, str(numer_miejsca)))
    conn.commit()
    conn.close()
    return f"Miejsce nr {numer_miejsca} w bazie Fadyssai zostało zaktualizowane!"

def usun_miejsce(numer_miejsca):
    conn = sqlite3.connect('fadyssai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT Base FROM miejsca WHERE numer_miejsca = ?', (str(numer_miejsca),))
    res = cursor.fetchone()
    if res and str(res[0]).lower() == 'true':
        conn.close()
        return f"OSTRZEŻENIE: Miejsce nr {numer_miejsca} pochodzi z bazy bazowej (CSV) i ma ustawioną flagę Base=true. Usuwanie tego miejsca jest absolutnie zablokowane!"
    
    cursor.execute('DELETE FROM miejsca WHERE numer_miejsca = ?', (str(numer_miejsca),))
    conn.commit()
    conn.close()
    return f"Miejsce nr {numer_miejsca} zostało usunięte z bazy."

def utworz_nowa_wycieczke(id, tytul_wycieczki, calosciowy_opis_wycieczki, calosciowa_taktyka_dnia, calkowity_czas_wycieczki_godziny, szacowana_godzina_powrotu, pobudka, czas_wyjazdu):
    conn = sqlite3.connect('fadyssai.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO wycieczka (id, tytul_wycieczki, calosciowy_opis_wycieczki, calosciowa_taktyka_dnia, calkowity_czas_wycieczki_godziny, szacowana_godzina_powrotu, pobudka, czas_wyjazdu, odbyta)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
    ''', (str(id), tytul_wycieczki, calosciowy_opis_wycieczki, calosciowa_taktyka_dnia, str(calkowity_czas_wycieczki_godziny), szacowana_godzina_powrotu, pobudka, czas_wyjazdu))
    conn.commit()
    conn.close()
    return f"Nowa wycieczka '{tytul_wycieczki}' (ID: {id}) została utworzona w bazie Fadyssai!"

def edytuj_wycieczke(id, tytul_wycieczki=None, calosciowy_opis_wycieczki=None, calosciowa_taktyka_dnia=None, szacowana_godzina_powrotu=None, pobudka=None, czas_wyjazdu=None):
    conn = sqlite3.connect('fadyssai.db')
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
    conn = sqlite3.connect('fadyssai.db')
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
    return f"Wycieczka #{id_wycieczki} wraz z krokami i checklistami została całkowicie usunięta z bazy."

def dodaj_krok_do_wycieczki(id_wycieczki, krok_wycieczki, nazwa, wspolrzedne, okienko_zwiedzania, godzina_ewakuacji, czerwona_strefa_ostrzezenie, strefa_luzu_i_regeneracji, podsumowanie_taktyki, potencjal_meltdownu, strategie_meltdown, opis):
    conn = sqlite3.connect('fadyssai.db')
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
    return f"Dodano krok nr {krok_wycieczki} ({nazwa}) do wycieczki #{id_wycieczki} w bazie!"

def edytuj_krok_w_wycieczce(id_wycieczki, krok_wycieczki, nazwa=None, okienko_zwiedzania=None, godzina_ewakuacji=None, czerwona_strefa_ostrzezenie=None, strefa_luzu_i_regeneracji=None, podsumowanie_taktyki=None, potencjal_meltdownu=None, strategie_meltdown=None, opis=None):
    conn = sqlite3.connect('fadyssai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM krok_wycieczki WHERE id_wycieczki = ? AND (krok_wycieczki = ? OR nazwa LIKE ?)', (str(id_wycieczki), str(krok_wycieczki), f"%{krok_wycieczki}%"))
    res = cursor.fetchone()
    if not res:
        conn.close()
        return f"Nie znaleziono kroku {krok_wycieczki} dla wycieczki #{id_wycieczki}."
    
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
    return f"Krok {krok_wycieczki} w wycieczce #{id_wycieczki} został zaktualizowany."

def usun_krok_z_wycieczki(id_wycieczki, krok_wycieczki):
    conn = sqlite3.connect('fadyssai.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM krok_wycieczki WHERE id_wycieczki = ? AND (krok_wycieczki = ? OR nazwa LIKE ?)', (str(id_wycieczki), str(krok_wycieczki), f"%{krok_wycieczki}%"))
    conn.commit()
    conn.close()
    return f"Usunięto krok {krok_wycieczki} z wycieczki #{id_wycieczki}."

def dodaj_element_checklisty(id_wycieczki, typ, nazwa, ilosc="1"):
    conn = sqlite3.connect('fadyssai.db')
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
    return f"Dodano do checklisty ({typ}) wycieczki #{id_wycieczki}: {nazwa} (ilość: {ilosc})"

def edytuj_element_checklisty(id_wycieczki, typ, stara_nazwa, nowa_nazwa=None, nowa_ilosc=None):
    conn = sqlite3.connect('fadyssai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM checklist WHERE id_wycieczki = ? AND typ = ?', (str(id_wycieczki), typ))
    res = cursor.fetchone()
    if not res:
        conn.close()
        return f"Nie znaleziono checklisty typu {typ} dla wycieczki #{id_wycieczki}."
    chl_id = res[0]
    
    cursor.execute('SELECT id FROM checklist_item WHERE id_checklisty = ? AND nazwa LIKE ?', (chl_id, f"%{stara_nazwa}%"))
    item_res = cursor.fetchone()
    if not item_res:
        conn.close()
        return f"Nie znaleziono elementu '{stara_nazwa}' w checkliście."
    item_id = item_res[0]
    
    if nowa_nazwa:
        cursor.execute('UPDATE checklist_item SET nazwa = ? WHERE id = ?', (nowa_nazwa, item_id))
    if nowa_ilosc:
        cursor.execute('UPDATE checklist_item SET ilosc = ? WHERE id = ?', (str(nowa_ilosc), item_id))
        
    conn.commit()
    conn.close()
    return f"Zaktualizowano element '{stara_nazwa}' w checkliście wycieczki #{id_wycieczki}."

def usun_element_checklisty(id_wycieczki, typ, nazwa):
    conn = sqlite3.connect('fadyssai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM checklist WHERE id_wycieczki = ? AND typ = ?', (str(id_wycieczki), typ))
    res = cursor.fetchone()
    if not res:
        conn.close()
        return f"Nie znaleziono checklisty."
    chl_id = res[0]
    cursor.execute('DELETE FROM checklist_item WHERE id_checklisty = ? AND nazwa LIKE ?', (chl_id, f"%{nazwa}%"))
    conn.commit()
    conn.close()
    return f"Usunięto element '{nazwa}' z checklisty wycieczki #{id_wycieczki}."

def pobierz_wszystkie_miejsca():
    conn = sqlite3.connect('fadyssai.db')
    df = pd.read_sql('SELECT * FROM miejsca', conn)
    conn.close()
    return df

def pobierz_aktywna_wycieczke_id():
    conn = sqlite3.connect('fadyssai.db')
    cursor = conn.cursor()
    cursor.execute('SELECT aktualne_id_wycieczki FROM aktywna_wycieczka WHERE id = 1')
    res = cursor.fetchone()
    conn.close()
    return str(res[0]) if res else "1"

def ustaw_aktywna_wycieczke_id(wycieczka_id):
    conn = sqlite3.connect('fadyssai.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE aktywna_wycieczka SET aktualne_id_wycieczki = ? WHERE id = 1', (str(wycieczka_id),))
    conn.commit()
    conn.close()

def pobierz_skrocone_opcje_wycieczek():
    conn = sqlite3.connect('fadyssai.db')
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
    tekst = "Jesteś asystentem podróży Fadyssai na Kretę.\n--- AKTUALNA BAZA DANYCH W SQLITE ---\n"
    conn = sqlite3.connect('fadyssai.db')
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
            base_flag = r.get('Base', 'false')
            tekst += f"- Nr {r['numer_miejsca']}: {r['nazwa']} (Typ: {r['typ']}, Odwiedzone: {r['odwiedzone']}, Base: {base_flag}, Dojazd: {r['czas_dojazdu']}, Koszt: {r['koszt']})\n"
    if not wycieczki_df.empty:
        tekst += "\nWycieczki:\n"
        for _, w in wycieczki_df.iterrows():
            if int(w.get('odbyta', 0)) == 1:
                continue
            tekst += f"- Wycieczka #{w['id']}: {w['tytul_wycieczki']} (Odbyta: {w['odbyta']}) | Opis: {w['calosciowy_opis_wycieczki']}\n"
    if not kroki_df.empty:
        tekst += "\nKroki wycieczek:\n"
        for _, k in kroki_df.iterrows():
            tekst += f"- Wycieczka #{k['id_wycieczki']}, Krok {k['krok_wycieczki']}: {k['nazwa']} (Okienko: {k['okienko_zwiedzania']})\n"
    if not checklisty_df.empty:
        tekst += "\nChecklisty:\n"
        for _, cl in checklisty_df.iterrows():
            tekst += f"- Wycieczka #{cl['id_wycieczki']} [{cl['typ']}]: {cl['nazwa']} (ilość: {cl['ilosc']})\n"

    return tekst

def pobierz_trase_osrm(punkty):
    if len(punkty) < 2:
        return []
    wsp_str = ";".join([f"{p[1]},{p[0]}" for p in punkty])
    url = f"http://router.project-osrm.org/route/v1/driving/{wsp_str}?overview=full&geometries=geojson"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'FadyssaiApp/1.0'})
        with urllib.request.urlopen(req, timeout=2) as response:
            data = json.loads(response.read().decode())
            if 'routes' in data and len(data['routes']) > 0:
                geojson_coords = data['routes'][0]['geometry']['coordinates']
                return [[c[1], c[0]] for c in geojson_coords]
    except:
        pass
    return [[p[0], p[1]] for p in punkty]

def dodaj_marker_domku(m):
    domek_icon_html = '<div style="background-color:black;color:white;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:14px;border:2px solid white;box-shadow:0 2px 5px rgba(0,0,0,0.5);">🏠</div>'
    domek_icon = folium.DivIcon(html=domek_icon_html, icon_size=(28, 28), icon_anchor=(14, 14))
    folium.Marker([DOMEK_LAT, DOMEK_LON], icon=domek_icon, tooltip="Nasz Domek").add_to(m)

aktualizuj_tool = types.FunctionDeclaration(
    name="aktualizuj_miejsce",
    description="Aktualizuje informacje o wybranym miejscu na Krecie na podstawie numeru miejsca. UWAGA: Miejsca z flagą Base=true nie mogą być modyfikowane.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "numer_miejsca": types.Schema(type=types.Type.STRING, description="Numer miejsca, np. '1'"),
            "opis": types.Schema(type=types.Type.STRING, description="Nowy opis miejsca"),
            "konieczna_akcja": types.Schema(type=types.Type.STRING, description="Nowa konieczna akcja"),
        },
        required=["numer_miejsca"]
    ),
)

usun_miejsce_tool = types.FunctionDeclaration(
    name="usun_miejsce",
    description="Usuwa miejsce z bazy danych. UWAGA: Miejsca z flagą Base=true nie mogą być pod żadnym pozorem usuwane.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "numer_miejsca": types.Schema(type=types.Type.STRING, description="Numer miejsca do usunięcia"),
        },
        required=["numer_miejsca"]
    ),
)

utworz_nowa_wycieczke_tool = types.FunctionDeclaration(
    name="utworz_nowa_wycieczke",
    description="Tworzy nową wycieczkę w bazie danych SQLite.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id": types.Schema(type=types.Type.STRING, description="Unikalny numer id wycieczki, np. '3'"),
            "tytul_wycieczki": types.Schema(type=types.Type.STRING, description="Tytuł wycieczki"),
            "calosciowy_opis_wycieczki": types.Schema(type=types.Type.STRING, description="Opis celów i przebiegu wyprawy"),
            "calosciowa_taktyka_dnia": types.Schema(type=types.Type.STRING, description="Strategia unikania tłumów i meltdownów"),
            "calkowity_czas_wycieczki_godziny": types.Schema(type=types.Type.STRING, description="Szacowany czas w godzinach"),
            "szacowana_godzina_powrotu": types.Schema(type=types.Type.STRING, description="Godzina powrotu"),
            "pobudka": types.Schema(type=types.Type.STRING, description="Godzina pobudki"),
            "czas_wyjazdu": types.Schema(type=types.Type.STRING, description="Godzina wyjazdu"),
        },
        required=["id", "tytul_wycieczki", "calosciowy_opis_wycieczki", "calosciowa_taktyka_dnia"]
    ),
)

edytuj_wycieczke_tool = types.FunctionDeclaration(
    name="edytuj_wycieczke",
    description="Edytuje parametry istniejącej wycieczki.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
            "tytul_wycieczki": types.Schema(type=types.Type.STRING, description="Nowy tytuł"),
            "calosciowy_opis_wycieczki": types.Schema(type=types.Type.STRING, description="Nowy opis"),
            "calosciowa_taktyka_dnia": types.Schema(type=types.Type.STRING, description="Nowa taktyka"),
            "szacowana_godzina_powrotu": types.Schema(type=types.Type.STRING, description="Nowa godzina powrotu"),
            "pobudka": types.Schema(type=types.Type.STRING, description="Nowa godzina pobudki"),
            "czas_wyjazdu": types.Schema(type=types.Type.STRING, description="Nowy czas wyjazdu"),
        },
        required=["id"]
    ),
)

usun_wycieczke_tool = types.FunctionDeclaration(
    name="usun_wycieczke",
    description="Usuwa całą wycieczkę wraz z jej krokami i checklistami z bazy danych.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki do usunięcia"),
        },
        required=["id_wycieczki"]
    ),
)

dodaj_krok_tool = types.FunctionDeclaration(
    name="dodaj_krok_do_wycieczki",
    description="Dodaje nowy krok do istniejącej wycieczki w bazie danych.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
            "krok_wycieczki": types.Schema(type=types.Type.STRING, description="Numer kroku"),
            "nazwa": types.Schema(type=types.Type.STRING, description="Nazwa miejsca lub etapu"),
            "wspolrzedne": types.Schema(type=types.Type.STRING, description="Współrzędne GPS"),
            "okienko_zwiedzania": types.Schema(type=types.Type.STRING, description="Okienko czasowe"),
            "godzina_ewakuacji": types.Schema(type=types.Type.STRING, description="Godzina ewakuacji"),
            "czerwona_strefa_ostrzezenie": types.Schema(type=types.Type.STRING, description="Ostrzeżenie"),
            "strefa_luzu_i_regeneracji": types.Schema(type=types.Type.STRING, description="Strefa wyciszenia"),
            "podsumowanie_taktyki": types.Schema(type=types.Type.STRING, description="Taktyka dnia"),
            "potencjal_meltdownu": types.Schema(type=types.Type.STRING, description="Ryzyko meltdowntu"),
            "strategie_meltdown": types.Schema(type=types.Type.STRING, description="Strategie radzenia sobie"),
            "opis": types.Schema(type=types.Type.STRING, description="Opis miejsca"),
        },
        required=["id_wycieczki", "krok_wycieczki", "nazwa", "wspolrzedne"]
    ),
)

edytuj_krok_tool = types.FunctionDeclaration(
    name="edytuj_krok_w_wycieczce",
    description="Edytuje parametry istniejącego kroku wycieczki.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
            "krok_wycieczki": types.Schema(type=types.Type.STRING, description="Numer lub nazwa kroku do edycji"),
            "nazwa": types.Schema(type=types.Type.STRING, description="Nowa nazwa"),
            "okienko_zwiedzania": types.Schema(type=types.Type.STRING, description="Nowe okienko czasowe"),
            "godzina_ewakuacji": types.Schema(type=types.Type.STRING, description="Nowa godzina ewakuacji"),
            "czerwona_strefa_ostrzezenie": types.Schema(type=types.Type.STRING, description="Nowe ostrzeżenie"),
            "strefa_luzu_i_regeneracji": types.Schema(type=types.Type.STRING, description="Nowa strefa luzu"),
            "podsumowanie_taktyki": types.Schema(type=types.Type.STRING, description="Nowe podsumowanie taktyki"),
            "potencjal_meltdownu": types.Schema(type=types.Type.STRING, description="Nowy potencjal meltdownu"),
            "strategie_meltdown": types.Schema(type=types.Type.STRING, description="Nowe strategie meltdown"),
            "opis": types.Schema(type=types.Type.STRING, description="Nowy opis"),
        },
        required=["id_wycieczki", "krok_wycieczki"]
    ),
)

usun_krok_tool = types.FunctionDeclaration(
    name="usun_krok_z_wycieczki",
    description="Usuwa wskazany krok z wycieczki na podstawie ID wycieczki oraz numeru/nazwy kroku.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
            "krok_wycieczki": types.Schema(type=types.Type.STRING, description="Numer lub nazwa kroku do usunięcia"),
        },
        required=["id_wycieczki", "krok_wycieczki"]
    ),
)

dodaj_checklist_tool = types.FunctionDeclaration(
    name="dodaj_element_checklisty",
    description="Dodaje nowy element do checklisty (np. sprzęt lub jedzenie) dla wskazanej wycieczki.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki, np. '1'"),
            "typ": types.Schema(type=types.Type.STRING, description="Typ checklisty, np. 'sprzęt' lub 'jedzenie'"),
            "nazwa": types.Schema(type=types.Type.STRING, description="Nazwa przedmiotu"),
            "ilosc": types.Schema(type=types.Type.STRING, description="Ilość, domyślnie '1'"),
        },
        required=["id_wycieczki", "typ", "nazwa"]
    ),
)

edytuj_checklist_tool = types.FunctionDeclaration(
    name="edytuj_element_checklisty",
    description="Edytuje istniejący element w checkliście wycieczki.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
            "typ": types.Schema(type=types.Type.STRING, description="Typ checklisty ('sprzęt' lub 'jedzenie')"),
            "stara_nazwa": types.Schema(type=types.Type.STRING, description="Aktualna nazwa elementu"),
            "nowa_nazwa": types.Schema(type=types.Type.STRING, description="Nowa nazwa elementu"),
            "nowa_ilosc": types.Schema(type=types.Type.STRING, description="Nowa ilość"),
        },
        required=["id_wycieczki", "typ", "stara_nazwa"]
    ),
)

usun_checklist_tool = types.FunctionDeclaration(
    name="usun_element_checklisty",
    description="Usuwa element z checklisty wycieczki.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "id_wycieczki": types.Schema(type=types.Type.STRING, description="ID wycieczki"),
            "typ": types.Schema(type=types.Type.STRING, description="Typ checklisty ('sprzęt' lub 'jedzenie')"),
            "nazwa": types.Schema(type=types.Type.STRING, description="Nazwa elementu do usunięcia"),
        },
        required=["id_wycieczki", "typ", "nazwa"]
    ),
)

fadyssai_tools = types.Tool(function_declarations=[
    aktualizuj_tool, 
    usun_miejsce_tool,
    utworz_nowa_wycieczke_tool, 
    edytuj_wycieczke_tool, 
    usun_wycieczke_tool, 
    dodaj_krok_tool, 
    edytuj_krok_tool, 
    usun_krok_tool, 
    dodaj_checklist_tool, 
    edytuj_checklist_tool, 
    usun_checklist_tool
])

def renderuj_sekcje_czatu_ai(klucz_unikalny_sufiks):
    st.markdown("---")
    st.markdown("### 💬 Asystent AI Fadyssai")
    
    if not gemini_api_key:
        st.info("👈 Wprowadź swój klucz API Google Gemini w menu bocznym, aby uruchomić czat i zarządzać wycieczkami w bazie.")
        return

    client = genai.Client(api_key=gemini_api_key)
    zewnetrzny_kontekst = wczytaj_kontekst_zewnetrzny()
    
    system_prompt = f"""Jesteś inteligentnym, empatycznym asystentem podróży Fadyssai na Kretę.
{zewnetrzny_kontekst}
- Masz pełny wgląd w całą bazę danych SQLite.
- Miejsca z flagą Base = true są bezwzględnie chronione przed modyfikacją lub usunięciem.
- Nigdy nie modyfikuj bazy samowolnie – tylko na wyraźne polecenie użytkownika."""

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

    prompt = st.chat_input("Rozmawiaj o wycieczkach, kminie plany...", key=f"chat_input_{klucz_unikalny_sufiks}")
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
                            tools=[fadyssai_tools],
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
                            wynik_bazy = "Wykonano operację."
                        
                        with st.spinner("Zapisuję zmiany w bazie SQLite..."):
                            follow_up = client.models.generate_content(
                                model=wybrany_model,
                                contents=contents + [
                                    model_content,
                                    types.Content(role="user", parts=[types.Part.from_function_response(name=call_name, response={"result": wynik_bazy})])
                                ],
                                config=types.GenerateContentConfig(tools=[fadyssai_tools])
                            )
                        
                        fu_cand = follow_up.candidates[0] if follow_up.candidates else None
                        if fu_cand and fu_cand.content and fu_cand.content.parts:
                            text_parts = [p.text for p in fu_cand.content.parts if hasattr(p, "text") and p.text]
                            assistant_reply = "".join(text_parts) if text_parts else "Operacja została zakończona pomyślnie."
                            st.session_state.chat_history.append({
                                "role": "assistant", 
                                "content": assistant_reply, 
                                "raw_content": fu_cand.content
                            })
                        else:
                            assistant_reply = "Operacja została zaktualizowana w bazie."
                else:
                    text_parts = [p.text for p in candidate.content.parts if hasattr(p, "text") and p.text] if candidate and candidate.content and candidate.content.parts else []
                    assistant_reply = "".join(text_parts) if text_parts else (response.text if hasattr(response, "text") else "Brak odpowiedzi.")
                    
                    st.session_state.chat_history.append({
                        "role": "assistant", 
                        "content": assistant_reply, 
                        "raw_content": candidate.content if candidate else types.Content(role="model", parts=[types.Part.from_text(text=assistant_reply)])
                    })
            except Exception as e:
                assistant_reply = f"Wystąpił błąd podczas komunikacji z AI: {e}"
                st.session_state.chat_history.append({
                    "role": "assistant", 
                    "content": assistant_reply, 
                    "raw_content": types.Content(role="model", parts=[types.Part.from_text(text=assistant_reply)])
                })

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

if "jump_to_step" not in st.session_state:
    st.session_state.jump_to_step = None

COLORS = {
    'must have': '#E83E8C',
    'nice to have': '#FD7E14',
    'others': '#007BFF',
    'activity': '#FFC107',
    'shop': '#28A745',
    'plaża': '#00BFFF'
}
DEFAULT_COLOR = '#DC3545'

df_miejsca = pobierz_wszystkie_miejsca()
wycieczki_options = pobierz_skrocone_opcje_wycieczek()

def renderuj_checklistu_expander(wycieczka_id):
    conn = sqlite3.connect('fadyssai.db')
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
        st.info("Brak zdefiniowanej checklisty dla tej wycieczki.")
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
                    st.checkbox(f"{itm['nazwa']}{ilosc_str}", key=f"chk_exp_{chl_id}_{itm['id']}")

def renderuj_zadania_dzieci_expander(tekst_zadan, unikalny_klucz):
    zadania_lista = [z.strip() for z in str(tekst_zadan).split('.') if z.strip()]
    if not zadania_lista:
        zadania_lista = [str(tekst_zadan)]
    for i, zadanie in enumerate(zadania_lista):
        st.checkbox(f"{zadanie}", key=f"zad_dziecko_exp_{unikalny_klucz}_{i}")

def renderuj_karte_wycieczki(wycieczka_id, pokaz_mape=True):
    conn = sqlite3.connect('fadyssai.db')
    wycieczka_row = pd.read_sql('SELECT * FROM wycieczka WHERE id = ?', conn, params=(str(wycieczka_id),))
    kroki_df = pd.read_sql('SELECT * FROM krok_wycieczki WHERE id_wycieczki = ?', conn, params=(str(wycieczka_id),))
    conn.close()
    
    if not wycieczka_row.empty:
        w_gen = wycieczka_row.iloc[0]
        tytul_w = str(w_gen['tytul_wycieczki'])
        
        st.markdown(f"""
        <div style="background-color:#e6ded1; padding:12px; border:2px solid #b89b82; border-radius:8px; text-align:center; font-size:13pt; font-weight:900; text-transform:uppercase; margin-bottom:12px; color:#663223;">
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
                
                m_trasa = folium.Map(location=[srodek_lat, srodek_lon], zoom_start=10, tiles="CartoDB positron")
                dodaj_marker_domku(m_trasa)
                
                for p in punkty_trasy:
                    if len(p) == 4:
                        lat, lon, krok, nazwa = p
                        icon_html = f'<div style="background-color:#663223;color:white;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-family:Arial;font-size:12px;font-weight:bold;border:2px solid white;box-shadow:0 2px 5px rgba(0,0,0,0.4);">{krok}</div>'
                        icon = folium.DivIcon(html=icon_html, icon_size=(26, 26), icon_anchor=(13, 13))
                        folium.Marker([lat, lon], icon=icon, tooltip=f"Krok {krok}: {nazwa}").add_to(m_trasa)
                    
                trasa_po_drogach = pobierz_trase_osrm(surowe_wspolrzedne)
                if trasa_po_drogach:
                    folium.PolyLine(trasa_po_drogach, color="#8b4513", weight=4, opacity=0.8).add_to(m_trasa)
                    
                st_folium(m_trasa, width="100%", height=280, returned_objects=[])

            st.markdown("---")

        pobudka_val = w_gen.get('pobudka', '07:00') if pd.notna(w_gen.get('pobudka')) else '07:00'
        wyjazd_val = w_gen.get('czas_wyjazdu', '07:30') if pd.notna(w_gen.get('czas_wyjazdu')) else '07:30'
        powrot_val = w_gen.get('szacowana_godzina_powrotu', '17:00')
        czas_trwania = f"{w_gen['calkowity_czas_wycieczki_godziny']} godz."

        st.markdown(f"""
        <div style="background-color:#e6ded1; border:2px solid #b89b82; border-radius:12px; padding:12px; margin-bottom:15px;">
            <div style="font-size:11pt; font-weight:bold; color:#663223; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
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
                    <div class="logistics-title">⏱️ Całkowity czas</div>
                    <div class="logistics-value">{czas_trwania}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if pd.notna(w_gen['calosciowy_opis_wycieczki']) and str(w_gen['calosciowy_opis_wycieczki']).strip() != "":
            st.markdown(f"""
            <div style="background-color:#e6ded1; border:2px solid #b89b82; border-radius:12px; padding:12px; margin-bottom:15px;">
                <div style="font-size:11pt; font-weight:bold; color:#663223; margin-bottom:6px;">
                    📝 Opis i cel wycieczki
                </div>
                <div style="color:#3b2f2f; font-size:10.5pt;">
                    {w_gen['calosciowy_opis_wycieczki']}
                </div>
            </div>
            """, unsafe_allow_html=True)

        if not kroki_df.empty:
            st.markdown("⚡ **Szybki skok do etapu:**")
            cols_kroki = st.columns(len(kroki_df))
            for idx, (_, k_item) in enumerate(kroki_df.iterrows()):
                with cols_kroki[idx]:
                    krok_id_target = k_item['id']
                    krok_num_lbl = k_item['krok_wycieczki']
                    st.markdown(f'''
                        <a href="#krok_{krok_id_target}" style="display: block; background-color: #e6ded1; border: 1px solid #b89b82; color: #663223; padding: 8px 0; text-align: center; border-radius: 8px; font-size: 16px; font-weight: bold; text-decoration: none; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                            {krok_num_lbl}
                        </a>
                    ''', unsafe_allow_html=True)
            st.markdown("---")

        with st.expander("🎒 Sprawdź checklistę wycieczki"):
            renderuj_checklistu_expander(wycieczka_id)

        st.markdown("---")

        if pd.notna(w_gen['calosciowa_taktyka_dnia']) and str(w_gen['calosciowa_taktyka_dnia']).strip() != "":
            st.markdown(f"""
            <div style="background-color:#e6ded1; padding:14px; border:2px solid #b89b82; border-radius:8px; margin-bottom:20px;">
                <span style="font-size:12pt; font-weight:bold; color:#663223;">🧠 TAKTYKA DNIA:</span><br>
                <span style="color:#3b2f2f;">{w_gen['calosciowa_taktyka_dnia']}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        st.markdown("### 📍 Szczegółowy plan (Kroki)")
        for _, k in kroki_df.iterrows():
            krok_num = str(k['krok_wycieczki'])
            krok_nazwa = str(k['nazwa'])
            
            pasujące_miejsce = df_miejsca[df_miejsca['numer_miejsca'] == krok_num]
            miejsce_id_cel = str(pasujące_miejsce.iloc[0]['numer_miejsca']) if not pasujące_miejsce.empty else "1"

            st.markdown(f'<div id="krok_{k["id"]}"></div>', unsafe_allow_html=True)
            
            google_search_url = f"https://www.google.com/search?q={krok_nazwa} Kreta"
            gps_maps_url = f"https://www.google.com/maps/search/?api=1&query={k['wspolrzedne']}"
            coords_clean = str(k['wspolrzedne']).replace(" ", "")
            sklep_maps_url = f"https://www.google.com/maps/search/supermarket/@{coords_clean},15z"
            resto_maps_url = f"https://www.google.com/maps/search/restaurant/@{coords_clean},15z"

            warn_html = f'<div class="net-box-warn" style="margin-top: 10px; margin-bottom: 0;"><div class="net-title-warn">⚠️ Ostrzeżenie</div><div class="net-text" style="color:#721c24; font-weight:bold;">{k["czerwona_strefa_ostrzezenie"]}</div></div>' if pd.notna(k.get('czerwona_strefa_ostrzezenie')) and str(k['czerwona_strefa_ostrzezenie']).strip() != "" else ""
            desc_html = f'<div style="margin-top: 10px; background-color:#fcf8f2; border:1px solid #b89b82; border-radius:8px; padding:10px; font-size:10pt; color:#3b2f2f; font-style:italic;">{k["opis"]}</div>' if pd.notna(k.get('opis')) and str(k.get('opis')).strip() != "" else ""

            card_html = f'''<div style="background-color:#e6ded1; border:2px solid #b89b82; border-radius:14px; padding:16px; margin-bottom:20px; box-shadow:0 2px 5px rgba(0,0,0,0.08); position:relative;"><div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;"><div style="background-color:#e83e8c; color:white; border-radius:50%; width:28px; height:28px; display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:11pt; border:2px solid white; box-shadow:0 1px 3px rgba(0,0,0,0.3);">{krok_num}</div><span style="font-size:13pt; font-weight:900; color:#663223; text-decoration:underline;">{krok_nazwa}</span></div>{desc_html}<div style="display: flex; gap: 6px; margin-top: 12px; margin-bottom: 12px;"><a href="{gps_maps_url}" target="_blank" class="custom-nav-btn" style="padding:4px 0; font-size:16px;" title="GPS">📍</a><a href="{google_search_url}" target="_blank" class="custom-nav-btn" style="padding:4px 0; font-size:16px;" title="Google">🔍</a><a href="{sklep_maps_url}" target="_blank" class="custom-nav-btn" style="padding:4px 0; font-size:16px;" title="Sklep">🛒</a><a href="{resto_maps_url}" target="_blank" class="custom-nav-btn" style="padding:4px 0; font-size:16px;" title="Restauracja">🍽️</a><a href="?tab=zabytek&place={miejsce_id_cel}" target="_self" class="custom-nav-btn" style="padding:4px 0; font-size:16px;" title="Opis">📝</a></div><div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px;"><div class="net-box" style="margin-bottom:0;"><div class="net-title">⏱️ Harmonogram</div><div class="net-value" style="font-size:11pt; font-weight:bold; color:#3b2f2f;">{k["okienko_zwiedzania"]}</div></div><div class="net-box-evac" style="margin-bottom:0;"><div class="net-title-evac">🚨 Ewakuacja</div><div style="font-size:11pt; font-weight:bold; color:#a71d2a;">{k.get("godzina_ewakuacji", "Brak")}</div></div></div><div class="net-box"><div class="net-title">🎯 Taktyka</div><div class="net-text">{k["podsumowanie_taktyki"]}</div></div><div class="net-box-regen" style="margin-bottom: 0;"><div class="net-title-regen">🌿 Strefa luzu i regeneracji</div><div class="net-text" style="color:#155724;">{k["strefa_luzu_i_regeneracji"]}</div></div>{warn_html}</div>'''
            
            st.markdown(card_html, unsafe_allow_html=True)
            st.markdown("---")

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button(f"🎯 Ustaw jako aktualną", key=f"btn_akt_{wycieczka_id}", use_container_width=True):
                ustaw_aktywna_wycieczke_id(wycieczka_id)
                st.success(f"Ustawiono wycieczkę #{wycieczka_id} jako aktualną!")
                st.rerun()
        with col_btn2:
            is_odbyta = int(w_gen.get('odbyta', 0)) == 1
            if is_odbyta:
                st.markdown('<div style="background-color:#d4edda; color:#155724; padding:8px; border-radius:6px; text-align:center; font-weight:bold; border:1px solid #c3e6cb;">✨ Wycieczka przebyta</div>', unsafe_allow_html=True)
            else:
                if st.button(f"✅ Oznacz jako przebytą", key=f"btn_odbyte_{wycieczka_id}", use_container_width=True):
                    oznacz_wycieczke_i_miejsca_jako_odbyte(wycieczka_id)
                    st.success(f"Wycieczka i powiązane miejsca zostały oznaczone jako odbyte!")
                    st.rerun()

    else:
        st.warning("Nie znaleziono wybranej wycieczki.")

domek_maps_url = "https://www.google.com/maps/search/?api=1&query=35.5914,24.0918"
sklep_maps_url = "https://www.google.com/maps/search/?api=1&query=35.586222,24.091861"
active_chat_sidebar = "active" if st.session_state.active_tab == "chat" else ""

with st.sidebar:
    st.markdown("### 🧭 Szybka Nawigacja")
    st.markdown(f"""
        <div class="sidebar-nav-bar">
            <a href="{sklep_maps_url}" target="_blank" class="sidebar-nav-btn" title="Sklep">🛒</a>
            <a href="{domek_maps_url}" target="_blank" class="sidebar-nav-btn" title="Domek">🏠</a>
            <a href="?tab=chat" target="_self" class="sidebar-nav-btn {active_chat_sidebar}" title="Asystent AI">💬</a>
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

st.markdown("<div style='margin-bottom: 60px;'></div>", unsafe_allow_html=True)

if st.session_state.active_tab == "chat":
    m_chat = folium.Map(location=[35.3, 24.5], zoom_start=9, tiles="CartoDB positron")
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
                bg_color = '#6c757d' if is_visited else COLORS.get(typ_raw, DEFAULT_COLOR)
                text_color = "black" if typ_raw == 'activity' else "white"
                
                icon_html = f'<div style="background-color:{bg_color};color:{text_color};border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-family:Arial;font-size:12px;font-weight:bold;border:2px solid white;box-shadow:0 2px 5px rgba(0,0,0,0.4);">{num}</div>'
                icon = folium.DivIcon(html=icon_html, icon_size=(26, 26), icon_anchor=(13, 13))
                folium.Marker([lat, lon], icon=icon, tooltip=f"{num}. {name}").add_to(m_chat)
            except:
                pass
    st_folium(m_chat, width="100%", height=320, returned_objects=[])
    
    renderuj_sekcje_czatu_ai("tab_chat")

elif st.session_state.active_tab == "zabytek":
    st.markdown('<div class="antique-header">🏛️ Miejsca & Zabytki</div>', unsafe_allow_html=True)
    
    list_options_zabytek = ["-- Wybierz miejsce z listy --"] + list(df_miejsca['numer_miejsca'].astype(str) + ". " + df_miejsca['nazwa'])
    curr_zabytek_idx = 0
    if st.session_state.active_place_id and st.session_state.active_place_id.isdigit():
        matching_z = [i for i, opt in enumerate(list_options_zabytek) if opt.startswith(st.session_state.active_place_id + ".")]
        if matching_z:
            curr_zabytek_idx = matching_z[0]

    wybrany_zabytek_main = st.selectbox("", options=list_options_zabytek, index=curr_zabytek_idx, key="main_zabytek_sb", label_visibility="collapsed")
    if wybrany_zabytek_main != "-- Wybierz miejsce z listy --":
        chosen_id_m = wybrany_zabytek_main.split(". ")[0]
        if chosen_id_m != st.session_state.active_place_id:
            st.session_state.active_place_id = chosen_id_m
            st.rerun()

    m = folium.Map(location=[35.3, 24.5], zoom_start=9, tiles="CartoDB positron")
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
                bg_color = '#6c757d' if is_visited else COLORS.get(typ_raw, DEFAULT_COLOR)
                text_color = "black" if typ_raw == 'activity' else "white"
                
                icon_html = f'<div style="background-color:{bg_color};color:{text_color};border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-family:Arial;font-size:12px;font-weight:bold;border:2px solid white;box-shadow:0 2px 5px rgba(0,0,0,0.4);">{num}</div>'
                icon = folium.DivIcon(html=icon_html, icon_size=(26, 26), icon_anchor=(13, 13))
                
                folium.Marker([lat, lon], icon=icon, tooltip=f"{num}. {name}").add_to(m)
            except:
                pass

    map_data = st_folium(m, width="100%", height=380)

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
            
            st.markdown(f"""
            <div style="background-color:#e6ded1; padding:12px; border-top:3px solid #b89b82; border-bottom:3px solid #b89b82; text-align:center; font-size:14pt; font-weight:900; text-transform:uppercase; margin-bottom:15px; color:#663223;">
                🏛️ Miejsce {p['numer_miejsca']}. {p['nazwa']}
            </div>
            """, unsafe_allow_html=True)

            is_visited = int(p.get('odwiedzone', 0)) == 1
            if is_visited:
                st.markdown("""
                <div style="text-align: center; margin-bottom: 10px;">
                    <span style="background-color: #d4edda; color: #155724; padding: 4px 12px; border-radius: 12px; font-weight: bold; border: 1px solid #c3e6cb; font-size: 11pt;">
                        ✨ Odwiedzone
                    </span>
                </div>
                """, unsafe_allow_html=True)

            numer_m = str(p['numer_miejsca'])
            for ekst in ['.jpg', '.jpeg', '.png']:
                sciezka_zdjecia = os.path.join("zdjecia", f"{numer_m}{ekst}")
                if os.path.exists(sciezka_zdjecia):
                    st.image(sciezka_zdjecia, caption=f"{p['nazwa']}")
                    break

            google_search_url = f"https://www.google.com/search?q={p['nazwa']} Kreta"
            st.markdown(f"<p style='text-align:center;'><a href='{google_search_url}' target='_blank' style='color:#8b4513;'>🔍 Szukaj w Google</a></p>", unsafe_allow_html=True)
            
            if pd.notna(p['opis']) and str(p['opis']).strip() != "":
                st.info(p['opis'])
                
            st.markdown(f"**⏰ Czas dojazdu:** {p['czas_dojazdu']}")
            st.markdown(f"**🕒 Godziny otwarcia:** {p['godziny_otwarcia']}")
            st.markdown(f"**🌟 Najlepsza pora:** {p['najlepsza_pora']}")
            st.markdown(f"**⏱️ Czas zwiedzania:** {p['orientacyjny_czas']}")
            st.markdown(f"**💶 Koszt (rodzina 2+2):** {p['koszt']}")
            
            if pd.notna(p['konieczna_akcja']) and str(p['konieczna_akcja']).strip() != "Brak" and str(p['konieczna_akcja']).strip() != "":
                st.warning(f"**! Konieczna akcja:** {p['konieczna_akcja']}")
                
            st.markdown(f"**🍽️ Zaplecze gastronomiczne:** {p['zaplecze_gastro']}")
            st.markdown(f"**🥪 Ile jedzenia:** {p['ile_jedzenia']}")
            st.markdown(f"**☀️ Ochrona przed słońcem:** {p['ochrona_slonce']}")
            
            st.markdown("### 🐂 Wyzwania & Rady")
            st.markdown(f"**🧠 Trudności ADHD:** {p['trudnosc_adhd']}")
            st.markdown(f"**⚡ Potencjał meltdownu:** {p['potencjal_meltdownu']}")
            st.markdown(f"**🛡️ Strategie na meltdown:** {p['strategie_meltdown']}")
            
            if pd.notna(p['zadania_dla_dzieci']) and str(p['zadania_dla_dzieci']).strip() != "":
                with st.expander("🧒 Dodatkowe zadania dla dzieci w tym miejscu"):
                    renderuj_zadania_dzieci_expander(p['zadania_dla_dzieci'], p['numer_miejsca'])
            
            st.markdown(f"**🔗 Najlepiej połączyć z:** {p['najlepiej_polaczyc']}")

    renderuj_sekcje_czatu_ai("tab_zabytek")

elif st.session_state.active_tab == "map":
    st.markdown('<div class="antique-header">🗺️ Wycieczki</div>', unsafe_allow_html=True)
    
    opcje_wycieczek_lista = ["-- Wybierz wycieczkę lub zobacz mapę wszystkich miejsc --"] + wycieczki_options
    wybrana_mapa_sb = st.selectbox("", options=opcje_wycieczek_lista, key="map_wycieczka_select", label_visibility="collapsed")
    
    if "last_clicked_place_info" in st.session_state and st.session_state.last_clicked_place_info:
        st.markdown(st.session_state.last_clicked_place_info)

    if wybrana_mapa_sb == "-- Wybierz wycieczkę lub zobacz mapę wszystkich miejsc --":
        m_all = folium.Map(location=[35.3, 24.5], zoom_start=9, tiles="CartoDB positron")
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
                    bg_color = '#6c757d' if is_visited else COLORS.get(typ_raw, DEFAULT_COLOR)
                    text_color = "black" if typ_raw == 'activity' else "white"
                    
                    icon_html = f'<div style="background-color:{bg_color};color:{text_color};border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-family:Arial;font-size:12px;font-weight:bold;border:2px solid white;box-shadow:0 2px 5px rgba(0,0,0,0.4);">{num}</div>'
                    icon = folium.DivIcon(html=icon_html, icon_size=(26, 26), icon_anchor=(13, 13))
                    folium.Marker([lat, lon], icon=icon, tooltip=f"{num}. {name}").add_to(m_all)
                except:
                    pass
        
        map_all_data = st_folium(m_all, width="100%", height=400)
        
        if map_all_data and map_all_data.get("last_object_clicked_tooltip"):
            clicked_tooltip = map_all_data["last_object_clicked_tooltip"]
            if "." in clicked_tooltip:
                klikniety_numer_miejsca = clicked_tooltip.split(".")[0].strip()
                
                conn = sqlite3.connect('fadyssai.db')
                powiazane_kroki = pd.read_sql('''
                    SELECT DISTINCT k.id_wycieczki, w.tytul_wycieczki 
                    FROM krok_wycieczki k 
                    JOIN wycieczka w ON k.id_wycieczki = w.id 
                    WHERE (k.krok_wycieczki = ? OR k.nazwa LIKE ?) AND w.odbyta = 0
                ''', conn, params=(klikniety_numer_miejsca, f"%{clicked_tooltip.split('.')[1].strip()}%"))
                conn.close()
                
                info_tekst = ""
                if not powiazane_kroki.empty:
                    info_tekst = f"📌 Miejsce **{clicked_tooltip}** znajduje się w następujących aktywnych wycieczkach:\n"
                    for _, row_w in powiazane_kroki.iterrows():
                        info_tekst += f"- **Wycieczka #{row_w['id_wycieczki']}**: {row_w['tytul_wycieczki']}\n"
                else:
                    info_tekst = f"📌 Miejsce **{clicked_tooltip}** nie jest obecnie przypisane jako krok w żadnej aktywnej wycieczce."
                
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
    st.markdown('<div class="antique-header">🚗 Aktualna Trasa i Wycieczka</div>', unsafe_allow_html=True)
    aktualne_id = pobierz_aktywna_wycieczke_id()
    
    conn = sqlite3.connect('fadyssai.db')
    curr_w_check = pd.read_sql('SELECT odbyta FROM wycieczka WHERE id = ?', conn, params=(str(aktualne_id),))
    conn.close()
    
    if not curr_w_check.empty and int(curr_w_check.iloc[0]['odbyta']) == 1:
        st.info("✨ Aktualnie ustawiona wycieczka została już ukończona i przebyta. Wybierz inną wycieczkę z menu wycieczek.")
    else:
        renderuj_karte_wycieczki(aktualne_id, pokaz_mape=False)

    renderuj_sekcje_czatu_ai("tab_route")
