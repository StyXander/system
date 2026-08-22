(function () {
  "use strict";

  const landing = document.getElementById("fusion-landing");
  const canvas = document.getElementById("fusion-fx");
  if (!landing || !canvas) return;

  const context = canvas.getContext("2d", { alpha: true });
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const compactViewport = window.matchMedia("(max-width: 760px)");
  const palette = {
    glow: { r: 220, g: 232, b: 238 },
    accent: { r: 120, g: 174, b: 185 },
    copper: { r: 185, g: 154, b: 99 },
  };

  let width = 0;
  let height = 0;
  let ratio = 1;
  let frame = 0;
  let phase = Math.random() * 100;
  let animationFrame = 0;
  let visible = true;
  let particles = [];
  let ripples = [];
  let hover = 0;
  let hoverTarget = 0;
  const pointer = { x: 0.5, y: 0.5, targetX: 0.5, targetY: 0.5 };

  function rgba(color, alpha) {
    return `rgba(${color.r}, ${color.g}, ${color.b}, ${alpha})`;
  }

  function newParticle(initial) {
    const max = Math.min(width, height) * 0.62;
    return {
      angle: Math.random() * Math.PI * 2,
      distance: initial ? Math.random() * max : 8 * ratio,
      speed: (0.12 + Math.random() * 0.34) * ratio,
      drift: (Math.random() - 0.5) * 0.004,
      size: (0.55 + Math.random() * 1.45) * ratio,
      alpha: 0.1 + Math.random() * 0.28,
      max,
      copper: Math.random() > 0.84,
    };
  }

  function resetParticles() {
    particles = [];
    const count = compactViewport.matches ? 32 : 72;
    for (let index = 0; index < count; index += 1) particles.push(newParticle(true));
  }

  function resizeCanvas() {
    const bounds = landing.getBoundingClientRect();
    ratio = Math.min(window.devicePixelRatio || 1, 2);
    width = Math.max(1, Math.floor(bounds.width * ratio));
    height = Math.max(1, Math.floor(bounds.height * ratio));
    canvas.width = width;
    canvas.height = height;
    canvas.style.width = `${bounds.width}px`;
    canvas.style.height = `${bounds.height}px`;
    resetParticles();
    drawStaticFrame();
  }

  function drawGlow(x, y) {
    const pulse = 1 + Math.sin(phase * 1.35) * 0.065;
    const radius = Math.min(width, height) * 0.31 * pulse * (1 - hover * 0.05);
    const intensity = 1 + hover * 0.32;
    const fringes = [
      { color: palette.accent, x: -9 * ratio, y: -4 * ratio, alpha: 0.11 * intensity },
      { color: palette.copper, x: 8 * ratio, y: 5 * ratio, alpha: 0.045 * intensity },
      { color: palette.glow, x: 0, y: 0, alpha: 0.13 * intensity },
    ];
    fringes.forEach((fringe) => {
      const gradient = context.createRadialGradient(
        x + fringe.x,
        y + fringe.y,
        0,
        x + fringe.x,
        y + fringe.y,
        radius,
      );
      gradient.addColorStop(0, rgba(fringe.color, fringe.alpha));
      gradient.addColorStop(0.45, rgba(fringe.color, fringe.alpha * 0.32));
      gradient.addColorStop(1, rgba(fringe.color, 0));
      context.fillStyle = gradient;
      context.fillRect(x - radius, y - radius, radius * 2, radius * 2);
    });
  }

  function drawRays(x, y) {
    const count = compactViewport.matches ? 9 : 15;
    const maxLength = Math.min(width, height) * 0.62;
    for (let index = 0; index < count; index += 1) {
      const angle = (index / count) * Math.PI * 2 + phase * 0.13 + Math.sin(phase * 0.5 + index) * 0.1;
      const length = maxLength * (0.4 + 0.58 * Math.abs(Math.sin(phase * 0.68 + index * 1.7)));
      const alpha = 0.02 + 0.042 * Math.abs(Math.sin(phase * 0.88 + index * 2.1));
      const endX = x + Math.cos(angle) * length;
      const endY = y + Math.sin(angle) * length;
      const gradient = context.createLinearGradient(x, y, endX, endY);
      gradient.addColorStop(0, rgba(palette.glow, alpha));
      gradient.addColorStop(1, rgba(palette.glow, 0));
      context.strokeStyle = gradient;
      context.lineWidth = 1.05 * ratio;
      context.beginPath();
      context.moveTo(x, y);
      context.lineTo(endX, endY);
      context.stroke();
    }
  }

  function drawBeam(x, y) {
    const radius = Math.min(width, height) * 0.78;
    const angle = phase * 0.31;
    const spread = 0.44;
    const gradient = context.createRadialGradient(x, y, 0, x, y, radius);
    gradient.addColorStop(0, rgba(palette.accent, 0.046));
    gradient.addColorStop(1, rgba(palette.accent, 0));
    context.fillStyle = gradient;
    context.beginPath();
    context.moveTo(x, y);
    context.arc(x, y, radius, angle - spread / 2, angle + spread / 2);
    context.closePath();
    context.fill();
  }

  function drawRipples(x, y, animate) {
    if (animate && frame % (compactViewport.matches ? 132 : 98) === 0) {
      ripples.push({ radius: 18 * ratio, alpha: 0.13 });
    }
    for (let index = ripples.length - 1; index >= 0; index -= 1) {
      const ripple = ripples[index];
      if (animate) {
        ripple.radius += 1.12 * ratio;
        ripple.alpha *= 0.986;
      }
      if (ripple.alpha < 0.004 || ripple.radius > Math.min(width, height) * 0.75) {
        ripples.splice(index, 1);
        continue;
      }
      context.strokeStyle = rgba(palette.accent, ripple.alpha);
      context.lineWidth = ratio;
      context.beginPath();
      context.arc(x, y, ripple.radius, 0, Math.PI * 2);
      context.stroke();
    }
  }

  function drawParticles(offsetX, offsetY, animate) {
    const centerX = width / 2;
    const centerY = height * 0.46;
    particles.forEach((particle, index) => {
      if (animate) {
        particle.distance += particle.speed;
        particle.angle += particle.drift;
      }
      if (particle.distance > particle.max) {
        particles[index] = newParticle(false);
        return;
      }
      const fade = 1 - particle.distance / particle.max;
      const x = centerX + offsetX + Math.cos(particle.angle) * particle.distance;
      const y = centerY + offsetY + Math.sin(particle.angle) * particle.distance;
      const color = particle.copper ? palette.copper : palette.accent;
      context.fillStyle = rgba(color, particle.alpha * fade);
      context.beginPath();
      context.arc(x, y, particle.size, 0, Math.PI * 2);
      context.fill();
    });
  }

  function paint(animate) {
    if (!width || !height) return;
    if (animate) {
      frame += 1;
      phase += 0.008;
      pointer.x += (pointer.targetX - pointer.x) * 0.05;
      pointer.y += (pointer.targetY - pointer.y) * 0.05;
      hover += (hoverTarget - hover) * 0.08;
    }
    const offsetX = (pointer.x - 0.5) * 46 * ratio;
    const offsetY = (pointer.y - 0.5) * 46 * ratio;
    const centerX = width / 2 + offsetX;
    const centerY = height * 0.46 + offsetY;
    context.clearRect(0, 0, width, height);
    context.globalCompositeOperation = "lighter";
    drawBeam(centerX, centerY);
    drawGlow(centerX, centerY);
    drawRays(centerX, centerY);
    drawRipples(centerX, centerY, animate);
    drawParticles(offsetX, offsetY, animate);
  }

  function drawStaticFrame() {
    paint(false);
  }

  function loop() {
    animationFrame = 0;
    if (!visible || reducedMotion.matches || document.hidden) return;
    paint(true);
    animationFrame = window.requestAnimationFrame(loop);
  }

  function syncAnimation() {
    if (visible && !reducedMotion.matches && !document.hidden && !animationFrame) {
      animationFrame = window.requestAnimationFrame(loop);
    } else if ((!visible || reducedMotion.matches || document.hidden) && animationFrame) {
      window.cancelAnimationFrame(animationFrame);
      animationFrame = 0;
      drawStaticFrame();
    }
  }

  function activateWorkspace(view, targetId) {
    const matchingLink = document.querySelector(`#primary-navigation [data-view="${view}"]`);
    if (matchingLink) matchingLink.click();
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        const target = document.getElementById(targetId) || document.getElementById("workspace-root");
        if (!target) return;
        const behavior = reducedMotion.matches ? "auto" : "smooth";
        if (targetId === "workspace-root") {
          window.scrollTo({ top: target.offsetTop, behavior });
        } else {
          target.scrollIntoView({ block: "start", behavior });
        }
        if (!target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
        try { target.focus({ preventScroll: true }); } catch (_e) { target.focus(); }
      });
    });
  }

  document.querySelectorAll("[data-fusion-view]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const targetId = (link.getAttribute("href") || "#workspace-root").replace(/^#/, "");
      activateWorkspace(link.dataset.fusionView || "overview", targetId);
    });
  });

  landing.addEventListener("pointermove", (event) => {
    const bounds = landing.getBoundingClientRect();
    pointer.targetX = (event.clientX - bounds.left) / Math.max(1, bounds.width);
    pointer.targetY = (event.clientY - bounds.top) / Math.max(1, bounds.height);
  }, { passive: true });

  landing.querySelectorAll("a").forEach((link) => {
    link.addEventListener("pointerenter", () => { hoverTarget = 1; });
    link.addEventListener("pointerleave", () => { hoverTarget = 0; });
  });

  const observer = new IntersectionObserver((entries) => {
    visible = entries.some((entry) => entry.isIntersecting);
    syncAnimation();
  }, { threshold: 0.02 });
  observer.observe(landing);

  window.addEventListener("resize", resizeCanvas, { passive: true });
  document.addEventListener("visibilitychange", syncAnimation);
  reducedMotion.addEventListener?.("change", () => {
    drawStaticFrame();
    syncAnimation();
  });

  resizeCanvas();
  drawStaticFrame();
  syncAnimation();
}());
