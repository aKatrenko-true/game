(() => {
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  async function api(url, options = {}) {
    const r = await fetch(url, {headers: {"Content-Type":"application/json"}, ...options});
    const data = await r.json().catch(() => null);
    if (!r.ok) throw new Error(data?.detail || ("HTTP " + r.status));
    return data;
  }
  function renderLfg() {
    const content = $("#content");
    if (!content || !document.querySelector('[data-view="lfg"].active, .mobile-tab[data-view="lfg"].active')) return;
    $("#crumb").textContent = "Поиск команды";
    $("#title").textContent = "Объявления LFG";
    $("#actions").innerHTML = "";
    content.innerHTML = '<div class="lfg-toolbar"><label>Игра<select id="lfg-game"><option value="">Все игры</option><option>CS2</option><option>WarDogs</option><option>Valorant</option><option>Apex Legends</option><option>Dota 2</option></select></label><label>Регион<select id="lfg-region"><option value="">Все регионы</option><option>EU</option><option>RU</option><option>NA</option><option>ASIA</option></select></label><label>Платформа<select id="lfg-platform"><option value="">Любая</option><option>PC</option><option>PlayStation</option><option>Xbox</option></select></label></div><form id="lfg-form" class="lfg-form"><h3>Создать объявление</h3><p class="sub">Публикация доступна после входа в личный кабинет.</p><div class="lfg-fields"><label>Игра<select name="game" required><option>CS2</option><option>WarDogs</option><option>Valorant</option><option>Apex Legends</option><option>Dota 2</option></select></label><label>Формат<select name="post_type"><option value="duo">Ищу дуо</option><option value="team">Нужен игрок в команду</option><option value="stack">Собираем стак</option></select></label><label>Ранг<input name="rank" maxlength="30" value="Любой"></label><label>Регион<select name="region"><option>EU</option><option>RU</option><option>NA</option><option>ASIA</option></select></label><label>Платформа<select name="platform"><option>PC</option><option>PlayStation</option><option>Xbox</option></select></label><label>Язык<select name="language"><option>Русский</option><option>English</option><option>Русский / English</option></select></label><label>Время игры<select name="play_time"><option>Вечером</option><option>Днём</option><option>Ночью</option><option>По выходным</option></select></label></div><label>Описание<textarea name="description" maxlength="300" placeholder="Режим, цели, микрофон, что важно для команды"></textarea></label><p id="lfg-error" class="error"></p><button class="btn primary" type="submit">Опубликовать объявление</button></form><div id="lfg-results" class="lfg-results"></div>';
    const update = async () => {
      const q = new URLSearchParams();
      [["lfg-game","game"],["lfg-region","region"],["lfg-platform","platform"]].forEach(([id,key]) => { if ($("#"+id).value) q.set(key,$("#"+id).value); });
      try {
        const rows = await api("/api/lfg?" + q.toString());
        $("#lfg-results").innerHTML = rows.map(x => '<article class="lfg-card"><div class="lfg-card-top"><span class="tag">'+esc(x.game)+'</span><span class="tag">'+esc(({duo:"Ищу дуо",team:"Нужен игрок в команду",stack:"Собираем стак"})[x.post_type]||x.post_type)+'</span></div><h3>'+esc(x.nickname)+'</h3><p>'+esc(x.description||"Без дополнительного описания")+'</p><div class="lfg-meta"><span>Ранг: '+esc(x.rank)+'</span><span>'+esc(x.region)+' · '+esc(x.platform)+'</span><span>'+esc(x.language)+' · '+esc(x.play_time)+'</span></div></article>').join("") || '<div class="empty">Пока нет объявлений по выбранным условиям</div>';
      } catch(e) { $("#lfg-results").innerHTML = '<div class="empty">Не удалось загрузить объявления. Попробуй обновить страницу.</div>'; }
    };
    ["lfg-game","lfg-region","lfg-platform"].forEach(id => $("#"+id).addEventListener("change", update));
    $("#lfg-form").addEventListener("submit", async (e) => {
      e.preventDefault(); $("#lfg-error").textContent = "";
      try { await api("/api/lfg",{method:"POST",body:JSON.stringify(Object.fromEntries(new FormData(e.currentTarget)))}); e.currentTarget.reset(); if ($("#toast")) { $("#toast").textContent="Объявление опубликовано"; $("#toast").classList.add("show"); } await update(); }
      catch(err) { $("#lfg-error").textContent = err.message + (err.message.includes("Войди") ? " — открой личный кабинет и войди." : ""); }
    });
    update();
  }
  document.addEventListener("click", (e) => { if (e.target.closest('[data-view="lfg"]')) setTimeout(renderLfg, 0); });
  document.addEventListener("click", (e) => { const b=e.target.closest("[data-go]"); if (b && b.dataset.go==="lfg") setTimeout(renderLfg,0); });
})();