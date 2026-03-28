from flask import Flask, render_template, request, redirect, send_file
import sqlite3
import qrcode
import json
from datetime import datetime
from cryptography.fernet import Fernet
import os

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)

DB_NAME = "voters.db"
QR_FOLDER = "static/qrs"
os.makedirs(QR_FOLDER, exist_ok=True)

with open("booth_secret.key", "rb") as f:
    cipher = Fernet(f.read())


def get_db():
    return sqlite3.connect(DB_NAME)


# ✅ CREATE TABLE IF NOT EXISTS
def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS voters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voter_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            qr_filename TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    db.commit()
    db.close()


@app.route("/")
def index():
    db = get_db()
    voters = db.execute(
        "SELECT voter_id, name, qr_filename FROM voters"
    ).fetchall()
    db.close()
    return render_template("index.html", voters=voters)


@app.route("/add", methods=["POST"])
def add_voter():
    voter_id = request.form["voter_id"].strip().upper()
    name = request.form["name"].strip()

    voter_data = {"voter_id": voter_id, "name": name}
    encrypted = cipher.encrypt(json.dumps(voter_data).encode())

    qr_filename = f"{voter_id}.png"
    qr_path = os.path.join(QR_FOLDER, qr_filename)
    qrcode.make(encrypted.decode()).save(qr_path)

    db = get_db()
    db.execute(
        "INSERT INTO voters (voter_id, name, qr_filename, created_at) VALUES (?, ?, ?, ?)",
        (voter_id, name, qr_filename, datetime.now().isoformat())
    )
    db.commit()
    db.close()

    return redirect("/")


@app.route("/delete/<voter_id>", methods=["POST"])
def delete_voter(voter_id):
    db = get_db()
    row = db.execute(
        "SELECT qr_filename FROM voters WHERE voter_id = ?",
        (voter_id,)
    ).fetchone()

    if row:
        qr_path = os.path.join(QR_FOLDER, row[0])
        if os.path.exists(qr_path):
            os.remove(qr_path)

        db.execute("DELETE FROM voters WHERE voter_id = ?", (voter_id,))
        db.commit()

    db.close()
    return redirect("/")


@app.route("/print_pdf")
def print_pdf():
    db = get_db()
    voters = db.execute(
        "SELECT voter_id, name, qr_filename FROM voters ORDER BY voter_id"
    ).fetchall()
    db.close()

    pdf_path = "voter_list.pdf"
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>VOTERS LIST</b>", styles["Title"]))
    elements.append(Spacer(1, 20))

    table_data = [["Voter ID", "Name", "QR Code"]]

    for v in voters:
        img = Image(os.path.join(QR_FOLDER, v[2]), width=70, height=70)
        table_data.append([v[0], v[1], img])

    table = Table(table_data, colWidths=[170, 170, 120])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold")
    ]))

    elements.append(table)

    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    doc.build(elements)

    return send_file(pdf_path, as_attachment=True)


if __name__ == "__main__":
    init_db()   # ✅ THIS WAS MISSING
    app.run(debug=True)