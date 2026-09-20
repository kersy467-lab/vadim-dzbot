/**
 * Cloudflare Worker for Telegram Class Bot & Mini App
 * Features:
 * 1. Cron Keep-Alive: Sends a GET request to Render /health every 10 minutes to prevent the free instance from sleeping.
 * 2. Reverse Proxy: Proxies all requests directly to the Render origin backend.
 */

const RENDER_ORIGIN = "https://YOUR-RENDER-APP-NAME.onrender.com"; // Замените на ваш URL на Render

export default {
  // 1. Cron Trigger Handler (Keep-Alive)
  async scheduled(event, env, ctx) {
    const targetUrl = env.RENDER_ORIGIN || RENDER_ORIGIN;
    try {
      const resp = await fetch(`${targetUrl}/health`);
      console.log(`Keep-alive ping to ${targetUrl}/health: status ${resp.status}`);
    } catch (err) {
      console.error(`Failed keep-alive ping: ${err.message}`);
    }
  },

  // 2. HTTP Request Proxy Handler
  async fetch(request, env, ctx) {
    const targetOrigin = env.RENDER_ORIGIN || RENDER_ORIGIN;
    const url = new URL(request.url);
    const targetUrl = new URL(url.pathname + url.search, targetOrigin);

    // Clone headers
    const headers = new Headers(request.headers);
    headers.set("X-Forwarded-Host", url.hostname);
    headers.set("X-Forwarded-Proto", url.protocol.replace(":", ""));

    const init = {
      method: request.method,
      headers: headers,
      body: request.body,
      redirect: "follow"
    };

    try {
      const response = await fetch(targetUrl.toString(), init);
      return response;
    } catch (err) {
      return new Response(`Error proxying to backend: ${err.message}`, { status: 502 });
    }
  }
};
