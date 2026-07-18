import os
import random

from flask import Flask, jsonify, redirect, render_template, request, url_for

from database import get_db, init_db
from seed import seed

app = Flask(__name__)

init_db()
seed()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/quiz")
def api_quiz():
    conn = get_db()
    question_rows = conn.execute(
        """
        SELECT q.id, q.text
        FROM questions q
        JOIN correct_answers c ON c.question_id = q.id
        WHERE (SELECT COUNT(*) FROM wrong_answers w WHERE w.question_id = q.id) >= 2
        """
    ).fetchall()

    if not question_rows:
        conn.close()
        return jsonify({"error": "No hay preguntas cargadas todavía"}), 400

    chosen = random.sample(question_rows, k=min(10, len(question_rows)))

    quiz = []
    for q in chosen:
        correct = conn.execute(
            "SELECT id, text FROM correct_answers WHERE question_id = ?", (q["id"],)
        ).fetchone()
        wrongs = conn.execute(
            "SELECT id, text FROM wrong_answers WHERE question_id = ?", (q["id"],)
        ).fetchall()
        wrong_sample = random.sample(wrongs, k=2)

        options = [{"option_key": f"correct-{correct['id']}", "text": correct["text"]}]
        options += [{"option_key": f"wrong-{w['id']}", "text": w["text"]} for w in wrong_sample]
        random.shuffle(options)

        quiz.append(
            {
                "question_id": q["id"],
                "question_text": q["text"],
                "options": options,
            }
        )

    conn.close()
    return jsonify(quiz)


@app.route("/api/quiz/submit", methods=["POST"])
def api_quiz_submit():
    data = request.get_json(force=True, silent=True) or {}
    answers = data.get("answers", {})

    conn = get_db()
    results = []
    score = 0
    for question_id_str, option_key in answers.items():
        question_id = int(question_id_str)
        correct = conn.execute(
            "SELECT id, text FROM correct_answers WHERE question_id = ?", (question_id,)
        ).fetchone()
        is_correct = bool(correct) and option_key == f"correct-{correct['id']}"
        if is_correct:
            score += 1
        results.append(
            {
                "question_id": question_id,
                "is_correct": is_correct,
                "correct_text": correct["text"] if correct else None,
            }
        )
    conn.close()

    return jsonify({"score": score, "total": len(answers), "results": results})


@app.route("/admin")
def admin():
    conn = get_db()
    questions = conn.execute("SELECT id, text FROM questions ORDER BY id DESC").fetchall()

    data = []
    for q in questions:
        correct = conn.execute(
            "SELECT text FROM correct_answers WHERE question_id = ?", (q["id"],)
        ).fetchone()
        wrongs = conn.execute(
            "SELECT id, text FROM wrong_answers WHERE question_id = ?", (q["id"],)
        ).fetchall()
        data.append(
            {
                "id": q["id"],
                "text": q["text"],
                "correct": correct["text"] if correct else None,
                "wrongs": wrongs,
            }
        )
    conn.close()
    return render_template("admin.html", questions=data)


@app.route("/admin/questions", methods=["POST"])
def admin_create_question():
    question_text = request.form.get("question_text", "").strip()
    correct_answer = request.form.get("correct_answer", "").strip()
    wrong_answers = [w.strip() for w in request.form.getlist("wrong_answers") if w.strip()]

    if not question_text or not correct_answer or len(wrong_answers) < 2:
        return redirect(url_for("admin"))

    conn = get_db()
    cur = conn.execute("INSERT INTO questions (text) VALUES (?)", (question_text,))
    question_id = cur.lastrowid
    conn.execute(
        "INSERT INTO correct_answers (question_id, text) VALUES (?, ?)",
        (question_id, correct_answer),
    )
    for w in wrong_answers:
        conn.execute(
            "INSERT INTO wrong_answers (question_id, text) VALUES (?, ?)", (question_id, w)
        )
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))


@app.route("/admin/questions/<int:question_id>/delete", methods=["POST"])
def admin_delete_question(question_id):
    conn = get_db()
    conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
