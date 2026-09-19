(() => {
  'use strict';
  document.querySelectorAll('.theme-toggle').forEach(button => button.addEventListener('click', () => {
    const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('smartcrm-theme', theme); } catch (_) {}
  }));
  const menu = document.querySelector('#menu-toggle');
  const backdrop = document.querySelector('.sidebar-backdrop');
  const sidebar = document.querySelector('#sidebar');
  const mobile = matchMedia('(max-width: 760px)');
  const syncMenu = () => { if (sidebar) sidebar.inert = mobile.matches && !document.body.classList.contains('menu-open'); };
  mobile.addEventListener('change', syncMenu); syncMenu();
  const closeMenu = () => {
    const wasOpen = document.body.classList.contains('menu-open');
    document.body.classList.remove('menu-open');
    menu?.setAttribute('aria-expanded', 'false');
    if (backdrop) backdrop.hidden = true;
    syncMenu();
    if (wasOpen) menu?.focus();
  };
  menu?.addEventListener('click', () => {
    const open = !document.body.classList.contains('menu-open');
    document.body.classList.toggle('menu-open', open); menu.setAttribute('aria-expanded', String(open)); backdrop.hidden = !open; syncMenu();
  });
  backdrop?.addEventListener('click', closeMenu);
  document.querySelectorAll('.dismiss').forEach(button => button.addEventListener('click', () => button.closest('.notice').remove()));
  document.addEventListener('click', event => {
    document.querySelectorAll('details[open]').forEach(detail => { if (!detail.contains(event.target)) detail.open = false; });
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      closeMenu();
      document.querySelectorAll('details[open]').forEach(detail => { detail.open = false; });
      document.querySelectorAll('.client-card').forEach(card => card.classList.add('preview-dismissed'));
    }
  });
  document.querySelectorAll('.client-card').forEach(card => card.addEventListener('mouseleave', () => card.classList.remove('preview-dismissed')));

  const kind = document.querySelector('#id_kind');
  function updateFields() {
    if (!kind) return;
    const company = kind.value === 'company';
    ['industry', 'contact_person'].forEach(name => { const field = document.querySelector('[data-field="' + name + '"]'); if (field) field.hidden = !company; });
    ['company', 'position'].forEach(name => { const field = document.querySelector('[data-field="' + name + '"]'); if (field) field.hidden = company; });
    const label = document.querySelector('label[for="id_name"]');
    if (label) label.textContent = company ? 'Название компании:' : 'Имя клиента:';
  }
  kind?.addEventListener('change', updateFields); updateFields();
  const photo = document.querySelector('#id_photo');
  let previewUrl;
  photo?.addEventListener('change', () => {
    const file = photo.files[0]; const image = document.querySelector('#photo-preview');
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    photo.setCustomValidity('');
    if (!file || !image) return;
    if (file.size > 5 * 1024 * 1024) { photo.setCustomValidity('Выберите изображение до 5 МБ.'); photo.reportValidity(); return; }
    photo.setCustomValidity('');
    previewUrl = URL.createObjectURL(file); image.src = previewUrl; image.hidden = false;
    const placeholder = document.querySelector('#photo-placeholder'); if (placeholder) placeholder.hidden = true;
  });
  document.querySelectorAll('.record-form').forEach(form => form.addEventListener('submit', () => {
    const button = form.querySelector('button[type="submit"]'); button.disabled = true; button.textContent = 'Сохраняем…';
  }));
  window.addEventListener('pageshow', () => {
    document.querySelectorAll('.record-form button[type="submit"]').forEach(button => { button.disabled = false; button.textContent = 'Сохранить'; });
  });

  const drawer = document.querySelector('#client-drawer');
  const content = document.querySelector('#drawer-content');
  let controller;
  let opener;
  async function loadClient(url) {
    controller?.abort(); controller = new AbortController();
    content.replaceChildren();
    const skeleton = document.createElement('div'); skeleton.className = 'skeleton'; skeleton.textContent = 'Загружаем карточку…'; content.append(skeleton);
    try {
      const target = new URL(url, location.href); target.searchParams.set('panel', '1');
      const response = await fetch(target, {signal: controller.signal});
      if (!response.ok || response.redirected) throw new Error('request failed');
      const html = await response.text();
      content.innerHTML = html;
    } catch (error) {
      if (error.name === 'AbortError') return;
      content.replaceChildren();
      const message = document.createElement('p'); message.textContent = 'Не удалось загрузить карточку. Проверьте соединение и вход в аккаунт.';
      const retry = document.createElement('button'); retry.textContent = 'Повторить'; retry.addEventListener('click', () => loadClient(url));
      const link = document.createElement('a'); link.href = url; link.textContent = 'Открыть отдельной страницей'; link.className = 'back-link';
      content.append(message, retry, link);
    }
  }
  document.querySelectorAll('[data-client-panel]').forEach(link => link.addEventListener('click', event => {
    if (!drawer?.showModal || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault(); opener = link;
    drawer.showModal(); document.body.classList.add('drawer-open'); loadClient(link.href);
  }));
  document.querySelector('.drawer-close')?.addEventListener('click', () => drawer.close());
  drawer?.addEventListener('click', event => { if (event.target === drawer && event.clientX < drawer.getBoundingClientRect().left) drawer.close(); });
  drawer?.addEventListener('close', () => { controller?.abort(); document.body.classList.remove('drawer-open'); opener?.focus(); });
})();
