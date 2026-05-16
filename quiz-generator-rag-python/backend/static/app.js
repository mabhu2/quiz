const STORAGE_KEYS = {
  history: "learnos.quiz.history",
  settings: "learnos.quiz.settings",
};

const DEFAULT_SETTINGS = {
  theme: "light",
  density: "comfortable",
  fontScale: 100,
  fontStyle: "system",
  defaultDifficulty: "mixed",
  defaultCount: 5,
  autoExplain: true,
  reduceMotion: false,
  motionIntensity: 70,
};

const SKILLS = ["logic", "syntax", "concept", "application"];

const state = {
  page: "home",
  settings: loadSettings(),
  history: loadHistory(),
  quiz: null,
  result: null,
  answers: new Map(),
  currentIndex: 0,
  questionStartedAt: 0,
  quizStartedAt: 0,
  elapsedMs: 0,
  timerId: null,
  lastRequest: null,
};

const elements = {
  body: document.body,
  pages: document.querySelectorAll("[data-page-panel]"),
  navLinks: document.querySelectorAll(".main-nav .nav-link"),
  routeButtons: document.querySelectorAll(".nav-link[data-page]"),
  quizForm: document.querySelector("#quizForm"),
  topicInput: document.querySelector("#topicInput"),
  difficultySelect: document.querySelector("#difficultySelect"),
  countSelect: document.querySelector("#countSelect"),
  modeSelect: document.querySelector("#modeSelect"),
  generateButton: document.querySelector("#generateButton"),
  loadingText: document.querySelector("#loadingText"),
  personalMessage: document.querySelector("#personalMessage"),
  totalQuizzes: document.querySelector("#totalQuizzes"),
  avgScore: document.querySelector("#avgScore"),
  bestSkill: document.querySelector("#bestSkill"),
  streakBadge: document.querySelector("#streakBadge"),
  readinessScore: document.querySelector("#readinessScore"),
  quickThemeButton: document.querySelector("#quickThemeButton"),
  exitQuizButton: document.querySelector("#exitQuizButton"),
  progressBar: document.querySelector("#progressBar"),
  questionCounter: document.querySelector("#questionCounter"),
  quizTimer: document.querySelector("#quizTimer"),
  questionDifficulty: document.querySelector("#questionDifficulty"),
  questionSkill: document.querySelector("#questionSkill"),
  questionText: document.querySelector("#questionText"),
  optionList: document.querySelector("#optionList"),
  feedbackBox: document.querySelector("#feedbackBox"),
  prevButton: document.querySelector("#prevButton"),
  finishQuizButton: document.querySelector("#finishQuizButton"),
  nextButton: document.querySelector("#nextButton"),
  scoreRing: document.querySelector("#scoreRing"),
  scorePercent: document.querySelector("#scorePercent"),
  masteryLevel: document.querySelector("#masteryLevel"),
  scoreMessage: document.querySelector("#scoreMessage"),
  scoreLine: document.querySelector("#scoreLine"),
  accuracyMetric: document.querySelector("#accuracyMetric"),
  timeMetric: document.querySelector("#timeMetric"),
  correctMetric: document.querySelector("#correctMetric"),
  incorrectMetric: document.querySelector("#incorrectMetric"),
  skillCards: document.querySelector("#skillCards"),
  nextTopics: document.querySelector("#nextTopics"),
  retryButton: document.querySelector("#retryButton"),
  weakPracticeButton: document.querySelector("#weakPracticeButton"),
  newQuizButton: document.querySelector("#newQuizButton"),
  dashTotal: document.querySelector("#dashTotal"),
  dashAverage: document.querySelector("#dashAverage"),
  dashTrend: document.querySelector("#dashTrend"),
  trendChart: document.querySelector("#trendChart"),
  radarChart: document.querySelector("#radarChart"),
  topicHeatmap: document.querySelector("#topicHeatmap"),
  timeline: document.querySelector("#timeline"),
  dashboardRecommendations: document.querySelector("#dashboardRecommendations"),
  historyList: document.querySelector("#historyList"),
  clearHistoryButton: document.querySelector("#clearHistoryButton"),
  fontSizeSlider: document.querySelector("#fontSizeSlider"),
  fontStyleSelect: document.querySelector("#fontStyleSelect"),
  densitySelect: document.querySelector("#densitySelect"),
  themeGrid: document.querySelector("#themeGrid"),
  defaultDifficultySelect: document.querySelector("#defaultDifficultySelect"),
  defaultCountSelect: document.querySelector("#defaultCountSelect"),
  autoExplainToggle: document.querySelector("#autoExplainToggle"),
  reduceMotionToggle: document.querySelector("#reduceMotionToggle"),
  motionIntensitySlider: document.querySelector("#motionIntensitySlider"),
  toast: document.querySelector("#toast"),
};

