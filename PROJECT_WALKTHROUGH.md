# 🚀 MedVoice Project Walkthrough Sequence

This document benchmarks the standard flow to demonstrate the interconnected system to a reviewer.

## 🎬 Phase 1: Onboarding (The Setup)
**Goal:** Show that the system is personalized and doctor-driven.

1.  **Start the System:** Open `http://127.0.0.1:8000`.
2.  **Navigation:** Click the **📝 Registration** card (Center/Orange).
3.  **Action:**
    *   Enter Patient Name: **"Alex Demo"**.
    *   Enter Condition: **"Visual Impairment & Diabetes"**.
    *   **Add Medicine 1:**
        *   Name: `Paracetamol`
        *   Dosage: `1`
        *   Stock: `5` (Low stock to trigger alerts later)
        *   Schedule: `Morning (9 AM)` (or pick a time passed already to trigger missed dose).
    *   **Add Medicine 2:**
        *   Name: `Metformin`
        *   Stock: `30`
        *   Schedule: `Evening (7 PM)`.
4.  **Submit:** Click **"Save & Initialize"**.
    *   *Observation:* You are redirected to the **Patient Assistant**.

---

## 🗣️ Phase 2: Patient Interaction (Voice Loop)
**Goal:** Demonstrate independence for the visually impaired user.

1.  **Landing:** You are now on the **Patient Portal**.
2.  **Voice Query (Knowledge):**
    *   Tap 🎤 and say: **"What is Metformin used for?"**
    *   *System Response:* "Metformin is the first-line medication for type 2 diabetes..." (Demonstrates Medical Knowledge Base).
3.  **Voice Query (Stock):**
    *   Tap 🎤 and say: **"How many Paracetamol do I have left?"**
    *   *System Response:* "Paracetamol: 5" (Verifies Setup Data).
4.  **Voice Action (Intake):**
    *   Tap 🎤 and say: **"I am taking Paracetamol"**.
    *   *System Response:* "Confirmed... Warning: You have low stock..." (Demonstrates Logic + Refill Prediction).
5.  **Voice Action (Vision):**
    *   Tap 🎤 and say: **"What is this?"** (Hold up an object).
    *   *System Response:* "I see a bottle of..." (Demonstrates Camera Integration).

---

Build a production-ready feature for an existing Flask-based project called **MedVoice (Voice-Based Medicine Management System)**.

## 🎯 FEATURE NAME

"Camera-Based Medicine Verification Module using OCR"

---

## 🧠 OBJECTIVE

Implement a camera-based OCR system that:

1. Captures an image of a medicine strip or bottle from the frontend
2. Extracts text using OCR
3. Matches detected medicine names with the patient's prescription stored in SQLite
4. Allows or blocks medicine intake based on validation
5. Returns a voice-friendly response

---

## ⚠️ IMPORTANT CONSTRAINTS

* DO NOT modify existing chatbot module
* DO NOT break voice assistant flow
* Keep this module isolated as a separate service file
* Must integrate via REST API only
* Maintain modular architecture

---

## 🏗️ BACKEND REQUIREMENTS (Flask)

### 📁 Create new file:

medicine_vision.py

---

## 📦 REQUIRED LIBRARIES

* opencv-python
* pytesseract
* easyocr (preferred for better accuracy)
* fuzzywuzzy
* python-Levenshtein
* pillow

---

## 🔍 OCR PIPELINE

### Step 1: Image Preprocessing (OpenCV)

* Convert to grayscale
* Apply Gaussian blur
* Apply thresholding (Otsu)
* Optional: edge detection for clarity

---

### Step 2: OCR Extraction

Use EasyOCR primarily, fallback to Tesseract if needed.

---

### Step 3: Text Cleaning

* Remove special characters
* Normalize to lowercase
* Tokenize words

---

### Step 4: Medicine Matching

* Fetch medicine names from SQLite database
* Use fuzzy matching (threshold ≥ 80)
* Support partial matches (e.g., “paracetamol 500”)

---

### Step 5: Validation Logic

