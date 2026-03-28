import os
import sqlite3
from flask import Flask, jsonify, render_template, request
from collections import defaultdict

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CENTRAL_DB = os.path.join(BASE_DIR, "central_duplicates.db")


def get_central_db():
    return sqlite3.connect(CENTRAL_DB)


def init_central_db():
    db = get_central_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS duplicate_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voter_hash TEXT,
            booth TEXT,
            vote_count INTEGER,
            timestamp TEXT
        )
    """)
    db.commit()
    db.close()


def detect_booth_databases():
    return [
        f for f in os.listdir(BASE_DIR)
        if f.startswith("booth_ledger_") and f.endswith(".db")
    ]


def load_votes_from_booth(db_file):
    path = os.path.join(BASE_DIR, db_file)
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT vote_count, voter_hash, timestamp
        FROM booth_ledger
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def save_duplicate(voter_hash, booth, vote_count, timestamp):
    db = get_central_db()
    db.execute("""
        INSERT INTO duplicate_votes (voter_hash, booth, vote_count, timestamp)
        VALUES (?, ?, ?, ?)
    """, (voter_hash, booth, vote_count, timestamp))
    db.commit()
    db.close()


def detect_duplicates_and_counts():
    booth_dbs = detect_booth_databases()
    vote_map = defaultdict(list)

    total_votes = 0

    for booth_db in booth_dbs:
        booth_name = booth_db.replace(".db", "").replace("_", "-").title()
        votes = load_votes_from_booth(booth_db)

        for vote_count, voter_hash, timestamp in votes:
            total_votes += 1
            vote_map[voter_hash].append({
                "booth": booth_name,
                "vote_count": vote_count,
                "timestamp": timestamp
            })

    duplicates = []
    duplicate_count = 0

    for voter_hash, entries in vote_map.items():
        if len(entries) > 1:
            duplicate_count += len(entries) - 1
            for e in entries[1:]:
                save_duplicate(
                    voter_hash,
                    e["booth"],
                    e["vote_count"],
                    e["timestamp"]
                )
                duplicates.append({
                    "voter_hash": voter_hash,
                    "booth": e["booth"],
                    "vote_count": e["vote_count"],
                    "timestamp": e["timestamp"]
                })

    valid_votes = len(vote_map)

    return {
        "total_votes": total_votes,
        "valid_votes": valid_votes,
        "duplicate_votes": duplicate_count,
        "duplicates": duplicates
    }


def get_original_votes():
    booth_dbs = detect_booth_databases()
    vote_map = defaultdict(list)

    for booth_db in booth_dbs:
        booth_name = booth_db.replace(".db", "").replace("_", "-").title()
        votes = load_votes_from_booth(booth_db)

        for vote_count, voter_hash, timestamp in votes:
            vote_map[voter_hash].append({
                "booth": booth_name,
                "vote_count": vote_count,
                "timestamp": timestamp
            })

    original_votes = []

    for voter_hash, entries in vote_map.items():
        first_vote = entries[0]
        original_votes.append({
            "voter_hash": voter_hash,
            "booth": first_vote["booth"],
            "vote_count": first_vote["vote_count"],
            "timestamp": first_vote["timestamp"]
        })

    return original_votes


@app.route("/")
def index():
    booths = detect_booth_databases()
    booth_names = [b.replace(".db", "").replace("_", "-").title() for b in booths]
    return render_template(
        "index.html",
        booth_count=len(booths),
        booths=booth_names
    )


@app.route("/upload_booth", methods=["POST"])
def upload_booth():
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file selected"})

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"status": "error", "message": "Empty filename"})

    if not file.filename.endswith(".db"):
        return jsonify({"status": "error", "message": "Only .db files allowed"})

    save_path = os.path.join(BASE_DIR, file.filename)
    file.save(save_path)

    return jsonify({"status": "success"})


@app.route("/start_verification")
def start_verification():
    result = detect_duplicates_and_counts()
    return jsonify(result)


@app.route("/original_votes")
def original_votes():
    votes = get_original_votes()
    return render_template("original_votes.html", votes=votes)


if __name__ == "__main__":
    init_central_db()
    app.run(debug=True)