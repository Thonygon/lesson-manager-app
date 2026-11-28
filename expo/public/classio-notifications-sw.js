self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const path = event.notification.data && event.notification.data.path;
  const safePath = typeof path === 'string' && path.startsWith('/') && !path.startsWith('//') && !path.includes('\\') ? path : '/';
  event.waitUntil((async () => {
    const url = new URL(safePath, self.location.origin).href;
    const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const existing = clients.find((client) => new URL(client.url).origin === self.location.origin);
    if (existing) {
      await existing.navigate(url);
      return existing.focus();
    }
    return self.clients.openWindow(url);
  })());
});
