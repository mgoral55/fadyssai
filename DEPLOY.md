# Deploy: dietpi-ha + tunel Cloudflare

Aplikacja działa jako kontener Docker na domowym serwerze `dietpi-ha` i jest
wystawiona publicznie pod `https://crete.mroczkowski.cc` przez tunel Cloudflare,
za bramką logowania Cloudflare Access.

> Repozytorium jest publiczne, więc **nie ma tu żadnych identyfikatorów ani adresów
> e-mail**. Konkretne ID konta, strefy, tunelu, aplikacji Access i lista dozwolonych
> adresów są tylko w panelu Cloudflare Zero Trust.

## Topologia

```
przeglądarka
  -> Cloudflare (proxy DNS, rekord CNAME crete -> <ID-tunelu>.cfargotunnel.com)
  -> Cloudflare Access (bramka logowania, kod jednorazowy na e-mail)
  -> tunel cloudflared (kontener w ha_stack, network_mode: host)
  -> http://127.0.0.1:8501 (kontener magda-crete)
```

Katalog stosu na serwerze: `/opt/magda-crete` (compose z tego repo), dane trwałe w
`/opt/magda-crete/data` montowane jako `/app/data` (`CRETAI_DATA_DIR`).

## Tunel jest zarządzany zdalnie

Kontener `cloudflared` startuje z `TUNNEL_TOKEN` i **nie ma pliku `config.yml`**.
Reguły ingress (hostname -> usługa) są trzymane po stronie Cloudflare i zmienia się je
przez API:

```
GET  /accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations
PUT  /accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations
```

`PUT` **podmienia całą konfigurację**, więc zawsze najpierw `GET`, potem dopisz swoją
regułę i zachowaj resztę: pozostałe hostnamey, sekcję `warp-routing` i domykającą
regułę `http_status:404`, która musi zostać na końcu listy.

Ponieważ `cloudflared` działa w trybie `network_mode: host`, reguły ingress mogą
wskazywać na porty wystawione na `127.0.0.1` — kontener aplikacji nie musi być
dostępny z sieci.

## Dlaczego `corsAllowedOrigins` w `.streamlit/config.toml`

Streamlit odrzuca uścisk WebSocket, jeśli nagłówek `Origin` jest mu nieznany, a za
tunelem `Origin` to publiczny adres, nie localhost. Bez wpisu
`corsAllowedOrigins = ["https://crete.mroczkowski.cc"]` aplikacja wisi na
"Please wait...". Po zmianie domeny trzeba zaktualizować ten wpis i przebudować obraz.

## Kolejność przy wystawianiu nowej usługi

Kolejność ma znaczenie — przy odwrotnej usługa jest chwilę dostępna bez logowania:

1. Utwórz aplikację Access (`POST /accounts/{account_id}/access/apps`, typ
   `self_hosted`, domena = docelowy hostname) oraz politykę
   (`POST /accounts/{account_id}/access/apps/{app_id}/policies`, `decision: allow`,
   `include` z listą adresów e-mail).
2. Dopisz regułę ingress do konfiguracji tunelu (patrz wyżej).
3. Dodaj rekord DNS: `CNAME`, nazwa = subdomena, treść =
   `<ID-tunelu>.cfargotunnel.com`, `proxied: true`.

Weryfikacja: `curl -sSo /dev/null -w '%{http_code} %{redirect_url}\n' https://<host>/`
powinno zwrócić `302` na `<organizacja>.cloudflareaccess.com/cdn-cgi/access/login/...`.

## Logowanie

Jedyny dostawca tożsamości to kod jednorazowy wysyłany e-mailem (one-time PIN), więc
nie trzeba zakładać żadnych kont. Każda osoba podaje swój adres, dostaje kod i po
zatwierdzeniu ma ciasteczko sesji na miesiąc (maksimum, jakie dopuszcza Access) —
kod trzeba podać raz na urządzenie.

Dodanie kolejnej osoby = dopisanie jej adresu do `include` w polityce
(`PUT /accounts/{account_id}/access/apps/{app_id}/policies/{policy_id}`). Aplikacja
nie ma własnego logowania, więc polityka Access jest jedyną kontrolą dostępu.

## Doradca AI: Claude Code CLI

