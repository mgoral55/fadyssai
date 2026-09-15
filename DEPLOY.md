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

| silnik | klucz | mediana błędu wobec Google | uwagi |
| --- | --- | --- | --- |
| Google Routes v2 | wymagany | odniesienie | uwzględnia ruch, jedyny płatny |
| Valhalla (publiczna OSM) | nie | +5 min (MAE 4.9 min) | domyślny, mediana opóźnienia 0.89 s |
| OSRM (serwer demo) | nie | -23 do +35 min (MAE 16.4 min) | zapas |
| szacunek geometryczny | nie | bez sieci | min/km z dystansu w linii prostej |

Pomiar: 54 miejsca z bazy przeliczone każdym silnikiem plus 12 tras sprawdzonych ręcznie w Google Maps
(dojazd z domku w Stavros). Profil demo OSRM liczy dojazd na lotnisko w Heraklionie na 2 h 58 min,
a Google i Valhalla zgodnie dają 2 h 29 min / 2 h 31 min — dlatego OSRM zszedł na drugie miejsce.
Geometria trasy rysowana na mapie nadal idzie z OSRM, więc kształt linii i czas nad nią pochodzą
z dwóch różnych silników.

Valhalla jest konsekwentnie o ok. 9% ostrożniejsza od Google, a na odcinkach poniżej 5 km potrafi
podwoić czas (Google daje 5 min na plażę w Stavros, Valhalla 9 min). Zapas na przyjazd przed czasem
jest tu celowo zostawiony bez korekty — nie ma go jak rzetelnie dopasować na 12 punktach odniesienia.

### Włączenie Google Routes

Silnik Google wchodzi na początek kolejki tylko wtedy, gdy kontener widzi klucz w zmiennej
`GOOGLE_ROUTES_API_KEY`. Bez niej aplikacja działa bez żadnych poświadczeń, tak jak dotąd.
Klucz trzeba trzymać poza repozytorium (publiczne) — w pliku `.env` obok `docker-compose.yml`,
z prawami `0600`:

```
install -m 0600 /dev/null /opt/magda-crete/.env
printf 'GOOGLE_ROUTES_API_KEY=%s\n' '<klucz>' > /opt/magda-crete/.env
docker compose -f /opt/magda-crete/docker-compose.yml up -d
```

Klucz musi mieć włączone Routes API i ograniczenie do tego jednego API. Odpowiedzi są cache'owane
na 24 h (`@st.cache_data`), więc jedno miejsce to jedno zapytanie na dobę.

### Statyczna kolumna "czas dojazdu ze Stavros"

Wartości w tej kolumnie w `miejsca.csv` są policzone Valhallą, a nie wpisane ręcznie — dawne
wpisy rozjeżdżały się z trasowaniem o medianę 7.5 min, a w skrajnym przypadku o 84 min.
Kolumna wchodziła do bazy tylko przy pierwszym imporcie CSV, więc `zsynchronizuj_czasy_dojazdu_z_csv()`
przepisuje ją z pliku fabrycznego przy każdym starcie — bez ruchu sieciowego, tak samo jak nazwy miejsc.

Jeden wiersz jest pomijany świadomie: „Zatoka w Wąwozie Katholiko” trzyma tam prozę
(`15 min do parkingu + 1 godz. spaceru wąwozem`), której trasowanie nie odtworzy.

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
