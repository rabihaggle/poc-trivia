from database import get_db, init_db

SAMPLE_QUESTIONS = [
    {
        "text": "¿Cuál es la capital de Francia?",
        "correct": "París",
        "wrongs": ["Madrid", "Berlín", "Roma"],
    },
    {
        "text": "¿Cuántos planetas tiene el sistema solar?",
        "correct": "8",
        "wrongs": ["9", "7", "10"],
    },
    {
        "text": "¿Quién pintó la Mona Lisa?",
        "correct": "Leonardo da Vinci",
        "wrongs": ["Pablo Picasso", "Vincent van Gogh", "Miguel Ángel"],
    },
    {
        "text": "¿Cuál es el río más largo del mundo?",
        "correct": "Amazonas",
        "wrongs": ["Nilo", "Misisipi", "Yangtsé"],
    },
    {
        "text": "¿En qué año llegó el ser humano a la Luna por primera vez?",
        "correct": "1969",
        "wrongs": ["1965", "1971", "1975"],
    },
    {
        "text": "¿Cuál es el idioma más hablado del mundo como lengua materna?",
        "correct": "Chino mandarín",
        "wrongs": ["Inglés", "Español", "Hindi"],
    },
    {
        "text": "¿Cuál es el metal líquido a temperatura ambiente?",
        "correct": "Mercurio",
        "wrongs": ["Hierro", "Plomo", "Aluminio"],
    },
    {
        "text": "¿Cuántos lados tiene un hexágono?",
        "correct": "6",
        "wrongs": ["5", "7", "8"],
    },
    {
        "text": "¿Qué gas respiramos principalmente para vivir?",
        "correct": "Oxígeno",
        "wrongs": ["Dióxido de carbono", "Nitrógeno", "Hidrógeno"],
    },
    {
        "text": "¿Quién escribió 'Cien años de soledad'?",
        "correct": "Gabriel García Márquez",
        "wrongs": ["Mario Vargas Llosa", "Jorge Luis Borges", "Pablo Neruda"],
    },
    {
        "text": "¿Cuál es el país más grande del mundo por superficie?",
        "correct": "Rusia",
        "wrongs": ["Canadá", "China", "Estados Unidos"],
    },
    {
        "text": "¿Cuál es el hueso más largo del cuerpo humano?",
        "correct": "Fémur",
        "wrongs": ["Tibia", "Húmero", "Radio"],
    },
    {
        "text": "¿En qué continente está Egipto?",
        "correct": "África",
        "wrongs": ["Asia", "Europa", "Oceanía"],
    },
    {
        "text": "¿Cuál es el océano más grande del mundo?",
        "correct": "Pacífico",
        "wrongs": ["Atlántico", "Índico", "Ártico"],
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
        cur = conn.execute("INSERT INTO questions (text) VALUES (?)", (q["text"],))
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