init();

function init() {
  applySettings();
  hydrateControls();
  bindEvents();
  renderPersonalization();
  renderDashboard();
  renderHistory();
  goToPage("home");
}

function bindEvents() {
  elements.routeButtons.forEach((button) => {
    button.addEventListener("click", () => goToPage(button.dataset.page));
  });

  elements.quizForm.addEventListener("submit", generateQuiz);
  elements.exitQuizButton.addEventListener("click", exitQuiz);
  elements.prevButton.addEventListener("click", previousQuestion);
  elements.finishQuizButton.addEventListener("click", finishQuizNow);
  elements.nextButton.addEventListener("click", nextQuestion);
  elements.retryButton.addEventListener("click", retryQuiz);
  elements.weakPracticeButton.addEventListener("click", practiceWeakAreas);
  elements.newQuizButton.addEventListener("click", () => goToPage("home"));
  elements.clearHistoryButton.addEventListener("click", clearHistory);
  elements.quickThemeButton.addEventListener("click", toggleQuickTheme);

  elements.fontSizeSlider.addEventListener("input", () => {
    state.settings.fontScale = Number(elements.fontSizeSlider.value);
    persistSettings();
  });

  elements.fontStyleSelect.addEventListener("change", () => {
    state.settings.fontStyle = elements.fontStyleSelect.value;
    persistSettings();
  });

  elements.densitySelect.addEventListener("change", () => {
    state.settings.density = elements.densitySelect.value;
    persistSettings();
  });

  elements.defaultDifficultySelect.addEventListener("change", () => {
    state.settings.defaultDifficulty = elements.defaultDifficultySelect.value;
    elements.difficultySelect.value = state.settings.defaultDifficulty;
    persistSettings();
  });

  elements.defaultCountSelect.addEventListener("change", () => {
    state.settings.defaultCount = Number(elements.defaultCountSelect.value);
    elements.countSelect.value = String(state.settings.defaultCount);
    persistSettings();
  });

  elements.autoExplainToggle.addEventListener("change", () => {
    state.settings.autoExplain = elements.autoExplainToggle.checked;
    persistSettings();
  });

  elements.reduceMotionToggle.addEventListener("change", () => {
    state.settings.reduceMotion = elements.reduceMotionToggle.checked;
    persistSettings();
  });

  elements.motionIntensitySlider.addEventListener("input", () => {
    state.settings.motionIntensity = Number(elements.motionIntensitySlider.value);
    persistSettings();
  });

  elements.themeGrid.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-theme]");
    if (!button) return;
    state.settings.theme = button.dataset.theme;
    persistSettings();
  });
}

async function generateQuiz(event) {
  event.preventDefault();
  const topic = elements.topicInput.value.trim();
  if (!topic) {
    elements.topicInput.focus();
    return;
  }

  const request = {
    topic,
    difficulty: elements.difficultySelect.value,
    question_count: Number(elements.countSelect.value),
    mode: elements.modeSelect.value,
  };

  state.lastRequest = request;
  state.quiz = null;
  state.result = null;
  state.answers = new Map();
  state.currentIndex = 0;
  setGenerating(true);
  goToPage("loading");

  try {
    const response = await fetch("/quiz/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const detail = await safeErrorDetail(response);
      throw new Error(detail || "The quiz engine could not create this quiz.");
    }

    state.quiz = await response.json();
    startQuizSession();
  } catch (error) {
    goToPage("home");
    showToast(error.message || "Quiz generation failed. Try a smaller quiz or another topic.");
  } finally {
    setGenerating(false);
  }
}

function startQuizSession() {
  state.answers = new Map();
  state.currentIndex = 0;
  state.quizStartedAt = performance.now();
  state.elapsedMs = 0;
  startTimer();
  renderQuestion();
  goToPage("quiz");
}