Aplikacja nie ma własnego klucza do modelu. Warstwa AI uruchamia w kontenerze
`claude -p` (Claude Code CLI, domyślnie model `claude-opus-5`) i czyta wynik jako JSON.
Narzędzia bazy danych nie są narzędziami CLI — model zleca je w polu
`wywolania_narzedzi`, a Python wykonuje je lokalnie na SQLite. CLI startuje z
`--safe-mode` i `--tools ""`, więc nie ma dostępu do plików, powłoki ani sieci.

Zamiast tokenu w zmiennej środowiskowej kontener dzieli sesję z CLI zalogowanym
na hoście: `/root/.claude` jest montowane do kontenera, a samą binarkę `claude`
dostarcza obraz (Node + `@anthropic-ai/claude-code` w przypiętej wersji).

Logowanie robi się raz, na serwerze:

```
npm install -g @anthropic-ai/claude-code@2.1.220
claude
```

W sesji interaktywnej `claude` wypisuje adres logowania i czeka na kod — po
zatwierdzeniu poświadczenia lądują w `/root/.claude` i kontener widzi je przez
montowanie. Wygasłą sesję odnawia się tym samym poleceniem na hoście.

Weryfikacja w kontenerze:

```
docker compose exec magda-crete claude -p --model claude-opus-5 'odpowiedz OK'
```

## Czas przejazdu: kolejka silników trasowania

Czasy dojazdu liczy kolejka silników, a nie jeden serwis. Pierwszy, który odpowie, wygrywa;
każdy ma osobny wpis w rejestrze awarii, więc padnięcie jednego nie wycisza pozostałych.
Odpowiedź silnika przechodzi jeszcze przez kalibrację (`_czas_przejazdu_z_trasy`).

Odniesieniem jest **27 tras zmierzonych ręcznie w Google Maps** przy ruchu z 17 września 2026,
dojazd z domku w Stavros, od 0.3 km do 223 km:

| silnik | klucz | MAE | mediana błędu | max błąd |
| --- | --- | --- | --- | --- |
| Google Routes v2 | wymagany | odniesienie | — | — |
| Valhalla po kalibracji | nie | **3.6 min** | 0.0 min | 9 min |
| Valhalla surowa | nie | 5.5 min | +5.0 min | 13.4 min |
| OSRM surowy | nie | 9.2 min | -3.7 min | 34.5 min |
| szacunek geometryczny | nie | 5.0 min | 0.0 min | 19 min |

Valhalla myliła się nie skalą, a **stałym narzutem** +5 min niemal wszędzie. Na dojeździe na plażę
Tersanas (Google 8 min) dawała 13 min, a na Seitan Limania (Google 27 min) 38 min. Parametry costing
Valhalli tego nie ruszają: `top_speed`, `maneuver_penalty`, `use_living_streets` i `service_penalty`
dają MAE 5.4-5.5, czyli tyle samo co domyślny profil.

Kalibracja to `wsp_czas * minuty_silnika + wsp_km * kilometry_trasy`. Dystans wchodzi do wzoru, bo to
on rozdziela trasy szybkie od wolnych: przy tym samym czasie więcej kilometrów znaczy więcej VOAK-u,
gdzie Valhalla jest dokładna, a mniej kilometrów znaczy serpentyny i miasteczka, gdzie zawyża. Model
z samą skalą czasu daje MAE 5.8 min zamiast 3.4. Walidacja leave-one-out: MAE 3.9 min.

Google zostaje bez korekty, bo jest odniesieniem. **OSRM zostaje surowy świadomie**: jego błąd nie jest
ani skalą, ani przesunięciem, tylko rozrzutem od -23 do +35 min. Sama skala pogarsza MAE z 9.2 na 11.8
(max 71 min), a dopasowanie dwucechowe wychodzi niestabilne - współczynniki o przeciwnych znakach
i max 23.6 min w walidacji. Lepszy szorstki zapas niż zapas z fałszywą precyzją.

Zaokrąglanie do 5 minut zostaje: na tych samych 27 trasach kosztuje 0.06 min MAE (3.56 wobec 3.50).

Ograniczenia, o których trzeba wiedzieć:

