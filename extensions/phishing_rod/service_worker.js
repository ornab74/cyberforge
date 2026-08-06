const ENDPOINT = "http://127.0.0.1:8787/v1/phishing-rod/analyze";
const STATUS_ENDPOINT = "http://127.0.0.1:8787/v1/phishing-rod/status";
const MAX_SCREENSHOT_CHARS = 3_500_000;
const REQUEST_TIMEOUT_MS = 15000;

async function fetchJson(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(url, {...options, signal: controller.signal, redirect: "error"});
    if (!response.ok) throw new Error(`CyberForge returned ${response.status}`);
    const text = await response.text();
    if (text.length > 1_000_000) throw new Error("CyberForge response exceeded size limit");
    return JSON.parse(text);
  } finally {
    clearTimeout(timer);
  }
}

async function captureRedactedTab(sender) {
  const tabId = sender?.tab?.id;
  const windowId = sender?.tab?.windowId;
  if (!Number.isInteger(tabId) || !Number.isInteger(windowId)) return {dataUrl: null, redactions: 0};

  let prepared = null;
  try {
    prepared = await chrome.tabs.sendMessage(tabId, {type: "CYBERFORGE_PREPARE_CAPTURE"});
    const dataUrl = await chrome.tabs.captureVisibleTab(windowId, {
      format: "jpeg",
      quality: 55,
    });
    if (typeof dataUrl !== "string" || dataUrl.length > MAX_SCREENSHOT_CHARS) {
      throw new Error("Redacted screenshot exceeded the local limit");
    }
    return {dataUrl, redactions: Number(prepared?.redactions || 0)};
  } catch (error) {
    return {dataUrl: null, redactions: Number(prepared?.redactions || 0), error: String(error)};
  } finally {
    try {
      await chrome.tabs.sendMessage(tabId, {type: "CYBERFORGE_RESTORE_CAPTURE"});
    } catch (_) {}
  }
}

async function analyzePacket(packet, sender) {
  const status = await fetchJson(STATUS_ENDPOINT).catch(() => null);
  const shouldCapture = Boolean(packet?.has_sensitive_fields) && Boolean(status?.vision?.enabled);
  if (shouldCapture) {
    const capture = await captureRedactedTab(sender);
    packet.screenshot_data_url = capture.dataUrl;
    packet.capture_redactions = capture.redactions;
    packet.capture_error = capture.error || null;
  } else {
    packet.screenshot_data_url = null;
    packet.capture_redactions = 0;
  }
  return await fetchJson(ENDPOINT, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(packet),
  });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "CYBERFORGE_PHISHING_ANALYZE") return false;
  (async () => {
    try {
      const result = await analyzePacket({...message.packet}, sender);
      sendResponse({ok: true, result});
    } catch (error) {
      sendResponse({ok: false, error: String(error)});
    }
  })();
  return true;
});
