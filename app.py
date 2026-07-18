import csv
import io
import os
import random
from functools import wraps

from authlib.integrations.flask_client import OAuth
from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.middleware.proxy_fix import ProxyFix

from database import get_db, init_db
from seed import seed

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-secret-change-me")

ADMIN_EMAILS = {
    e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()
}

oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

init_db()
seed()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            session["next"] = request.path
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def api_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return jsonify({"error": "login_required"}), 401
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            session["next"] = request.path
            return redirect(url_for("login"))
        if session["user"]["email"].lower() not in ADMIN_EMAILS:
            return render_template("forbidden.html"), 403
        return view(*args, **kwargs)

    return wrapped


@app.route("/login")
def login():
    redirect_uri = url_for("auth_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/auth/callback")
def auth_callback():
    token = google.authorize_access_token()
    user_info = token.get("userinfo")
    if not user_info:
        user_info = google.get("https://www.googleapis.com/oauth2/v3/userinfo", token=token).json()
    session["user"] = {
        "email": user_info["email"],
        "name": user_info.get("name") or user_info["email"],
    }
    next_url = session.pop("next", None) or url_for("index")
    return redirect(next_url)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ranking")
@login_required
def ranking():
    conn = get_db()
    scores = conn.execute(
        """
        SELECT email, name, score, total, played_at
        FROM attempts
        ORDER BY score DESC, played_at DESC
        LIMIT 50
        """
    ).fetchall()
    conn.close()
    return render_template("ranking.html", scores=scores)


def pick_balanced_by_level(question_rows, count=10):
    by_level = {level: [] for level in LEVELS}
    for q in question_rows:
        by_level.setdefault(q["level"], []).append(q)
    for pool in by_level.values():
        random.shuffle(pool)

    chosen = []
    level_order = list(by_level.keys())
    while len(chosen) < count and any(by_level[lvl] for lvl in level_order):
        for lvl in level_order:
            if len(chosen) >= count:
                break
            if by_level[lvl]:
                chosen.append(by_level[lvl].pop())
    return chosen


@app.route("/api/quiz")
@api_login_required
def api_quiz():
    conn = get_db()
    question_rows = conn.execute(
        """
        SELECT q.id, q.text, q.level
        FROM questions q
        JOIN correct_answers c ON c.question_id = q.id
        WHERE (SELECT COUNT(*) FROM wrong_answers w WHERE w.question_id = q.id) >= 2
        """
    ).fetchall()

    if not question_rows:
        conn.close()
        return jsonify({"error": "No hay preguntas cargadas todavía"}), 400

    chosen = pick_balanced_by_level(question_rows, count=10)

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


def resolve_option_text(conn, option_key):
    if not option_key or "-" not in option_key:
        return None
    kind, _, raw_id = option_key.partition("-")
    if not raw_id.isdigit():
        return None
    table = "correct_answers" if kind == "correct" else "wrong_answers"
    row = conn.execute(f"SELECT text FROM {table} WHERE id = ?", (int(raw_id),)).fetchone()
    return row["text"] if row else None


