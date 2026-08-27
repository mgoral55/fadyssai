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
import base64

# --- 1. KONFIGURACJA STRONY I STYL PERGAMINU ---
st.set_page_config(page_title="Fadyssai - Kreta", layout="centered", page_icon="🧭")

st.markdown("""
    <style>
    /* Globalne tło pergaminu i czcionka */
    .stApp {
        background-color: #f4ecdf;
        color: #3b2f2f;
    }
    /* Pasek boczny w klimacie */
    [data-testid="stSidebar"] {
        background-color: #e6ded1;
    }
    /* Stylizacja nagłówków */
    h3 {
        color: #663223;
        font-family: Georgia, serif;
    }
    /* Styl dla paska nawigacyjnego i belek przycisków */
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
    /* Styl sekcji zdjęć pod belką */
    .photo-container {
        width: 100%;
        margin-bottom: 15px;
        text-align: center;
    }
    .photo-container img {
        width: 100%;
        max-height: 250px;
        object-fit: cover;
        border-radius: 8px;
        border: 2px solid #b89b82;
    }
    .photo-placeholder {
        width: 100%;
        height: 120px;
        background-color: #e6ded1;
        border: 2px dashed #b89b82;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #663223;
        font-style: italic;
        margin-bottom: 15px;
        font-size: 14px;
    }
    </style>
""", unsafe_allow_html=True)

# Stałe współrzędne domu
DOMEK_LAT = 35.5914
DOMEK_LON = 24.0918

