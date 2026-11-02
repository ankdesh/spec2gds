// Optional controls. The complete guide and navigation also work without scripts.
const toggle = document.querySelector('.nav-toggle');
const sidebar = document.querySelector('#sidebar');
function closeNavigation() {
  sidebar?.classList.remove('is-open');
  toggle?.setAttribute('aria-expanded', 'false');
}
toggle?.addEventListener('click', () => {
  const open = sidebar.classList.toggle('is-open');
  toggle.setAttribute('aria-expanded', String(open));
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && sidebar?.classList.contains('is-open')) {
    closeNavigation();
    toggle?.focus();
  }
});
document.addEventListener('click', event => {
  if (!sidebar?.contains(event.target) && !toggle?.contains(event.target)) closeNavigation();
});
document.querySelectorAll('pre').forEach(block => {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'copy-code';
  button.textContent = 'Copy';
  button.setAttribute('aria-label', 'Copy this code block');
  button.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(block.querySelector('code').textContent);
      button.textContent = 'Copied';
    } catch {
      button.textContent = 'Select text to copy';
    }
  });
  block.append(button);
});
