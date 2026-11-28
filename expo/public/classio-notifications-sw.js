self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const path = event.notification.data && event.notification.data.path;
  const safePath = typeof path === 'string' && path.startsWith('/') && !path.startsWith('//') && !path.includes('\\') ? path : '/';
  event.waitUntil((async () => {
    const target = new URL(safePath, self.location.origin);
    const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const existing = clients.find((client) => new URL(client.url).origin === self.location.origin);
    if (existing) {
      const currentPath = new URL(existing.url).pathname;
      if (target.pathname === '/oral-assignment' && currentPath !== '/oral-assignment') target.searchParams.set('from', currentPath);
      await existing.navigate(target.href);
      return existing.focus();
    }
    return self.clients.openWindow(target.href);
  })());
});
