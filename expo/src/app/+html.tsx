import type { PropsWithChildren } from 'react';
import { ScrollViewStyleReset } from 'expo-router/html';

// The cover is in the document itself, so it paints before React, auth, and
// route hydration. React removes it only after its animated overlay mounts.
const bootstrapTheme = "try{var theme=localStorage.getItem('classio.themePreference');if(theme==='dark'||theme==='light')document.documentElement.setAttribute('data-classio-theme',theme)}catch(e){}";
const bootCss = `
#classio-boot-overlay{position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;justify-content:center;background:#F4F8FF;color:#193459;background-image:radial-gradient(circle at 18% 25%,#DBEAFE 0%,transparent 43%),radial-gradient(circle at 83% 75%,#D6F5EB 0%,transparent 42%)}
#classio-boot-overlay .classio-boot-mark{font:800 30px system-ui,sans-serif;letter-spacing:-1px;animation:classio-boot-arrive .8s ease-out both}
#classio-boot-overlay .classio-boot-star{color:#60A5FA;margin-right:12px}
@keyframes classio-boot-arrive{from{opacity:0;transform:translateY(12px) scale(.94)}to{opacity:1;transform:translateY(0) scale(1)}}
html[data-classio-theme="dark"] #classio-boot-overlay{background-color:#0B1730;color:#E2E8F0;background-image:radial-gradient(circle at 18% 25%,#173669 0%,transparent 43%),radial-gradient(circle at 83% 75%,#0B4E49 0%,transparent 42%)}
@media(prefers-color-scheme:dark){html:not([data-classio-theme="light"]) #classio-boot-overlay{background-color:#0B1730;color:#E2E8F0;background-image:radial-gradient(circle at 18% 25%,#173669 0%,transparent 43%),radial-gradient(circle at 83% 75%,#0B4E49 0%,transparent 42%)}}
`;

export default function Html({ children }: PropsWithChildren) {
  return <html lang="en"><head><meta charSet="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" /><ScrollViewStyleReset /><style dangerouslySetInnerHTML={{ __html: bootCss }} /><script dangerouslySetInnerHTML={{ __html: bootstrapTheme }} /></head><body><div id="classio-boot-overlay" aria-label="Classio"><div className="classio-boot-mark"><span className="classio-boot-star">✦</span>Classio</div></div>{children}</body></html>;
}
