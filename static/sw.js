const CACHE_NAME = 'bitrade-v1';
const STATIC_ASSETS = [
  '/static/css/bauhaus.css',
  '/static/manifest.json',
  '/static/icons/icon.svg',
];

// 설치: 정적 자산만 캐싱
self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// 활성화: 이전 캐시 삭제
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// fetch: 네트워크 우선, 실패 시 캐시 폴백
// API 요청(/api/*)은 캐시 없이 항상 네트워크
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);

  // API, 인증 관련은 캐시 건너뜀
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/login') || url.pathname.startsWith('/logout')) {
    return;
  }

  e.respondWith(
    fetch(e.request)
      .then((res) => {
        // 정적 자산은 캐시 업데이트
        if (STATIC_ASSETS.includes(url.pathname)) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(e.request, clone));
        }
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});
