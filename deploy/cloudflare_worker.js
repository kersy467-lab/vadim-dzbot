/**
 * Cloudflare Worker for School Class Bot & Mini App
 * 
 * 1. CDN Edge Caching: Caches photos (/api/media/*), bells, static JS/CSS and assets.
 *    Drastically reduces Render outbound bandwidth usage by 95-99%.
 * 2. Keep-Alive Cron: Pings Render's /health endpoint every 10 minutes to prevent sleeping.
 * 3. Transparent Reverse Proxy: Fast, low-latency streaming for live duels & API.
 */

// Your Render backend URL (without trailing slash)
const ORIGIN_URL = "https://dzbot-6eid.onrender.com";

// Cache TTL configurations (in seconds)
const CACHE_RULES = [
  // Telegram photos from homework: 7 days (604800 sec)
  { prefix: "/api/media/", ttl: 604800 },
  // Bell schedule & subjects: 7 days (604800 sec)
  { prefix: "/api/bells", ttl: 604800 },
  { prefix: "/api/subjects", ttl: 604800 },
  // Permanent week schedule: 7 days
  { prefix: "/api/schedule/week", ttl: 604800 },
  // Daily schedule: 2 minutes (120 sec)
  { prefix: "/api/schedule", ttl: 120 },
  // Static frontend assets (images, fonts, scripts, css): 7 days
  { prefix: "/static/", ttl: 604800 },
];

export default {
  /**
   * Handle incoming HTTP requests from users / Mini App
   */
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const targetUrl = new URL(url.pathname + url.search, env.ORIGIN_URL || ORIGIN_URL);

    // Support WebSocket upgrade for multiplayer games (Durak, Blackjack)
    if (request.headers.get("Upgrade") === "websocket") {
      return fetch(targetUrl.toString(), request);
    }

    // Only GET and HEAD requests can be cached
    const isGetOrHead = request.method === "GET" || request.method === "HEAD";
    const cacheRule = isGetOrHead
      ? CACHE_RULES.find((rule) => url.pathname.startsWith(rule.prefix))
      : null;

    const cache = caches.default;

    // 1. Check Cloudflare Edge Cache
    if (cacheRule) {
      const cachedResponse = await cache.match(request);
      if (cachedResponse) {
        const newHeaders = new Headers(cachedResponse.headers);
        newHeaders.set("X-Cache-Status", "HIT-CLOUDFLARE");
        return new Response(cachedResponse.body, {
          status: cachedResponse.status,
          statusText: cachedResponse.statusText,
          headers: newHeaders,
        });
      }
    }

    // 2. Prepare request to Render backend
    const originHeaders = new Headers(request.headers);
    originHeaders.set("Host", targetUrl.host);
    originHeaders.set("X-Forwarded-Host", url.host);
    originHeaders.set("X-Forwarded-Proto", url.protocol.replace(":", ""));

    const modifiedRequest = new Request(targetUrl.toString(), {
      method: request.method,
      headers: originHeaders,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      redirect: "follow",
    });

    // 3. Fetch from Render
    let response;
    try {
      response = await fetch(modifiedRequest);
    } catch (err) {
      return new Response(`Origin Connection Error: ${err.message}`, { status: 502 });
    }

    // 4. Cache valid response if matching rule
    if (cacheRule && response.status === 200) {
      const responseToCache = new Response(response.body, response);
      responseToCache.headers.set(
        "Cache-Control",
        `public, max-age=${cacheRule.ttl}, s-maxage=${cacheRule.ttl}`
      );
      responseToCache.headers.set("X-Cache-Status", "MISS-CACHED");

      // Asynchronously store in Cloudflare cache without blocking client
      ctx.waitUntil(cache.put(request, responseToCache.clone()));
      return responseToCache;
    }

    // 5. Return dynamic response
    const dynamicHeaders = new Headers(response.headers);
    dynamicHeaders.set("X-Cache-Status", "BYPASS");
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: dynamicHeaders,
    });
  },

  /**
   * Cron Trigger: Automatically pings Render every 10 minutes to prevent sleep
   */
  async scheduled(event, env, ctx) {
    const healthUrl = `${env.ORIGIN_URL || ORIGIN_URL}/health`;
    console.log(`[KeepAlive] Pinging ${healthUrl}...`);
    try {
      const res = await fetch(healthUrl, { method: "GET", timeout: 10000 });
      console.log(`[KeepAlive] Response status: ${res.status}`);
    } catch (err) {
      console.error(`[KeepAlive] Ping failed: ${err.message}`);
    }
  },
};
