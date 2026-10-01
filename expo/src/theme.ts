import { Platform } from 'react-native';

function token(name: string, fallback: string) { return Platform.OS === 'web' ? `var(--classio-${name}, ${fallback})` : fallback; }

export const colors = {
  ink: token('ink', '#0F172A'),
  inkSecondary: token('ink-secondary', '#334155'),
  muted: token('muted', '#64748B'),
  subtle: token('subtle', '#94A3B8'),
  line: token('line', '#E2E8F0'),
  lineStrong: token('line-strong', '#CBD5E1'),
  canvas: token('canvas', '#F8FAFC'),
  surface: token('surface', '#FFFFFF'),
  surfaceSoft: token('surface-soft', '#F1F5F9'),
  surfaceRaised: token('surface-raised', '#FFFFFF'),
  primary: token('primary', '#2563EB'),
  primarySoft: token('primary-soft', '#EFF6FF'),
  success: token('success', '#059669'),
  successSoft: token('success-soft', '#ECFDF5'),
  warning: token('warning', '#B45309'),
  warningSoft: token('warning-soft', '#FFFBEB'),
  danger: token('danger', '#DC2626'),
  dangerSoft: token('danger-soft', '#FEF2F2'),
  violet: token('violet', '#7C3AED'),
  violetSoft: token('violet-soft', '#F5F3FF'),
  pink: token('pink', '#BE185D'),
  pinkSoft: token('pink-soft', '#FDF2F8'),
  orange: token('orange', '#C2410C'),
  orangeSoft: token('orange-soft', '#FFF7ED'),
  inverse: token('inverse', '#FFFFFF'),
  inverseMuted: token('inverse-muted', '#CBD5E1'),
  navDark: token('nav-dark', '#0F172A'),
  navDarkSoft: token('nav-dark-soft', '#1E293B'),
  shadow: token('shadow', '#0F172A'),
};

