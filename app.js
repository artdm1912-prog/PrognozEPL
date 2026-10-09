/**
 * 5-FACTOR POISSON ANALYTICAL ENGINE 2026/27
 * Двухфакторная модель: (Создано A * Допущено B / Базис лиги)
 */

// ============================================================================
// 1. БАЗИСЫ ЛИГ (Норматив на 1 команду за матч в сезоне 26/27)
// ============================================================================
const LEAGUE_BASELINES = {
  EPL: {
    name: 'АПЛ',
    phase1: { goals: 1.38, xg: 1.35, sot: 4.20, shots: 12.50, corners: 5.10 },
    phase2: {
      home: { goals: 1.52, xg: 1.48, sot: 4.60, shots: 13.80, corners: 5.60 },
      away: { goals: 1.24, xg: 1.22, sot: 3.80, shots: 11.20, corners: 4.60 }
    }
  },
  SERIE_A: {
    name: 'Серия А',
    phase1: { goals: 1.28, xg: 1.25, sot: 3.90, shots: 11.80, corners: 4.80 },
    phase2: {
      home: { goals: 1.40, xg: 1.36, sot: 4.25, shots: 12.80, corners: 5.20 },
      away: { goals: 1.16, xg: 1.14, sot: 3.55, shots: 10.80, corners: 4.40 }
    }
  },
  LA_LIGA: {
    name: 'Ла Лига',
    phase1: { goals: 1.26, xg: 1.23, sot: 3.85, shots: 11.60, corners: 4.70 },
    phase2: {
      home: { goals: 1.38, xg: 1.34, sot: 4.20, shots: 12.50, corners: 5.10 },
      away: { goals: 1.14, xg: 1.12, sot: 3.50, shots: 10.70, corners: 4.30 }
    }
  },
  BUNDESLIGA: {
    name: 'Бундеслига',
    phase1: { goals: 1.56, xg: 1.52, sot: 4.70, shots: 13.60, corners: 5.30 },
    phase2: {
      home: { goals: 1.70, xg: 1.65, sot: 5.10, shots: 14.80, corners: 5.80 },
      away: { goals: 1.42, xg: 1.39, sot: 4.30, shots: 12.40, corners: 4.80 }
    }
  },
  RPL: {
    name: 'РПЛ',
    phase1: { goals: 1.22, xg: 1.20, sot: 3.80, shots: 11.40, corners: 4.60 },
    phase2: {
      home: { goals: 1.34, xg: 1.31, sot: 4.10, shots: 12.20, corners: 5.00 },
      away: { goals: 1.10, xg: 1.09, sot: 3.50, shots: 10.60, corners: 4.20 }
    }
  }
};

// ============================================================================
// 2. ВЕСА И МНОЖИТЕЛИ КОНВЕРСИИ В ГОЛЫ
// ============================================================================
const WEIGHTS = {
  xg: 0.35,
  sot: 0.25,
  goals: 0.20,
  shots: 0.10,
  corners: 0.10
};

const CONVERSIONS = {
  xg:      { home: 1.00, away: 1.00 },
  sot:     { home: 0.38, away: 0.28 },
  goals:   { home: 1.00, away: 1.00 },
  shots:   { home: 0.14, away: 0.09 },
  corners: { home: 0.34, away: 0.23 }
};

// ============================================================================
// 3. БАЗА КОМАНД (СЕЗОН 2026/27)
// ============================================================================
// Команды загружаются из опубликованного team_stats.json; демонстрационных данных нет.
const TEAMS_DATABASE = { EPL: [] };
const STATS_URL = 'https://raw.githubusercontent.com/artdm1912-prog/PrognozEPL/main/team_stats.json';
const API_METRICS = { xg: 'xg', sot: 'shots_on_target', goals: 'goals', shots: 'shots', corners: 'corners' };
let statsMetadata = null;
let statsLoadError = null;