- Kalibracja jest dopasowana do tras **z domku w Stavros** przy ruchu z jednego popołudnia. Odcinki
  między kolejnymi punktami wycieczki dostają ten sam wzór, bo koduje on sposób, w jaki Valhalla
  modeluje prędkości klas dróg na Krecie, a nie tę jedną trasę - ale nie jest to na nich zmierzone.
- Największy pozostały błąd to Seitan Limania (+8 min) i Maravel Garden (+8 min). Bez danych o ruchu
  nie ma czym tego poprawić.
- Geometria trasy rysowana na mapie nadal idzie z OSRM, więc kształt linii i czas nad nią pochodzą
  z dwóch różnych silników.

### Włączenie Google Routes

Google to sufit dokładności - jedyny silnik z ruchem drogowym. Wchodzi na początek kolejki tylko wtedy,
gdy kontener widzi klucz w `GOOGLE_ROUTES_API_KEY`. Bez niej aplikacja działa bez żadnych poświadczeń.

SKU `Routes: Compute Routes Essentials` ma **10 000 darmowych wywołań miesięcznie**, a potem 5 USD
za tysiąc. Przy 54 miejscach i cache na 24 h realne zużycie to kilkaset wywołań na miesiąc, czyli zero.
Warto sprawdzić w rozliczeniach, czy `routingPreference: TRAFFIC_AWARE` trafia w Essentials, a nie
w droższy tier - jeśli trafia w droższy, zostaje `TRAFFIC_UNAWARE` albo brak klucza.

Klucz trzeba trzymać poza repozytorium (publiczne) - w pliku `.env` obok `docker-compose.yml`,
z prawami `0600`:

```
install -m 0600 /dev/null /opt/magda-crete/.env
printf 'GOOGLE_ROUTES_API_KEY=%s\n' '<klucz>' > /opt/magda-crete/.env
docker compose -f /opt/magda-crete/docker-compose.yml up -d
```

Klucz musi mieć włączone Routes API i ograniczenie do tego jednego API.

### Współrzędne miejsc są ważniejsze od silnika

Audyt z 17 września 2026: 51 z 54 pinezek w `miejsca.csv` sprawdzone przez wyszukiwanie miejsc
w Google Maps. 31 mieści się w 600 m od prawdziwej, ale jedenaście było przesuniętych na tyle, że
psuły czas przejazdu bardziej niż jakikolwiek wybór silnika - najgorsza o 21 km. Zostały poprawione
na współrzędne z pinezki miejsca w Google.

Kalibracja silnika kupiła 2 min dokładności. Jedna zła pinezka kosztowała 80 min. **Przy każdej
skardze na czas przejazdu najpierw sprawdź pinezkę, potem silnik.**

Cztery pinezki zostały nietknięte, bo nie ma dla nich dowodu: Google zwraca na nie stronę wyników,
a nie konkretne miejsce (jaskinia Koutalas, zatoka w wąwozie Katholiko), albo pokazuje inny punkt
obiektu niż nazywa baza (wejście do wąwozu Imbros zamiast wyjścia). Przy zatoce Katholiko dochodzi
pytanie, czy współrzędna ma wskazywać parking, czy samą zatokę na końcu godzinnego marszu.

Dwa wiersze przeczyły same sobie - opis i adres wskazywały różne wioski. Rozstrzygnięte na korzyść
opisu, bo Google potwierdza obie nazwy jako sklepy z ceramiką dokładnie tam, gdzie mówi opis.
Poprawione zostały i pinezka, i adres:

| miejsce | opis mówił | adres mówił | jest teraz | skok czasu |
| --- | --- | --- | --- | --- |
| Ilys Ceramics | Margarites | Chania, Epimenidou 15 | Margarites 750 52 | 30 min na 1 godz. 50 min |
| Flakatoras Ceramics | Chania | Gavalochori | Zampeliou 19, Chania | 55 min na 30 min |

Ilys wyskoczył na 1 godz. 50 min, więc wycieczki, które go trzymały razem z czymś pod Chanią,
warto przejrzeć pod kątem sensu, a nie tylko godzin.

Przy dwóch winnicach poprawiona pinezka przeczy adresowi z bazy i wygrywa pinezka: Stemfilo ma
w bazie adres w Voukolies, a Google stawia ją pod Fournes; Manousakis ma Vatolakkos, a Google
5 km dalej na zachód. Aplikacja generuje linki nawigacyjne do Google Maps, więc zgodność z pinezką
Google jest tym, co faktycznie dowozi rodzinę na miejsce.

