from database import get_db, init_db

SAMPLE_QUESTIONS = [
    # --- A1 ---
    {
        "level": "A1",
        "text": "Choose the correct option: I ___ a student.",
        "correct": "am",
        "wrongs": ["is", "be"],
    },
    {
        "level": "A1",
        "text": "What is the plural of 'cat'?",
        "correct": "cats",
        "wrongs": ["cates", "catss"],
    },
    {
        "level": "A1",
        "text": "Choose the correct option: She ___ from Spain.",
        "correct": "is",
        "wrongs": ["are", "am"],
    },
    {
        "level": "A1",
        "text": "Complete: There ___ two books on the table.",
        "correct": "are",
        "wrongs": ["is", "be"],
    },
    {
        "level": "A1",
        "text": "Choose the correct option: ___ you like coffee?",
        "correct": "Do",
        "wrongs": ["Does", "Are"],
    },
    # --- A2 ---
    {
        "level": "A2",
        "text": "Choose the correct past tense: Yesterday, I ___ to the park.",
        "correct": "went",
        "wrongs": ["go", "goes"],
    },
    {
        "level": "A2",
        "text": "Complete: She ___ TV every evening.",
        "correct": "watches",
        "wrongs": ["watch", "watching"],
    },
    {
        "level": "A2",
        "text": "Choose the correct option: I have ___ apple.",
        "correct": "an",
        "wrongs": ["a", "the"],
    },
    {
        "level": "A2",
        "text": "What is the opposite of 'big'?",
        "correct": "small",
        "wrongs": ["large", "tall"],
    },
    {
        "level": "A2",
        "text": "Complete: He is taller ___ his brother.",
        "correct": "than",
        "wrongs": ["then", "that"],
    },
    # --- B1 ---
    {
        "level": "B1",
        "text": "Choose the correct option: If it rains, I ___ stay home.",
        "correct": "will",
        "wrongs": ["would", "had"],
    },
    {
        "level": "B1",
        "text": "Choose the correct option: She has been living here ___ 2015.",
        "correct": "since",
        "wrongs": ["for", "from"],
    },
    {
        "level": "B1",
        "text": "What does 'to give up' mean?",
        "correct": "to stop trying",
        "wrongs": ["to raise something", "to celebrate"],
    },
    {
        "level": "B1",
        "text": "Complete: This book is ___ interesting than the last one.",
        "correct": "more",
        "wrongs": ["most", "much more"],
    },
    {
        "level": "B1",
        "text": "Choose the correct option: I'm looking forward ___ you.",
        "correct": "to seeing",
        "wrongs": ["to see", "seeing"],
    },
    # --- B2 ---
    {
        "level": "B2",
        "text": "Choose the correct option: I wish I ___ more time to study.",
        "correct": "had",
        "wrongs": ["have", "would have"],
    },
    {
        "level": "B2",
        "text": "Complete: By the time we arrived, the movie ___ already started.",
        "correct": "had already",
        "wrongs": ["already", "has already"],
    },
    {
        "level": "B2",
        "text": "Choose the correct option: Despite ___ tired, she finished the race.",
        "correct": "being",
        "wrongs": ["be", "to be"],
    },
    {
        "level": "B2",
        "text": "What is a synonym for 'reluctant'?",
        "correct": "unwilling",
        "wrongs": ["eager", "confident"],
    },
    {
        "level": "B2",
        "text": "Complete: The report ___ by the manager before it was published.",
        "correct": "was reviewed",
        "wrongs": ["reviewed", "has review"],
    },
    # --- C1 ---
    {
        "level": "C1",
        "text": "Choose the correct option: Not only ___ late, but he also forgot the documents.",
        "correct": "did he arrive",
        "wrongs": ["he arrived", "he did arrive"],
    },
    {
        "level": "C1",
        "text": "Complete: Had I known about the meeting, I ___ attended.",
        "correct": "would have",
        "wrongs": ["will have", "would"],
    },
    {
        "level": "C1",
        "text": "What does 'to bite the bullet' mean?",
        "correct": "to accept something difficult",
        "wrongs": ["to eat quickly", "to argue with someone"],
    },
    {
        "level": "C1",
        "text": "Choose the correct option: It's high time you ___ your responsibilities seriously.",
        "correct": "took",
        "wrongs": ["take", "will take"],
    },
    {
        "level": "C1",
        "text": "Complete: Rarely ___ such dedication in a new employee.",
        "correct": "have I seen",
        "wrongs": ["I have seen", "I saw"],
    },
    # --- C2 ---
    {
        "level": "C2",
        "text": "Choose the correct option: ___ the storm, the event proceeded as planned.",
        "correct": "Notwithstanding",
        "wrongs": ["Despite of", "Although of"],
    },
    {
        "level": "C2",
        "text": "What is the meaning of 'ubiquitous'?",
        "correct": "present everywhere",
        "wrongs": ["very rare", "extremely large"],
    },
    {
        "level": "C2",
        "text": "Complete: ___ had she finished speaking than the audience erupted in applause.",
        "correct": "No sooner",
        "wrongs": ["No earlier", "Not before"],
    },
    {
        "level": "C2",
        "text": "Choose the correct option: The committee's decision was, to say the ___, controversial.",
        "correct": "least",
        "wrongs": ["most", "very"],
    },
    {
        "level": "C2",
        "text": "What does 'to be at loggerheads' mean?",
        "correct": "to be in strong disagreement",
        "wrongs": ["to be very tired", "to work together closely"],
    },
]


def seed():
    init_db()
    conn = get_db()
    existing = conn.execute("SELECT COUNT(*) AS c FROM questions").fetchone()["c"]
    if existing > 0:
        print(f"Ya hay {existing} preguntas cargadas. No se insertó nada.")
        conn.close()
        return

    for q in SAMPLE_QUESTIONS:
        cur = conn.execute(
            "INSERT INTO questions (text, level) VALUES (?, ?)", (q["text"], q["level"])
        )
        question_id = cur.lastrowid
        conn.execute(
            "INSERT INTO correct_answers (question_id, text) VALUES (?, ?)",
            (question_id, q["correct"]),
        )
        for w in q["wrongs"]:
            conn.execute(
                "INSERT INTO wrong_answers (question_id, text) VALUES (?, ?)", (question_id, w)
            )
    conn.commit()
    conn.close()
    print(f"Se cargaron {len(SAMPLE_QUESTIONS)} preguntas de ejemplo.")


if __name__ == "__main__":
    seed()
