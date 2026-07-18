const startScreen = document.getElementById('start-screen');
const challengeRow = document.getElementById('challenge-row');
const quizForm = document.getElementById('quiz-form');
const quizLevelText = document.getElementById('quiz-level-text');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const questionsList = document.getElementById('questions-list');
const resultScreen = document.getElementById('result-screen');
const motivationText = document.getElementById('motivation-text');
const scoreText = document.getElementById('score-text');
const levelInfo = document.getElementById('level-info');
const reviewList = document.getElementById('review-list');
const nextLevelBtn = document.getElementById('next-level-btn');
const retryBtn = document.getElementById('retry-btn');
const confettiContainer = document.getElementById('confetti-container');

const MOTIVATION_PHRASES = {
  high: [
    "🔥 You're on fire!",
    '🌟 Absolutely amazing!',
    '🏆 Outstanding performance!',
    "🚀 You're unstoppable!",
    '🎯 Nailed it!',
  ],
  mid: [
    '💪 Great job!',
    '👏 Well done!',
    '✨ Impressive work!',
    '📈 Solid progress!',
    '🙌 Nice one!',
  ],
  low: [
    '🌱 Every expert was once a beginner!',
    '💡 Practice makes progress!',
    "🎯 Keep going, you've got this!",
    '📚 Learning is a journey — enjoy it!',
    '🧩 One piece at a time!',
  ],
};

const CONFETTI_COLORS = ['#6c5ce7', '#fd79a8', '#74b9ff', '#ffeaa7', '#55efc4'];
const LEVELS_ORDER = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];

let currentQuiz = [];

function renderChallengeButtons(currentLevel) {
  if (!challengeRow) return;
  const idx = LEVELS_ORDER.indexOf(currentLevel);
  const higher = idx >= 0 ? LEVELS_ORDER.slice(idx + 1) : [];

  challengeRow.innerHTML = '';
  if (higher.length === 0) return;

  const hint = document.createElement('p');
  hint.className = 'challenge-hint';
  hint.textContent = 'Feeling lucky? Skip ahead:';
  challengeRow.appendChild(hint);

  const wrap = document.createElement('div');
  wrap.className = 'challenge-buttons';
  higher.forEach(lvl => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-challenge';
    btn.dataset.startLevel = lvl;
    btn.textContent = `🍀 I'll risk it — ${lvl}`;
    wrap.appendChild(btn);
  });
  challengeRow.appendChild(wrap);
}

function pickMotivation(score) {
  const tier = score >= 8 ? 'high' : score >= 5 ? 'mid' : 'low';
  const phrases = MOTIVATION_PHRASES[tier];
  return phrases[Math.floor(Math.random() * phrases.length)];
}

function launchConfetti() {
  if (!confettiContainer) return;
  for (let i = 0; i < 40; i++) {
    const piece = document.createElement('div');
    piece.className = 'confetti-piece';
    piece.style.left = `${Math.random() * 100}%`;
    piece.style.background = CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)];
    piece.style.animationDuration = `${2 + Math.random() * 1.5}s`;
    piece.style.animationDelay = `${Math.random() * 0.4}s`;
    confettiContainer.appendChild(piece);
    setTimeout(() => piece.remove(), 4200);
  }
}

function updateProgress() {
  const total = currentQuiz.length || 10;
  const answered = currentQuiz.filter(q =>
    quizForm.querySelector(`input[name="question-${q.question_id}"]:checked`)
  ).length;
  progressFill.style.width = `${(answered / total) * 100}%`;
  progressText.textContent = `${answered} / ${total} answered`;
}

async function loadQuiz(level) {
  const url = level ? `/api/quiz?level=${encodeURIComponent(level)}` : '/api/quiz';
  const res = await fetch(url);
  if (res.status === 401) {
    window.location.href = '/login';
    return;
  }
  if (!res.ok) {
    questionsList.innerHTML = '<p>No questions have been loaded yet. Ask an admin to add some in the admin panel.</p>';
    return;
  }
  const data = await res.json();
  currentQuiz = data.questions;
  quizLevelText.textContent = `Level: ${data.level}`;
  renderQuiz();
  updateProgress();
}