Geokoder Nominatim nie nadaje się do tego audytu: rozstrzygnął tylko 24 z 54 nazw i nie zna właśnie
farmy Arevitis, czyli najgorszego przypadku.

### Trzy miejsca, w których żyje ta sama współrzędna

Poprawiona pinezka musi przejść przez wszystkie trzy, inaczej poprawka jest tylko kosmetyczna:

1. `miejsca.csv` - plik fabryczny, źródło prawdy.
2. `miejsca.wspolrzedne` w bazie - stąd czyta karta miejsca. Przepisywane przez
   `zsynchronizuj_miejsca_z_csv()` przy każdym starcie.
3. `krok_wycieczki.wspolrzedne` - **stąd trasuje wycieczka**. Krok dostaje kopię przy wstawieniu
   i w całym `app.py` nie ma ani jednego `UPDATE krok_wycieczki SET wspolrzedne`. Przepisuje je
   `zsynchronizuj_wspolrzedne_krokow()`, wiążąc krok z miejscem przez `numer_miejsca` (nie przez
   nazwę - krok nazywa się „Arevitis Farm (Wizytacja)", miejsce „Arevitis Farm (farma ekologiczna)").

Jest jeszcze czwarte miejsce, którego synchronizacja **nie** rusza: tabela `czasy_dojazdu` trzyma
gotowy tekst czasu każdego odcinka, a godziny w agendzie są z niego wyprowadzone. Zapisuje ją tylko
`przelicz_i_zsynchronizuj_wycieczke`, czyli edycja kroku. Dopóki wycieczka nie zostanie przeliczona,
agenda pokazuje czasy z momentu jej ostatniej edycji - po zmianie silnika albo pinezki trzeba to
zrobić świadomie, bo przeliczanie przepisuje też pobudkę, wyjazd, powrót, okienka zwiedzania
i godziny ewakuacji.

### Statyczna kolumna "czas dojazdu ze Stavros"

Wartości w tej kolumnie w `miejsca.csv` są policzone skalibrowaną Valhallą, a nie wpisane ręcznie -
dawne wpisy rozjeżdżały się z trasowaniem o medianę 7.5 min, a w skrajnym przypadku o 84 min.
Kolumna wchodziła do bazy tylko przy pierwszym imporcie CSV, więc `zsynchronizuj_czasy_dojazdu_z_csv()`
przepisuje ją z pliku fabrycznego przy każdym starcie - bez ruchu sieciowego, tak samo jak nazwy miejsc.

Jeden wiersz jest pomijany świadomie: „Zatoka w Wąwozie Katholiko” trzyma tam prozę
(`15 min do parkingu + 1 godz. spaceru wąwozem`), której trasowanie nie odtworzy.

Przeliczenie kolumny po zmianie kalibracji robi się skryptem korzystającym z `_valhalla_czas_przejazdu`
wyciągniętego z `app.py` przez `conftest.wczytaj_funkcje_z_app` - dzięki temu plik i aplikacja liczą
tym samym kodem.

## Krótkie opisy miejsc w nazwie (1-2 słowa w nawiasie)

Zamiast trzymać opisy jako oddzielne pole (kolumna w bazie/CSV, osobny blok HTML, checkbox w pasku bocznym),
krótki deskryptor (1-2 słowa) znajduje się w nawiasie na końcu nazwy każdego odwiedzanego miejsca w `miejsca.csv`
oraz `wycieczki.csv` (np. `Pałac Minojski w Knossos (ruiny pałacu)`, `Cretaquarium (akwarium)`).

Aplikacja przy starcie synchronizuje nazwy do bazy (`zsynchronizuj_nazwy_miejsc_z_csv`), a sekcja „Plan na dzień”
wyświetla je bezpośrednio w tytule wiersza. Funkcje nawigacji i dopasowywania kroków automatycznie oczyszczają nawiasy.

## Tryb offline (PWA + service worker)

Streamlit to aplikacja serwerowa — interfejs to cienki klient na WebSockecie do
`/_stcore/stream`. Bez sieci nie wstanie i żadna konfiguracja tego nie zmieni. Offline
działa więc **osobna, statyczna strona** z zapisanym planem dnia, a nie sama aplikacja.

