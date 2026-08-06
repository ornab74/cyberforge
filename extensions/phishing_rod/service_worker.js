const ENDPOINT = "http://127.0.0.1:8787/v1/phishing-rod/analyze";

async function analyzePacket(packet) {
  const response = await fetch(ENDPOINT, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(packet),
  });
  if (!response.ok) {
    throw new Error(`CyberForge returned ${response.status}`);
  }
  return await response.json();
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "CYBERFORGE_PHISHING_ANALYZE") return false;
  (async () => {
    try {
      const result = await analyzePacket(message.packet);
      sendResponse({ok: true, result});
    } catch (error) {
      sendResponse({ok: false, error: String(error)});
    }
  })();
  return true;
});
