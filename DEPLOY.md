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

## Uwagi eksploatacyjne

- `HEALTHCHECK` z `Dockerfile` odpytuje `/_stcore/health` z wnętrza kontenera, więc
  bramka Access mu nie przeszkadza. Publicznie ten endpoint jest już za logowaniem —
  zewnętrzny monitoring uptime'u nie przepuści go bez tokenu usługi (service token).
- Poświadczenia Claude leżą w `/root/.claude` na hoście i nie ma ich w repo ani w obrazie.
  To kolejny powód, żeby aplikacja nie stała otwarta — funkcje AI zużywają limit konta.
- Po zmianie kodu: `git pull && docker compose up -d --build` w `/opt/magda-crete`.
