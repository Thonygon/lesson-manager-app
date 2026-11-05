// Informational notice. Dismissal is not consent and never gates essential storage.
(() => {
  const version = '2026-11-05.1';
  const key = 'masterClassioStorageNoticeSeen';
  const banner = document.getElementById('storage-notice');
  const message = document.getElementById('storage-notice-message');
  const link = document.getElementById('storage-notice-link');
  const dismiss = document.getElementById('storage-notice-dismiss');
  if (!banner || !message || !link || !dismiss) return;
  const copy = {
    en: ['We use essential security storage and local preferences to remember your settings.', 'Storage details', 'Got it'],
    es: ['Usamos almacenamiento esencial de seguridad y preferencias locales para recordar tus ajustes.', 'Detalles de almacenamiento', 'Entendido'],
    tr: ['Güvenlik için gerekli depolama ve ayarlarınızı hatırlayan yerel tercihleri kullanıyoruz.', 'Depolama ayrıntıları', 'Anladım'],
  };
  const update = () => {
    const language = ['en', 'es', 'tr'].includes(document.documentElement.lang) ? document.documentElement.lang : 'en';
    const [body, details, close] = copy[language];
    message.textContent = body;
    link.textContent = details;
    link.href = `/cookies/${language}/`;
    dismiss.textContent = close;
    banner.setAttribute('aria-label', details);
  };
  update();
  new MutationObserver(update).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
  try { banner.hidden = localStorage.getItem(key) === version; } catch { banner.hidden = false; }
  dismiss.addEventListener('click', () => {
    banner.hidden = true;
    try { localStorage.setItem(key, version); } catch { /* The notice can be dismissed for this page without storage. */ }
  });
})();