IF detected medicine exists in patient's prescription:
→ status = "allowed"
→ message = "This medicine is prescribed. You can take it."
ELSE:
→ status = "blocked"
→ message = "This medicine is NOT prescribed. Do not take it."

---

## 🔌 API ENDPOINT

POST /api/scan-medicine

### Input:

* multipart/form-data
* image file

### Output JSON:

{
"status": "allowed | blocked | unknown",
"medicine": "detected_name",
"confidence": 0-100,
"message": "voice-friendly response"
}

---

## 🧾 DATABASE INTEGRATION

Use existing SQLite database.

Query:

* Get medicines where user_id = current patient

Return:

* List of medicine names

---

## 🎤 FRONTEND REQUIREMENTS (JavaScript)

* Add camera capture button
* Use getUserMedia API
* Capture frame and send to backend via fetch()

---

### Example Flow:

1. User clicks "Scan Medicine"
2. Camera opens
3. Capture image
4. Send POST request to /api/scan-medicine
5. Receive response
6. Use SpeechSynthesis to speak response

---

## 🛡️ ERROR HANDLING

Handle:

* No text detected → "I couldn't read the medicine. Please try again."
* Low confidence → ask user to retake image
* Multiple matches → pick highest score
* Blurry image → detect via variance and warn user

---

## ⚡ PERFORMANCE REQUIREMENTS

* Response time < 2 seconds
* Optimize OCR pipeline
* Avoid blocking main thread

---

## 🔒 SAFETY LOGIC (CRITICAL)

* NEVER allow unknown medicine
* Default fallback = BLOCKED
* Add warning tone in response

---

## 🧱 PROJECT STRUCTURE

/app.py
/medicine_vision.py   ← new module
/models.py
/templates/
/static/

---

## 🔗 INTEGRATION

* Import and register blueprint in app.py
* Keep routes separate
* No changes to chatbot.py

---

## 🧪 TEST CASES

1. Scan "Paracetamol" → Allowed
2. Scan unknown medicine → Blocked
3. Scan blurry image → Retry prompt
4. Scan multiple strips → Pick best match

---

## 🚀 BONUS (if possible)

* Add confidence score display
* Store scan logs in DB
* Add bounding box visualization for detected text

---

## 📢 FINAL EXPECTATION

Generate:

* Fully working Flask backend code
* Frontend JS for camera capture
* Clean modular structure
* Comments explaining key parts

Ensure code is clean, production-ready, and easy to integrate into an existing MedVoice system.
Build a production-ready feature for an existing Flask-based project called **MedVoice (Voice-Based Medicine Management System)**.

## 🎯 FEATURE NAME

"Camera-Based Medicine Verification Module using OCR"

---

## 🧠 OBJECTIVE

Implement a camera-based OCR system that:

1. Captures an image of a medicine strip or bottle from the frontend
2. Extracts text using OCR
3. Matches detected medicine names with the patient's prescription stored in SQLite
4. Allows or blocks medicine intake based on validation
5. Returns a voice-friendly response

---

## ⚠️ IMPORTANT CONSTRAINTS

* DO NOT modify existing chatbot module
* DO NOT break voice assistant flow
* Keep this module isolated as a separate service file
* Must integrate via REST API only
* Maintain modular architecture

---

## 🏗️ BACKEND REQUIREMENTS (Flask)

### 📁 Create new file:

medicine_vision.py

---

## 📦 REQUIRED LIBRARIES

* opencv-python
* pytesseract
* easyocr (preferred for better accuracy)
* fuzzywuzzy
* python-Levenshtein
* pillow

---

## 🔍 OCR PIPELINE

### Step 1: Image Preprocessing (OpenCV)

* Convert to grayscale
* Apply Gaussian blur
* Apply thresholding (Otsu)
* Optional: edge detection for clarity

---

### Step 2: OCR Extraction

Use EasyOCR primarily, fallback to Tesseract if needed.

---

### Step 3: Text Cleaning

* Remove special characters
* Normalize to lowercase
* Tokenize words

---

### Step 4: Medicine Matching

* Fetch medicine names from SQLite database
* Use fuzzy matching (threshold ≥ 80)
* Support partial matches (e.g., “paracetamol 500”)

