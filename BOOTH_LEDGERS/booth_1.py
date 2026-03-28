import cv2
from pyzbar.pyzbar import decode
import hashlib
import json
from datetime import datetime
from cryptography.fernet import Fernet
import sqlite3
import pygame
import time

with open("booth_secret.key", "rb") as key_file:
    DEVICE_SECRET_KEY = key_file.read()

cipher = Fernet(DEVICE_SECRET_KEY)

DB_NAME ="../CENTRAL_VERIFICATION/booth_ledger_1.db"

def get_db():
    return sqlite3.connect(DB_NAME)

def create_ledger_table():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS booth_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vote_count INTEGER NOT NULL,
            voter_hash TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    db.commit()
    db.close()

def save_vote_to_db(vote_count, voter_hash, timestamp):
    db = get_db()
    db.execute("""
        INSERT INTO booth_ledger (vote_count, voter_hash, timestamp)
        VALUES (?, ?, ?)
    """, (vote_count, voter_hash, timestamp))
    db.commit()
    db.close()

def check_duplicate(voter_hash):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM booth_ledger WHERE voter_hash = ?
    """, (voter_hash,))
    count = cursor.fetchone()[0]
    db.close()
    return count > 0

class Block:
    def __init__(self, index, timestamp, voter_hash):
        self.index = index
        self.timestamp = timestamp
        self.voter_hash = voter_hash

class Blockchain:
    def __init__(self):
        self.chain = []
        self.create_genesis_block()

    def create_genesis_block(self):
        genesis_block = Block(
            index=0,
            timestamp=datetime.now().isoformat(),
            voter_hash="GENESIS"
        )
        self.chain.append(genesis_block)

    def get_latest_block(self):
        return self.chain[-1]

    def add_block(self, voter_hash, timestamp):
        previous_block = self.get_latest_block()
        new_block = Block(
            index=previous_block.index + 1,
            timestamp=timestamp,
            voter_hash=voter_hash
        )
        self.chain.append(new_block)
        return new_block

def hash_voter_id(voter_id):
    salt = "OBVV_SECURE_SALT"
    return hashlib.sha256((voter_id + salt).encode()).hexdigest()

def init_audio():
    pygame.mixer.init()

def play_alarm():
    pygame.mixer.music.load("syren.mpeg")
    pygame.mixer.music.play(loops=1)  # plays 3 times total

    time.sleep(3)
    pygame.mixer.music.stop()

def scan_qr_code():
    cap = cv2.VideoCapture(0)
    print("QR Scanner started. Show QR to camera (press 'q' to cancel).")

    last_data = None

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        decoded_objects = decode(frame)

        for obj in decoded_objects:
            try:
                if obj.data == last_data:
                    continue

                last_data = obj.data

                decrypted = cipher.decrypt(obj.data)
                voter_data = json.loads(decrypted.decode())

                cap.release()
                cv2.destroyAllWindows()
                return voter_data

            except Exception:
                print("Unauthorized or invalid QR")

        cv2.imshow("Scan Voter QR Code", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    return None

if __name__ == "__main__":
    create_ledger_table()
    init_audio()

    booth_blockchain = Blockchain()
    print("OBVV Polling Booth Started (Offline)")

    while True:
        print("\nPress ENTER to scan QR or type 'exit' to stop:")
        cmd = input()

        if cmd.lower() == "exit":
            break

        voter = scan_qr_code()

        if voter is None:
            print("QR scan cancelled or failed.")
            continue

        scan_timestamp = datetime.now().isoformat()
        voter_hash = hash_voter_id(voter["voter_id"])

        if check_duplicate(voter_hash):
            print("DUPLICATE VOTE DETECTED AT BOOTH LEVEL")
            play_alarm()
            continue

        new_block = booth_blockchain.add_block(voter_hash, scan_timestamp)

        save_vote_to_db(
            vote_count=new_block.index,
            voter_hash=voter_hash,
            timestamp=scan_timestamp
        )

        print("Vote recorded successfully")
        print("Vote Count :", new_block.index)
        print("Timestamp  :", scan_timestamp)

    print("\nLedger stored in SQL database:", DB_NAME)