Elementy:

- `static/sw.js` — service worker, zasięg `/app/static/`.
- `static/offline.html` — punkt wejścia offline, `start_url` manifestu PWA.
- `static/ping.txt` — sonda łączności (worker nigdy jej nie cache'uje).
- `static/icon-*.png` — favicon i ikony PWA wygenerowane z `logo.png` (kri-kri).
  Zastąpiły zewnętrzny CDN flaticon, więc instalacja PWA nie zależy od obcej domeny.
  `icon-maskable-512.png` ma zapas tła, bo Android obcina maskable do koła o średnicy 80%
  i przy wspólnym wpisie z `any` ucinałby napis. `icon-apple-180.png` jest bez
  przezroczystości — iOS ignoruje ikony z manifestu i podkłada czerń pod kanał alfa.
- `enableStaticServing = true` w `.streamlit/config.toml` — bez tego `/app/static/`
  zwraca 404. Katalog `static/` wchodzi do obrazu przez `COPY . .`.

Przepływ: aplikacja przy wejściu w plan dnia generuje samodzielny HTML
(`generuj_autonomiczny_pakiet_offline_html`) i oddaje go do `window.__cretaiZapiszPakietOffline`,
które pisze go do Cache Storage (przez `postMessage` do workera, pod kluczem
`/app/static/dossier.html`) oraz do `localStorage` jako zapasu. `offline.html` przy starcie
sonduje `ping.txt`: gdy sieć jest — przekierowuje na `/`, gdy nie ma — renderuje pakiet.
Wymuszenie widoku offline przy działającej sieci: `/app/static/offline.html?offline=1`.

Dwie rzeczy wynikają wprost z ograniczeń Streamlita i trzeba je znać:

- **Zasięg workera to `/app/static/`, nie `/`.** Streamlit nie ustawia nagłówka
  `Service-Worker-Allowed`, więc szerszego zasięgu nie da się uzyskać bez proxy przed
  aplikacją. Skutek: wejście offline na goły `https://crete.mroczkowski.cc/` daje błąd sieci
  przeglądarki. Offline działa **ikona PWA z ekranu głównego**, bo jej `start_url` celuje
  w `/app/static/offline.html`. Gdyby to kiedyś przeszkadzało, lekarstwem jest proxy
  (np. Caddy) serwujący `/sw.js` z roota i przekierowanie ingress tunelu na jego port.
- **Rejestracja workera musi biec w realmie okna nadrzędnego.** `st.components.v1.html`
  renderuje sandboxowany iframe; `register()` wywołany w jego wnętrzu kończy się
  `An unknown error occurred when fetching the script`. Dlatego sekcja manifestu
  wstrzykuje `<script id="cretai-sw-bootstrap">` do `window.parent.document`.

Worker nie zapisuje odpowiedzi, które nie są `basic`/`ok` albo są przekierowaniem
(`mozna_zapisac`) — bez tego wygaśnięcie sesji Cloudflare Access wsadziłoby do cache ekran
logowania zamiast planu dnia.

Weryfikacja po deployu (z zalogowaną sesją Access lub tunelem do `127.0.0.1:8501`):

```
curl -sSo /dev/null -w '%{http_code} %{content_type}\n' http://127.0.0.1:8501/app/static/sw.js
curl -sSo /dev/null -w '%{http_code}\n' http://127.0.0.1:8501/app/static/offline.html
```

Worker musi wyjść jako `200 application/javascript`. Po zmianie `static/sw.js` trzeba
podnieść `CACHE_VERSION` — inaczej stary cache zostaje na urządzeniach.

## Uwagi eksploatacyjne

- `HEALTHCHECK` z `Dockerfile` odpytuje `/_stcore/health` z wnętrza kontenera, więc
  bramka Access mu nie przeszkadza. Publicznie ten endpoint jest już za logowaniem —
  zewnętrzny monitoring uptime'u nie przepuści go bez tokenu usługi (service token).
- Poświadczenia Claude leżą w `/root/.claude` na hoście i nie ma ich w repo ani w obrazie.
  To kolejny powód, żeby aplikacja nie stała otwarta — funkcje AI zużywają limit konta.
- Po zmianie kodu: `git pull && docker compose up -d --build` w `/opt/magda-crete`.