function renderQuiz() {
  questionsList.innerHTML = '';
  currentQuiz.forEach((q, index) => {
    const block = document.createElement('div');
    block.className = 'question-block';

    const title = document.createElement('h3');
    title.textContent = `${index + 1}. ${q.question_text}`;
    block.appendChild(title);

    q.options.forEach(opt => {
      const optionLabel = document.createElement('label');
      optionLabel.className = 'option';

      const input = document.createElement('input');
      input.type = 'radio';
      input.name = `question-${q.question_id}`;
      input.value = opt.option_key;
      input.required = true;

      optionLabel.appendChild(input);
      optionLabel.appendChild(document.createTextNode(opt.text));
      block.appendChild(optionLabel);
    });

    questionsList.appendChild(block);
  });
}

questionsList.addEventListener('change', updateProgress);

startScreen.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-start-level]');
  if (!btn) return;
  const level = btn.dataset.startLevel || '';
  startScreen.classList.add('hidden');
  quizForm.classList.remove('hidden');
  await loadQuiz(level);
});

renderChallengeButtons(startScreen.dataset.currentLevel);

quizForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const answers = {};
  currentQuiz.forEach(q => {
    const selected = quizForm.querySelector(`input[name="question-${q.question_id}"]:checked`);
    if (selected) {
      answers[q.question_id] = selected.value;
    }
  });

  const res = await fetch('/api/quiz/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers }),
  });
  if (res.status === 401) {
    window.location.href = '/login';
    return;
  }
  const data = await res.json();
  showResult(data);
});

function showResult(data) {
  quizForm.classList.add('hidden');
  resultScreen.classList.remove('hidden');
  scoreText.textContent = `Score: ${data.score} / ${data.total}`;
  motivationText.textContent = pickMotivation(data.score);

  if (data.leveled_up) {
    levelInfo.textContent = `🎉 Level ${data.level} passed! You leveled up to ${data.next_level}.`;
    levelInfo.className = 'level-info level-up';
  } else if (data.is_max_level && data.score > 6) {
    levelInfo.textContent = `🏆 You scored ${data.score}/10 at level ${data.level} — the highest level. Great job!`;
    levelInfo.className = 'level-info level-up';
  } else {
    levelInfo.textContent = `Your English level: ${data.level}. Score 7 or more to level up next time.`;
    levelInfo.className = 'level-info';
  }

  if (data.score >= 7) {
    launchConfetti();
  }

  const newLevel = data.leveled_up ? data.next_level : data.level;
  startScreen.dataset.currentLevel = newLevel;
  renderChallengeButtons(newLevel);

  if (data.leveled_up) {
    nextLevelBtn.textContent = `Next level: ${data.next_level} ▶`;
    nextLevelBtn.dataset.level = data.next_level;
    nextLevelBtn.classList.remove('hidden');
  } else {
    nextLevelBtn.classList.add('hidden');
  }

  reviewList.innerHTML = '';
  data.results.forEach(r => {
    const q = currentQuiz.find(qq => qq.question_id === r.question_id);
    const item = document.createElement('div');
    item.className = 'review-item ' + (r.is_correct ? 'correct' : 'incorrect');
    item.textContent = `${q ? q.question_text : ''} — ${r.is_correct ? 'Correct ✔' : `Incorrect ✘ (Correct answer: ${r.correct_text})`}`;
    reviewList.appendChild(item);
  });
}

retryBtn.addEventListener('click', () => {
  resultScreen.classList.add('hidden');
  startScreen.classList.remove('hidden');
});

nextLevelBtn.addEventListener('click', async () => {
  const level = nextLevelBtn.dataset.level || '';
  resultScreen.classList.add('hidden');
  quizForm.classList.remove('hidden');
  await loadQuiz(level);
});