function renderQuestion() {
  if (!state.quiz) return;
  const question = state.quiz.questions[state.currentIndex];
  const saved = state.answers.get(question.id);
  const progress = ((state.currentIndex + 1) / state.quiz.questions.length) * 100;

  elements.progressBar.style.width = `${progress}%`;
  elements.questionCounter.textContent = `${state.currentIndex + 1}/${state.quiz.questions.length}`;
  elements.questionDifficulty.textContent = capitalize(question.difficulty);
  elements.questionSkill.textContent = capitalize(question.skill_tag);
  elements.questionText.textContent = question.question;
  elements.prevButton.disabled = state.currentIndex === 0;
  elements.nextButton.textContent =
    state.currentIndex === state.quiz.questions.length - 1 ? "Submit" : "Next";
  elements.feedbackBox.classList.add("is-hidden");
  elements.feedbackBox.textContent = "";
  elements.optionList.innerHTML = "";
  state.questionStartedAt = performance.now();

  Object.entries(question.options).forEach(([key, value]) => {
    const option = document.createElement("button");
    option.type = "button";
    option.className = "option-button";
    option.dataset.answer = key;

    const marker = document.createElement("span");
    marker.textContent = key;
    const label = document.createElement("strong");
    label.textContent = value;
    option.append(marker, label);

    if (saved?.selected_answer === key) {
      option.classList.add("is-selected");
    }

    option.addEventListener("click", () => chooseAnswer(question, key));
    elements.optionList.appendChild(option);
  });

  if (saved && shouldShowFeedback()) {
    showFeedback(question, saved.selected_answer);
  }

  preloadNextQuestion();
}

function chooseAnswer(question, selectedAnswer) {
  const elapsed = Math.max(0, Math.round(performance.now() - state.questionStartedAt));
  state.answers.set(question.id, {
    question_id: question.id,
    selected_answer: selectedAnswer,
    response_time_ms: elapsed,
  });

  elements.optionList.querySelectorAll(".option-button").forEach((button) => {
    button.classList.toggle("is-selected", button.dataset.answer === selectedAnswer);
    button.classList.remove("is-correct", "is-wrong");
  });

  if (shouldShowFeedback()) {
    showFeedback(question, selectedAnswer);
  }
}

function shouldShowFeedback() {
  return state.settings.autoExplain && elements.modeSelect.value !== "exam";
}

function showFeedback(question, selectedAnswer) {
  elements.optionList.querySelectorAll(".option-button").forEach((button) => {
    const answer = button.dataset.answer;
    button.classList.toggle("is-correct", answer === question.correct_answer);
    button.classList.toggle(
      "is-wrong",
      answer === selectedAnswer && selectedAnswer !== question.correct_answer,
    );
  });

  elements.feedbackBox.textContent = question.explanation;
  elements.feedbackBox.classList.remove("is-hidden");
}

function previousQuestion() {
  if (state.currentIndex <= 0) return;
  state.currentIndex -= 1;
  renderQuestion();
}

async function nextQuestion() {
  if (!state.quiz) return;

  if (state.currentIndex < state.quiz.questions.length - 1) {
    state.currentIndex += 1;
    renderQuestion();
    return;
  }

  await submitQuiz();
}

async function submitQuiz() {
  stopTimer();
  state.elapsedMs = Math.max(0, Math.round(performance.now() - state.quizStartedAt));

  try {
    const response = await fetch("/quiz/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        quiz: state.quiz,
        answers: Array.from(state.answers.values()),
      }),
    });

    if (!response.ok) {
      throw new Error("Result analysis failed.");
    }

    state.result = await response.json();
    saveSession();
    renderResults(state.result, state.elapsedMs);
    renderPersonalization();
    renderDashboard();
    renderHistory();
    goToPage("results");
  } catch (error) {
    showToast(error.message || "Could not evaluate this quiz.");
    startTimer();
  }
}

