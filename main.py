import cv2
import requests
import time
import os
import sqlite3

from dotenv import load_dotenv
from datetime import datetime

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ==========================================================
# LOAD ENV VARIABLES
# ==========================================================
load_dotenv()

API_TOKEN = os.getenv("PLATE_API_TOKEN")

# ==========================================================
# DATABASE SETUP
# ==========================================================
def setup_database():

    conn = sqlite3.connect("parking_system.db")

    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS registered_vehicles(

        plate_number TEXT PRIMARY KEY,

        owner_name TEXT,

        flat_number TEXT

    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS vehicle_logs(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        plate_number TEXT,

        date TEXT,

        entry_time TEXT,

        exit_time TEXT,

        status TEXT

    )
    ''')

    conn.commit()

    conn.close()


# ==========================================================
# REGISTER RESIDENT
# ==========================================================
def register_new_resident():

    print("\n===== RESIDENT ENROLLMENT =====")

    plate = input("License Plate : ").strip().upper().replace(" ","")

    name = input("Owner Name : ").strip()

    flat = input("Flat Number : ").strip()

    conn = sqlite3.connect("parking_system.db")

    cursor = conn.cursor()

    try:

        cursor.execute('''

        INSERT INTO registered_vehicles

        VALUES(?,?,?)

        ''',(plate,name,flat))

        conn.commit()

        print("✅ Resident Registered")

    except sqlite3.IntegrityError:

        print("❌ Plate already exists")

    conn.close()


# ==========================================================
# TFIDF MATCHING
# ==========================================================
def get_closest_resident_vector(scanned_plate,cursor):

    cursor.execute("SELECT plate_number FROM registered_vehicles")

    all_plates = [row[0] for row in cursor.fetchall()]

    if not all_plates:

        return None,0

    best_match = None

    highest_similarity = 0

    for resident_plate in all_plates:

        try:

            vectorizer = TfidfVectorizer(

                analyzer='char',

                ngram_range=(2,3)

            )

            tfidf = vectorizer.fit_transform(

                [scanned_plate,resident_plate]

            ).toarray()

            similarity = cosine_similarity(

                [tfidf[0]],

                [tfidf[1]]

            )[0][0]

            if similarity > highest_similarity:

                highest_similarity = similarity

                best_match = resident_plate

        except:

            continue

    return best_match,highest_similarity


# ==========================================================
# PROCESS PLATE
# ==========================================================
def process_plate(plate_text):

    plate_text = plate_text.upper().replace(" ","")

    print("\nDetected :",plate_text)

    conn = sqlite3.connect("parking_system.db")

    cursor = conn.cursor()

    current_date = datetime.now().strftime("%Y-%m-%d")

    current_time = datetime.now().strftime("%H:%M:%S")

    # TFIDF correction

    best_match,similarity = get_closest_resident_vector(

        plate_text,

        cursor

    )

    if similarity >= 0.35:

        print("\n🤖 Similar Resident Found")

        print("Corrected :",best_match)

        print("Similarity :",round(similarity*100,1),"%")

        plate_text = best_match

    # Check whitelist

    cursor.execute(

        "SELECT * FROM registered_vehicles WHERE plate_number=?",

        (plate_text,)

    )

    resident = cursor.fetchone()

    if resident is None:

        print("\n🔴 ACCESS DENIED")

        print("Unknown Vehicle")

        conn.close()

        return

    owner = resident[1]

    flat = resident[2]

    # Check INSIDE status

    cursor.execute('''

    SELECT id

    FROM vehicle_logs

    WHERE plate_number=?

    AND status='INSIDE'

    AND exit_time IS NULL

    ''',(plate_text,))

    active = cursor.fetchone()

    if active:

        log_id = active[0]

        cursor.execute('''

        UPDATE vehicle_logs

        SET exit_time=?,

            status='OUTSIDE'

        WHERE id=?

        ''',(current_time,log_id))

        print("\n🛑 EXIT")

        print(f"Goodbye {owner}")

        print("Time :",current_time)

    else:

        cursor.execute('''

        INSERT INTO vehicle_logs(

            plate_number,

            date,

            entry_time,

            exit_time,

            status

        )

        VALUES(

            ?,?,?,NULL,'INSIDE'

        )

        ''',(plate_text,current_date,current_time))

        print("\n🟢 ENTRY")

        print(f"Welcome {owner}")

        print("Flat :",flat)

        print("Time :",current_time)

    conn.commit()

    conn.close()


# ==========================================================
# LIVE CAMERA ANPR
# ==========================================================
def start_camera():

    cap = cv2.VideoCapture(0)

    last_sent = 0

    print("\nPress Q to stop camera")

    while True:

        ret,frame = cap.read()

        if not ret:

            break

        cv2.imshow("ANPR Camera",frame)

        current_time = time.time()

        if current_time - last_sent > 5:

            cv2.imwrite("temp.jpg",frame)

            try:

                with open("temp.jpg","rb") as fp:

                    response = requests.post(

                        "https://api.platerecognizer.com/v1/plate-reader/",

                        files={"upload":fp},

                        headers={

                            "Authorization":

                            f"Token {API_TOKEN}"

                        }

                    )

                data = response.json()

                if (

                    "results" in data

                    and

                    len(data["results"]) > 0

                ):

                    plate = data["results"][0]["plate"]

                    plate = plate.upper()

                    process_plate(plate)

                else:

                    print("\n❌ No Plate Found")

            except Exception as e:

                print("\nAPI Error :",e)

            last_sent = current_time

        if cv2.waitKey(1) & 0xFF == ord('q'):

            break

    cap.release()

    cv2.destroyAllWindows()


# ==========================================================
# MAIN MENU
# ==========================================================
if __name__ == "__main__":

    setup_database()

    while True:

        print("\n========== ANPR SYSTEM ==========")

        print("1. Register Resident")

        print("2. Start Live Camera")

        print("3. Exit")

        choice = input("\nEnter choice : ")

        if choice == "1":

            register_new_resident()

        elif choice == "2":

            start_camera()

        elif choice == "3":

            break

        else:

            print("Invalid Choice")