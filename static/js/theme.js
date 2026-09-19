(() => {
  let theme;
  try { theme = localStorage.getItem('smartcrm-theme'); } catch (_) {}
  if (!['light', 'dark'].includes(theme)) theme = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  document.documentElement.dataset.theme = theme;
})();
