import type { PropsWithChildren } from 'react';
import { ScrollViewStyleReset } from 'expo-router/html';

// The cover is in the document itself, so it paints before React, auth, and
// route hydration. React removes it only after its animated overlay mounts.
const bootstrapTheme = "try{var theme=localStorage.getItem('classio.themePreference');if(theme==='dark'||theme==='light')document.documentElement.setAttribute('data-classio-theme',theme)}catch(e){}";
// A tab opened before a deployment can still request a removed, hashed Metro
// chunk. Install this before the app bundle so the user gets a recovery action.
const staleChunkRecovery = `
(function(){
  var shown=false;
  var copy={
    en:['Classio was updated','Save any work in progress, then reload to use the latest tools and downloads.','Reload now','Later'],
    es:['Classio se actualizó','Guarda el trabajo en curso y recarga para usar las herramientas y descargas más recientes.','Recargar ahora','Más tarde'],
    tr:['Classio güncellendi','Devam eden çalışmanızı kaydedin; en yeni araçları ve indirmeleri kullanmak için sayfayı yenileyin.','Şimdi yenile','Daha sonra']
  };
  function isMissingChunk(value){
    return /(?:Loading module|Failed to fetch dynamically imported module|Importing a module script failed|ChunkLoadError)/i.test(value)
      && /_expo\\/static\\/js\\/web\\/[^\\s)]+\\.js/i.test(value);
  }
  function show(){
    if(shown)return;
    if(!document.body){document.addEventListener('DOMContentLoaded',show,{once:true});return;}
    shown=true;
    var lang=(document.documentElement.lang||'en').slice(0,2);
    try{lang=(localStorage.getItem('classio.interfaceLanguage')||lang).slice(0,2)}catch(e){}
    var words=copy[lang]||copy.en;
    var box=document.createElement('div');
    box.id='classio-chunk-recovery';
    box.setAttribute('role','alertdialog');
    box.setAttribute('aria-modal','true');
    box.setAttribute('aria-label',words[0]);
    var panel=document.createElement('div');panel.className='classio-chunk-panel';
    var title=document.createElement('strong');title.textContent=words[0];
    var detail=document.createElement('p');detail.textContent=words[1];
    var actions=document.createElement('div');actions.className='classio-chunk-actions';
    var later=document.createElement('button');later.type='button';later.textContent=words[3];later.onclick=function(){box.remove();shown=false;};
    var reload=document.createElement('button');reload.type='button';reload.textContent=words[2];reload.className='classio-chunk-reload';
    reload.onclick=function(){
      var url=new URL(location.href);
      url.searchParams.set('classio_refresh',String(Date.now()));
      location.replace(url.toString());
    };
    actions.appendChild(later);actions.appendChild(reload);
    panel.appendChild(title);panel.appendChild(detail);panel.appendChild(actions);
    box.appendChild(panel);document.body.appendChild(box);reload.focus();
  }
  window.addEventListener('error',function(event){
    var target=event.target;
    var source=target && target.src || '';
    var message=String(event.message||event.error && event.error.message||'');
    if(isMissingChunk(message)||(/_expo\\/static\\/js\\/web\\/[^\\s)]+\\.js/i.test(source)&&target.tagName==='SCRIPT'))show();
  },true);
  window.addEventListener('unhandledrejection',function(event){
    var reason=event.reason;
    if(isMissingChunk(String(reason && reason.message || reason || '')))show();
  });
  // A long-lived tab can keep running an old bundle even when no chunk fails.
  // Check only after it has been open for a while and when the user returns.
  var lastVersionCheck=Date.now();
  function checkVersion(){
    if(document.visibilityState==='hidden'||shown||Date.now()-lastVersionCheck<600000)return;
    lastVersionCheck=Date.now();
    var current=document.querySelector('script[src*="/_expo/static/js/web/entry-"]');
    var currentPath=current && current.getAttribute('src') || '';
    if(!currentPath)return;
    fetch('/sign-in?classio_version='+Date.now(),{cache:'no-store'})
      .then(function(response){return response.ok?response.text():'';})
      .then(function(html){
        var latest=html.match(/\\/_expo\\/static\\/js\\/web\\/entry-[a-f0-9]+\\.js/i);
        if(latest&&currentPath.indexOf(latest[0])<0)show();
      }).catch(function(){});
  }
  document.addEventListener('visibilitychange',checkVersion);
  window.setInterval(checkVersion,900000);
})();`;
const bootCss = `
#classio-boot-overlay{position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;justify-content:center;background:#F4F8FF;color:#193459;background-image:radial-gradient(circle at 18% 25%,#DBEAFE 0%,transparent 43%),radial-gradient(circle at 83% 75%,#D6F5EB 0%,transparent 42%)}
#classio-boot-overlay .classio-boot-mark{font:800 30px system-ui,sans-serif;letter-spacing:-1px;animation:classio-boot-arrive .8s ease-out both}
#classio-boot-overlay .classio-boot-star{color:#60A5FA;margin-right:12px}
@keyframes classio-boot-arrive{from{opacity:0;transform:translateY(12px) scale(.94)}to{opacity:1;transform:translateY(0) scale(1)}}
html[data-classio-theme="dark"] #classio-boot-overlay{background-color:#0B1730;color:#E2E8F0;background-image:radial-gradient(circle at 18% 25%,#173669 0%,transparent 43%),radial-gradient(circle at 83% 75%,#0B4E49 0%,transparent 42%)}
@media(prefers-color-scheme:dark){html:not([data-classio-theme="light"]) #classio-boot-overlay{background-color:#0B1730;color:#E2E8F0;background-image:radial-gradient(circle at 18% 25%,#173669 0%,transparent 43%),radial-gradient(circle at 83% 75%,#0B4E49 0%,transparent 42%)}}
#classio-chunk-recovery{position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;justify-content:center;padding:20px;background:rgba(7,17,38,.72);font-family:system-ui,sans-serif}
.classio-chunk-panel{width:min(100%,440px);padding:24px;border:1px solid #CBD5E1;border-radius:20px;background:#FFFFFF;color:#14213D;box-shadow:0 24px 64px rgba(0,0,0,.28)}
.classio-chunk-panel strong{font-size:20px}.classio-chunk-panel p{line-height:1.5;color:#475569}
.classio-chunk-actions{display:flex;justify-content:flex-end;gap:10px;flex-wrap:wrap}.classio-chunk-actions button{min-height:44px;padding:10px 16px;border:1px solid #94A3B8;border-radius:10px;background:transparent;color:inherit;font:600 14px system-ui,sans-serif;cursor:pointer}.classio-chunk-actions .classio-chunk-reload{background:#2563EB;border-color:#2563EB;color:#FFFFFF}
html[data-classio-theme="dark"] .classio-chunk-panel{background:#101D34;color:#F8FAFC;border-color:#344663}html[data-classio-theme="dark"] .classio-chunk-panel p{color:#CBD5E1}
@media(prefers-color-scheme:dark){html:not([data-classio-theme="light"]) .classio-chunk-panel{background:#101D34;color:#F8FAFC;border-color:#344663}html:not([data-classio-theme="light"]) .classio-chunk-panel p{color:#CBD5E1}}
`;

export default function Html({ children }: PropsWithChildren) {
  return <html lang="en"><head><meta charSet="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" /><ScrollViewStyleReset /><style dangerouslySetInnerHTML={{ __html: bootCss }} /><script dangerouslySetInnerHTML={{ __html: bootstrapTheme }} /><script dangerouslySetInnerHTML={{ __html: staleChunkRecovery }} /></head><body><div id="classio-boot-overlay" aria-label="Classio"><div className="classio-boot-mark"><span className="classio-boot-star">✦</span>Classio</div></div>{children}</body></html>;
}
