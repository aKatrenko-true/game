(async function applyCMSContent(){
 // Only allow explicit image URL schemes and reject CSS-breaking characters before
 // interpolating a value into a CSS url(). CMS content is admin-authored, but the
 // public page must still treat persisted values as untrusted input.
 const safeImageUrl=value=>{
  const url=String(value||"").trim();
  if(/["'()<>\\\s\n\r]/.test(url))return "";
  if(/^https:\/\/[^\s]+$/i.test(url))return url;
  if(/^data:image\/(png|jpeg|webp|gif|svg\+xml);base64,[a-z0-9+/=]+$/i.test(url))return url;
  return "";
 };
 try{
  const r=await fetch("/api/cms/content",{cache:"no-store"});if(!r.ok)return;
  const data=await r.json(),settings=data.settings||{},sections=data.sections||[];
  const bySlug=Object.fromEntries(sections.map(s=>[s.slug,s]));
  if(settings.site_title){document.title=settings.site_title+" — Игровое сообщество";document.querySelector('meta[name="apple-mobile-web-app-title"]')?.setAttribute("content",settings.site_title)}
  if(settings.meta_description)document.querySelector('meta[name="description"]')?.setAttribute("content",settings.meta_description);
  const navLabels={players:settings.menu_players,teams:settings.menu_teams,matches:settings.menu_matches,lfg:settings.menu_lfg};
  for(const [view,label] of Object.entries(navLabels)){
   if(!label)continue;
   document.querySelectorAll('[data-view="'+view+'"]').forEach(el=>{
    const icon=el.querySelector("span"),prefix=icon?.textContent||"";
    if(icon){el.textContent="";el.append(icon,document.createTextNode(label))}
    else el.textContent=label;
   });
  }
  if(settings.primary_color&&/^#[0-9a-fA-F]{6}$/.test(settings.primary_color))document.documentElement.style.setProperty("--green",settings.primary_color);
  if(settings.background_color&&/^#[0-9a-fA-F]{6}$/.test(settings.background_color))document.documentElement.style.setProperty("--bg",settings.background_color);
  if(settings.logo_text)document.querySelectorAll(".brand").forEach(el=>{
   if(el.closest(".admin-main"))return;
   el.textContent="";const mark=document.createElement("span");mark.className="mark";mark.textContent=settings.logo_text.slice(0,1).toUpperCase();el.append(mark,document.createTextNode(settings.logo_text));
  });
  const hero=bySlug.hero,heroEl=document.querySelector(".hero");
  if(hero&&heroEl){
   heroEl.hidden=!hero.visible;
   if(hero.visible){
    const h=heroEl.querySelector("h1"),sub=heroEl.querySelector(".sub");
    if(h&&hero.title)h.textContent=hero.title;
    if(sub&&hero.body)sub.textContent=hero.body;
    const heroImage=safeImageUrl(hero.image_url);
   if(heroImage)heroEl.style.backgroundImage='linear-gradient(90deg,#0c111def 0%,#101321d9 48%,#151329a8 100%),url("'+heroImage+'")';
   }
  }
  const gameImageSettings=[
   [".game-cs2",settings.game_cs2_image],
   [".game-valorant",settings.game_valorant_image],
   [".game-wd",settings.game_wd_image],
   [".game-apex",settings.game_apex_image]
  ];
  for(const [selector,image] of gameImageSettings){
   const tile=document.querySelector(selector);
   if(tile&&image&&/^(https:\/\/|data:image\/(png|jpeg|webp|gif|svg\+xml);)/i.test(image)){
    tile.style.backgroundImage='linear-gradient(180deg,#080b1210 0%,#080b1260 38%,#080b12f0 100%),url("'+image.replace(/["\\\n\r]/g,"")+'")';
   }
  }
  const games=bySlug.games,gameEl=document.querySelector(".game-showcase");
  if(games&&gameEl){gameEl.hidden=!games.visible;const h=gameEl.querySelector("h2");if(h&&games.title)h.textContent=games.title;const p=gameEl.querySelector(".showcase-heading>p");if(p&&games.body)p.textContent=games.body}
  const playerSection=bySlug.players,teamSection=bySlug.teams,matchSection=bySlug.matches;
  const playerPanel=document.querySelector("#featured")?.closest(".panel"),matchPanel=document.querySelector("#featured-matches")?.closest(".panel");
  if(playerSection&&playerPanel){playerPanel.hidden=!playerSection.visible;const h=playerPanel.querySelector("h2");if(h&&playerSection.title)h.textContent=playerSection.title}
  if(matchSection&&matchPanel){matchPanel.hidden=!matchSection.visible;const h=matchPanel.querySelector("h2");if(h&&matchSection.title)h.textContent=matchSection.title}
  // Treat visibility as a site-wide rule, not only a homepage-card toggle.
  const hiddenViews=new Set(["players","teams","matches"].filter(view=>bySlug[view]&&!bySlug[view].visible));
  window.__cmsHiddenViews=hiddenViews;
  for(const view of ["players","teams","matches"]){
   const hidden=hiddenViews.has(view);
   document.querySelectorAll('[data-view="'+view+'"],[data-go="'+view+'"]').forEach(el=>{el.hidden=hidden;el.setAttribute("aria-hidden",String(hidden));});
  }
  // The directory container is shared by all SPA routes; never hide it for a single view.
  if(hiddenViews.size&&typeof window.render==="function")window.render("overview");
  // Sort the primary homepage areas using CMS order. Players/matches share one two-column area.
  const main=document.querySelector("main");
  const directory=document.querySelector(".directory");
  if(main){
   const groups=[
    {el:heroEl,items:[hero].filter(Boolean)},
    {el:gameEl,items:[games].filter(Boolean)},
    {el:document.querySelector(".stats"),items:[{sort_order:25}]},
    {el:document.querySelector(".columns"),items:[playerSection,matchSection].filter(Boolean)},
    {el:directory,items:[teamSection].filter(Boolean)}
   ].filter(g=>g.el);
   const key=g=>g.items.length?Math.min(...g.items.map(s=>Number(s.sort_order)||0)):Number.MAX_SAFE_INTEGER;
   groups.sort((a,b)=>key(a)-key(b));
   const footer=main.querySelector("footer");
   groups.forEach(g=>{if(footer)main.insertBefore(g.el,footer)});
  }
  // Custom sections are rendered as safe text, never interpreted as HTML.
  sections.filter(s=>s.visible&&["custom","gallery","content"].includes(s.kind)).forEach(s=>{
   if(document.querySelector('[data-cms-slug="'+CSS.escape(s.slug)+'"]'))return;
   const el=document.createElement("section");el.className="panel cms-public-section";el.dataset.cmsSlug=s.slug;
   const h=document.createElement("h2");h.textContent=s.title;el.append(h);
   if(s.body){const p=document.createElement("p");p.className="sub";p.textContent=s.body;el.append(p)}
   if(s.image_url){const img=document.createElement("img");img.src=s.image_url;img.alt=s.title;img.loading="lazy";img.style.cssText="max-width:100%;max-height:420px;object-fit:contain;border-radius:12px";el.append(img)}
   const footer=main?.querySelector("footer");if(main){if(footer)main.insertBefore(el,footer);else main.append(el)}
  });
 }catch(e){console.warn("CMS content could not be applied",e)}
})();