import csv
import io
import os
import random
from collections import Counter
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
LEVEL_UP_THRESHOLD = 6  # score strictly greater than this levels the player up

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
        SELECT email, name, level, score, total, played_at
        FROM attempts
        ORDER BY score DESC, played_at DESC
        LIMIT 50
        """
    ).fetchall()
    conn.close()
    return render_template("ranking.html", scores=scores)


def get_player_level(conn, email):
    """The CEFR level the player's next quiz should be served at."""
    last = conn.execute(
        "SELECT level, score FROM attempts WHERE email = ? ORDER BY played_at DESC, id DESC LIMIT 1",
        (email,),
    ).fetchone()
    if not last or last["level"] not in LEVELS:
        return LEVELS[0]
    index = LEVELS.index(last["level"])
    if last["score"] > LEVEL_UP_THRESHOLD and index < len(LEVELS) - 1:
        return LEVELS[index + 1]
    return last["level"]


def pick_for_level(question_rows, level, count=10):
    by_level = {lvl: [] for lvl in LEVELS}
    for q in question_rows:
        by_level.setdefault(q["level"], []).append(q)
    for pool in by_level.values():
        random.shuffle(pool)

    chosen = by_level.get(level, [])[:count]

    # Fallback in case the target level doesn't have enough questions loaded yet.
    if len(chosen) < count:
        other_levels = [lvl for lvl in LEVELS if lvl != level]
        for lvl in other_levels:
            for q in by_level[lvl]:
                if len(chosen) >= count:
                    break
                chosen.append(q)
            if len(chosen) >= count:
                break

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
        return jsonify({"error": "No questions have been loaded yet"}), 400

    level = get_player_level(conn, session["user"]["email"])
    chosen = pick_for_level(question_rows, level, count=10)

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
    return jsonify({"level": level, "questions": quiz})


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
                question["text"] if question else "(question deleted)",
                question["level"] if question else None,
                resolve_option_text(conn, option_key),
                correct["text"] if correct else "(no correct answer)",
                1 if is_correct else 0,
                question_id,
            )
        )

    levels_used = [rec[1] for rec in answer_records if rec[1] in LEVELS]
    attempt_level = Counter(levels_used).most_common(1)[0][0] if levels_used else LEVELS[0]

    user = session["user"]
    cur = conn.execute(
        "INSERT INTO attempts (email, name, level, score, total) VALUES (?, ?, ?, ?, ?)",
        (user["email"], user["name"], attempt_level, score, len(answers)),
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

    level_index = LEVELS.index(attempt_level)
    leveled_up = score > LEVEL_UP_THRESHOLD and level_index < len(LEVELS) - 1
    next_level = LEVELS[level_index + 1] if leveled_up else attempt_level
    is_max_level = attempt_level == LEVELS[-1]

    return jsonify(
        {
            "score": score,
            "total": len(answers),
            "results": results,
            "level": attempt_level,
            "leveled_up": leveled_up,
            "next_level": next_level,
            "is_max_level": is_max_level,
        }
    )


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
    rows = conn.execute(
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
    users = []
    for r in rows:
        users.append({**dict(r), "current_level": get_player_level(conn, r["email"])})
    conn.close()
    return render_template("admin_results.html", users=users)


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    conn = get_db()

    total_users = conn.execute("SELECT COUNT(DISTINCT email) AS c FROM attempts").fetchone()["c"]
    total_attempts = conn.execute("SELECT COUNT(*) AS c FROM attempts").fetchone()["c"]
    total_questions = conn.execute("SELECT COUNT(*) AS c FROM questions").fetchone()["c"]
    avg_score_row = conn.execute("SELECT AVG(score) AS avg FROM attempts").fetchone()
    avg_score = round(avg_score_row["avg"], 1) if avg_score_row["avg"] is not None else None
    level_up_count = conn.execute(
        "SELECT COUNT(*) AS c FROM attempts WHERE score > ? AND level != ?",
        (LEVEL_UP_THRESHOLD, LEVELS[-1]),
    ).fetchone()["c"]

    # Attempts (games played) at each level, with the average score at that level.
    attempts_rows = conn.execute(
        "SELECT level, COUNT(*) AS count, AVG(score) AS avg_score FROM attempts GROUP BY level"
    ).fetchall()
    attempts_map = {r["level"]: r for r in attempts_rows}
    max_attempts_count = max((r["count"] for r in attempts_rows), default=0)
    attempts_by_level = []
    for lvl in LEVELS:
        r = attempts_map.get(lvl)
        count = r["count"] if r else 0
        avg = round(r["avg_score"], 1) if r and r["avg_score"] is not None else None
        attempts_by_level.append(
            {
                "level": lvl,
                "count": count,
                "avg_score": avg,
                "pct": round(count / max_attempts_count * 100) if max_attempts_count else 0,
            }
        )

    # Question bank composition per level.
    q_rows = conn.execute("SELECT level, COUNT(*) AS c FROM questions GROUP BY level").fetchall()
    q_map = {r["level"]: r["c"] for r in q_rows}
    max_q_count = max(q_map.values(), default=0)
    questions_by_level = [
        {
            "level": lvl,
            "count": q_map.get(lvl, 0),
            "pct": round(q_map.get(lvl, 0) / max_q_count * 100) if max_q_count else 0,
        }
        for lvl in LEVELS
    ]

    # Each player's current calculated level (i.e. the level their next quiz would use).
    emails = [r["email"] for r in conn.execute("SELECT DISTINCT email FROM attempts").fetchall()]
    level_counts = {lvl: 0 for lvl in LEVELS}
    for email in emails:
        level_counts[get_player_level(conn, email)] += 1
    max_user_count = max(level_counts.values(), default=0)
    users_by_level = [
        {
            "level": lvl,
            "count": level_counts[lvl],
            "pct": round(level_counts[lvl] / max_user_count * 100) if max_user_count else 0,
        }
        for lvl in LEVELS
    ]

    recent_attempts = conn.execute(
        """
        SELECT email, name, level, score, total, played_at
        FROM attempts ORDER BY played_at DESC, id DESC LIMIT 20
        """
    ).fetchall()

    conn.close()
    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_attempts=total_attempts,
        total_questions=total_questions,
        avg_score=avg_score,
        level_up_count=level_up_count,
        attempts_by_level=attempts_by_level,
        questions_by_level=questions_by_level,
        users_by_level=users_by_level,
        recent_attempts=recent_attempts,
    )


@app.route("/admin/results/<string:email>")
@admin_required
def admin_user_results(email):
    conn = get_db()
    attempts = conn.execute(
        "SELECT id, name, level, score, total, played_at FROM attempts WHERE email = ? ORDER BY played_at DESC",
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
            SELECT a.email, a.name, a.level, a.score, a.total, a.played_at
            FROM attempts a
            {where_clause}
            ORDER BY a.played_at DESC
            """,
            params,
        ).fetchall()
        writer.writerow(["email", "name", "level", "score", "total", "played_at_utc"])
        for r in rows:
            writer.writerow(
                [r["email"], r["name"], r["level"], r["score"], r["total"], r["played_at"]]
            )
        name_part = "summary"
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
                "name",
                "played_at_utc",
                "attempt_score",
                "attempt_total",
                "level",
                "question",
                "selected_answer",
                "correct_answer",
                "is_correct",
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
                    "yes" if r["is_correct"] else "no",
                ]
            )
        name_part = "detail"
    conn.close()

    filename = f"trivia_{name_part}"
    if email:
        filename += f"_{email.replace('@', '_at_')}"
    if date_from or date_to:
        filename += f"_{date_from or 'start'}_to_{date_to or 'now'}"
    filename += ".csv"

    csv_data = "﻿" + output.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
