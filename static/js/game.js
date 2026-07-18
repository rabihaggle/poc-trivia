const startBtn = document.getElementById('start-btn');
const startScreen = document.getElementById('start-screen');
const quizForm = document.getElementById('quiz-form');
const questionsList = document.getElementById('questions-list');
const resultScreen = document.getElementById('result-screen');
const scoreText = document.getElementById('score-text');
const reviewList = document.getElementById('review-list');
const retryBtn = document.getElementById('retry-btn');

let currentQuiz = [];

async function loadQuiz() {
  const res = await fetch('/api/quiz');
  if (!res.ok) {
    questionsList.innerHTML = '<p>No hay preguntas cargadas. Andá al panel de administración para cargar algunas.</p>';
    return;
  }
  currentQuiz = await res.json();
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
  const data = await res.json();
  showResult(data);
});

function showResult(data) {
  quizForm.classList.add('hidden');
  resultScreen.classList.remove('hidden');
  scoreText.textContent = `Puntaje: ${data.score} / ${data.total}`;

  reviewList.innerHTML = '';
  data.results.forEach(r => {
    const q = currentQuiz.find(qq => qq.question_id === r.question_id);
    const item = document.createElement('div');
    item.className = 'review-item ' + (r.is_correct ? 'correct' : 'incorrect');
    item.textContent = `${q ? q.question_text : ''} — ${r.is_correct ? 'Correcto ✔' : `Incorrecto ✘ (Correcta: ${r.correct_text})`}`;
    reviewList.appendChild(item);
  });
}

retryBtn.addEventListener('click', () => {
  resultScreen.classList.add('hidden');
  startScreen.classList.remove('hidden');
});