export const classioThemeCss = `
:root {
  color-scheme: light;
  --classio-ink:#0F172A;--classio-ink-secondary:#334155;--classio-muted:#64748B;--classio-subtle:#94A3B8;
  --classio-line:#E2E8F0;--classio-line-strong:#CBD5E1;--classio-canvas:#F8FAFC;--classio-surface:#FFFFFF;
  --classio-surface-soft:#F1F5F9;--classio-surface-raised:#FFFFFF;--classio-primary:#2563EB;--classio-primary-soft:#EFF6FF;
  --classio-success:#059669;--classio-success-soft:#ECFDF5;--classio-warning:#B45309;--classio-warning-soft:#FFFBEB;
  --classio-danger:#DC2626;--classio-danger-soft:#FEF2F2;--classio-violet:#7C3AED;--classio-violet-soft:#F5F3FF;
  --classio-pink:#BE185D;--classio-pink-soft:#FDF2F8;--classio-orange:#C2410C;--classio-orange-soft:#FFF7ED;
  --classio-inverse:#FFFFFF;--classio-inverse-muted:#CBD5E1;--classio-nav-dark:#0F172A;--classio-nav-dark-soft:#1E293B;--classio-shadow:#0F172A;
}
:root[data-classio-theme="dark"] {
  color-scheme: dark;
  --classio-ink:#F8FAFC;--classio-ink-secondary:#E2E8F0;--classio-muted:#CBD5E1;--classio-subtle:#94A3B8;
  --classio-line:#334155;--classio-line-strong:#475569;--classio-canvas:#08111F;--classio-surface:#111C2E;
  --classio-surface-soft:#17243A;--classio-surface-raised:#152238;--classio-primary:#60A5FA;--classio-primary-soft:#172C4D;
  --classio-success:#34D399;--classio-success-soft:#0D352E;--classio-warning:#FBBF24;--classio-warning-soft:#3A2A0D;
  --classio-danger:#F87171;--classio-danger-soft:#3B161C;--classio-violet:#A78BFA;--classio-violet-soft:#2B1D4A;
  --classio-pink:#F472B6;--classio-pink-soft:#3B1830;--classio-orange:#FB923C;--classio-orange-soft:#3A2112;
  --classio-inverse:#FFFFFF;--classio-inverse-muted:#CBD5E1;--classio-nav-dark:#050B15;--classio-nav-dark-soft:#111C2E;--classio-shadow:#000000;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-classio-theme="light"]) {
    color-scheme: dark;
    --classio-ink:#F8FAFC;--classio-ink-secondary:#E2E8F0;--classio-muted:#CBD5E1;--classio-subtle:#94A3B8;
    --classio-line:#334155;--classio-line-strong:#475569;--classio-canvas:#08111F;--classio-surface:#111C2E;
    --classio-surface-soft:#17243A;--classio-surface-raised:#152238;--classio-primary:#60A5FA;--classio-primary-soft:#172C4D;
    --classio-success:#34D399;--classio-success-soft:#0D352E;--classio-warning:#FBBF24;--classio-warning-soft:#3A2A0D;
    --classio-danger:#F87171;--classio-danger-soft:#3B161C;--classio-violet:#A78BFA;--classio-violet-soft:#2B1D4A;
    --classio-pink:#F472B6;--classio-pink-soft:#3B1830;--classio-orange:#FB923C;--classio-orange-soft:#3A2112;
    --classio-inverse:#FFFFFF;--classio-inverse-muted:#CBD5E1;--classio-nav-dark:#050B15;--classio-nav-dark-soft:#111C2E;--classio-shadow:#000000;
  }
}
html,body,#root{background:var(--classio-canvas);min-height:100%;}
#root{position:relative;z-index:1;background:transparent;}
/* React Navigation paints its root scene with its default canvas; keep only the
   navigation scaffolding transparent so the Classio live backdrop remains visible. */
#root>div,
#root>div>div,
#root>div>div>div,
#root>div>div>div>div,
#root>div>div>div>div>div,
#root>div>div>div>div>div>div,
#root>div>div>div>div>div>div>div,
#root>div>div>div>div>div>div>div>div{background-color:transparent!important;}
#classio-live-background{
  position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden;
  background:
    radial-gradient(circle at 12% 14%, color-mix(in srgb, var(--classio-primary) 12%, transparent), transparent 28%),
    radial-gradient(circle at 85% 18%, color-mix(in srgb, var(--classio-success) 11%, transparent), transparent 24%),
    radial-gradient(circle at 52% 78%, color-mix(in srgb, var(--classio-warning) 6%, transparent), transparent 18%),
    linear-gradient(180deg, color-mix(in srgb, var(--classio-canvas) 94%, white 6%), var(--classio-canvas));
}
#classio-live-background canvas{position:absolute;inset:0;width:100%;height:100%;display:block;opacity:.95;}
#classio-live-background::before{
  content:"";position:absolute;inset:-12%;opacity:.8;filter:blur(32px);
  background:radial-gradient(circle at 50% 50%,rgba(255,255,255,.16),transparent 55%),linear-gradient(120deg,rgba(255,255,255,.10),transparent 45%,rgba(255,255,255,.05) 70%,transparent 100%);
  animation:classio-background-drift 24s ease-in-out infinite alternate;
}
#classio-live-background::after{
  content:"";position:absolute;inset:0;opacity:.65;
  background:linear-gradient(180deg,rgba(255,255,255,.08),transparent 18%,transparent 82%,rgba(15,23,42,.05)),radial-gradient(circle at center,transparent 0%,transparent 52%,rgba(15,23,42,.04) 100%);
}
:root[data-classio-theme="dark"] #classio-live-background{
  background:radial-gradient(circle at 12% 14%,rgba(59,130,246,.18),transparent 28%),radial-gradient(circle at 85% 18%,rgba(52,211,153,.14),transparent 24%),radial-gradient(circle at 52% 78%,rgba(245,158,11,.07),transparent 18%),linear-gradient(180deg,#1a2640,#0f172a);
}
:root[data-classio-theme="dark"] #classio-live-background::before{opacity:.24;}
:root[data-classio-theme="dark"] #classio-live-background::after{opacity:.58;}
@media(prefers-color-scheme:dark){
  :root:not([data-classio-theme="light"]) #classio-live-background{background:radial-gradient(circle at 12% 14%,rgba(59,130,246,.18),transparent 28%),radial-gradient(circle at 85% 18%,rgba(52,211,153,.14),transparent 24%),radial-gradient(circle at 52% 78%,rgba(245,158,11,.07),transparent 18%),linear-gradient(180deg,#1a2640,#0f172a)}
  :root:not([data-classio-theme="light"]) #classio-live-background::before{opacity:.24}
  :root:not([data-classio-theme="light"]) #classio-live-background::after{opacity:.58}
}
@keyframes classio-background-drift{from{transform:translate3d(-1.5%,-1%,0) scale(1)}to{transform:translate3d(2%,1.5%,0) scale(1.04)}}
@media(max-width:768px){#classio-live-background::before{opacity:.55;filter:blur(22px)}#classio-live-background::after{opacity:.5}}
@media(prefers-reduced-motion:reduce){#classio-live-background::before{animation:none!important}#classio-live-background canvas{opacity:.55}}
*{box-sizing:border-box;}
*:focus-visible{outline:3px solid var(--classio-primary);outline-offset:2px;}
`;
