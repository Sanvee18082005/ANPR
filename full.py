import cv2
import easyocr
import numpy as np
import sqlite3
from datetime import datetime
from ultralytics import YOLO
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Initialize engines globally
print("📦 Loading YOLO Neural Network...")
yolo_model = YOLO("yolov8n.pt")

print("🔤 Loading OCR Engine...")
reader = easyocr.Reader(['en'])

# =====================================================================
# STEP 1: CLEAN RESIDENT DATABASE SETUP
# =====================================================================
def setup_database():
    conn = sqlite3.connect('parking_system.db')
    cursor = conn.cursor()
    # Table 1: Authorized Whitelist Profiles
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registered_vehicles (
            plate_number TEXT PRIMARY KEY,
            owner_name TEXT,
            flat_number TEXT
        )
    ''')
    # Table 2: In-and-Out Traffic History Ledger
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicle_logs (
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

# =====================================================================
# STEP 2: FEEDING RESIDENT DATA PORTAL
# =====================================================================
def register_new_resident():
    print("\n--- 📝 RESIDENT ENROLLMENT PORTAL ---")
    plate = input("Enter License Plate (e.g., DL7CQ1939): ").strip().upper().replace(" ", "")
    name = input("Enter Owner Name: ").strip()
    flat = input("Enter Flat Number: ").strip()
    
    conn = sqlite3.connect('parking_system.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO registered_vehicles (plate_number, owner_name, flat_number)
            VALUES (?, ?, ?)
        ''', (plate, name, flat))
        conn.commit()
        print(f"🎉 Success: Registered {name} ({flat}) -> [Whitelist Plate: {plate}]")
    except sqlite3.IntegrityError:
        print("❌ Error: This plate number is already in the resident registry.")
    conn.close()

# =====================================================================
# STEP 3: EMBEDDING MATRIX COUPLING (RECOGNITION SAFETY NET)
# =====================================================================
def get_closest_resident_vector(scanned_plate, cursor):
    cursor.execute("SELECT plate_number FROM registered_vehicles")
    all_plates = [row[0] for row in cursor.fetchall()]
    
    if not all_plates or scanned_plate == "UNKNOWN":
        return None, 0.0
        
    best_match = None
    highest_similarity = 0.0
    
    for resident_plate in all_plates:
        vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(2, 3))
        try:
            tfidf_matrix = vectorizer.fit_transform([scanned_plate, resident_plate]).toarray()
            similarity = cosine_similarity([tfidf_matrix[0]], [tfidf_matrix[1]])[0][0]
            if similarity > highest_similarity:
                highest_similarity = similarity
                best_match = resident_plate
        except Exception:
            continue
            
    return best_match, highest_similarity

# =====================================================================
# STEP 4: AUTOMATED RESIDENT ONLY GATEWAY check IN/OUT
# =====================================================================
"""def process_gate_image(image_filename):
    img = cv2.imread(image_filename)
    if img is None:
        print(f"❌ Error: Could not find image '{image_filename}'. Check spelling.")
        return

    # YOLO boundary box targeting
    results = yolo_model.predict(img, verbose=False)
    cropped_image = None
    
    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            h, w, _ = img.shape
            pad = 6
            crop_y1, crop_y2 = max(0, y1-pad), min(h, y2+pad)
            crop_x1, crop_x2 = max(0, x1-pad), min(w, x2+pad)
            cropped_image = img[crop_y1:crop_y2, crop_x1:crop_x2]
            break

    if cropped_image is None:
        print("❌ YOLO failed to find any plate shapes on the vehicle body structure.")
        return

    # Image normalization and enhancement
    gray_crop = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2GRAY)
    resized_crop = cv2.resize(gray_crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    clean_crop = cv2.adaptiveThreshold(resized_crop, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    cv2.imwrite('debug_crop.jpg', clean_crop)
    
    # OCR character pull
    ocr_result = reader.readtext(clean_crop)
    if not ocr_result:
        plate_text = "UNKNOWN"
    else:
        raw_text = "".join(ocr_result[0][-2].split()).upper()
        plate_text = "".join(char for char in raw_text if char.isalnum())"""
    
        
    print("\n" + "="*50)
    print(f"🔍 AI RAW SCAN STRING OUTPUT (CLEANED): {plate_text}")
    print("="*50)

    conn = sqlite3.connect('parking_system.db')
    cursor = conn.cursor()
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M:%S")
    
    # Run spatial embedding mismatch checker
    best_plate_match, similarity_score = get_closest_resident_vector(plate_text, cursor)
    
    if similarity_score >= 0.35: 
        print(f"🤖 [Vector Embedding Match Found!]")
        print(f"   -> Remapped '{plate_text}' to Whitelisted Resident: '{best_plate_match}'")
        print(f"   -> Vector Similarity Confidence: {similarity_score*100:.1f}%")
        plate_text = best_plate_match

    # Verify if the vehicle exists in our whitelisted profiles
    cursor.execute("SELECT * FROM registered_vehicles WHERE plate_number = ?", (plate_text,))
    resident = cursor.fetchone()
    
    if resident is None:
        # --------- VEHICLE SECURE LOCK UNKNOWN DISMISSAL ---------
        print(f"🔴 ACCESS DENIED! Plate '{plate_text}' is not registered as a resident.")
        print("💬 Action: Keep Boom Barrier CLOSED. Direct driver to turn around or use external parking.")
    else:
        owner_name, flat_num = resident[1], resident[2]
        
        # Check if this resident is currently checked inside the complex
        cursor.execute('''
            SELECT id FROM vehicle_logs 
            WHERE plate_number = ? AND exit_time IS NULL AND status = 'INSIDE'
        ''', (plate_text,))
        active_session = cursor.fetchone()
        
        if active_session is not None:
            # --------- RESIDENT EXIT TIMING SEGMENT ---------
            log_id = active_session[0]
            cursor.execute('''
                UPDATE vehicle_logs 
                SET exit_time = ?, status = 'OUTSIDE' 
                WHERE id = ?
            ''', (current_time, log_id))
            print(f"🛑 ACCESS GRANTED (RESIDENT EXIT) - Goodbye {owner_name}!")
            print(f"⏱️ Exit Logged at: {current_time}.")
        else:
            # --------- RESIDENT ENTRY TIMING SEGMENT ---------
            cursor.execute('''
                INSERT INTO vehicle_logs (plate_number, date, entry_time, exit_time, status)
                VALUES (?, ?, ?, NULL, 'INSIDE')
            ''', (plate_text, current_date, current_time))
            print(f"🟢 ACCESS GRANTED (RESIDENT ENTRY) - Welcome home {owner_name} ({flat_num})!")
            print(f"⏱️ Entry Logged at: {current_time}.")

    conn.commit()
    conn.close()
    print("="*50 + "\n>>> Security check transactions completed.")

# =====================================================================
# STEP 5: RUNTIME MAIN HUB LOOP
# =====================================================================
if __name__ == "__main__":
    setup_database()
    while True:
        print("\n=== 🏛️ MYGATE RESIDENT-ONLY ACCESS SYSTEM ===")
        print("1. Feed Resident Whitelist Data (Enrollment)")
        print("2. Scan Vehicle Image at Main Gate (ANPR Check)")
        print("3. Exit Program")
        
        choice = input("Select an option (1/2/3): ").strip()
        if choice == '1':
            register_new_resident()
        elif choice == '2':
            img_input = input("\nEnter image filename to scan (e.g., car1.jpg): ").strip()
            process_gate_image(img_input)
        elif choice == '3':
            print("System shutting down cleanly. Goodbye!")
            break