---

### Step 5: Validation Logic

IF detected medicine exists in patient's prescription:
→ status = "allowed"
→ message = "This medicine is prescribed. You can take it."
ELSE:
→ status = "blocked"
→ message = "This medicine is NOT prescribed. Do not take it."

---

## 🔌 API ENDPOINT

POST /api/scan-medicine

### Input:

* multipart/form-data
* image file

### Output JSON:

{
"status": "allowed | blocked | unknown",
"medicine": "detected_name",
"confidence": 0-100,
"message": "voice-friendly response"
}

---

## 🧾 DATABASE INTEGRATION

Use existing SQLite database.

Query:

* Get medicines where user_id = current patient

Return:

* List of medicine names

---

## 🎤 FRONTEND REQUIREMENTS (JavaScript)

* Add camera capture button
* Use getUserMedia API
* Capture frame and send to backend via fetch()

---

### Example Flow:

1. User clicks "Scan Medicine"
2. Camera opens
3. Capture image
4. Send POST request to /api/scan-medicine
5. Receive response
6. Use SpeechSynthesis to speak response

---

## 🛡️ ERROR HANDLING

Handle:

* No text detected → "I couldn't read the medicine. Please try again."
* Low confidence → ask user to retake image
* Multiple matches → pick highest score
* Blurry image → detect via variance and warn user

---

## ⚡ PERFORMANCE REQUIREMENTS

* Response time < 2 seconds
* Optimize OCR pipeline
* Avoid blocking main thread

---

## 🔒 SAFETY LOGIC (CRITICAL)

* NEVER allow unknown medicine
* Default fallback = BLOCKED
* Add warning tone in response

---

## 🧱 PROJECT STRUCTURE

/app.py
/medicine_vision.py   ← new module
/models.py
/templates/
/static/

---

## 🔗 INTEGRATION

* Import and register blueprint in app.py
* Keep routes separate
* No changes to chatbot.py

---

## 🧪 TEST CASES

1. Scan "Paracetamol" → Allowed
2. Scan unknown medicine → Blocked
3. Scan blurry image → Retry prompt
4. Scan multiple strips → Pick best match

---

## 🚀 BONUS (if possible)

* Add confidence score display
* Store scan logs in DB
* Add bounding box visualization for detected text

---

## 📢 FINAL EXPECTATION

Generate:

* Fully working Flask backend code
* Frontend JS for camera capture
* Clean modular structure
* Comments explaining key parts

Ensure code is clean, production-ready, and easy to integrate into an existing MedVoice system.
Build a production-ready feature for an existing Flask-based project called **MedVoice (Voice-Based Medicine Management System)**.

## 🎯 FEATURE NAME

"Camera-Based Medicine Verification Module using OCR"

---

## 🧠 OBJECTIVE

Implement a camera-based OCR system that:

1. Captures an image of a medicine strip or bottle from the frontend
2. Extracts text using OCR
3. Matches detected medicine names with the patient's prescription stored in SQLite
4. Allows or blocks medicine intake based on validation
5. Returns a voice-friendly response

---

## ⚠️ IMPORTANT CONSTRAINTS

* DO NOT modify existing chatbot module
* DO NOT break voice assistant flow
* Keep this module isolated as a separate service file
* Must integrate via REST API only
* Maintain modular architecture

---

## 🏗️ BACKEND REQUIREMENTS (Flask)

### 📁 Create new file:

medicine_vision.py

---

## 📦 REQUIRED LIBRARIES

* opencv-python
* pytesseract
* easyocr (preferred for better accuracy)
* fuzzywuzzy
* python-Levenshtein
* pillow

---

## 🔍 OCR PIPELINE

### Step 1: Image Preprocessing (OpenCV)

* Convert to grayscale
* Apply Gaussian blur
* Apply thresholding (Otsu)
* Optional: edge detection for clarity

---

### Step 2: OCR Extraction

Use EasyOCR primarily, fallback to Tesseract if needed.

---

### Step 3: Text Cleaning

* Remove special characters
* Normalize to lowercase
* Tokenize words

