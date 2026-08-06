(() => {
  const SENSITIVE = [
    'input[type="password"]',
    'input[autocomplete="username"]',
    'input[autocomplete="current-password"]',
    'input[autocomplete="new-password"]',
    'input[autocomplete="one-time-code"]',
    'input[autocomplete="cc-number"]',
    'input[autocomplete="cc-csc"]'
  ].join(',');

  let verdict = "REVIEW";
  let scanning = false;
  let lastDigest = "";
  let overlay = null;

  function forms() {
    return [...document.forms].slice(0, 32).map(form => ({
      action: form.action || location.href,
      method: (form.method || "get").toLowerCase(),
      field_types: [...form.elements].map(el => (el.type || "").toLowerCase()).filter(Boolean),
      autocomplete: [...form.elements].map(el => (el.autocomplete || "").toLowerCase()).filter(Boolean)
    }));
  }

  function packet() {
    const visible = (document.body?.innerText || "").slice(0, 20000);
    return {
      url: location.href,
      title: document.title || "",
      visible_text: visible,
      claimed_brand: detectBrand(`${document.title} ${visible.slice(0, 3000)}`),
      redirect_count: 0,
      url_reputation: "unknown",
      forms: forms(),
      screenshot_data_url: null,
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
      removeOverlay();
      return;
    }
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = "cyberforge-phishing-rod-overlay";
      overlay.style.cssText = "position:fixed;inset:0;z-index:2147483647;background:rgba(20,24,30,.72);backdrop-filter:blur(12px);display:grid;place-items:center;font-family:system-ui;color:white;padding:24px";
      overlay.innerHTML = `<div style="max-width:620px;background:#151922;border:1px solid #ff6b6b;border-radius:18px;padding:28px;box-shadow:0 18px 80px #0008"><h1 style="margin-top:0">PHISHING ROD</h1><p>Credential entry is temporarily paused while this page is reviewed.</p><pre id="cyberforge-rod-signals" style="white-space:pre-wrap"></pre><button id="cyberforge-rod-back" style="padding:12px 18px">Go back</button></div>`;
      document.documentElement.appendChild(overlay);
      overlay.querySelector("#cyberforge-rod-back")?.addEventListener("click", () => history.back());
    }
    const signalBox = overlay.querySelector("#cyberforge-rod-signals");
    if (signalBox) signalBox.textContent = (result.signals || []).map(s => `• ${s.code}: ${s.detail}`).join("\n") || "Review required.";
  }

  function removeOverlay() {
    overlay?.remove();
    overlay = null;
  }

  async function scan(reason) {
    if (scanning || !document.body) return;
    const data = packet();
    const key = digest(JSON.stringify({url: data.url, forms: data.forms, title: data.title, text: data.visible_text.slice(0, 3000)}));
    if (key === lastDigest && reason !== "sensitive-focus") return;
    lastDigest = key;
    scanning = true;
    try {
      const response = await chrome.runtime.sendMessage({type: "CYBERFORGE_PHISHING_ANALYZE", packet: data});
      if (response?.ok) freeze(response.result);
      else verdict = "REVIEW";
    } finally {
      scanning = false;
    }
  }

  document.addEventListener("focusin", event => {
    if (event.target?.matches?.(SENSITIVE)) scan("sensitive-focus");
  }, true);

  document.addEventListener("beforeinput", event => {
    if (event.target?.matches?.(SENSITIVE) && verdict !== "SAFE") {
      event.preventDefault();
      scan("sensitive-input");
    }
  }, true);

  document.addEventListener("submit", event => {
    if (event.target?.querySelector?.(SENSITIVE) && verdict !== "SAFE") {
      event.preventDefault();
      event.stopImmediatePropagation();
      scan("sensitive-submit");
    }
  }, true);

  addEventListener("DOMContentLoaded", () => setTimeout(() => scan("load"), 600), {once: true});
  const observer = new MutationObserver(() => {
    if (document.querySelector(SENSITIVE)) setTimeout(() => scan("sensitive-dom"), 250);
  });
  observer.observe(document.documentElement, {subtree: true, childList: true});
})();
