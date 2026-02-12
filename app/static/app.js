/* ─── RH Quiz — Single Page Application ─── */

(function () {
  'use strict';

  // ── State ──
  const state = {
    userId: null,
    displayName: null,
    currentQuiz: null,      // { subject, questions, multiplier_active }
    selectedAnswers: {},     // { questionId: answerId }
    currentQuestion: 0,
    leaderboardTimer: null,
    leaderboardCountdown: 30,
  };

  // ── Fun loading GIFs (cat themed) ──
  const LOADING_GIFS = [
    'https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif',
    'https://media.giphy.com/media/mlvseq9yvZhba/giphy.gif',
    'https://media.giphy.com/media/o0vwzuFwCGAFO/giphy.gif',
    'https://media.giphy.com/media/13borq7Zo2kulO/giphy.gif',
    'https://media.giphy.com/media/nR4L10XlJcSeQ/giphy.gif',
    'https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif',
    'https://media.giphy.com/media/MDJ9IbxxvDUQM/giphy.gif',
    'https://media.giphy.com/media/VbnUQpnihPSIgIXuZv/giphy.gif',
  ];

  // ── Cookie helpers ──
  function setCookie(name, value, days = 365) {
    const d = new Date();
    d.setTime(d.getTime() + days * 86400000);
    document.cookie = `${name}=${encodeURIComponent(value)};expires=${d.toUTCString()};path=/;SameSite=Lax`;
  }

  function getCookie(name) {
    const v = document.cookie.match('(^|;)\\s*' + name + '=([^;]*)');
    return v ? decodeURIComponent(v[2]) : null;
  }

  function deleteCookie(name) {
    document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;SameSite=Lax`;
  }

  // ── Toast ──
  function toast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 3000);
  }

  // ── Screen management ──
  function showScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    const screen = document.getElementById(`screen-${id}`);
    if (screen) screen.classList.add('active');

    const header = document.getElementById('app-header');
    header.style.display = id === 'welcome' ? 'none' : '';

    // Nav active state
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    if (id === 'subject' || id === 'quiz' || id === 'loading' || id === 'results') {
      document.getElementById('nav-quiz')?.classList.add('active');
    }
    if (id === 'leaderboard') {
      document.getElementById('nav-lb')?.classList.add('active');
    }

    // Quiz submit bar
    document.getElementById('quiz-submit-bar').style.display = id === 'quiz' ? '' : 'none';

    // Leaderboard auto-refresh
    if (id === 'leaderboard') {
      loadLeaderboard();
      startLeaderboardRefresh();
    } else {
      stopLeaderboardRefresh();
    }
  }

  // ── API helpers ──
  async function api(path, options = {}) {
    const res = await fetch(path, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  }

  // ── User management ──
  async function registerUser(name) {
    const data = await api('/api/user/register', {
      method: 'POST',
      body: JSON.stringify({ display_name: name }),
    });
    state.userId = data.id;
    state.displayName = data.display_name;
    setCookie('rh_quiz_user_id', data.id);
    setCookie('rh_quiz_user_name', data.display_name);
    updateUserBadge();
  }

  function updateUserBadge() {
    const name = state.displayName || '?';
    document.getElementById('user-display-name').textContent = name;
    document.getElementById('user-avatar').textContent = name.charAt(0).toUpperCase();
  }

  function restoreUser() {
    const id = getCookie('rh_quiz_user_id');
    const name = getCookie('rh_quiz_user_name');
    if (id && name) {
      state.userId = id;
      state.displayName = name;
      updateUserBadge();
      return true;
    }
    return false;
  }

  // ── Quiz generation ──
  async function generateQuiz(subject) {
    showScreen('loading');
    document.getElementById('loading-subject').textContent = `About: ${subject}`;

    // Random fun GIF
    const gif = LOADING_GIFS[Math.floor(Math.random() * LOADING_GIFS.length)];
    document.getElementById('loading-gif').src = gif;

    try {
      const data = await api('/api/quiz/generate', {
        method: 'POST',
        body: JSON.stringify({ subject }),
      });

      state.currentQuiz = data;
      state.selectedAnswers = {};
      state.currentQuestion = 0;
      renderQuiz();
      showScreen('quiz');
    } catch (e) {
      toast(e.message, 'error');
      showScreen('subject');
    }
  }

  // ── Quiz rendering ──
  function renderQuiz() {
    const quiz = state.currentQuiz;
    const container = document.getElementById('quiz-container');

    const progressPct = ((state.currentQuestion + 1) / quiz.questions.length) * 100;

    let html = `
      <div class="quiz-progress">
        <div class="progress-bar"><div class="progress-fill" style="width:${progressPct}%"></div></div>
        <span class="progress-text">${state.currentQuestion + 1} / ${quiz.questions.length}</span>
      </div>
    `;

    if (quiz.multiplier_active) {
      html += `<div class="multiplier-badge">⚡ 2× MULTIPLIER ACTIVE</div>`;
    }

    const q = quiz.questions[state.currentQuestion];
    html += `
      <div class="question-card">
        <div class="question-number">Question ${state.currentQuestion + 1}</div>
        <div class="question-text">${escapeHtml(q.question)}</div>
        <div class="answers-list">
    `;

    for (const a of q.answers) {
      const selected = state.selectedAnswers[q.id] === a.id;
      html += `
        <div class="answer-option ${selected ? 'selected' : ''}" data-qid="${q.id}" data-aid="${a.id}">
          <div class="radio"></div>
          <span class="answer-text">${escapeHtml(a.text)}</span>
        </div>
      `;
    }

    html += `</div></div>`;

    // Navigation buttons
    html += `<div style="display:flex;gap:10px;margin-top:4px;">`;
    if (state.currentQuestion > 0) {
      html += `<button class="btn btn-secondary" id="btn-prev-q" style="flex:1">← Back</button>`;
    }
    if (state.currentQuestion < quiz.questions.length - 1) {
      html += `<button class="btn btn-secondary" id="btn-next-q" style="flex:1" ${!state.selectedAnswers[q.id] ? 'disabled' : ''}>Next →</button>`;
    }
    html += `</div>`;

    container.innerHTML = html;

    // Answer click handlers
    container.querySelectorAll('.answer-option').forEach(el => {
      el.addEventListener('click', () => {
        const qid = el.dataset.qid;
        const aid = el.dataset.aid;
        state.selectedAnswers[qid] = aid;
        renderQuiz(); // Re-render to update selection
      });
    });

    // Navigation
    document.getElementById('btn-prev-q')?.addEventListener('click', () => {
      state.currentQuestion--;
      renderQuiz();
    });
    document.getElementById('btn-next-q')?.addEventListener('click', () => {
      state.currentQuestion++;
      renderQuiz();
    });

    // Submit button state
    const submitBtn = document.getElementById('btn-submit-quiz');
    const allAnswered = quiz.questions.every(q => state.selectedAnswers[q.id]);
    submitBtn.disabled = !allAnswered;
    document.getElementById('quiz-submit-bar').style.display = '';
  }

  // ── Submit quiz ──
  async function submitQuiz() {
    const quiz = state.currentQuiz;
    const answers = quiz.questions.map(q => ({
      question_id: q.id,
      answer_id: state.selectedAnswers[q.id],
    }));

    const payload = {
      subject: quiz.subject,
      questions: quiz.questions.map(q => ({
        id: q.id,
        question: q.question,
        answers: q.answers.map(a => ({
          id: a.id,
          text: a.text,
          class: a.answer_class,
          explanation: a.explanation || '',
        })),
      })),
      answers,
    };

    try {
      const result = await api(`/api/quiz/submit?user_id=${state.userId}`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      renderResults(result, quiz);
      showScreen('results');
    } catch (e) {
      toast(e.message, 'error');
    }
  }

  // ── Results rendering ──
  function renderResults(result, quiz) {
    const container = document.getElementById('results-container');

    const scoreClass = result.score_total > 0 ? 'positive' : result.score_total < 0 ? 'negative' : 'neutral';
    const multiplierText = result.multiplier > 1 ? ` (${result.score_raw} × ${result.multiplier})` : '';

    let html = `
      <div class="score-hero">
        <div class="score-label">Your Score</div>
        <div class="score-value ${scoreClass}">${result.score_total > 0 ? '+' : ''}${result.score_total}</div>
        <div class="score-breakdown">${result.score_raw} pts raw${multiplierText}</div>
      </div>
    `;

    // Detail per question
    for (let i = 0; i < result.details.length; i++) {
      const d = result.details[i];
      const q = quiz.questions[i];

      let answerClass, answerLabel;
      if (d.selected_class === 'correct') {
        answerClass = 'correct';
        answerLabel = '✓ Correct';
      } else if (d.selected_class === 'obviously_wrong') {
        answerClass = 'wrong';
        answerLabel = '✗ Obviously Wrong';
      } else {
        answerClass = 'doubtful';
        answerLabel = '~ Doubtful';
      }

      html += `
        <div class="result-detail">
          <div class="q-label">Question ${i + 1}</div>
          <div class="q-text">${escapeHtml(q.question)}</div>
          <div class="result-answer ${answerClass}">
            <span>${answerLabel}: ${escapeHtml(d.selected_text)}</span>
            <span class="points">${d.points > 0 ? '+' : ''}${d.points}</span>
          </div>
      `;

      if (d.selected_class !== 'correct' && d.correct_answer_text) {
        html += `<div class="result-correct-answer">✓ Correct answer: ${escapeHtml(d.correct_answer_text)}</div>`;
      }

      if (d.explanation) {
        html += `<div class="result-explanation">${escapeHtml(d.explanation)}</div>`;
      }

      html += `</div>`;
    }

    html += `
      <div class="results-actions">
        <button class="btn btn-primary btn-block" id="btn-more">More…</button>
        <button class="btn btn-secondary btn-block" id="btn-to-leaderboard">View Leaderboard</button>
      </div>
    `;

    container.innerHTML = html;

    document.getElementById('btn-more').addEventListener('click', () => {
      document.getElementById('input-subject').value = '';
      showScreen('subject');
    });

    document.getElementById('btn-to-leaderboard').addEventListener('click', () => {
      showScreen('leaderboard');
    });
  }

  // ── Leaderboard ──
  async function loadLeaderboard() {
    const container = document.getElementById('leaderboard-container');

    try {
      const data = await api('/api/leaderboard');

      let html = `
        <div class="leaderboard-header">
          <h2>🏆 Leaderboard</h2>
          <div class="refresh-badge">
            <div class="refresh-dot"></div>
            <span id="lb-countdown">${state.leaderboardCountdown}s</span>
          </div>
        </div>
      `;

      if (data.entries.length === 0) {
        html += `
          <div class="lb-empty">
            <div class="icon">🎯</div>
            <p>No scores yet. Be the first to play!</p>
          </div>
        `;
      } else {
        html += `
          <div class="leaderboard-table">
            <div class="lb-row header">
              <span>#</span>
              <span>Player</span>
              <span style="text-align:right">Score</span>
            </div>
        `;

        data.entries.forEach((entry, i) => {
          const rank = i + 1;
          let rowClass = '';
          if (rank === 1) rowClass = 'top-1';
          else if (rank === 2) rowClass = 'top-2';
          else if (rank === 3) rowClass = 'top-3';
          if (entry.user_id === state.userId) rowClass += ' is-you';

          const trophy = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : rank;

          html += `
            <div class="lb-row ${rowClass}">
              <div class="lb-rank">${trophy}</div>
              <div class="lb-name">
                ${escapeHtml(entry.display_name)}
                ${entry.user_id === state.userId ? '<span class="you-tag">(you)</span>' : ''}
              </div>
              <div class="lb-score-block">
                <div class="lb-total">${entry.total_score}</div>
                <div class="lb-meta">${entry.quizzes_taken} quiz${entry.quizzes_taken !== 1 ? 'zes' : ''} · best: ${entry.best_score}</div>
              </div>
            </div>
          `;
        });

        html += `</div>`;
      }

      // Admin reset
      html += `
        <div class="admin-row">
          <span>Admin</span>
          <button class="btn btn-danger" id="btn-reset-lb">Reset Leaderboard</button>
        </div>
      `;

      // Back to quiz
      html += `
        <button class="btn btn-secondary btn-block" id="btn-back-quiz" style="margin-top:8px;">← Back to Quiz</button>
      `;

      container.innerHTML = html;

      document.getElementById('btn-reset-lb')?.addEventListener('click', resetLeaderboard);
      document.getElementById('btn-back-quiz')?.addEventListener('click', () => showScreen('subject'));

    } catch (e) {
      toast('Failed to load leaderboard', 'error');
    }
  }

  async function resetLeaderboard() {
    const token = prompt('Enter admin token:');
    if (!token) return;

    try {
      await api('/api/leaderboard/reset', {
        method: 'DELETE',
        headers: { 'X-Admin-Token': token },
      });
      toast('Leaderboard reset!', 'success');
      loadLeaderboard();
    } catch (e) {
      toast(e.message, 'error');
    }
  }

  function startLeaderboardRefresh() {
    stopLeaderboardRefresh();
    state.leaderboardCountdown = 30;

    state.leaderboardTimer = setInterval(() => {
      state.leaderboardCountdown--;
      const el = document.getElementById('lb-countdown');
      if (el) el.textContent = `${state.leaderboardCountdown}s`;

      if (state.leaderboardCountdown <= 0) {
        state.leaderboardCountdown = 30;
        loadLeaderboard();
      }
    }, 1000);
  }

  function stopLeaderboardRefresh() {
    if (state.leaderboardTimer) {
      clearInterval(state.leaderboardTimer);
      state.leaderboardTimer = null;
    }
  }

  // ── Utilities ──
  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // ── Init & Event Binding ──
  function init() {
    // Restore user from cookie
    if (restoreUser()) {
      showScreen('subject');
    } else {
      showScreen('welcome');
    }

    // Name input
    const nameInput = document.getElementById('input-name');
    const startBtn = document.getElementById('btn-start');

    nameInput.addEventListener('input', () => {
      startBtn.disabled = !nameInput.value.trim();
    });

    nameInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && nameInput.value.trim()) startBtn.click();
    });

    startBtn.addEventListener('click', async () => {
      const name = nameInput.value.trim();
      if (!name) return;
      startBtn.disabled = true;
      startBtn.textContent = 'Setting up…';
      try {
        await registerUser(name);
        showScreen('subject');
      } catch (e) {
        toast(e.message, 'error');
      } finally {
        startBtn.disabled = false;
        startBtn.textContent = "Let's go";
      }
    });

    // Change name
    document.getElementById('btn-change-name').addEventListener('click', () => {
      deleteCookie('rh_quiz_user_id');
      deleteCookie('rh_quiz_user_name');
      state.userId = null;
      state.displayName = null;
      document.getElementById('input-name').value = '';
      showScreen('welcome');
    });

    // Subject input
    const subjectInput = document.getElementById('input-subject');
    const generateBtn = document.getElementById('btn-generate');

    subjectInput.addEventListener('input', () => {
      generateBtn.disabled = !subjectInput.value.trim();
    });

    subjectInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && subjectInput.value.trim()) generateBtn.click();
    });

    generateBtn.addEventListener('click', () => {
      const subject = subjectInput.value.trim();
      if (!subject) return;
      generateQuiz(subject);
    });

    // Submit quiz
    document.getElementById('btn-submit-quiz').addEventListener('click', submitQuiz);

    // Nav buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const screen = btn.dataset.screen;
        if (screen) showScreen(screen);
      });
    });
  }

  // Boot
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