function safeText(value) {
  return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function convertTeam(t) {
  if (!t || !t.per_match || !Number.isInteger(t.played) || t.played < 1) return null;
  const stats = {};
  for (const [metric, apiKey] of Object.entries(API_METRICS)) {
    const p = t.per_match[apiKey];
    const home = t.home && t.home.per_match && t.home.per_match[apiKey];
    const away = t.away && t.away.per_match && t.away.per_match[apiKey];
    if (!p || !Number.isFinite(Number(p.for)) || !Number.isFinite(Number(p.against))) return null;
    stats[metric] = {
      created: Number(p.for), conceded: Number(p.against),
      home: home && Number.isFinite(Number(home.for)) && Number.isFinite(Number(home.against))
        ? { created: Number(home.for), conceded: Number(home.against) } : null,
      away: away && Number.isFinite(Number(away.for)) && Number.isFinite(Number(away.against))
        ? { created: Number(away.for), conceded: Number(away.against) } : null
    };
  }
  return {
    id: String(t.id), name: safeText(t.name),
    played: t.played,
    homeMatches: Number(t.home_played) || 0,
    awayMatches: Number(t.away_played) || 0,
    injuryModPercent: 0,
    injuriesNote: 'Кадровые данные не подключены — поправка 0% (нейтрально)',
    stats
  };
}

async function loadLeagueData() {
  const phaseBadge = document.getElementById('phase-badge');
  phaseBadge.textContent = 'Загрузка подтверждённой статистики АПЛ…';
  try {
    const response = await fetch(STATS_URL, { cache: 'no-store' });
    if (!response.ok) throw new Error('HTTP ' + response.status);
    const json = await response.json();
    if (json.season !== '2026/27' || json.league !== 'АПЛ' || !json.teams || typeof json.teams !== 'object') {
      throw new Error('Неверный формат, лига или сезон данных');
    }
    const teams = Object.values(json.teams).map(convertTeam).filter(Boolean)
      .sort((a, b) => a.name.localeCompare(b.name, 'ru'));
    if (teams.length < 2) throw new Error('Недостаточно команд с полной статистикой');
    TEAMS_DATABASE.EPL = teams;
    statsMetadata = json;
    statsLoadError = null;
  } catch (error) {
    TEAMS_DATABASE.EPL = [];
    statsLoadError = error.message;
  }
  populateTeamSelectors();
}

// ============================================================================
// 4. ДВУХФАКТОРНЫЙ РАСЧЁТ
// ============================================================================
function calculateMatchForecast(homeTeam, awayTeam, leagueKey) {
  const league = LEAGUE_BASELINES[leagueKey];

  // Проверка фазы выборки (5+ домашних у хозяев и 5+ выездных у гостей)
  const isPhase2 = (homeTeam.homeMatches >= 5) && (awayTeam.awayMatches >= 5) &&
    ["xg", "sot", "goals", "shots", "corners"].every(m => homeTeam.stats[m].home && awayTeam.stats[m].away);

  // Факторы поля: в Фазе 1 даем 1.10 / 0.90, в Фазе 2 строго 1.00
  const homeAdvantage = isPhase2 ? 1.00 : 1.10;
  const awayDiscount  = isPhase2 ? 1.00 : 0.90;

  const baseline = isPhase2 ? league.phase2 : { home: league.phase1, away: league.phase1 };

  const metrics = ['xg', 'sot', 'goals', 'shots', 'corners'];
  const tableRows = [];

  let homeTotalXScore = 0;
  let awayTotalXScore = 0;

  metrics.forEach(m => {
    // Взаимное столкновение: (Создано A * Допущено B / Базис лиги) * Фактор поля
    const homeCreated = isPhase2 ? homeTeam.stats[m].home.created : homeTeam.stats[m].created;
    const awayConceded = isPhase2 ? awayTeam.stats[m].away.conceded : awayTeam.stats[m].conceded;
    const awayCreated = isPhase2 ? awayTeam.stats[m].away.created : awayTeam.stats[m].created;
    const homeConceded = isPhase2 ? homeTeam.stats[m].home.conceded : homeTeam.stats[m].conceded;
    const hVol = ((homeCreated * awayConceded) / baseline.home[m]) * homeAdvantage;
    const aVol = ((awayCreated * homeConceded) / baseline.away[m]) * awayDiscount;

    // Перевод объема в голы
    const hGoalExp = hVol * CONVERSIONS[m].home;
    const aGoalExp = aVol * CONVERSIONS[m].away;

    // Взвешивание в xScore
    homeTotalXScore += hGoalExp * WEIGHTS[m];
    awayTotalXScore += aGoalExp * WEIGHTS[m];

    tableRows.push({
      metricKey: m,
      homeVolume: hVol.toFixed(1),
      homeGoalExp: hGoalExp.toFixed(1),
      awayVolume: aVol.toFixed(1),
      awayGoalExp: aGoalExp.toFixed(1),
      totalVolume: (hVol + aVol).toFixed(1),
      scoreExp: `${hGoalExp.toFixed(1)} : ${aGoalExp.toFixed(1)} (${Math.round(hGoalExp)}:${Math.round(aGoalExp)})`
    });
  });

  // Кадровая модификация (Mod Кадры)
  const homeModScore = homeTotalXScore * (1 + (homeTeam.injuryModPercent || 0) / 100);
  const awayModScore = awayTotalXScore * (1 + (awayTeam.injuryModPercent || 0) / 100);

  return {
    isPhase2,
    tableRows,
    baseScore: {
      home: homeTotalXScore.toFixed(1),
      away: awayTotalXScore.toFixed(1),
      rounded: `${Math.round(homeTotalXScore)} : ${Math.round(awayTotalXScore)}`
    },
    modScore: {
      home: homeModScore.toFixed(1),
      away: awayModScore.toFixed(1),
      rounded: `${Math.round(homeModScore)} : ${Math.round(awayModScore)}`
    },
    totalXScore: (homeModScore + awayModScore).toFixed(1)
  };
}

// ============================================================================
// 5. ГЕНЕРАЦИЯ И ОБНОВЛЕНИЕ ИНТЕРФЕЙСА
// ============================================================================
function updateUI() {
  const leagueKey = document.getElementById('league-select').value;
  const homeId = document.getElementById('home-team-select').value;
  const awayId = document.getElementById('away-team-select').value;

  const leagueTeams = TEAMS_DATABASE[leagueKey] || [];
  if (leagueTeams.length < 2) return;
  const homeTeam = leagueTeams.find(t => t.id === homeId) || leagueTeams[0];
  const awayTeam = leagueTeams.find(t => t.id === awayId) || leagueTeams[1];

  if (homeTeam.id === awayTeam.id) {
    document.getElementById('match-header-card').textContent = 'Выбери две разные команды.';
    document.getElementById('forecast-table-container').innerHTML = '';
    return;
  }
  const forecast = calculateMatchForecast(homeTeam, awayTeam, leagueKey);
  const leagueBase = LEAGUE_BASELINES[leagueKey].phase1;

  // 1. Бейдж фазы
  const phaseBadge = document.getElementById('phase-badge');
  if (forecast.isPhase2) {
    phaseBadge.className = 'px-3 py-1 bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 rounded-full text-xs font-semibold';
    phaseBadge.innerText = '● Фаза 2 (Сплит Дома/Выезд 5+ матчей, без коэфф. поля)';
  } else {
    phaseBadge.className = 'px-3 py-1 bg-blue-950/80 border border-blue-500/40 text-blue-300 rounded-full text-xs font-semibold';
    phaseBadge.innerText = '● Фаза 1 (Старт сезона: Общая статистика + фактор поля 1.1/0.9)';
  }

  const smallSample = Math.min(homeTeam.played, awayTeam.played) < 8;
  const verificationLine = `<div class="text-xs text-amber-300 mt-3">${smallSample ? '⚠ Малая выборка: прогноз предварительный. Не рекомендация для ставок.' : 'Расчётная оценка, не гарантия результата.'} Хозяева: ${homeTeam.played} матчей, гости: ${awayTeam.played} матчей. Данные: ${safeText(statsMetadata.updated_at || 'дата неизвестна')}. Источник: footballdata.io через GitHub.</div>`;

  // 2. Карточка матча (Вердикт)
  const headerCard = document.getElementById('match-header-card');
  let verdictText = 'Склоняется к ТБ (2.5)';
  if (forecast.totalXScore < 2.20) verdictText = 'Выраженный низовой характер (ТМ 2.5 / ТМ 2.0)';
  else if (forecast.totalXScore <= 2.69) verdictText = 'Пограничный баланс, склоняется к ТМ (2.5) / ТБ (2.0)';
  else if (forecast.totalXScore >= 3.20) verdictText = 'Ярко выраженный верховой матч (ТБ 2.5 / ТБ 3.0)';

  headerCard.innerHTML = `
    <div class="flex flex-col md:flex-row justify-between items-center gap-4">
      <div class="text-center md:text-left">
        <h2 class="text-2xl font-black text-white tracking-wide">${homeTeam.name} — ${awayTeam.name}</h2>
        <div class="text-xs text-slate-400 mt-1">Сезон 2026/27 • ${LEAGUE_BASELINES[leagueKey].name}</div>
      </div>
      <div class="bg-slate-900/90 border border-slate-700 px-6 py-3 rounded-xl text-center">
        <div class="text-xs uppercase tracking-wider text-slate-400 font-bold">Прогноз счёта</div>
        <div class="text-3xl font-black text-blue-400 mt-0.5">${forecast.modScore.rounded}</div>
        <div class="text-xs text-slate-400">дробный: <span class="text-slate-200 font-semibold">${forecast.modScore.home} : ${forecast.modScore.away}</span> (базовый: ${forecast.baseScore.home}:${forecast.baseScore.away})</div>
      </div>
    </div>
    <div class="mt-4 pt-4 border-t border-slate-700/60 flex flex-wrap gap-4 text-xs">
      <div><span class="text-slate-400">Вердикт по тоталу:</span> <span class="text-emerald-400 font-semibold">${verdictText}</span> (сумма ${forecast.totalXScore})</div>
      <div><span class="text-slate-400">Базис лиги:</span> Голы ${leagueBase.goals} | xG ${leagueBase.xg} | Створ ${leagueBase.sot} | Удары ${leagueBase.shots} | Углы ${leagueBase.corners}</div>
    ${verificationLine}
    </div>
  `;

  // 3. Таблица
  const metricTitles = {
    xg: 'xG / xGA (35%)',
    sot: 'Удары в створ (25%)',
    goals: 'Реальные голы (20%)',
    shots: 'Все удары (10%)',
    corners: 'Угловые (10%)'
  };

  const volumeUnits = {
    xg: 'xG',
    sot: 'в створ',
    goals: 'гола',
    shots: 'удара',
    corners: 'угловых'
  };

  const rowsHTML = forecast.tableRows.map(row => `
    <tr class="border-b border-slate-700/40 hover:bg-slate-800/40 transition">
      <td class="py-2.5 px-3 text-center font-bold text-slate-100">
        ${row.homeVolume} <span class="text-xs text-slate-400 font-normal">(${row.homeGoalExp} гола)</span>
      </td>
      <td class="py-2.5 px-3 text-center text-xs font-semibold text-slate-300">
        ${metricTitles[row.metricKey]}
      </td>
      <td class="py-2.5 px-3 text-center font-bold text-slate-100">
        ${row.awayVolume} <span class="text-xs text-slate-400 font-normal">(${row.awayGoalExp} гола)</span>
      </td>
      <td class="py-2.5 px-3 text-center text-xs text-slate-400">
        ${row.totalVolume} ${volumeUnits[row.metricKey]}
      </td>
      <td class="py-2.5 px-3 text-center font-semibold text-blue-300 text-xs">
        ${row.scoreExp}
      </td>
    </tr>
  `).join('');

  document.getElementById('forecast-table-container').innerHTML = `
    <div class="overflow-x-auto rounded-xl border border-slate-700 bg-slate-850">
      <table class="min-w-full text-sm">
        <thead class="bg-slate-800 text-slate-300 text-xs uppercase tracking-wider border-b border-slate-700">
          <tr>
            <th class="py-3 px-3 text-center">${homeTeam.name} (Объём → Голы)</th>
            <th class="py-3 px-3 text-center">Показатель (Вес)</th>
            <th class="py-3 px-3 text-center">${awayTeam.name} (Объём → Голы)</th>
            <th class="py-3 px-3 text-center">Тотал объёма</th>
            <th class="py-3 px-3 text-center">Ожидание (Счёт)</th>
          </tr>
        </thead>
        <tbody>
          ${rowsHTML}
          <tr class="bg-slate-800/70 font-bold border-b border-slate-700">
            <td colspan="3" class="py-3 px-4 text-left text-slate-200">Σ xScore (Базовый)</td>
            <td colspan="2" class="py-3 px-4 text-right text-slate-100 font-mono">${forecast.baseScore.home} : ${forecast.baseScore.away} (${forecast.baseScore.rounded})</td>
          </tr>
          <tr class="bg-blue-950/40 font-bold text-blue-300">
            <td colspan="3" class="py-3 px-4 text-left">Mod Кадры (${homeTeam.injuryModPercent}% / ${awayTeam.injuryModPercent}%)</td>
            <td colspan="2" class="py-3 px-4 text-right text-emerald-400 font-mono text-base">${forecast.modScore.home} : ${forecast.modScore.away} (${forecast.modScore.rounded})</td>
          </tr>
        </tbody>
      </table>
    </div>
  `;

  // 4. Карточки травм
  document.getElementById('home-injury-card').innerHTML = `
    <div class="text-xs uppercase font-bold text-slate-400">Состав: ${homeTeam.name}</div>
    <div class="text-sm text-slate-200 mt-1">${homeTeam.injuriesNote}</div>
    <div class="text-xs text-blue-400 mt-2 font-medium">Поправка: ${homeTeam.injuryModPercent}% к атакующему потенциалу</div>
  `;

  document.getElementById('away-injury-card').innerHTML = `
    <div class="text-xs uppercase font-bold text-slate-400">Состав: ${awayTeam.name}</div>
    <div class="text-sm text-slate-200 mt-1">${awayTeam.injuriesNote}</div>
    <div class="text-xs text-blue-400 mt-2 font-medium">Поправка: ${awayTeam.injuryModPercent}% к атакующему потенциалу</div>
  `;
}

// ============================================================================
// 6. СЕЛЕКТОРЫ И ИНИЦИАЛИЗАЦИЯ
// ============================================================================
function populateTeamSelectors() {
  const leagueKey = document.getElementById('league-select').value;
  const teams = TEAMS_DATABASE[leagueKey] || [];

  const homeSelect = document.getElementById('home-team-select');
  const awaySelect = document.getElementById('away-team-select');

  if (teams.length < 2) {
    homeSelect.innerHTML = '<option>Нет данных</option>';
    awaySelect.innerHTML = '<option>Нет данных</option>';
    document.getElementById('phase-badge').textContent = 'Нет подтверждённых данных';
    document.getElementById('match-header-card').textContent = 'Не удалось загрузить статистику АПЛ: ' + (statsLoadError || 'неизвестная ошибка') + '. Проверьте подключение к GitHub и обновите страницу.';
    document.getElementById('forecast-table-container').innerHTML = '';
    document.getElementById('home-injury-card').innerHTML = '';
    document.getElementById('away-injury-card').innerHTML = '';
    return;
  }
  homeSelect.innerHTML = teams.map((t, idx) => `<option value="${t.id}" ${idx === 0 ? 'selected' : ''}>${t.name}</option>`).join('');
  awaySelect.innerHTML = teams.map((t, idx) => `<option value="${t.id}" ${idx === 1 ? 'selected' : ''}>${t.name}</option>`).join('');

  updateUI();
}

document.getElementById('league-select').addEventListener('change', populateTeamSelectors);
document.getElementById('home-team-select').addEventListener('change', updateUI);
document.getElementById('away-team-select').addEventListener('change', updateUI);

// Тестируем только АПЛ; для остальных лиг не показываем придуманные показатели.
const leagueSelect = document.getElementById('league-select');
leagueSelect.innerHTML = '<option value="EPL">Английская Премьер-лига (АПЛ)</option>';
loadLeagueData();
