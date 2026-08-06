(() => {
  const SENSITIVE = [
    'input[type="password"]',
    'input[autocomplete="username"]',
    'input[autocomplete="current-password"]',
    'input[autocomplete="new-password"]',
    'input[autocomplete="one-time-code"]',
    'input[autocomplete="cc-number"]',
    'input[autocomplete="cc-csc"]',
    'textarea[autocomplete="one-time-code"]'
  ].join(',');

  const PRIVATE_CAPTURE = [
    SENSITIVE,
    '[contenteditable="true"]',
    'input[type="email"]',
    'input[type="tel"]',
    'input[name*="token" i]',
    'input[name*="secret" i]',
    'textarea[name*="message" i]',
    '[data-private]',
    '[aria-label*="message" i]'
  ].join(',');

  let verdict = "REVIEW";
  let scanning = false;
  let lastDigest = "";
  let overlay = null;
  let captureMasks = [];
  let scanGeneration = 0;
  let safeUntil = 0;

  function originOf(value) {
    try { return new URL(value, location.href).origin; } catch (_) { return ""; }
  }

  function forms() {
    return [...document.forms].slice(0, 32).map(form => ({
      action: form.action || location.href,
      method: (form.method || "get").toLowerCase(),
      field_types: [...form.elements].map(el => (el.type || "").toLowerCase()).filter(Boolean).slice(0, 64),
      autocomplete: [...form.elements].map(el => (el.autocomplete || "").toLowerCase()).filter(Boolean).slice(0, 64),
      target: String(form.target || "").slice(0, 80),
      hidden_fields: [...form.elements].filter(el => (el.type || "").toLowerCase() === "hidden").length
    }));
  }

  function linkMismatches() {
    return [...document.querySelectorAll('a[href]')].slice(0, 500).flatMap(anchor => {
      const text = (anchor.innerText || anchor.textContent || "").trim().slice(0, 240);
      const href = anchor.href || "";
      const visibleDomain = text.match(/(?:https?:\/\/)?([a-z0-9.-]+\.[a-z]{2,})/i)?.[1]?.toLowerCase();
      if (!visibleDomain) return [];
      try {
        const actual = new URL(href, location.href).hostname.toLowerCase();
        return actual && !actual.endsWith(visibleDomain)
          ? [{visible_domain: visibleDomain, actual_domain: actual, text}]
          : [];
      } catch (_) { return []; }
    }).slice(0, 24);
  }

  function scriptOrigins() {
    return [...new Set([...document.scripts]
      .map(script => originOf(script.src))
      .filter(Boolean))].slice(0, 48);
  }

  function packet() {
    const visible = (document.body?.innerText || "").slice(0, 20000);
    return {
      url: location.href,
      title: document.title || "",
      visible_text: visible,
      claimed_brand: detectBrand(`${document.title} ${visible.slice(0, 5000)}`),
      redirect_count: Number(sessionStorage.getItem("cyberforgeRedirectCount") || 0),
      url_reputation: "unknown",
      forms: forms(),
      link_mismatches: linkMismatches(),
      script_origins: scriptOrigins(),
      frame_count: window.frames.length,
      has_sensitive_fields: Boolean(document.querySelector(SENSITIVE)),
      screenshot_data_url: null,
      capture_redactions: 0,
      use_local_vision: true,
      consent_to_store: false
    };
  }

  function detectBrand(text) {
    const brands = ["Google", "Microsoft", "Apple", "Amazon", "PayPal", "Facebook", "Instagram", "Discord", "Slack", "TikTok", "GitHub"];
    return brands.find(name => new RegExp(`\\b${name}\\b`, "i").test(text)) || "";
  }

  function digest(value) {
    let hash = 2166136261;
    for (let i = 0; i < value.length; i++) hash = Math.imul(hash ^ value.charCodeAt(i), 16777619);
    return String(hash >>> 0);
  }

  function freeze(result) {
    verdict = result.verdict;
    if (!result.pause_sensitive_input) {
      safeUntil = Date.now() + 15000;
      removeOverlay();
      return;
    }
    safeUntil = 0;
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = "cyberforge-phishing-rod-overlay";
      overlay.style.cssText = "position:fixed;inset:0;z-index:2147483647;background:rgba(20,24,30,.72);backdrop-filter:blur(12px);display:grid;place-items:center;font-family:system-ui;color:white;padding:24px";
      overlay.innerHTML = `<div style="max-width:680px;background:#151922;border:1px solid #ff6b6b;border-radius:18px;padding:28px;box-shadow:0 18px 80px #0008"><h1 style="margin-top:0">PHISHING ROD</h1><p>Credential entry is temporarily paused while this page is reviewed.</p><p id="cyberforge-rod-verdict" style="font-weight:700"></p><pre id="cyberforge-rod-signals" style="white-space:pre-wrap;max-height:260px;overflow:auto"></pre><div style="display:flex;gap:12px;flex-wrap:wrap"><button id="cyberforge-rod-back" style="padding:12px 18px">Go back</button><button id="cyberforge-rod-rescan" style="padding:12px 18px">Rescan</button></div><p style="opacity:.72;font-size:12px">SAFE means no strong danger was detected, not a guarantee.</p></div>`;
      document.documentElement.appendChild(overlay);
      overlay.querySelector("#cyberforge-rod-back")?.addEventListener("click", () => history.back());
      overlay.querySelector("#cyberforge-rod-rescan")?.addEventListener("click", () => scan("manual-rescan", true));
    }
    const verdictBox = overlay.querySelector("#cyberforge-rod-verdict");
    if (verdictBox) verdictBox.textContent = `${result.visible_verdict || result.verdict} · risk ${Number(result.risk_score || 0).toFixed(3)}`;
    const signalBox = overlay.querySelector("#cyberforge-rod-signals");
    if (signalBox) signalBox.textContent = (result.signals || []).map(s => `• ${s.code}: ${s.detail}`).join("\n") || "Review required.";
  }

  function removeOverlay() {
    overlay?.remove();
    overlay = null;
  }

  function prepareCapture() {
    restoreCapture();
    const elements = [...document.querySelectorAll(PRIVATE_CAPTURE)].slice(0, 4096);
    for (const element of elements) {
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0 || rect.bottom < 0 || rect.right < 0 || rect.top > innerHeight || rect.left > innerWidth) continue;
      const mask = document.createElement("div");
      mask.dataset.cyberforgeCaptureMask = "true";
      mask.style.cssText = `position:fixed;left:${Math.max(0, rect.left)}px;top:${Math.max(0, rect.top)}px;width:${Math.min(innerWidth, rect.width)}px;height:${Math.min(innerHeight, rect.height)}px;background:#111;z-index:2147483646;border-radius:4px;pointer-events:none`;
      document.documentElement.appendChild(mask);
      captureMasks.push(mask);
    }
    return captureMasks.length;
  }

  function restoreCapture() {
    captureMasks.forEach(mask => mask.remove());
    captureMasks = [];
  }

  async function scan(reason, force = false) {
    if (scanning || !document.body) return;
    const data = packet();
    const key = digest(JSON.stringify({url: data.url, forms: data.forms, title: data.title, text: data.visible_text.slice(0, 3000), links: data.link_mismatches}));
    if (!force && key === lastDigest && reason !== "sensitive-focus") return;
    lastDigest = key;
    scanning = true;
    const generation = ++scanGeneration;
    try {
      const response = await chrome.runtime.sendMessage({type: "CYBERFORGE_PHISHING_ANALYZE", packet: data});
      if (generation !== scanGeneration) return;
      if (response?.ok) freeze(response.result);
      else {
        verdict = "REVIEW";
        safeUntil = 0;
      }
    } finally {
      scanning = false;
    }
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === "CYBERFORGE_PREPARE_CAPTURE") {
      sendResponse({redactions: prepareCapture()});
      return true;
    }
    if (message?.type === "CYBERFORGE_RESTORE_CAPTURE") {
      restoreCapture();
      sendResponse({ok: true});
      return true;
    }
    return false;
  });

  document.addEventListener("focusin", event => {
    if (event.target?.matches?.(SENSITIVE)) scan("sensitive-focus");
  }, true);

  document.addEventListener("beforeinput", event => {
    const currentlySafe = verdict === "SAFE" && Date.now() < safeUntil;
    if (event.target?.matches?.(SENSITIVE) && !currentlySafe) {
      event.preventDefault();
      scan("sensitive-input");
    }
  }, true);

  document.addEventListener("paste", event => {
    const currentlySafe = verdict === "SAFE" && Date.now() < safeUntil;
    if (event.target?.matches?.(SENSITIVE) && !currentlySafe) {
      event.preventDefault();
      scan("sensitive-paste");
    }
  }, true);

  document.addEventListener("submit", event => {
    const currentlySafe = verdict === "SAFE" && Date.now() < safeUntil;
    if (event.target?.querySelector?.(SENSITIVE) && !currentlySafe) {
      event.preventDefault();
      event.stopImmediatePropagation();
      scan("sensitive-submit");
    }
  }, true);

  addEventListener("pagehide", restoreCapture, {capture: true});
  addEventListener("DOMContentLoaded", () => setTimeout(() => scan("load"), 700), {once: true});
  const observer = new MutationObserver(() => {
    if (document.querySelector(SENSITIVE)) setTimeout(() => scan("sensitive-dom"), 350);
  });
  observer.observe(document.documentElement, {subtree: true, childList: true, attributes: true, attributeFilter: ["action", "href", "src", "autocomplete", "type"]});
})();
