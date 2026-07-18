const startBtn = document.getElementById('start-btn');
const startScreen = document.getElementById('start-screen');
const quizForm = document.getElementById('quiz-form');
const quizLevelText = document.getElementById('quiz-level-text');
const questionsList = document.getElementById('questions-list');
const resultScreen = document.getElementById('result-screen');
const scoreText = document.getElementById('score-text');
const levelInfo = document.getElementById('level-info');
const reviewList = document.getElementById('review-list');
const retryBtn = document.getElementById('retry-btn');

let currentQuiz = [];

async function loadQuiz() {
  const res = await fetch('/api/quiz');
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

startBtn.addEventListener('click', async () => {
  startScreen.classList.add('hidden');
  quizForm.classList.remove('hidden');
  await loadQuiz();
});

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
