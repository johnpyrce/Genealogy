/* Served only by the production gateway; never included in local previews. */
(() => {
  let timezone = null;
  try { timezone = Intl.DateTimeFormat().resolvedOptions().timeZone; } catch {}
  const context = {
    timezone,
    utc_offset_minutes: -new Date().getTimezoneOffset(),
    language: navigator.language || null,
  };
  for (const [key, value] of Object.entries(context)) {
    const input = document.querySelector(`input[name="${key}"]`);
    if (input && value !== null) input.value = value;
  }
  const script = document.currentScript;
  if (script?.dataset.event && script?.dataset.token) {
    fetch('/__access/context', {
      method: 'POST', credentials: 'same-origin', keepalive: true,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...context, id: script.dataset.event, token: script.dataset.token }),
    }).catch(() => {});
  }
})();
