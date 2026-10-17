const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
let password = "";
let tab = "players", players = [], teams = [], matches = [], users = [];
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
async function api(url, options) {
  options = options || {};
  const headers = Object.assign({"Content-Type":"application/json","X-Admin-Password":password}, options.headers || {});
  const response = await fetch(url, Object.assign({}, options, {headers:headers}));
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(data && data.detail ? data.detail : "HTTP " + response.status);
  return data;
}
function message(text, error) { const el = $("#admin-message"); if (el) { el.textContent = text; el.className = error ? "error" : "admin-success"; } }
async function loadData() {
  const r = await Promise.all([api("/api/admin/summary"), api("/api/players"), api("/api/teams"), api("/api/matches"), api("/api/admin/users")]);
  const s = r[0]; players = r[1]; teams = r[2]; matches = r[3]; users = r[4];
  $("#admin-stats").innerHTML = [["Игроки",s.players],["Команды",s.teams],["Матчи",s.matches],["Профили WarDogs",s.warDogsPlayers]].map(x => "<article><span>"+x[0]+"</span><b>"+x[1]+"</b><small>В базе данных</small></article>").join("");
  $("#login-panel").hidden = true; $("#dashboard").hidden = false; render();
}
async function submitLogin(event) {
  event.preventDefault(); password = $("#password").value; $("#login-error").textContent = "";
  try { await api("/api/admin/summary"); await loadData(); }
  catch (e) { $("#login-error").textContent = e.message; }
}
$("#login-form").addEventListener("submit", submitLogin);
$("#logout").addEventListener("click", () => { password = ""; $("#dashboard").hidden = true; $("#login-panel").hidden = false; $("#password").value = ""; });
$("#refresh").addEventListener("click", () => loadData().then(() => message("Данные обновлены",false)).catch(e => message(e.message,true)));
$$("[data-tab]").forEach(b => b.addEventListener("click", () => { tab = b.dataset.tab; render(); }));
function render() {
  $$("[data-tab]").forEach(b => b.classList.toggle("primary", b.dataset.tab === tab));
  $("#section-title").textContent = ({players:"Игроки",teams:"Команды",matches:"Матчи",users:"Аккаунты и модерация"})[tab];
  if (tab === "players") renderPlayers();
  if (tab === "teams") renderTeams();
  if (tab === "matches") renderMatches();
  if (tab === "users") renderUsers();
}
function renderPlayers() {
  $("#admin-content").innerHTML = '<div class="admin-form-grid"><form id="add-player" class="admin-form"><h3>Добавить игрока</h3><label>Никнейм<input name="nickname" minlength="3" maxlength="20" pattern="[A-Za-z0-9_]+" required></label><label>Игра<select name="game"><option>WarDogs</option><option>CS2</option><option>Valorant</option><option>Apex Legends</option><option>Dota 2</option></select></label><label>Ранг<input name="rank" value="Unranked" maxlength="30"></label><button class="btn primary">Добавить игрока</button></form><div class="admin-form"><h3>Список профилей</h3><input id="player-search" placeholder="Поиск по нику или игре"></div></div><div class="admin-table-wrap"><table><thead><tr><th>Никнейм</th><th>Игра</th><th>Ранг</th><th>Победы</th><th>Действия</th></tr></thead><tbody id="player-rows"></tbody></table></div>';
  const draw = () => {
    const q = $("#player-search").value.toLowerCase();
    $("#player-rows").innerHTML = players.filter(p => (p.nickname+" "+p.game).toLowerCase().includes(q)).map(p => '<tr><td><b>'+esc(p.nickname)+'</b></td><td>'+esc(p.game)+'</td><td>'+esc(p.rank)+'</td><td>'+p.wins+'</td><td><button class="btn edit-player" data-id="'+p.id+'">Изменить</button> <button class="btn danger delete-player" data-id="'+p.id+'">Удалить</button></td></tr>').join("") || '<tr><td colspan="5">Профили не найдены</td></tr>';
    $$(".edit-player").forEach(b => b.addEventListener("click", async () => {
      const p = players.find(x => x.id === Number(b.dataset.id));
      const nickname = prompt("Никнейм:",p.nickname); if (nickname === null) return;
      const game = prompt("Игра:",p.game); if (game === null) return;
      const rank = prompt("Ранг:",p.rank); if (rank === null) return;
      const wins = prompt("Победы:",p.wins); if (wins === null) return;
      const region = prompt("Регион:",p.region || "EU"); if (region === null) return;
      const play_time = prompt("Время игры:",p.play_time || "Вечером"); if (play_time === null) return;
      const play_style = prompt("Стиль игры:",p.play_style || "Любой"); if (play_style === null) return;
      const looking_for = prompt("Кого ищет:",p.looking_for || "Напарника"); if (looking_for === null) return;
      try { await api("/api/admin/players/"+p.id,{method:"PATCH",body:JSON.stringify({nickname,game,rank,wins:Number(wins),region,play_time,play_style,looking_for})}); await loadData(); message("Все поля профиля обновлены",false); } catch(e) { message(e.message,true); }
    }));
    $$(".delete-player").forEach(b => b.addEventListener("click", async () => {
      const p = players.find(x => x.id === Number(b.dataset.id)); if (!confirm("Удалить профиль "+p.nickname+"?")) return;
      try { await api("/api/admin/players/"+p.id,{method:"DELETE"}); await loadData(); message("Профиль удалён",false); } catch(e) { message(e.message,true); }
    }));
  };
  $("#player-search").addEventListener("input",draw); draw();
  $("#add-player").addEventListener("submit", async e => {
    e.preventDefault(); try { await api("/api/admin/players",{method:"POST",body:JSON.stringify(Object.fromEntries(new FormData(e.currentTarget)))}); await loadData(); message("Игрок добавлен",false); } catch(err) { message(err.message,true); }
  });
}
function renderTeams() {
  $("#admin-content").innerHTML = '<form id="add-team" class="admin-form admin-create"><h3>Создать команду</h3><div class="admin-form-grid"><label>Название<input name="name" minlength="3" maxlength="40" required></label><label>Игра<select name="game"><option>WarDogs</option><option>CS2</option><option>Valorant</option><option>Apex Legends</option><option>Dota 2</option></select></label></div><label>Описание<input name="description" maxlength="240"></label><button class="btn primary">Создать команду</button></form><div class="admin-table-wrap"><table><thead><tr><th>Команда</th><th>Игра</th><th>Описание</th><th>Действия</th></tr></thead><tbody>'+ (teams.map(t => '<tr><td><b>'+esc(t.name)+'</b></td><td>'+esc(t.game)+'</td><td>'+esc(t.description)+'</td><td><button class="btn edit-team" data-id="'+t.id+'">Изменить</button> <button class="btn danger delete-team" data-id="'+t.id+'">Удалить</button></td></tr>').join("") || '<tr><td colspan="4">Команд пока нет</td></tr>') + '</tbody></table></div>';
  $("#add-team").addEventListener("submit", async e => { e.preventDefault(); try { await api("/api/admin/teams",{method:"POST",body:JSON.stringify(Object.fromEntries(new FormData(e.currentTarget)))}); await loadData(); message("Команда создана",false); } catch(err) { message(err.message,true); } });
  $(".edit-team").forEach(b => b.addEventListener("click", async () => {
    const t=teams.find(x=>x.id===Number(b.dataset.id)); const name=prompt("Название:",t.name); if(name===null)return;
    const game=prompt("Игра:",t.game); if(game===null)return; const description=prompt("Описание:",t.description); if(description===null)return;
    try { await api("/api/admin/teams/"+t.id,{method:"PATCH",body:JSON.stringify({name,game,description})}); await loadData(); message("Команда обновлена",false); } catch(e){message(e.message,true);}
  }));
  $(".delete-team").forEach(b => b.addEventListener("click", async () => { const t = teams.find(x => x.id === Number(b.dataset.id)); if (!confirm("Удалить команду "+t.name+"?")) return; try { await api("/api/admin/teams/"+t.id,{method:"DELETE"}); await loadData(); message("Команда удалена",false); } catch(e) { message(e.message,true); } }));
}
function renderMatches() {
  $("#admin-content").innerHTML = '<form id="add-match" class="admin-form admin-create"><h3>Запланировать матч</h3><div class="admin-form-grid"><label>Игра<select name="game"><option>WarDogs</option><option>CS2</option><option>Valorant</option><option>Apex Legends</option><option>Dota 2</option></select></label><label>Дата и время<input name="scheduled_at" type="datetime-local" required></label><label>Команда A<input name="team_a" required minlength="2" maxlength="40"></label><label>Команда B<input name="team_b" required minlength="2" maxlength="40"></label></div><button class="btn primary">Создать матч</button></form><div class="admin-table-wrap"><table><thead><tr><th>Матч</th><th>Игра</th><th>Счёт</th><th>Статус</th><th>Дата</th><th>Действия</th></tr></thead><tbody>'+ (matches.map(m => '<tr><td><b>'+esc(m.team_a)+' vs '+esc(m.team_b)+'</b></td><td>'+esc(m.game)+'</td><td>'+m.score_a+':'+m.score_b+'</td><td>'+esc(m.status)+'</td><td>'+esc(m.scheduled_at)+'</td><td><button class="btn edit-match" data-id="'+m.id+'">Счёт/статус</button> <button class="btn danger delete-match" data-id="'+m.id+'">Удалить</button></td></tr>').join("") || '<tr><td colspan="6">Матчей пока нет</td></tr>') + '</tbody></table></div>';
  $("#add-match").addEventListener("submit", async e => { e.preventDefault(); const d = Object.fromEntries(new FormData(e.currentTarget)); d.scheduled_at = d.scheduled_at.replace("T"," "); try { await api("/api/admin/matches",{method:"POST",body:JSON.stringify(d)}); await loadData(); message("Матч создан",false); } catch(err) { message(err.message,true); } });
  $$(".edit-match").forEach(b => b.addEventListener("click", async () => { const m = matches.find(x => x.id === Number(b.dataset.id)); const game=prompt("Игра:",m.game);if(game===null)return;const team_a=prompt("Команда A:",m.team_a);if(team_a===null)return;const team_b=prompt("Команда B:",m.team_b);if(team_b===null)return;const scheduled_at=prompt("Дата и время (YYYY-MM-DD HH:MM):",m.scheduled_at);if(scheduled_at===null)return;const status=prompt("Статус: Scheduled, Live или Completed",m.status);if(status===null)return;const score_a=prompt("Счёт команды A",m.score_a);if(score_a===null)return;const score_b=prompt("Счёт команды B",m.score_b);if(score_b===null)return;try{await api("/api/admin/matches/"+m.id+"/full",{method:"PATCH",body:JSON.stringify({game,team_a,team_b,scheduled_at,status,score_a:Number(score_a),score_b:Number(score_b)})});await loadData();message("Все поля матча обновлены",false)}catch(e){message(e.message,true)} }));
  $$(".delete-match").forEach(b => b.addEventListener("click", async () => { const m = matches.find(x => x.id === Number(b.dataset.id)); if (!confirm("Удалить матч "+m.team_a+" vs "+m.team_b+"?")) return; try { await api("/api/admin/matches/"+m.id,{method:"DELETE"}); await loadData(); message("Матч удалён",false); } catch(e) { message(e.message,true); } }));
}
if (password) loadData().catch(error => { sessionStorage.removeItem("gh_admin_password"); password = ""; $("#login-panel").hidden = false; $("#dashboard").hidden = true; $("#login-error").textContent = error.message; });
function renderUsers() {
  const q = "";
  $( "#admin-content" ).innerHTML = '<div class="admin-form admin-create"><h3>Аккаунты пользователей</h3><p class="sub">Блокировка запрещает вход и отзывает активные сессии. Сброс пароля создаёт новый пароль, который нужно передать пользователю безопасным способом.</p><input id="user-search" placeholder="Поиск по никнейму"><div class="admin-table-wrap"><table><thead><tr><th>Аккаунт</th><th>Игровой профиль</th><th>Статус</th><th>Создан</th><th>Действия</th></tr></thead><tbody id="user-rows"></tbody></table></div></div>';
  const draw = () => {
    const query = $("#user-search").value.toLowerCase();
    $("#user-rows").innerHTML = users.filter(u => (u.nickname+" "+(u.game||"")).toLowerCase().includes(query)).map(u =>
      '<tr><td><b>'+esc(u.nickname)+'</b><br><small>ID '+u.id+'</small></td><td>'+esc(u.game||"Нет профиля")+'<br>'+esc(u.rank||"")+'</td><td>'+(u.is_blocked?'<span class="error">Заблокирован</span>':'<span class="admin-success">Активен</span>')+'</td><td>'+esc(u.created_at)+'</td><td><button class="btn edit-user" data-id="'+u.id+'">Изменить ник</button> <button class="btn reset-user-password" data-id="'+u.id+'">Сбросить пароль</button> <button class="btn toggle-user" data-id="'+u.id+'">'+(u.is_blocked?'Разблокировать':'Заблокировать')+'</button> <button class="btn danger delete-user" data-id="'+u.id+'">Удалить</button></td></tr>'
    ).join("") || '<tr><td colspan="5">Аккаунтов не найдено</td></tr>';
    $$(".edit-user").forEach(b=>b.addEventListener("click",async()=>{
      const u=users.find(x=>x.id===Number(b.dataset.id));const nickname=prompt("Новый никнейм:",u.nickname);if(nickname===null)return;
      try{await api("/api/admin/users/"+u.id,{method:"PATCH",body:JSON.stringify({nickname})});await loadData();message("Никнейм аккаунта обновлён",false)}catch(e){message(e.message,true)}
    }));
    $$(".reset-user-password").forEach(b=>b.addEventListener("click",async()=>{
      const u=users.find(x=>x.id===Number(b.dataset.id));const password=prompt("Введи новый пароль (минимум 10 символов) для "+u.nickname+":");if(password===null)return;
      if(password.length<10){message("Пароль должен содержать минимум 10 символов",true);return}
      if(!confirm("Сбросить пароль для "+u.nickname+"? Все текущие сессии будут завершены."))return;
      try{await api("/api/admin/users/"+u.id,{method:"PATCH",body:JSON.stringify({password})});message("Пароль изменён; пользователь должен войти заново",false)}catch(e){message(e.message,true)}
    }));
    $$(".toggle-user").forEach(b=>b.addEventListener("click",async()=>{
      const u=users.find(x=>x.id===Number(b.dataset.id));const blocked=!u.is_blocked;
      if(!confirm((blocked?"Заблокировать":"Разблокировать")+" аккаунт "+u.nickname+"?"))return;
      try{await api("/api/admin/users/"+u.id,{method:"PATCH",body:JSON.stringify({is_blocked:blocked})});await loadData();message(blocked?"Аккаунт заблокирован":"Аккаунт разблокирован",false)}catch(e){message(e.message,true)}
    }));
    $$(".delete-user").forEach(b=>b.addEventListener("click",async()=>{
      const u=users.find(x=>x.id===Number(b.dataset.id));if(!confirm("Окончательно удалить аккаунт "+u.nickname+" и его привязанный игровой профиль? Это действие нельзя отменить."))return;
      try{await api("/api/admin/users/"+u.id,{method:"DELETE"});await loadData();message("Аккаунт удалён",false)}catch(e){message(e.message,true)}
    }));
  };
  $("#user-search").addEventListener("input",draw);draw();
}