@app.route("/api/quiz/submit", methods=["POST"])
@api_login_required
def api_quiz_submit():
    data = request.get_json(force=True, silent=True) or {}
    answers = data.get("answers", {})

    conn = get_db()
    results = []
    score = 0
    answer_records = []
    for question_id_str, option_key in answers.items():
        question_id = int(question_id_str)
        question = conn.execute(
            "SELECT text, level FROM questions WHERE id = ?", (question_id,)
        ).fetchone()
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
        answer_records.append(
            (
                question["text"] if question else "(pregunta eliminada)",
                question["level"] if question else None,
                resolve_option_text(conn, option_key),
                correct["text"] if correct else "(sin respuesta correcta)",
                1 if is_correct else 0,
                question_id,
            )
        )

    user = session["user"]
    cur = conn.execute(
        "INSERT INTO attempts (email, name, score, total) VALUES (?, ?, ?, ?)",
        (user["email"], user["name"], score, len(answers)),
    )
    attempt_id = cur.lastrowid
    for question_text, level, selected_text, correct_text, is_correct, question_id in answer_records:
        conn.execute(
            """
            INSERT INTO attempt_answers
                (attempt_id, question_id, question_text, level, selected_text, correct_text, is_correct)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (attempt_id, question_id, question_text, level, selected_text, correct_text, is_correct),
        )
    conn.commit()
    conn.close()

    return jsonify({"score": score, "total": len(answers), "results": results})


@app.route("/admin")
@admin_required
def admin():
    conn = get_db()
    questions = conn.execute("SELECT id, text, level FROM questions ORDER BY level, id DESC").fetchall()

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
                "level": q["level"],
                "correct": correct["text"] if correct else None,
                "wrongs": wrongs,
            }
        )
    conn.close()
    return render_template("admin.html", questions=data, levels=LEVELS)


@app.route("/admin/questions", methods=["POST"])
@admin_required
def admin_create_question():
    question_text = request.form.get("question_text", "").strip()
    level = request.form.get("level", "").strip().upper()
    correct_answer = request.form.get("correct_answer", "").strip()
    wrong_answers = [w.strip() for w in request.form.getlist("wrong_answers") if w.strip()]

    if not question_text or level not in LEVELS or not correct_answer or len(wrong_answers) < 2:
        return redirect(url_for("admin"))

    conn = get_db()
    cur = conn.execute(
        "INSERT INTO questions (text, level) VALUES (?, ?)", (question_text, level)
    )
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
@admin_required
def admin_delete_question(question_id):
    conn = get_db()
    conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))


@app.route("/admin/results")
@admin_required
def admin_results():
    conn = get_db()
    users = conn.execute(
        """
        SELECT
            email,
            MAX(name) AS name,
            COUNT(*) AS attempt_count,
            MAX(score) AS best_score,
            MAX(total) AS total,
            MAX(played_at) AS last_played
        FROM attempts
        GROUP BY email
        ORDER BY last_played DESC
        """
    ).fetchall()
    conn.close()
    return render_template("admin_results.html", users=users)


@app.route("/admin/results/<string:email>")
@admin_required
def admin_user_results(email):
    conn = get_db()
    attempts = conn.execute(
        "SELECT id, name, score, total, played_at FROM attempts WHERE email = ? ORDER BY played_at DESC",
        (email,),
    ).fetchall()

    detail = []
    for a in attempts:
        answers = conn.execute(
            """
            SELECT question_text, level, selected_text, correct_text, is_correct
            FROM attempt_answers WHERE attempt_id = ? ORDER BY id
            """,
            (a["id"],),
        ).fetchall()

        counts = {}
        for ans in answers:
            lvl = ans["level"] or "?"
            counts.setdefault(lvl, {"correct": 0, "total": 0})
            counts[lvl]["total"] += 1
            if ans["is_correct"]:
                counts[lvl]["correct"] += 1
        level_summary = [
            {"level": lvl, **counts[lvl]} for lvl in LEVELS if lvl in counts
        ]

        detail.append({"attempt": a, "answers": answers, "level_summary": level_summary})

    conn.close()
    return render_template("admin_user_results.html", email=email, detail=detail)


@app.route("/admin/export")
@admin_required
def admin_export():
    email = request.args.get("email", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    granularity = "summary" if request.args.get("granularity") == "summary" else "detail"

    conditions = []
    params = []
    if email:
        conditions.append("a.email = ?")
        params.append(email)
    if date_from:
        conditions.append("a.played_at >= ?")
        params.append(f"{date_from} 00:00:00")
    if date_to:
        conditions.append("a.played_at <= ?")
        params.append(f"{date_to} 23:59:59")
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    conn = get_db()
    output = io.StringIO()
    writer = csv.writer(output)

    if granularity == "summary":
        rows = conn.execute(
            f"""
            SELECT a.email, a.name, a.score, a.total, a.played_at
            FROM attempts a
            {where_clause}
            ORDER BY a.played_at DESC
            """,
            params,
        ).fetchall()
        writer.writerow(["email", "nombre", "puntaje", "total", "fecha_hora_utc"])
        for r in rows:
            writer.writerow([r["email"], r["name"], r["score"], r["total"], r["played_at"]])
        name_part = "resumen"
    else:
        rows = conn.execute(
            f"""
            SELECT a.email, a.name, a.score AS attempt_score, a.total AS attempt_total,
                   a.played_at, aa.level, aa.question_text, aa.selected_text,
                   aa.correct_text, aa.is_correct
            FROM attempts a
            JOIN attempt_answers aa ON aa.attempt_id = a.id
            {where_clause}
            ORDER BY a.played_at DESC, aa.id
            """,
            params,
        ).fetchall()
        writer.writerow(
            [
                "email",
                "nombre",
                "fecha_hora_utc",
                "puntaje_intento",
                "total_intento",
                "nivel",
                "pregunta",
                "respuesta_elegida",
                "respuesta_correcta",
                "correcta",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    r["email"],
                    r["name"],
                    r["played_at"],
                    r["attempt_score"],
                    r["attempt_total"],
                    r["level"],
                    r["question_text"],
                    r["selected_text"],
                    r["correct_text"],
                    "si" if r["is_correct"] else "no",
                ]
            )
        name_part = "detalle"
    conn.close()

    filename = f"trivia_{name_part}"
    if email:
        filename += f"_{email.replace('@', '_at_')}"
    if date_from or date_to:
        filename += f"_{date_from or 'inicio'}_a_{date_to or 'hoy'}"
    filename += ".csv"

    csv_data = "﻿" + output.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