function renderResults(result, elapsedMs) {
  const percent = Math.round(result.accuracy_percent);
  const circumference = 365;
  const offset = circumference - (circumference * percent) / 100;
  const correct = result.score;
  const incorrect = result.total_questions - result.score;

  elements.scoreRing.style.strokeDashoffset = String(offset);
  elements.scorePercent.textContent = `${percent}%`;
  elements.masteryLevel.textContent = result.topic_mastery_level;
  elements.scoreMessage.textContent = performanceMessage(percent);
  elements.scoreLine.textContent = `${correct} of ${result.total_questions} correct`;
  elements.accuracyMetric.textContent = `${percent}%`;
  elements.timeMetric.textContent = formatTime(elapsedMs);
  elements.correctMetric.textContent = String(correct);
  elements.incorrectMetric.textContent = String(incorrect);

  renderSkillCards(result);
  renderRecommendations(elements.nextTopics, result.suggested_next_topics);
}

function renderSkillCards(result) {
  const skillStats = buildSkillStats(result.outcomes);
  elements.skillCards.innerHTML = "";

  SKILLS.forEach((skill) => {
    const stats = skillStats[skill] || { total: 0, correct: 0 };
    const accuracy = stats.total ? Math.round((stats.correct / stats.total) * 100) : 0;
    const card = document.createElement("article");
    card.className = "skill-card";
    card.innerHTML = `
      <header><span>${capitalize(skill)}</span><strong>${accuracy}%</strong></header>
      <div class="skill-bar"><span style="width: ${accuracy}%"></span></div>
      <p class="muted-line">${stats.correct}/${stats.total} correct</p>
    `;
    elements.skillCards.appendChild(card);
  });
}

function goToPage(page) {
  state.page = page;
  elements.pages.forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.pagePanel === page);
  });

  elements.navLinks.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.page === page);
  });

  if (page !== "quiz") {
    stopTimer();
  }

  if (page === "analytics") renderDashboard();
  if (page === "history") renderHistory();
}

function exitQuiz() {
  abandonActiveQuiz();
  goToPage("home");
}

async function finishQuizNow() {
  if (!state.quiz) return;
  await submitQuiz();
}

function abandonActiveQuiz() {
  stopTimer();
  state.answers = new Map();
  state.currentIndex = 0;
  state.questionStartedAt = 0;
  state.quizStartedAt = 0;
  state.elapsedMs = 0;
}

function retryQuiz() {
  if (!state.quiz) return;
  startQuizSession();
}

function practiceWeakAreas() {
  if (!state.result || !state.quiz) {
    goToPage("home");
    return;
  }

  const weak = state.result.weak_areas[0];
  const topic = weak
    ? `${state.quiz.quiz_meta.topic} ${weak.skill_tag} ${weak.difficulty}`
    : state.quiz.quiz_meta.topic;
  elements.topicInput.value = topic;
  elements.difficultySelect.value = weak?.difficulty || "mixed";
  elements.countSelect.value = "5";
  elements.modeSelect.value = "learning";
  goToPage("home");
}

function startTimer() {
  stopTimer();
  elements.quizTimer.textContent = "00:00";
  state.timerId = window.setInterval(() => {
    const elapsed = Math.max(0, performance.now() - state.quizStartedAt);
    elements.quizTimer.textContent = formatTime(elapsed);
  }, 500);
}

function stopTimer() {
  if (state.timerId) {
    window.clearInterval(state.timerId);
    state.timerId = null;
  }
}

function setGenerating(isGenerating) {
  elements.generateButton.disabled = isGenerating;
  elements.generateButton.classList.toggle("is-generating", isGenerating);
  elements.loadingText.textContent = isGenerating
    ? "Designing your assessment..."
    : "Ready";
}

function saveSession() {
  if (!state.quiz || !state.result) return;
  const session = {
    id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()),
    date: new Date().toISOString(),
    quiz: state.quiz,
    result: state.result,
    elapsedMs: state.elapsedMs,
    request: state.lastRequest,
  };

  state.history = [session, ...state.history].slice(0, 60);
  localStorage.setItem(STORAGE_KEYS.history, JSON.stringify(state.history));
}

function renderPersonalization() {
  const stats = getAggregateStats();
  elements.totalQuizzes.textContent = String(stats.total);
  elements.avgScore.textContent = `${stats.average}%`;
  elements.bestSkill.textContent = capitalize(stats.bestSkill);
  elements.streakBadge.textContent = `${stats.streak} day streak`;
  elements.readinessScore.textContent = stats.total > 0 ? `${stats.average}` : "AI";

  if (stats.total === 0) {
    elements.personalMessage.textContent = "Ready for a new session";
  } else if (stats.average >= 85) {
    elements.personalMessage.textContent = "Advanced insights unlocked";
  } else if (stats.average < 55) {
    elements.personalMessage.textContent = "Focus mode recommended";
  } else {
    elements.personalMessage.textContent = "Good momentum today";
  }
}