---

### Step 4: Medicine Matching

* Fetch medicine names from SQLite database
* Use fuzzy matching (threshold ≥ 80)
* Support partial matches (e.g., “paracetamol 500”)

---

### Step 5: Validation Logic

IF detected medicine exists in patient's prescription:
→ status = "allowed"
→ message = "This medicine is prescribed. You can take it."
ELSE:
→ status = "blocked"
→ message = "This medicine is NOT prescribed. Do not take it."

---

## 🔌 API ENDPOINT

POST /api/scan-medicine

### Input:

* multipart/form-data
* image file

### Output JSON:

{
"status": "allowed | blocked | unknown",
"medicine": "detected_name",
"confidence": 0-100,
"message": "voice-friendly response"
}

---

## 🧾 DATABASE INTEGRATION

Use existing SQLite database.

Query:

* Get medicines where user_id = current patient

Return:

* List of medicine names

---

## 🎤 FRONTEND REQUIREMENTS (JavaScript)

* Add camera capture button
* Use getUserMedia API
* Capture frame and send to backend via fetch()

---

### Example Flow:

1. User clicks "Scan Medicine"
2. Camera opens
3. Capture image
4. Send POST request to /api/scan-medicine
5. Receive response
6. Use SpeechSynthesis to speak response

---

## 🛡️ ERROR HANDLING

Handle:

* No text detected → "I couldn't read the medicine. Please try again."
* Low confidence → ask user to retake image
* Multiple matches → pick highest score
* Blurry image → detect via variance and warn user

---

## ⚡ PERFORMANCE REQUIREMENTS

* Response time < 2 seconds
* Optimize OCR pipeline
* Avoid blocking main thread

---

## 🔒 SAFETY LOGIC (CRITICAL)

* NEVER allow unknown medicine
* Default fallback = BLOCKED
* Add warning tone in response

---

## 🧱 PROJECT STRUCTURE

/app.py
/medicine_vision.py   ← new module
/models.py
/templates/
/static/

---

## 🔗 INTEGRATION

* Import and register blueprint in app.py
* Keep routes separate
* No changes to chatbot.py

---

## 🧪 TEST CASES

1. Scan "Paracetamol" → Allowed
2. Scan unknown medicine → Blocked
3. Scan blurry image → Retry prompt
4. Scan multiple strips → Pick best match

---

## 🚀 BONUS (if possible)

* Add confidence score display
* Store scan logs in DB
* Add bounding box visualization for detected text

---

## 📢 FINAL EXPECTATION

Generate:

* Fully working Flask backend code
* Frontend JS for camera capture
* Clean modular structure
* Comments explaining key parts

Ensure code is clean, production-ready, and easy to integrate into an existing MedVoice system.
## 📊 Phase 3: Health Status Monitoring (Dashboard)
**Goal:** Visualize adherence and health data.

1.  **Navigation:** Go back to Home (`/`) -> Click **📊 Health Status Dashboard**.
2.  **Observation:**
    *   **Patient Profile**: See the name and condition ("Diabetes", etc.) at the top.
    *   **Adherence Progress**: Watch the **Progress Bars** move as you take medicines.
    *   **Stats**: See exactly "Taken: X / Total: Y".
    *   **Alerts**: Check the red box for any "Missed Dose" warnings.

---

## 🏥 Phase 4: Pharmacy Coordination (Refills)
**Goal:** Show the closed loop with the healthcare system.

1.  **Navigation:** Go back to Home (`/`) -> Click **🏥 Pharmacy Portal**.
2.  **Observation:**
    *   You should see a **Refill Ticket** for `Paracetamol`.
    *   Reason: Stock (4) <= Threshold (5).
3.  **Action:** Click **"Authorize Refill"**.
    *   *Result:* Simulates sending the medicine to the patient.

---

## ✅ Sequence Complete
This flow proves:
1.  **Data Persistence**: Setup -> Patient -> Family -> Pharmacy.
2.  **Real-time Logic**: Intake updates stock instantly across portals.
3.  **Accessibility**: The patient never touched a screen, only voice.
