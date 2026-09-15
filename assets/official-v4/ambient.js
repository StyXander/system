/* 柔光跟随指针；仅移动时插值，跟随与背景共用暂停和系统偏好。 */
(() => {
  const hero = document.querySelector('.cinematic-landing');
  if (!hero) return;
  const preference = matchMedia('(prefers-reduced-motion: reduce)');
  const pointer = matchMedia('(hover: hover) and (pointer: fine)');
  const scenes = [hero, document.querySelector('.demo-positioning')].filter(Boolean);
  scenes.forEach(scene => {
    let ambient = scene.querySelector('.audit-ambient');
    if (!ambient) {
      ambient = document.createElement('div');
      ambient.className = 'audit-ambient';
      ambient.setAttribute('aria-hidden', 'true');
      scene.prepend(ambient);
    }
    for (const name of ['audit-diffuse-blue', 'audit-diffuse-ice']) {
      const light = document.createElement('span');
      light.className = name;
      ambient.append(light);
    }
  });
  const glow = document.createElement('div');
  glow.className = 'audit-pointer-glow';
  glow.setAttribute('aria-hidden', 'true');
  document.body.append(glow);
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'audit-motion-toggle';
  let paused = false, frame = 0, lastTime = 0;
  let x = 0, y = 0, targetX = 0, targetY = 0;
  let tracking = false;
  const visible = new Map(scenes.map(scene => [scene, true]));
  const enabled = () => !paused && !preference.matches && !document.hidden;
  function stopPointer() {
    cancelAnimationFrame(frame);
    frame = 0; lastTime = 0; tracking = false;
    glow.classList.remove('is-tracking');
  }
  function sync() {
    scenes.forEach(scene => {
      scene.dataset.motion = enabled() && visible.get(scene) ? 'running' : 'paused';
    });
    button.setAttribute('aria-pressed', String(!paused && !preference.matches));
    button.textContent = preference.matches ? '光效：已随系统关闭' : paused ? '光效：关' : '光效：开';
    button.disabled = preference.matches;
    if (!enabled() || !pointer.matches) stopPointer();
  }
  function draw(time) {
    // 按时间插值以兼容不同刷新率；靠近目标后停止空转。
    const dt = lastTime ? Math.min(time - lastTime, 64) : 16;
    lastTime = time;
    const ease = 1 - Math.exp(-dt / 65);
    x += (targetX - x) * ease; y += (targetY - y) * ease;
    glow.style.transform = `translate3d(${x}px, ${y}px, 0)`;
    if (Math.abs(targetX - x) + Math.abs(targetY - y) > .2) {
      frame = requestAnimationFrame(draw);
    } else { frame = 0; lastTime = 0; }
  }
  document.addEventListener('pointermove', event => {
    if (!enabled() || !pointer.matches || event.pointerType === 'touch') return;
    const target = document.elementFromPoint(event.clientX, event.clientY);
    glow.classList.toggle('is-dark-surface', Boolean(target && target.closest('.demo-knowledge-base')));
    targetX = event.clientX; targetY = event.clientY;
    if (!tracking) {
      x = targetX; y = targetY;
      glow.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      tracking = true; glow.classList.add('is-tracking');
    }
    if (!frame) frame = requestAnimationFrame(draw);
  }, { passive: true });
  document.documentElement.addEventListener('pointerleave', stopPointer);
  window.addEventListener('blur', stopPointer);
  button.addEventListener('click', () => { paused = !paused; sync(); });
  preference.addEventListener('change', sync);
  pointer.addEventListener('change', sync);
  document.addEventListener('visibilitychange', sync);
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => visible.set(entry.target, entry.isIntersecting)); sync();
  });
  scenes.forEach(scene => observer.observe(scene));
  hero.append(button); sync();
})();