function renderDashboard() {
  const stats = getAggregateStats();
  elements.dashTotal.textContent = String(stats.total);
  elements.dashAverage.textContent = `${stats.average}%`;
  elements.dashTrend.textContent = `${stats.trend >= 0 ? "+" : ""}${stats.trend}%`;
  renderTrendChart();
  renderRadarChart();
  renderTopicHeatmap();
  renderTimeline();
  renderDashboardRecommendations();
}

function renderTrendChart() {
  const recent = [...state.history].reverse().slice(-8);
  const width = 420;
  const height = 120;
  const points = recent.length
    ? recent.map((session, index) => {
        const x = recent.length === 1 ? width / 2 : (index / (recent.length - 1)) * width;
        const y = height - (session.result.accuracy_percent / 100) * (height - 20) - 10;
        return `${x},${y}`;
      })
    : ["0,92", "84,74", "168,80", "252,52", "336,58", "420,36"];

  elements.trendChart.innerHTML = `
    <polyline points="${points.join(" ")}" fill="none" stroke="var(--accent)" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"></polyline>
    <line x1="0" y1="110" x2="420" y2="110" stroke="var(--line)" stroke-width="2"></line>
  `;
}

function renderRadarChart() {
  const stats = buildHistoricalSkillStats();
  const center = 130;
  const maxRadius = 92;
  const axes = SKILLS.map((skill, index) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / SKILLS.length;
    const accuracy = stats[skill]?.total
      ? stats[skill].correct / stats[skill].total
      : 0.42 + index * 0.08;
    return {
      skill,
      axisX: center + Math.cos(angle) * maxRadius,
      axisY: center + Math.sin(angle) * maxRadius,
      pointX: center + Math.cos(angle) * maxRadius * accuracy,
      pointY: center + Math.sin(angle) * maxRadius * accuracy,
      labelX: center + Math.cos(angle) * (maxRadius + 24),
      labelY: center + Math.sin(angle) * (maxRadius + 24),
    };
  });

  elements.radarChart.innerHTML = `
    <circle cx="${center}" cy="${center}" r="92" fill="none" stroke="var(--line)" stroke-width="2"></circle>
    <circle cx="${center}" cy="${center}" r="54" fill="none" stroke="var(--line)" stroke-width="1"></circle>
    ${axes.map((axis) => `<line x1="${center}" y1="${center}" x2="${axis.axisX}" y2="${axis.axisY}" stroke="var(--line)" stroke-width="1"></line>`).join("")}
    <polygon points="${axes.map((axis) => `${axis.pointX},${axis.pointY}`).join(" ")}" fill="rgba(15,118,110,0.18)" stroke="var(--accent)" stroke-width="4" stroke-linejoin="round"></polygon>
    ${axes.map((axis) => `<text x="${axis.labelX}" y="${axis.labelY}" text-anchor="middle" fill="var(--muted)" font-size="13" font-weight="800">${capitalize(axis.skill)}</text>`).join("")}
  `;
}

function renderTopicHeatmap() {
  const topics = buildTopicStats();
  elements.topicHeatmap.innerHTML = "";
  if (!topics.length) {
    ["JavaScript", "Deep Learning", "Marketing"].forEach((topic, index) => {
      topics.push({ topic, accuracy: [74, 61, 82][index], count: 0 });
    });
  }

  topics.slice(0, 9).forEach((item) => {
    const card = document.createElement("div");
    card.className = "heat-topic";
    card.innerHTML = `
      <strong>${escapeHtml(item.topic)}</strong>
      <span class="muted-line">${item.accuracy}% mastery</span>
      <div class="heat-meter"><span style="width: ${item.accuracy}%"></span></div>
    `;
    elements.topicHeatmap.appendChild(card);
  });
}

