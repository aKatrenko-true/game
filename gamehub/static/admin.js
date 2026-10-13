const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
let password = sessionStorage.getItem("gh_admin_password") || "";
let tab = "players", players = [], teams = [], matches = [];
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
  const r = await Promise.all([api("/api/admin/summary"), api("/api/players"), api("/api/teams"), api("/api/matches")]);
  const s = r[0]; players = r[1]; teams = r[2]; matches = r[3];
  $("#admin-stats").innerHTML = [["Игроки",s.players],["Команды",s.teams],["Матчи",s.matches],["Профили WarDogs",s.warDogsPlayers]].map(x => "<article><span>"+x[0]+"</span><b>"+x[1]+"</b><small>В базе данных</small></article>").join("");
  $("#login-panel").hidden = true; $("#dashboard").hidden = false; render();
}
async function submitLogin(event) {
  event.preventDefault(); password = $("#password").value; $("#login-error").textContent = "";
  try { await api("/api/admin/summary"); sessionStorage.setItem("gh_admin_password",password); await loadData(); }
  catch (e) { $("#login-error").textContent = e.message; }
}
$("#login-form").addEventListener("submit", submitLogin);
$("#logout").addEventListener("click", () => { sessionStorage.removeItem("gh_admin_password"); password = ""; $("#dashboard").hidden = true; $("#login-panel").hidden = false; $("#password").value = ""; });
$("#refresh").addEventListener("click", () => loadData().then(() => message("Данные обновлены",false)).catch(e => message(e.message,true)));
$$("[data-tab]").forEach(b => b.addEventListener("click", () => { tab = b.dataset.tab; render(); }));
function render() {
  $$("[data-tab]").forEach(b => b.classList.toggle("primary", b.dataset.tab === tab));
  $("#section-title").textContent = ({players:"Игроки",teams:"Команды",matches:"Матчи"})[tab];
  if (tab === "players") renderPlayers();
  if (tab === "teams") renderTeams();
  if (tab === "matches") renderMatches();
}
function renderPlayers() {
  $("#admin-content").innerHTML = '<div class="admin-form-grid"><form id="add-player" class="admin-form"><h3>Добавить игрока</h3><label>Никнейм<input name="nickname" minlength="3" maxlength="20" pattern="[A-Za-z0-9_]+" required></label><label>Игра<select name="game"><option>WarDogs</option><option>CS2</option><option>Valorant</option><option>Apex Legends</option><option>Dota 2</option></select></label><label>Ранг<input name="rank" value="Unranked" maxlength="30"></label><button class="btn primary">Добавить игрока</button></form><div class="admin-form"><h3>Список профилей</h3><input id="player-search" placeholder="Поиск по нику или игре"></div></div><div class="admin-table-wrap"><table><thead><tr><th>Никнейм</th><th>Игра</th><th>Ранг</th><th>Победы</th><th>Действия</th></tr></thead><tbody id="player-rows"></tbody></table></div>';
  const draw = () => {
    const q = $("#player-search").value.toLowerCase();
    $("#player-rows").innerHTML = players.filter(p => (p.nickname+" "+p.game).toLowerCase().includes(q)).map(p => '<tr><td><b>'+esc(p.nickname)+'</b></td><td>'+esc(p.game)+'</td><td>'+esc(p.rank)+'</td><td>'+p.wins+'</td><td><button class="btn edit-player" data-id="'+p.id+'">Изменить</button> <button class="btn danger delete-player" data-id="'+p.id+'">Удалить</button></td></tr>').join("") || '<tr><td colspan="5">Профили не найдены</td></tr>';
    $$(".edit-player").forEach(b => b.addEventListener("click", async () => {
      const p = players.find(x => x.id === Number(b.dataset.id)); const rank = prompt("Ранг:",p.rank); if (rank === null) return;
      const wins = prompt("Количество побед:",p.wins); if (wins === null) return;
      try { await api("/api/admin/players/"+p.id,{method:"PATCH",body:JSON.stringify({rank:rank,wins:Number(wins)})}); await loadData(); message("Профиль обновлён",false); } catch(e) { message(e.message,true); }
    }));
    $$(".delete-player").forEach(b => b.addEventListener("click", async () => {
      const p = players.find(x => x.id === Number(b.dataset.id)); if (!confirm("Удалить профиль "+p.nickname+"?")) return;
      try { await api("/api/admin/players/"+p.id,{method:"DELETE"}); await loadData(); message("Профиль удалён",false); } catch(e) { message(e.message,true); }
    }));
  };
  $("#player-search").addEventListener("input",draw); draw();
  $("#add-player").addEventListener("submit", async e => {
    e.preventDefault(); try { await api("/api/players",{method:"POST",body:JSON.stringify(Object.fromEntries(new FormData(e.currentTarget)))}); await loadData(); message("Игрок добавлен",false); } catch(err) { message(err.message,true); }
  });
}
function renderTeams() {
  $("#admin-content").innerHTML = '<form id="add-team" class="admin-form admin-create"><h3>Создать команду</h3><div class="admin-form-grid"><label>Название<input name="name" minlength="3" maxlength="40" required></label><label>Игра<select name="game"><option>WarDogs</option><option>CS2</option><option>Valorant</option><option>Apex Legends</option><option>Dota 2</option></select></label></div><label>Описание<input name="description" maxlength="240"></label><button class="btn primary">Создать команду</button></form><div class="admin-table-wrap"><table><thead><tr><th>Команда</th><th>Игра</th><th>Описание</th><th>Действия</th></tr></thead><tbody>'+ (teams.map(t => '<tr><td><b>'+esc(t.name)+'</b></td><td>'+esc(t.game)+'</td><td>'+esc(t.description)+'</td><td><button class="btn danger delete-team" data-id="'+t.id+'">Удалить</button></td></tr>').join("") || '<tr><td colspan="4">Команд пока нет</td></tr>') + '</tbody></table></div>';
  $("#add-team").addEventListener("submit", async e => { e.preventDefault(); try { await api("/api/admin/teams",{method:"POST",body:JSON.stringify(Object.fromEntries(new FormData(e.currentTarget)))}); await loadData(); message("Команда создана",false); } catch(err) { message(err.message,true); } });
  $$(".delete-team").forEach(b => b.addEventListener("click", async () => { const t = teams.find(x => x.id === Number(b.dataset.id)); if (!confirm("Удалить команду "+t.name+"?")) return; try { await api("/api/admin/teams/"+t.id,{method:"DELETE"}); await loadData(); message("Команда удалена",false); } catch(e) { message(e.message,true); } }));
}
function renderMatches() {
  $("#admin-content").innerHTML = '<form id="add-match" class="admin-form admin-create"><h3>Запланировать матч</h3><div class="admin-form-grid"><label>Игра<select name="game"><option>WarDogs</option><option>CS2</option><option>Valorant</option><option>Apex Legends</option><option>Dota 2</option></select></label><label>Дата и время<input name="scheduled_at" type="datetime-local" required></label><label>Команда A<input name="team_a" required minlength="2" maxlength="40"></label><label>Команда B<input name="team_b" required minlength="2" maxlength="40"></label></div><button class="btn primary">Создать матч</button></form><div class="admin-table-wrap"><table><thead><tr><th>Матч</th><th>Игра</th><th>Счёт</th><th>Статус</th><th>Дата</th><th>Действия</th></tr></thead><tbody>'+ (matches.map(m => '<tr><td><b>'+esc(m.team_a)+' vs '+esc(m.team_b)+'</b></td><td>'+esc(m.game)+'</td><td>'+m.score_a+':'+m.score_b+'</td><td>'+esc(m.status)+'</td><td>'+esc(m.scheduled_at)+'</td><td><button class="btn edit-match" data-id="'+m.id+'">Счёт/статус</button> <button class="btn danger delete-match" data-id="'+m.id+'">Удалить</button></td></tr>').join("") || '<tr><td colspan="6">Матчей пока нет</td></tr>') + '</tbody></table></div>';
  $("#add-match").addEventListener("submit", async e => { e.preventDefault(); const d = Object.fromEntries(new FormData(e.currentTarget)); d.scheduled_at = d.scheduled_at.replace("T"," "); try { await api("/api/admin/matches",{method:"POST",body:JSON.stringify(d)}); await loadData(); message("Матч создан",false); } catch(err) { message(err.message,true); } });
  $$(".edit-match").forEach(b => b.addEventListener("click", async () => { const m = matches.find(x => x.id === Number(b.dataset.id)); const status = prompt("Статус: Scheduled, Live или Completed",m.status); if (status === null) return; const a = prompt("Счёт команды A",m.score_a); if (a === null) return; const z = prompt("Счёт команды B",m.score_b); if (z === null) return; try { await api("/api/admin/matches/"+m.id,{method:"PATCH",body:JSON.stringify({status:status,score_a:Number(a),score_b:Number(z)})}); await loadData(); message("Матч обновлён",false); } catch(e) { message(e.message,true); } }));
  $$(".delete-match").forEach(b => b.addEventListener("click", async () => { const m = matches.find(x => x.id === Number(b.dataset.id)); if (!confirm("Удалить матч "+m.team_a+" vs "+m.team_b+"?")) return; try { await api("/api/admin/matches/"+m.id,{method:"DELETE"}); await loadData(); message("Матч удалён",false); } catch(e) { message(e.message,true); } }));
}
if (password) loadData().catch(error => { sessionStorage.removeItem("gh_admin_password"); password = ""; $("#login-panel").hidden = false; $("#dashboard").hidden = true; $("#login-error").textContent = error.message; });