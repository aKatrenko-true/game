(async function applyCMSContent(){
 try{
  const r=await fetch("/api/cms/content",{cache:"no-store"});if(!r.ok)return;const data=await r.json();
  const settings=data.settings||{}, sections=data.sections||[];
  if(settings.site_title){document.title=settings.site_title+" — Игровое сообщество";document.querySelector('meta[name="apple-mobile-web-app-title"]')?.setAttribute("content",settings.site_title)}
  if(settings.meta_description)document.querySelector('meta[name="description"]')?.setAttribute("content",settings.meta_description);
  if(settings.primary_color && /^#[0-9a-fA-F]{6}$/.test(settings.primary_color))document.documentElement.style.setProperty("--green",settings.primary_color);
  if(settings.background_color && /^#[0-9a-fA-F]{6}$/.test(settings.background_color))document.documentElement.style.setProperty("--bg",settings.background_color);
  const logo=settings.logo_text;if(logo){document.querySelectorAll(".brand").forEach(el=>{if(el.closest(".admin-main"))return;el.textContent="";const mark=document.createElement("span");mark.className="mark";mark.textContent=logo.slice(0,1).toUpperCase();el.append(mark,document.createTextNode(logo))})}
  const bySlug=Object.fromEntries(sections.map(s=>[s.slug,s]));
  const hero=bySlug.hero;
  if(hero){
   const section=document.querySelector(".hero");
   if(section){
    if(!hero.visible)section.hidden=true;
    else{
     const h=section.querySelector("h1"),sub=section.querySelector(".sub");
     if(h&&hero.title)h.textContent=hero.title;
     if(sub&&hero.body)sub.textContent=hero.body;
     if(hero.image_url){section.style.backgroundImage="linear-gradient(90deg,#0c111deF 0%,#101321d9 48%,#151329a8 100%),url("+JSON.stringify(hero.image_url)+")"}
    }
   }
  }
  const games=bySlug.games;if(games&&!games.visible){const el=document.querySelector(".game-showcase");if(el)el.hidden=true;}
  const players=bySlug.players, matches=bySlug.matches;
  if(players&&!players.visible){const el=document.querySelector("#featured")?.closest(".panel");if(el)el.hidden=true;}
  if(matches&&!matches.visible){const el=document.querySelector("#featured-matches")?.closest(".panel");if(el)el.hidden=true;}
  const teams=bySlug.teams;if(teams&&!teams.visible){const el=[...document.querySelectorAll(".nav,[data-view],.mobile-tab")].find(n=>n.textContent.toLowerCase().includes("команд"));if(el)el.hidden=true;}
  // Apply custom image to the hero and section cover blocks.
  for(const s of sections){if(!s.visible)continue;const target=document.querySelector('[data-cms-slug="'+CSS.escape(s.slug)+'"]');if(target&&s.image_url){target.style.backgroundImage="linear-gradient(180deg,#080b1255,#080b12dd),url("+JSON.stringify(s.image_url)+")";target.style.backgroundSize="cover";target.style.backgroundPosition="center";}}
  // Allow future custom sections to be rendered without changing app logic.
  const custom=sections.filter(s=>s.visible&&["custom","gallery","content"].includes(s.kind));
  const main=document.querySelector("main");
  custom.forEach(s=>{if(document.querySelector('[data-cms-slug="'+CSS.escape(s.slug)+'"]'))return;const el=document.createElement("section");el.className="panel cms-public-section";el.dataset.cmsSlug=s.slug;const h=document.createElement("h2");h.textContent=s.title;el.append(h);if(s.body){const p=document.createElement("p");p.className="sub";p.textContent=s.body;el.append(p)}if(s.image_url){const img=document.createElement("img");img.src=s.image_url;img.alt=s.title;img.loading="lazy";img.style.cssText="max-width:100%;max-height:420px;object-fit:contain;border-radius:12px";el.append(img)}const footer=main.querySelector("footer");main.insertBefore(el,footer)});
 }catch(e){console.warn("CMS content could not be applied",e)}
})();