/*
 * Service worker CretAi.
 *
 * Zasięg to `/app/static/` (Streamlit serwuje katalog `static/` właśnie stamtąd i nie
 * ustawia nagłówka `Service-Worker-Allowed`, więc szerszego zasięgu nie da się uzyskać
 * bez proxy przed aplikacją). Dlatego punktem wejścia offline jest `offline.html`,
 * ustawiony jako `start_url` manifestu PWA — ikona na ekranie głównym startuje wewnątrz
 * zasięgu i działa bez sieci.
 *
 * Worker nie próbuje cache'ować samego Streamlita: aplikacja wymaga żywego WebSocketa
 * do `/_stcore/stream`, więc offline i tak by nie wstała.
 */

const CACHE_VERSION = 'cretai-offline-v2';
const SCOPE_PATH = '/app/static/';
const OFFLINE_PAGE = SCOPE_PATH + 'offline.html';
const DOSSIER_KEY = SCOPE_PATH + 'dossier.html';
const PING_PATH = SCOPE_PATH + 'ping.txt';

const PRECACHE = [OFFLINE_PAGE];

/**
 * Za aplikacją stoi Cloudflare Access. Po wygaśnięciu sesji każde zapytanie dostaje
 * przekierowanie na ekran logowania — takiej odpowiedzi nie wolno zapisać w cache,
 * bo offline zamiast planu dnia pokazałby formularz logowania.
 */
function mozna_zapisac(response) {
  return Boolean(
    response &&
    response.ok &&
    response.type === 'basic' &&
    !response.redirected
  );
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((klucze) => Promise.all(
        klucze
          .filter((k) => k !== CACHE_VERSION)
          .map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

/*
 * Strona Streamlita leży poza zasięgiem workera, więc nie jest przez niego kontrolowana
 * i `navigator.serviceWorker.controller` jest tam nullem. Pakiet offline dociera więc
 * przez `registration.active.postMessage` i ładowany jest do Cache Storage — w odróżnieniu
 * od localStorage nie ma tu limitu ~5 MB ani ryzyka osobnego magazynu dla PWA na iOS.
 */
self.addEventListener('message', (event) => {
  const dane = event.data || {};
  if (dane.type !== 'CACHE_DOSSIER' || !dane.html) {
    return;
  }

  const odpowiedz = new Response(dane.html, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'X-Cretai-Trip-Id': String(dane.tripId || ''),
    },
  });

  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.put(DOSSIER_KEY, odpowiedz))
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;

  if (request.method !== 'GET') {
    return;
  }

  const url = new URL(request.url);
  if (url.origin !== self.location.origin || !url.pathname.startsWith(SCOPE_PATH)) {
    return;
  }

  // Sonda łączności używana przez offline.html musi zawsze iść do sieci,
  // inaczej odpowiedź z cache udawałaby działającą aplikację.
  if (url.pathname === PING_PATH) {
    event.respondWith(fetch(request, { cache: 'no-store' }));
    return;
  }

  // Pakiet offline istnieje wyłącznie w cache — nie ma go na dysku serwera.
  if (url.pathname === DOSSIER_KEY) {
    event.respondWith(
      caches.match(DOSSIER_KEY).then(
        (trafienie) => trafienie || new Response('', { status: 404 })
      )
    );
    return;
  }

  // Reszta zasięgu: natychmiast z cache, w tle odświeżenie (stale-while-revalidate).
  //
  // Kluczem cache jest URL bez query. Bez tej normalizacji `offline.html?offline=1`
  // byłby osobnym wpisem: cache rósłby o jeden rekord na każdy wariant parametrów,
  // a zimny start bez sieci pod adresem z query nie trafiałby w wpis z precache.
  const klucz = url.origin + url.pathname;

  event.respondWith(
    caches.match(klucz).then((trafienie) => {
      const zSieci = fetch(request)
        .then((response) => {
          if (mozna_zapisac(response)) {
            const kopia = response.clone();
            caches.open(CACHE_VERSION).then((cache) => cache.put(klucz, kopia));
          }
          return response;
        })
        .catch(() => trafienie || new Response(
          'Brak sieci i brak kopii w cache.',
          { status: 504, statusText: 'Gateway Timeout' }
        ));

      return trafienie || zSieci;
    })
  );
});
