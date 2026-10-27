// Visible mouse pointer for screen recordings (headless Chrome draws none).
(() => {
  const draw = () => {
    if (document.getElementById('__cursor')) return;
    const c = document.createElement('div');
    c.id = '__cursor';
    c.style.cssText = 'position:fixed;left:0;top:0;width:22px;height:22px;z-index:2147483647;' +
      'pointer-events:none;border-radius:50%;background:rgba(234,35,40,.35);' +
      'border:2px solid #ea2328;transform:translate(-50%,-50%);transition:transform .08s';
    document.documentElement.appendChild(c);
    addEventListener('mousemove', (e) => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
    addEventListener('mousedown', () => { c.style.transform = 'translate(-50%,-50%) scale(.7)'; }, true);
    addEventListener('mouseup', () => { c.style.transform = 'translate(-50%,-50%)'; }, true);
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', draw); else draw();
})();