function renderTimeline() {
  elements.timeline.innerHTML = "";
  const sessions = state.history.slice(0, 5);
  if (!sessions.length) {
    elements.timeline.innerHTML = `<div class="timeline-row"><span>Today</span><strong>No sessions yet</strong><em></em></div>`;
    return;
  }

  sessions.forEach((session) => {
    const row = document.createElement("div");
    row.className = "timeline-row";
    row.innerHTML = `
      <span>${formatDate(session.date)}</span>
      <strong>${escapeHtml(session.quiz.quiz_meta.topic)}</strong>
      <span>${Math.round(session.result.accuracy_percent)}%</span>
    `;
    elements.timeline.appendChild(row);
  });
}

function renderDashboardRecommendations() {
  const latest = state.history[0];
  const recommendations = latest?.result.suggested_next_topics || [
    "Generate a diagnostic quiz",
    "Build a learning baseline",
    "Review weak skills after your first result",
  ];
  renderRecommendations(elements.dashboardRecommendations, recommendations);
}

function renderHistory() {
  elements.historyList.innerHTML = "";
  if (!state.history.length) {
    elements.historyList.innerHTML = `
      <article class="history-card">
        <div>
          <h3>No quiz sessions yet</h3>
          <div class="history-meta"><span class="tag">Your completed quizzes will appear here</span></div>
        </div>
      </article>
    `;
    return;
  }

  state.history.forEach((session) => {
    const card = document.createElement("article");
    card.className = "history-card";
    card.innerHTML = `
      <div>
        <h3>${escapeHtml(session.quiz.quiz_meta.topic)}</h3>
        <div class="history-meta">
          <span class="tag">${Math.round(session.result.accuracy_percent)}%</span>
          <span class="tag">${capitalize(session.quiz.quiz_meta.difficulty_mode)}</span>
          <span class="tag">${formatDate(session.date)}</span>
        </div>
      </div>
      <strong>${session.result.score}/${session.result.total_questions}</strong>
      <button class="secondary-button" type="button">Open</button>
    `;
    card.querySelector("button").addEventListener("click", () => openHistorySession(session.id));
    elements.historyList.appendChild(card);
  });
}

function openHistorySession(id) {
  const session = state.history.find((item) => item.id === id);
  if (!session) return;
  state.quiz = session.quiz;
  state.result = session.result;
  state.elapsedMs = session.elapsedMs;
  renderResults(session.result, session.elapsedMs);
  goToPage("results");
}

function clearHistory() {
  state.history = [];
  localStorage.removeItem(STORAGE_KEYS.history);
  renderHistory();
  renderDashboard();
  renderPersonalization();
  showToast("History cleared.");
}

function renderRecommendations(container, recommendations) {
  container.innerHTML = "";
  recommendations.forEach((topic) => {
    const tag = document.createElement("span");
    tag.textContent = topic;
    tag.addEventListener("click", () => {
      elements.topicInput.value = topic;
      elements.modeSelect.value = "learning";
      goToPage("home");
    });
    container.appendChild(tag);
  });
}

function getAggregateStats() {
  const total = state.history.length;
  const scores = state.history.map((session) => session.result.accuracy_percent);
  const average = total ? Math.round(scores.reduce((sum, value) => sum + value, 0) / total) : 0;
  const recent = scores.slice(0, 3);
  const older = scores.slice(3, 6);
  const recentAvg = recent.length
    ? recent.reduce((sum, value) => sum + value, 0) / recent.length
    : 0;
  const olderAvg = older.length
    ? older.reduce((sum, value) => sum + value, 0) / older.length
    : recentAvg;
  const skillStats = buildHistoricalSkillStats();
  const bestSkill = SKILLS.reduce((best, skill) => {
    const stats = skillStats[skill] || { total: 0, correct: 0 };
    const score = stats.total ? stats.correct / stats.total : 0;
    const bestStats = skillStats[best] || { total: 0, correct: 0 };
    const bestScore = bestStats.total ? bestStats.correct / bestStats.total : -1;
    return score > bestScore ? skill : best;
  }, "concept");

  return {
    total,
    average,
    trend: Math.round(recentAvg - olderAvg),
    bestSkill,
    streak: calculateStreak(),
  };
}