# --- 2. BAZA DANYCH SQLITE & DOMYŚLNE DANE WBUDOWANE ---
def init_db():
    conn = sqlite3.connect('fadyssai.db')
    cursor = conn.cursor()
    
    # Tabela miejsc
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
            zadania_dla_dzieci TEXT
        )
    ''')

    # Tabela WYCIECZKA
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wycieczka (
            id TEXT PRIMARY KEY,
            tytul_wycieczki TEXT,
            calosciowy_opis_wycieczki TEXT,
            calosciowa_taktyka_dnia TEXT,
            calkowity_czas_wycieczki_godziny TEXT,
            szacowana_godzina_powrotu TEXT
        )
    ''')

    # Tabela KROK_WYCIECZKI
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS krok_wycieczki (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_wycieczki TEXT,
            krok_wycieczki TEXT,
            nazwa TEXT,
            wspolrzedne TEXT,
            okienko_zwiedzania TEXT,
            godzina_ewakuacji TEXT,
            cel_nastepny_i_czas TEXT,
            czerwona_strefa_ostrzezenie TEXT,
            strefa_luzu_i_regeneracji TEXT,
            podsumowanie_taktyki TEXT,
            potencjal_meltdownu TEXT,
            strategie_meltdown TEXT,
            opis TEXT
        )
    ''')

    # Tabela CHECKLIST
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_wycieczki TEXT,
            typ TEXT
        )
    ''')

    # Tabela CHECKLIST_ITEM
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checklist_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_checklisty INTEGER,
            nazwa TEXT,
            ilosc TEXT
        )
    ''')

    # Tabela przechowująca ID aktywnej wycieczki
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS aktywna_wycieczka (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            aktualne_id_wycieczki TEXT
        )
    ''')
    cursor.execute('INSERT OR IGNORE INTO aktywna_wycieczka (id, aktualne_id_wycieczki) VALUES (1, "1")')
    conn.commit()

    # Synchronizacja miejsc z miejsca.csv (jeśli istnieje)
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
                    potencjal_meltdownu, strategie_meltdown, ochrona_slonce, najlepiej_polaczyc, zadania_dla_dzieci
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    # Sprawdzenie, czy tabele wycieczek są puste – jeśli tak, wstawiamy domyślne wycieczki
    cursor.execute('SELECT COUNT(*) FROM wycieczka')
    if cursor.fetchone()[0] == 0:
        # WYCIECZKA 1
        cursor.execute('''
            INSERT INTO wycieczka (id, tytul_wycieczki, calosciowy_opis_wycieczki, calosciowa_taktyka_dnia, calkowity_czas_wycieczki_godziny, szacowana_godzina_powrotu)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            "1",
            "Mity i Oceaniczne Głębiny: Pałac w Knossos & Cretaquarium",
            "Wyprawa łącząca mityczną historię starożytnej Krety z podwodnym światem głębin w klimatyzowanym akwarium oraz relaksem nad jeziorem Kournas.",
            "Żelazna kontrola czasu rano w Knossos, obiad w Cretaquarium i popołudniowe wyciszenie nad jeziorem.",
            "12.0",
            "18:30"
        ))

        kroki_w1 = [
            ("1", "1", "Pałac w Knossos", "35.2980, 25.1631", "08:00 - 09:45", "09:45", "Cretaquarium (25 min)", "BEZWZGLĘDNIE EWAKUOWAĆ SIĘ PRZED 10:00! Tłumy i upał.", "Brak - rygor czasowy.", "Szybkie wejście na otwarcie o 8:00.", "Wysoki (tłumy, brak cienia, duchota)", "Użycie aplikacji 3D na iPadzie jako kotwica uwagi, szybka ewakuacja w razie buntu.", "Legendarna stolica minojskiej Krety z ruinami pałacu króla Minosa."),
            ("1", "2", "Cretaquarium", "35.3326, 25.2825", "10:10 - 12:00", "12:00", "Obiad na miejscu (0 min)", "Unikać godzin szczytu (11:00 - 15:00).", "Średnia - kawiarnia obok.", "Wyciszenie sensoryczne w klimatyzowanym półmroku.", "Średni (pogłos w betonowych halach, tłum)", "Słuchawki wygłuszające, powolne tempo, półmrok przy akwariach.", "Jedno z największych i najnowocześniejszych oceanariów w basenie Morza Śródziemnego.")
        ]
        cursor.executemany('''
            INSERT INTO krok_wycieczki (id_wycieczki, krok_wycieczki, nazwa, wspolrzedne, okienko_zwiedzania, godzina_ewakuacji, cel_nastepny_i_czas, czerwona_strefa_ostrzezenie, strefa_luzu_i_regeneracji, podsumowanie_taktyki, potencjal_meltdownu, strategie_meltdown, opis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

        # WYCIECZKA 2
        cursor.execute('''
            INSERT INTO wycieczka (id, tytul_wycieczki, calosciowy_opis_wycieczki, calosciowa_taktyka_dnia, calkowity_czas_wycieczki_godziny, szacowana_godzina_powrotu)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            "2",
            "Wyspa Łez i Sekretne Zatoki: Spinalonga & Agios Nikolaos",
            "Malownicza wyprawa na historyczną wyspę-twierdzę Spinalonga z rejsem statkiem z Eloundy oraz popołudniowym relaksem i kawą nad malowniczym jeziorem Voulismeni w Agios Nikolaos.",
            "Wczesny wyjazd na parking w Elounda, rejs na Spinalongę przed największym upałem, a po obiedzie spacer wokół jeziora w Agios Nikolaos.",
            "10.5",
            "17:00"
        ))

        kroki_w2 = [
            ("2", "1", "Elounda - Port i Rejs na Spinalongę", "35.2575, 25.7314", "09:00 - 11:30", "11:30", "Agios Nikolaos (20 min)", "Silne słońce na łodzi i na wyspie. Konieczne nakrycia głowy!", "Odpoczynek w cieniu kawiarni w porcie Elounda.", "Spokojny rejs tradycyjną łodzią i zwiedzanie historycznej twierdzy.", "Średni (długi rejs, nasłonecznienie)", "Okulary przeciwsłoneczne, woda z lodem w termosie, czapka.", "Dawna wenecka twierdza i późniejsza kolonia trędowatych z niezwykłą atmosferą."),
            ("2", "2", "Agios Nikolaos & Jezioro Voulismeni", "35.1915, 25.7171", "12:50 - 15:30", "15:30", "Powrót do bazy", "Dużo turystów wokół jeziora w godzinach popołudniowych.", "Kawiarnie nad brzegiem jeziora z widokiem na klify.", "Niespieszny obiad i lody nad wodą.", "Niski (przyjemny spacer, dużo miejsc do zatrzymania)", "Lody jako nagroda, swobodne tempo.", "Urokliwe miasteczko wokół bezdennego jeziora połączonego z morzem wąskim kanałem.")
        ]
        cursor.executemany('''
            INSERT INTO krok_wycieczki (id_wycieczki, krok_wycieczki, nazwa, wspolrzedne, okienko_zwiedzania, godzina_ewakuacji, cel_nastepny_i_czas, czerwona_strefa_ostrzezenie, strefa_luzu_i_regeneracji, podsumowanie_taktyki, potencjal_meltdownu, strategie_meltdown, opis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

def aktualizuj_miejsce(numer_miejsca, opis=None, konieczna_akcja=None):
    conn = sqlite3.connect('fadyssai.db')
    cursor = conn.cursor()
    if opis:
        cursor.execute('UPDATE miejsca SET opis = ? WHERE numer_miejsca = ?', (opis, str(numer_miejsca)))
    if konieczna_akcja:
        cursor.execute('UPDATE miejsca SET konieczna_akcja = ? WHERE numer_miejsca = ?', (konieczna_akcja, str(numer_miejsca)))
    conn.commit()
    conn.close()
    return f"Miejsce nr {numer_miejsca} w bazie Fadyssai zostało zaktualizowane!"

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
    df_w = pd.read_sql('SELECT id, tytul_wycieczki FROM wycieczka', conn)
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

# Pomocnicza funkcja pobierająca trasę po drogach z OSRM
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

# Pomocnicza funkcja dodająca marker domku do mapy
def dodaj_marker_domku(m):
    domek_icon_html = '<div style="background-color:black;color:white;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:14px;border:2px solid white;box-shadow:0 2px 5px rgba(0,0,0,0.5);">🏠</div>'
    domek_icon = folium.DivIcon(html=domek_icon_html, icon_size=(28, 28), icon_anchor=(14, 14))
    folium.Marker([DOMEK_LAT, DOMEK_LON], icon=domek_icon, tooltip="Nasz Domek").add_to(m)

# --- 3. NARĘDZIA DLA GEMINI ---
aktualizuj_tool = types.FunctionDeclaration(
    name="aktualizuj_miejsce",
    description="Aktualizuje informacje o wybranym miejscu na Krecie (np. opis lub konieczną akcję) na podstawie numeru miejsca.",
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
fadyssai_tools = types.Tool(function_declarations=[aktualizuj_tool])

# --- 4. STAN APLIKACJI (Domyślnie chat) ---
if "tab" in st.query_params:
    st.session_state.active_tab = st.query_params["tab"]
elif "active_tab" not in st.session_state:
    st.session_state.active_tab = "chat"

if "active_place_id" not in st.session_state:
    st.session_state.active_place_id = None

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

# --- PANEL BOCZNY (MENU WYSUWANE) ---
with st.sidebar:
    st.header("🧭 Menu Fadyssai")
    
    if wycieczki_options:
        aktualne_id = pobierz_aktywna_wycieczke_id()
        curr_idx = 0
        for idx, opt in enumerate(wycieczki_options):
            if opt.startswith(aktualne_id + "."):
                curr_idx = idx
                break
                
        wybrana_wycieczka_sb = st.selectbox("🚗 Wybierz aktywną wycieczkę:", options=wycieczki_options, index=curr_idx)
        if wybrana_wycieczka_sb:
            nowe_id = wybrana_wycieczka_sb.split(". ")[0]
            if nowe_id != aktualne_id:
                ustaw_aktywna_wycieczke_id(nowe_id)
                st.rerun()

    st.markdown("---")
    
    list_options = ["-- Wybierz miejsce --"] + list(df_miejsca['numer_miejsca'].astype(str) + ". " + df_miejsca['nazwa'])
    current_index = 0
    if st.session_state.active_place_id and st.session_state.active_place_id.isdigit():
        matching = [i for i, opt in enumerate(list_options) if opt.startswith(st.session_state.active_place_id + ".")]
        if matching:
            current_index = matching[0]
            
    selected_place_selectbox = st.selectbox(
        "🔍 Wybierz miejsce:",
        options=list_options,
        index=current_index
    )

    if selected_place_selectbox != "-- Wybierz miejsce --":
        chosen_id = selected_place_selectbox.split(". ")[0]
        if chosen_id != st.session_state.active_place_id:
            st.session_state.active_place_id = chosen_id
            st.rerun()

    st.markdown("---")
    st.header("⚙️ Ustawienia Asystenta")
    gemini_api_key = st.text_input("Klucz API Google Gemini", type="password", key="api_key_input")

# --- GŁÓWNY INTERFEJS: 2 RZĘDY IKONEK ---
domek_maps_url = "https://www.google.com/maps/search/?api=1&query=35.5914,24.0918"
sklep_maps_url = "https://www.google.com/maps/search/?api=1&query=35.586222,24.091861"

active_zabytek = "active" if st.session_state.active_tab == "zabytek" else ""
active_map = "active" if st.session_state.active_tab == "map" else ""
active_route = "active" if st.session_state.active_tab == "route" else ""
active_chat = "active" if st.session_state.active_tab == "chat" else ""

st.markdown(f"""
    <div class="custom-nav-bar">
        <a href="{sklep_maps_url}" target="_blank" class="custom-nav-btn" title="Nawiguj do Sklepu">🛒</a>
        <a href="{domek_maps_url}" target="_blank" class="custom-nav-btn" title="Nawiguj do Domku">🏠</a>
        <a href="?tab=chat" target="_self" class="custom-nav-btn {active_chat}" title="Czat AI">💬</a>
    </div>
    <div class="custom-nav-bar" style="margin-bottom: 1rem;">
        <a href="?tab=zabytek" target="_self" class="custom-nav-btn {active_zabytek}" title="Zabytek / Mapa miejsc">🏛️</a>
        <a href="?tab=map" target="_self" class="custom-nav-btn {active_map}" title="Wybór Wycieczki">🗺️</a>
        <a href="?tab=route" target="_self" class="custom-nav-btn {active_route}" title="Trasa i Wycieczka">🚗</a>
    </div>
""", unsafe_allow_html=True)

# Pomocnicza funkcja obsługująca ścieżkę do podfolderu "zdjęcia"
def renderuj_zdjecie_lub_placeholder(nazwa_pliku):
    # Sprawdzamy w podfolderze "zdjęcia" oraz "zdjecia" (na wypadek literówek w nazwie folderu)
    mozliwe_katalogi = ["zdjęcia", "zdjecia", "."]
    sciezka_pliku = None
    
    for kat in mozliwe_katalogi:
        pelna = os.path.join(kat, nazwa_pliku)
        if os.path.exists(pelna):
            sciezka_pliku = pelna
            break
            
    if sciezka_pliku:
        with open(sciezka_pliku, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("utf-8")
        st.markdown(f'<div class="photo-container"><img src="data:image/jpeg;base64,{encoded}"></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="photo-placeholder">📷 [Brak pliku {nazwa_pliku} w folderze "zdjęcia"]</div>', unsafe_allow_html=True)

# --- FUNKCJA RENDEROWANIA KARTY WYCIECZKI ---
def renderuj_karte_wycieczki(wycieczka_id):
    conn = sqlite3.connect('fadyssai.db')
    wycieczka_row = pd.read_sql('SELECT * FROM wycieczka WHERE id = ?', conn, params=(str(wycieczka_id),))
    kroki_df = pd.read_sql('SELECT * FROM krok_wycieczki WHERE id_wycieczki = ?', conn, params=(str(wycieczka_id),))
    
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
    
    if not wycieczka_row.empty:
        w_gen = wycieczka_row.iloc[0]
        st.markdown(f"""
        <div style="background-color:#e6ded1; padding:12px; border-top:3px solid #b89b82; border-bottom:3px solid #b89b82; text-align:center; font-size:14pt; font-weight:900; text-transform:uppercase; margin-bottom:15px; color:#663223;">
            🚗 Wycieczka #{w_gen['id']}: {w_gen['tytul_wycieczki']}
        </div>
        """, unsafe_allow_html=True)
        
        # --- ZDJĘCIE WYCIECZKI (NUMER PIERWSZEGO MIEJSCA) ---
        pierwsze_miejsce_nr = None
        if not kroki_df.empty:
            pierwsze_miejsce_nr = str(kroki_df.iloc[0]['krok_wycieczki'])
        
        foto_wycieczki = f"{pierwsze_miejsce_nr}.jpg" if pierwsze_miejsce_nr else "1.jpg"
        renderuj_zdjecie_lub_placeholder(foto_wycieczki)

        # --- MAPA TRASY WYCIECZKI PO DROGACH (OSRM) ---
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
                
            st_folium(m_trasa, width="100%", height=320, returned_objects=[])

        st.markdown("---")
        
        if pd.notna(w_gen['calosciowy_opis_wycieczki']) and str(w_gen['calosciowy_opis_wycieczki']).strip() != "":
            st.info(w_gen['calosciowy_opis_wycieczki'])
            
        st.markdown(f"**Taktyka dnia:** {w_gen['calosciowa_taktyka_dnia']}")
        st.markdown(f"**⏱️ Czas trwania / Powrót:** {w_gen['calkowity_czas_wycieczki_godziny']}h | Powrót: {w_gen['szacowana_godzina_powrotu']}")
        
        if not checklisty_df.empty:
            st.markdown("---")
            st.markdown("### 🎒 Checklista Wycieczki")
            for _, chl in checklisty_df.iterrows():
                typ_chl = chl['typ'].capitalize()
                chl_id = chl['id']
                powiazane_itemy = items_df[items_df['id_checklisty'] == chl_id] if not items_df.empty else pd.DataFrame()
                
                if not powiazane_itemy.empty:
                    st.markdown(f"**📌 {typ_chl}:**")
                    for _, itm in powiazane_itemy.iterrows():
                        ilosc_str = f" *({itm['ilosc']})*" if pd.notna(itm['ilosc']) and itm['ilosc'] != "1" else ""
                        st.markdown(f"- {itm['nazwa']}{ilosc_str}")

        st.markdown("---")
        st.markdown("### 🗺️ Etapy i Miejsca wycieczki")
        
        kroki_html = "<div style='border-left: 4px solid #b89b82; padding-left: 12px; margin-bottom: 20px;'>"
        for _, k in kroki_df.iterrows():
            kroki_html += f"<div style='margin-bottom: 6px; font-weight: bold; color: #663223;'>Krok {k['krok_wycieczki']}: {k['nazwa']}</div>"
        kroki_html += "</div>"
        st.markdown(kroki_html, unsafe_allow_html=True)
        
        st.markdown("---")

        for _, k in kroki_df.iterrows():
            st.markdown(f"""
            <div style="background-color:#e6ded1; padding:10px; border-left:4px solid #8b4513; margin-top:10px; margin-bottom:5px; font-weight:bold; color:#663223;">
                {k['krok_wycieczki']}. {k['nazwa']}
            </div>
            """, unsafe_allow_html=True)
            
            google_search_url = f"https://www.google.com/search?q={k['nazwa']} Kreta"
            gps_maps_url = f"https://www.google.com/maps/search/?api=1&query={k['wspolrzedne']}"
            sklep_maps_url = f"https://www.google.com/maps/search/?api=1&query=supermarket+near+{k['wspolrzedne']}"
            resto_maps_url = f"https://www.google.com/maps/search/?api=1&query=restaurant+near+{k['wspolrzedne']}"

            st.markdown(f"""
                <div class="custom-nav-bar" style="margin-bottom: 10px;">
                    <a href="{google_search_url}" target="_blank" class="custom-nav-btn" title="Szukaj w Google">🔍</a>
                    <a href="{gps_maps_url}" target="_blank" class="custom-nav-btn" title="Pineska GPS">📍</a>
                    <a href="{sklep_maps_url}" target="_blank" class="custom-nav-btn" title="Najbliższy sklep spożywczy">🛒</a>
                    <a href="{resto_maps_url}" target="_blank" class="custom-nav-btn" title="Najbliższa restauracja">🍽️</a>
                </div>
            """, unsafe_allow_html=True)

            if pd.notna(k['opis']) and str(k['opis']).strip() != "":
                st.write(k['opis'])
                
            st.markdown(f"**🕒 Okienko zwiedzania:** {k['okienko_zwiedzania']} (Ewakuacja: {k['godzina_ewakuacji']})")
            st.markdown(f"**🚗 Następny cel:** {k['cel_nastepny_i_czas']}")
            
            if pd.notna(k['czerwona_strefa_ostrzezenie']) and str(k['czerwona_strefa_ostrzezenie']).strip() != "":
                st.warning(f"**🚨 Ostrzeżenie / Czerwona Strefa:** {k['czerwona_strefa_ostrzezenie']}")
                
            st.markdown("### 🐂 Taktyka & Regeneracja")
            st.markdown(f"**🧠 Podsumowanie taktyki:** {k['podsumowanie_taktyki']}")
            st.markdown(f"**🛡️ Strefa luzu i regeneracji:** {k['strefa_luzu_i_regeneracji']}")
            
            if pd.notna(k['potencjal_meltdownu']) and str(k['potencjal_meltdownu']).strip() != "":
                st.markdown(f"**⚡ Prawdopodobieństwo meltdownu:** {k['potencjal_meltdownu']}")
            if pd.notna(k['strategie_meltdown']) and str(k['strategie_meltdown']).strip() != "":
                st.markdown(f"**🛡️ Strategia zapobiegania meltdownowi:** {k['strategie_meltdown']}")
            
            st.markdown("---")
    else:
        st.warning("Nie znaleziono wybranej wycieczki.")

# --- ZAWARTOŚĆ ZALEŻNA OD WYBRANEJ ZAKŁADKI ---
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
                bg_color = COLORS.get(typ_raw, DEFAULT_COLOR)
                text_color = "black" if typ_raw == 'activity' else "white"
                
                icon_html = f'<div style="background-color:{bg_color};color:{text_color};border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-family:Arial;font-size:12px;font-weight:bold;border:2px solid white;box-shadow:0 2px 5px rgba(0,0,0,0.4);">{num}</div>'
                icon = folium.DivIcon(html=icon_html, icon_size=(26, 26), icon_anchor=(13, 13))
                folium.Marker([lat, lon], icon=icon, tooltip=f"{num}. {name}").add_to(m_chat)
            except:
                pass
    st_folium(m_chat, width="100%", height=320, returned_objects=[])
    
    st.markdown("---")
    st.markdown("### 💬 Asystent Fadyssai")
    
    if not gemini_api_key:
        st.info("👈 Wprowadź klucz API Google Gemini w menu bocznym, aby uruchomić czat i zarządzać bazą.")
    else:
        client = genai.Client(api_key=gemini_api_key)

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("Napisz np. 'Zmień konieczną akcję dla miejsca 1 na...'..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                contents = [types.Content(role="user" if m["role"] == "user" else "model", parts=[types.Part.from_text(text=m["content"])]) for m in st.session_state.chat_history]

                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=contents,
                    config=types.GenerateContentConfig(
                        tools=[fadyssai_tools],
                        system_instruction="Jesteś inteligentnym asystentem podróży Fadyssai na Krecie. Masz dostęp do bazy miejsc z pliku miejsca.csv oraz wycieczek. Jeśli użytkownik chce zmodyfikować dane miejsca, użyj narzędzia aktualizuj_miejsce."
                    )
                )

                if response.function_calls:
                    for call in response.function_calls:
                        if call.name == "aktualizuj_miejsce":
                            args = call.args
                            wynik_bazy = aktualizuj_miejsce(**args)
                            
                            follow_up = client.models.generate_content(
                                model='gemini-2.5-flash',
                                contents=contents + [
                                    types.Content(role="model", parts=[types.Part.from_function_call(name=call.name, args=args)]),
                                    types.Content(role="user", parts=[types.Part.from_function_response(name=call.name, response={"result": wynik_bazy})])
                                ],
                                config=types.GenerateContentConfig(tools=[fadyssai_tools])
                            )
                            assistant_reply = follow_up.text
                else:
                    assistant_reply = response.text

                st.markdown(assistant_reply)
                st.session_state.chat_history.append({"role": "assistant", "content": assistant_reply})
                st.rerun()

elif st.session_state.active_tab == "zabytek":
    st.info("💡 Kliknij w dowolny punkt na poniższej mapie, aby zobaczyć szczegóły miejsca.")
    
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
                bg_color = COLORS.get(typ_raw, DEFAULT_COLOR)
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
                🏛️ {p['numer_miejsca']}. {p['nazwa']}
            </div>
            """, unsafe_allow_html=True)
            
            # --- ZDJĘCIE MIEJSCA (Z FOLDERU ZDJĘCIA) ---
            renderuj_zdjecie_lub_placeholder(f"{p['numer_miejsca']}.jpg")

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
            
            st.markdown("### 🧒 Zadania dla dzieci")
            st.markdown(p['zadania_dla_dzieci'])
            
            st.markdown(f"**🔗 Najlepiej połączyć z:** {p['najlepiej_polaczyc']}")

elif st.session_state.active_tab == "map":
    st.markdown("### 🗺️ Wybór Wycieczki")
    
    wycieczki_options = pobierz_skrocone_opcje_wycieczek()
    if wycieczki_options:
        wybrana_mapa_sb = st.selectbox("Wybierz wycieczkę do przeglądania:", options=wycieczki_options, key="map_wycieczka_select")
        
        if wybrana_mapa_sb:
            wybrana_id = wybrana_mapa_sb.split(". ")[0]
            st.markdown("---")
            renderuj_karte_wycieczki(wybrana_id)
    else:
        st.info("Brak dostępnych wycieczek w bazie.")

elif st.session_state.active_tab == "route":
    aktualne_id = pobierz_aktywna_wycieczke_id()
    renderuj_karte_wycieczki(aktualne_id)
