import { useEffect } from 'react';
import { Platform } from 'react-native';

type Particle = { x: number; y: number; vx: number; vy: number; radius: number; alternate: boolean };

function colorWithAlpha(value: string, alpha: number, fallback = '37,99,235') {
  const clean = value.trim();
  if (clean.startsWith('#') && (clean.length === 7 || clean.length === 4)) {
    const hex = clean.length === 4 ? clean.slice(1).split('').map((part) => part + part).join('') : clean.slice(1);
    const number = Number.parseInt(hex, 16);
    return `rgba(${(number >> 16) & 255},${(number >> 8) & 255},${number & 255},${alpha})`;
  }
  const channels = clean.match(/[\d.]+/g)?.slice(0, 3).join(',');
  return `rgba(${channels || fallback},${alpha})`;
}

/** Mount the same theme-aware connected-particle backdrop used by Streamlit. */
export function LiveBackground() {
  useEffect(() => {
    if (Platform.OS !== 'web' || typeof document === 'undefined' || typeof window === 'undefined') return;
    let background = document.getElementById('classio-live-background');
    if (!background) {
      background = document.createElement('div');
      background.id = 'classio-live-background';
      background.setAttribute('aria-hidden', 'true');
      document.body.prepend(background);
    }
    const canvas = document.createElement('canvas');
    canvas.setAttribute('aria-hidden', 'true');
    background.replaceChildren(canvas);
    const context = canvas.getContext('2d', { alpha: true });
    if (!context) return () => background?.remove();

    let width = 0; let height = 0; let mobile = false; let reduced = false; let paused = document.hidden; let frame = 0;
    let particles: Particle[] = [];
    const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const resize = () => {
      width = window.innerWidth; height = window.innerHeight; mobile = width < 768; reduced = motionQuery.matches;
      const ratio = Math.min(window.devicePixelRatio || 1, 1.8);
      canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
      canvas.style.width = `${width}px`; canvas.style.height = `${height}px`;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      const count = reduced ? (mobile ? 10 : 16) : (mobile ? 18 : 34);
      particles = Array.from({ length: count }, (_, index) => particles[index] ?? ({
        x: Math.random() * width, y: Math.random() * height,
        vx: (Math.random() - 0.5) * (mobile ? 0.09 : 0.14),
        vy: (Math.random() - 0.5) * (mobile ? 0.07 : 0.11),
        radius: Math.random() * (mobile ? 1.6 : 2.1) + 0.8,
        alternate: Math.random() > 0.64,
      }));
    };
    const draw = () => {
      frame = window.requestAnimationFrame(draw);
      if (paused) return;
      const styles = window.getComputedStyle(document.documentElement);
      const selected = document.documentElement.dataset.classioTheme;
      const dark = selected === 'dark' || (!selected && darkQuery.matches);
      const primary = styles.getPropertyValue('--classio-primary') || (dark ? '#60A5FA' : '#2563EB');
      const success = styles.getPropertyValue('--classio-success') || (dark ? '#34D399' : '#059669');
      context.clearRect(0, 0, width, height);
      const speed = dark ? 1 : 1.55;
      for (const particle of particles) {
        particle.x += reduced ? 0.01 : particle.vx * speed; particle.y += reduced ? 0.01 : particle.vy * speed;
        if (particle.x < -20) particle.x = width + 20; if (particle.x > width + 20) particle.x = -20;
        if (particle.y < -20) particle.y = height + 20; if (particle.y > height + 20) particle.y = -20;
      }
      const maxDistance = mobile ? 120 : 160; const glowDistance = mobile ? 70 : 96;
      for (let first = 0; first < particles.length; first += 1) for (let second = first + 1; second < particles.length; second += 1) {
        const a = particles[first]; const b = particles[second]; const distance = Math.hypot(a.x - b.x, a.y - b.y);
        if (distance > maxDistance) continue;
        const alpha = 1 - distance / maxDistance;
        context.beginPath(); context.moveTo(a.x, a.y); context.lineTo(b.x, b.y);
        context.strokeStyle = colorWithAlpha(a.alternate ? success : primary, alpha * (dark ? 0.12 : 0.2));
        context.lineWidth = distance < glowDistance ? (dark ? 1.15 : 1.35) : (dark ? 0.8 : 1);
        context.stroke();
      }
      for (const particle of particles) {
        context.beginPath(); context.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2);
        context.fillStyle = colorWithAlpha(particle.alternate ? success : primary, dark ? (particle.alternate ? 0.46 : 0.7) : (particle.alternate ? 0.34 : 0.54));
        context.shadowBlur = reduced ? 0 : (dark ? 14 : 8); context.shadowColor = colorWithAlpha(particle.alternate ? success : primary, 0.22); context.fill();
      }
      context.shadowBlur = 0;
    };
    const visibility = () => { paused = document.hidden; };
    resize(); draw();
    window.addEventListener('resize', resize, { passive: true });
    document.addEventListener('visibilitychange', visibility, { passive: true });
    motionQuery.addEventListener?.('change', resize); darkQuery.addEventListener?.('change', resize);
    return () => {
      window.cancelAnimationFrame(frame); window.removeEventListener('resize', resize); document.removeEventListener('visibilitychange', visibility);
      motionQuery.removeEventListener?.('change', resize); darkQuery.removeEventListener?.('change', resize); background?.remove();
    };
  }, []);
  return null;
}