function buildSkillStats(outcomes) {
  return outcomes.reduce((acc, outcome) => {
    if (!acc[outcome.skill_tag]) {
      acc[outcome.skill_tag] = { total: 0, correct: 0 };
    }
    acc[outcome.skill_tag].total += 1;
    if (outcome.is_correct) {
      acc[outcome.skill_tag].correct += 1;
    }
    return acc;
  }, {});
}

function buildHistoricalSkillStats() {
  return state.history.reduce((acc, session) => {
    const stats = buildSkillStats(session.result.outcomes);
    Object.entries(stats).forEach(([skill, value]) => {
      if (!acc[skill]) acc[skill] = { total: 0, correct: 0 };
      acc[skill].total += value.total;
      acc[skill].correct += value.correct;
    });
    return acc;
  }, {});
}

function buildTopicStats() {
  const topicMap = new Map();
  state.history.forEach((session) => {
    const topic = session.quiz.quiz_meta.topic;
    const current = topicMap.get(topic) || { topic, total: 0, score: 0 };
    current.total += 1;
    current.score += session.result.accuracy_percent;
    topicMap.set(topic, current);
  });

  return Array.from(topicMap.values())
    .map((item) => ({
      topic: item.topic,
      count: item.total,
      accuracy: Math.round(item.score / item.total),
    }))
    .sort((a, b) => b.count - a.count || b.accuracy - a.accuracy);
}

function calculateStreak() {
  const dates = new Set(state.history.map((session) => session.date.slice(0, 10)));
  let streak = 0;
  const cursor = new Date();
  while (dates.has(cursor.toISOString().slice(0, 10))) {
    streak += 1;
    cursor.setDate(cursor.getDate() - 1);
  }
  return streak;
}

function hydrateControls() {
  elements.difficultySelect.value = state.settings.defaultDifficulty;
  elements.countSelect.value = String(state.settings.defaultCount);
  elements.fontSizeSlider.value = String(state.settings.fontScale);
  elements.fontStyleSelect.value = state.settings.fontStyle;
  elements.densitySelect.value = state.settings.density;
  elements.defaultDifficultySelect.value = state.settings.defaultDifficulty;
  elements.defaultCountSelect.value = String(state.settings.defaultCount);
  elements.autoExplainToggle.checked = state.settings.autoExplain;
  elements.reduceMotionToggle.checked = state.settings.reduceMotion;
  elements.motionIntensitySlider.value = String(state.settings.motionIntensity);
}

function applySettings() {
  elements.body.dataset.theme = state.settings.theme;
  elements.body.dataset.density = state.settings.density;
  elements.body.dataset.font = state.settings.fontStyle;
  elements.body.classList.toggle("reduce-motion", state.settings.reduceMotion);
  elements.body.style.setProperty("--font-scale", String(state.settings.fontScale / 100));
  elements.body.style.setProperty(
    "--motion-scale",
    String(Math.max(0.15, state.settings.motionIntensity / 70)),
  );

  elements.themeGrid?.querySelectorAll("button[data-theme]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.theme === state.settings.theme);
  });
}

function persistSettings() {
  applySettings();
  localStorage.setItem(STORAGE_KEYS.settings, JSON.stringify(state.settings));
}

function toggleQuickTheme() {
  state.settings.theme = state.settings.theme === "light" ? "dark" : "light";
  persistSettings();
}

function loadSettings() {
  try {
    return {
      ...DEFAULT_SETTINGS,
      ...JSON.parse(localStorage.getItem(STORAGE_KEYS.settings) || "{}"),
    };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

function loadHistory() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEYS.history) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function preloadNextQuestion() {
  if (!state.quiz) return;
  const next = state.quiz.questions[state.currentIndex + 1];
  if (!next) return;
  JSON.stringify(next.options);
}

async function safeErrorDetail(response) {
  try {
    const data = await response.json();
    return typeof data.detail === "string" ? data.detail : "";
  } catch {
    return "";
  }
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("is-visible");
  window.setTimeout(() => {
    elements.toast.classList.remove("is-visible");
  }, 3600);
}

function performanceMessage(percent) {
  if (percent >= 90) return "Excellent";
  if (percent >= 70) return "Good Progress";
  return "Needs Improvement";
}

function formatTime(ms) {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remaining).padStart(2, "0")}`;
}

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

function capitalize(value) {
  return String(value || "")
    .charAt(0)
    .toUpperCase() + String(value || "").slice(1);
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}
