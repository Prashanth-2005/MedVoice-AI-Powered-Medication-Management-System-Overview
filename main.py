from fastapi import FastAPI, Request, Form, Response, Depends,  UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import database
import datetime
import uvicorn
import math
import asyncio
import medical_knowledge
import notifications
import shutil
import os
import pypdf
import re
import services.ocr_service as ocr_service
import services.llm_service as llm_service
import services.tracking_service as tracking_service
import services.tts_service as tts_service
import services.caregiver_service as caregiver_service
import services.pharmacy_service as pharmacy_service
import PyPDF2
import io
import requests
import json

# Initialize
app = FastAPI()
# Ensure DB is ready (idempotent)
database.init_db()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Security & Login ---

async def verify_cookie(request: Request):
    token = request.cookies.get("auth_token")
    if token != "valid_session":
        return False
    return True

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")

@app.post("/api/login")
async def login_api(response: Response, pin: str = Form(...)):
    user = database.get_user_info()
    stored_pin = user.get("caregiver_pin")
    
    if not stored_pin:
        if pin == "0000": 
             response.set_cookie(key="auth_token", value="valid_session")
             return {"status": "success"}
        else:
             from fastapi import HTTPException
             raise HTTPException(status_code=401, detail="Setup not complete. Use PIN 0000")

    if pin == stored_pin:
        response.set_cookie(key="auth_token", value="valid_session")
        return {"status": "success"}
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Incorrect PIN")

@app.get("/logout")
async def logout(response: Response):
    response = RedirectResponse(url="/login")
    response.delete_cookie("auth_token")
    return response

# --- Models ---
class CommandRequest(BaseModel):
    command: str

class VisionRequest(BaseModel):
    image: str

class SetupData(BaseModel):
    user: dict
    medicines: list
    contact: dict = None
    pin: str = None

class LocationUpdate(BaseModel):
    latitude: float
    longitude: float

# --- Location API ---

@app.post("/api/location/update")
async def api_update_location(data: LocationUpdate):
    # For now, we update for the default user (ID 1)
    database.update_location(1, data.latitude, data.longitude)
    return {"status": "success"}

@app.get("/api/location/latest")
async def api_get_latest_location():
    loc = database.get_latest_location(1)
    if loc:
        return loc
    return {"latitude": 0, "longitude": 0, "timestamp": "No data"}

# --- Pages ---

@app.post("/api/setup")
async def save_setup(data: SetupData):
    from fastapi import HTTPException
    existing_user = database.get_user_info()
    if existing_user and existing_user.get('caregiver_pin'):
        if data.pin != existing_user['caregiver_pin']:
            notifications.log_event("SECURITY", f"Failed setup attempt: Incorrect PIN for {existing_user.get('name')}")
            raise HTTPException(status_code=403, detail="Invalid Caregiver PIN")

    database.reset_and_fill_db(data.user, data.medicines, data.contact, pin=data.pin)
    notifications.log_event("SYSTEM", f"User onboarding/update completed: {data.user.get('name')}")
    return {"status": "success"}

@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    if not await verify_cookie(request):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request, "setup.html")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request, "landing.html")

@app.post("/api/scan-medicine")
async def scan_medicine_fastapi(image: UploadFile = File(...)):
    if not image:
        return JSONResponse(content={
            "status": "unknown",
            "message": "Warning: No image file received."
        }, status_code=400)
    
    img_bytes = await image.read()
    
    # 1. OCR Step
    extracted_text = ocr_service.ocr_service.scan_image_bytes(img_bytes)
    
    # 2. Verification Step
    match = tracking_service.tracking_service.find_prescription_match(extracted_text)
    
    if not match:
        reply = "I couldn't verify this medicine against your prescriptions."
        return JSONResponse(content={"status": "error", "message": reply, "voice_url": ""}, status_code=400)
        
    # 3. Explain Step (Qwen3)
    patient_summary = database.get_patient_summary_text()
    prompt = f"Patient context:\n{patient_summary}\n\nThe patient is holding {match['name']}. Explain what this is for in 1 short conversational sentence."
    explanation = await asyncio.to_thread(llm_service.llm_service.generate_response, prompt)
    
    # 4. Generate TTS
    # voice_path = await tts_service.tts_service.generate_speech(explanation)
    # Using browser TTS for now so we return the text to the frontend.
    
    return JSONResponse(content={
        "status": "success",
        "medicine": match['name'],
        "message": explanation
    }, status_code=200)

@app.post("/api/vision")
async def analyze_image(req: VisionRequest):
    import base64
    img_bytes = base64.b64decode(req.image.split(",")[1] if "," in req.image else req.image)
    
    # 1. OCR Step
    extracted_text = ocr_service.ocr_service.scan_image_bytes(img_bytes)
    
    # 2. Verification Step
    match = tracking_service.tracking_service.find_prescription_match(extracted_text)
    
    if not match:
        return {"reply": "I couldn't verify this medicine against your prescriptions."}
        
    # 3. Explain Step (Qwen3)
    patient_summary = database.get_patient_summary_text()
    prompt = f"Patient context:\n{patient_summary}\n\nThe patient is holding {match['name']}. Explain what this is for in 1 short conversational sentence."
    explanation = await asyncio.to_thread(llm_service.llm_service.generate_response, prompt)
    
    return {"reply": explanation}

@app.get("/patient", response_class=HTMLResponse)
async def patient_app(request: Request):
    notifications.log_event("ACCESS", "Patient Portal accessed")
    return templates.TemplateResponse(request, "index.html")

@app.get("/api/medicines")
async def get_medicines():
    return database.get_all_medicines()

@app.get("/api/profile")
async def get_profile():
    return database.get_user_info()

@app.get("/api/alerts")
async def get_alerts():
    # Step 5: Missed Dose Detection
    alerts = database.get_missed_doses()
    reminders = database.get_active_reminders()
    
    if alerts:
         notifications.log_event("MONITOR", f"Missed dose alerts generated: {len(alerts)}")
         
    return {"alerts": alerts, "reminders": reminders}

def get_primary_caregiver_email():
    """Helper to extract the primary caregiver's email from the contacts database."""
    try:
        contacts = database.get_contacts(contact_type='family')
        if contacts:
            # The email is stored in a combined field: "EMAIL: ... | MSG: ..."
            raw_contact = contacts[0]['email_phone']
            if "EMAIL:" in raw_contact:
                return raw_contact.split('|')[0].replace("EMAIL:", "").strip()
            return raw_contact # Direct email if format differs
    except:
        pass
    return "caregiver@example.com"

@app.post("/api/command")
async def handle_command(cmd_request: CommandRequest):
    try:
        command = cmd_request.command.lower()
        notifications.log_event("VOICE", f"Received command: '{command}'")
        patient_summary = database.get_patient_summary()
        
        # --- VISION FALLBACK ---
        strong_vision = ["scan", "capture", "take a photo", "take photo", "identify", "what is this"]
        is_vision = any(word in command for word in strong_vision) or re.search(r'\b(check|see|read|look|identify)\b.*\b(this|medicine|tablet|pill|label|bottle|prescription|pack|box|camera)\b', command)
        if is_vision:
            return JSONResponse(content={
                "reply": "Switching to scanner. Please hold the medicine steady.",
                "trigger_vision": True
            })

        response_text = "I didn't quite catch that."

        # 1. EMERGENCY INTENT (Static)
        if any(w in command for w in ["call", "emergency", "ambulance", "doctor now", "suffering", "immediate help", "serious"]):
            user = database.get_user_info()
            caregiver_email = get_primary_caregiver_email()
            
            # Trigger Backend Alert
            notifications.send_emergency_alert(
                patient_name=user.get('name', 'Patient'),
                condition=user.get('disability_type', 'Unknown'),
                family_contact=caregiver_email
            )
            
            # Special Response for Frontend to trigger Siren
            return JSONResponse(content={
                "reply": "EMERGENCY: Initiating emergency alert. I am contacting your caregiver and emergency services now. Help is on the way.",
                "emergency": True
            })

        # 2. HELLO/GREETINGS INTENT (Static)
        elif any(re.search(rf"\b{w}\b", command) for w in ["hello", "hi", "hey", "hii", "வணக்கம்"]):
            response_text = "Hello. I am MedVoice, your health assistant."

        # 3. INTAKE INTENT (Static)
        elif any(w in command for w in ["take", "taking", "taken", "took", "had", "yes", "consumed", "finish"]):
            medicines = tracking_service.tracking_service.get_all_prescriptions()
            matched_meds = []
            
            # A. Try Specific Keyword Match (Flexible)
            for med in medicines:
                med_name_lower = med['name'].lower()
                if med_name_lower in command or any(part.lower() in command for part in med['name'].split() if len(part) > 3):
                    matched_meds.append(med)
            
            # B. If no name found, check Context (What is due NOW?)
            if not matched_meds:
                now = datetime.datetime.now()
                today_str = now.strftime('%Y-%m-%d')
                
                # Find candidate medicines due around this time (+/- 2 hours)
                for med in medicines:
                    if not med['schedule_time']: continue
                    times = [t.strip() for t in med['schedule_time'].split(',')]
                    
                    is_due_now = False
                    for t_str in times:
                        try:
                            th, tm = 0, 0
                            if "AM" in t_str or "PM" in t_str:
                                dt = datetime.datetime.strptime(t_str, "%I:%M %p")
                                th, tm = dt.hour, dt.minute
                            else:
                                parts = t_str.split(':')
                                th, tm = int(parts[0]), int(parts[1])
                            if abs(now.hour - th) <= 2:
                                is_due_now = True
                        except:
                            pass
                    
                    if is_due_now:
                        # Verify it hasn't been taken yet today
                        with database.get_db() as conn:
                            count = conn.execute("SELECT count(*) FROM intake_logs WHERE medicine_id=? AND date(intake_time)=? AND status='taken'", (med['id'], today_str)).fetchone()[0]
                            if count == 0:
                                matched_meds.append(med)

            # Process Matches
            if matched_meds:
                names_confirmed = []
                warnings = []
                
                for med in matched_meds:
                    updated_med = tracking_service.tracking_service.log_medication_intake(med['id'])
                    names_confirmed.append(med['name'])
                    
                    # Check Stock
                    remaining = updated_med['stock_count']
                    if remaining <= 3:
                        # Process Refills and Alerts
                        ordered = pharmacy_service.pharmacy_service.process_automated_refills()
                        warnings.append(f"{med['name']} Low Stock. Sent Refill Request.")

                warn_msg = " ".join(warnings)
                response_text = f"Great. I have marked {', '.join(names_confirmed)} as taken. {warn_msg}"
            
            else:
                response_text = "I couldn't identify which medicine you took, and nothing is scheduled for right now. Please tell me the medicine name."

        # 4. REFILL INTENT (Static)
        elif "refill" in command or "order" in command:
            ordered = pharmacy_service.pharmacy_service.process_automated_refills()
            if ordered:
                response_text = f"I have sent refill requests for: {', '.join(ordered)}."
            else:
                response_text = "Your stock levels are okay. No refills needed yet."

        # 5. STOCK QUERY INTENT (Static)
        elif any(word in command for word in ["stock", "how many", "remaining", "left", "மீதி", "எத்தனை"]):
            medicines = tracking_service.tracking_service.get_all_prescriptions()
            matched_meds = []
            for med in medicines:
                med_name_lower = med['name'].lower()
                if med_name_lower in command or any(part.lower() in command for part in med['name'].split() if len(part) > 3):
                    matched_meds.append(med)
            
            if matched_meds:
                replies = []
                for med in matched_meds:
                    replies.append(f"You have {med['stock_count']} tablets of {med['name']} left.")
                response_text = " ".join(replies)
            else:
                low_stock_meds = [m['name'] for m in medicines if m['stock_count'] <= m['refill_threshold']]
                if low_stock_meds:
                    response_text = f"You are low on stock for: {', '.join(low_stock_meds)}."
                else:
                    response_text = "All your medicines have sufficient stock."

        # 6. WHICH TABLET INTENT (Static)
        elif "which" in command and ("take" in command or "tablet" in command):
            now = datetime.datetime.now()
            current_hour = now.hour
            time_slot = "morning"
            if 12 <= current_hour < 17:
                time_slot = "afternoon"
            elif current_hour >= 17:
                time_slot = "evening"
                
            candidates = []
            medicines = tracking_service.tracking_service.get_all_prescriptions()
            for med in medicines:
                schedule = med['schedule_time']
                if not schedule: continue
                
                if time_slot == "morning" and ("08" in schedule or "09" in schedule):
                    candidates.append(med['name'])
                elif time_slot == "afternoon" and ("12" in schedule or "13" in schedule):
                    candidates.append(med['name'])
                elif time_slot == "evening" and ("19" in schedule or "20" in schedule or "21" in schedule):
                    candidates.append(med['name'])
            
            if candidates:
                response_text = f"It is {time_slot}. Recommended: {', '.join(candidates)}."
            else:
                response_text = f"No medicines scheduled for this {time_slot}."

        # 7. AWARENESS & HEALTH QUESTIONS (AI Reasoning - LLM)
        elif any(word in command for word in [
            "caregiver", "instruction", "headache", "fever", "cold", 
            "pain", "hurt", "diabetes", "pressure", "what is", 
            "missed", "forgot", "should", "help", "me", "my", "patient",
            "condition", "who", "name", "age", "diagnosis",
            "உதவியாளர்", "வலி", "காய்ச்சல்", "பெயர்", "நிலை", "உதவி"
        ]):
            patient_summary = database.get_patient_summary_text()
            prompt = f"You are MedVoice, a helpful voice assistant for a patient. Keep answers to 1-2 short sentences.\nPatient Context:\n{patient_summary}\n\nPatient asks: {command}"
            advice = await asyncio.to_thread(llm_service.llm_service.generate_response, prompt)
            response_text = advice

        # 8. GLOBAL AI FALLBACK (LLM)
        else:
            patient_context = database.get_patient_summary_text()
            prompt = f"You are MedVoice, a helpful voice assistant. Keep answers very brief (1-2 sentences). Patient Context:\n{patient_context}\n\nPatient asks: {command}"
            response_text = await asyncio.to_thread(llm_service.llm_service.generate_response, prompt)

        # Final Localization Pass (Ensure Tamil speakers never hear English)
        patient_summary = database.get_patient_summary()
        if "ta" in patient_summary.get('language', '').lower():
            if not re.search(r'[\u0B80-\u0BFF]', response_text):
                translation_prompt = f"Translate the following text exactly to Tamil (தமிழ்). Do not add any extra conversation. Text: {response_text}"
                response_text = await asyncio.to_thread(llm_service.llm_service.generate_response, translation_prompt)

        return JSONResponse(content={"reply": response_text})

    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"COMMAND ERROR: {error_msg}")
        notifications.log_event("SYSTEM_ERROR", f"Error processing command '{cmd_request.command}': {str(e)}")
        return JSONResponse(content={"reply": "I apologize, I'm having a bit of trouble processing that. Could you please say it again?"})

# --- Dashboards ---

@app.get("/dashboard/family", response_class=HTMLResponse)
async def family_dashboard(request: Request):
    if not await verify_cookie(request):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request, "dashboard_family.html")

@app.get("/dashboard/pharmacy", response_class=HTMLResponse)
async def pharmacy_dashboard(request: Request):
    if not await verify_cookie(request):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request, "dashboard_pharmacy.html")

@app.get("/pharmacy/register", response_class=HTMLResponse)
async def pharmacy_register_page(request: Request):
    return templates.TemplateResponse(request, "register_pharmacy.html")

def haversine(lat1, lon1, lat2, lon2):
    import math
    R = 6371.0 # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)

class PharmacyRegistration(BaseModel):
    pharmacy_name: str
    license_number: str
    contact: str
    email: str
    address: str
    latitude: float
    longitude: float
    operating_hours: str

@app.post("/api/pharmacy/register")
async def api_register_pharmacy(req: PharmacyRegistration):
    pharmacy_id = database.register_pharmacy(req.dict())
    return {"status": "success", "pharmacy_id": pharmacy_id}

@app.get("/api/pharmacies/nearby")
async def get_nearby_pharmacies(lat: float = 12.9716, lon: float = 77.5946):
    pharmacies = database.get_all_pharmacies()
    for p in pharmacies:
        p['distance_km'] = haversine(lat, lon, p.get('latitude', 0), p.get('longitude', 0))
    pharmacies.sort(key=lambda x: x['distance_km'])
    return {"pharmacies": pharmacies}

class MapPharmacyRequest(BaseModel):
    pharmacy_id: int

@app.post("/api/patient/map-pharmacy")
async def map_pharmacy(req: MapPharmacyRequest):
    user = database.get_user_info()
    patient_id = user.get('user_id', 1) if user else 1
    database.map_patient_to_pharmacy(patient_id, req.pharmacy_id)
    return {"status": "success"}

@app.get("/dashboard/analytics", response_class=HTMLResponse)
async def analytics_dashboard(request: Request):
    if not await verify_cookie(request):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request, "dashboard_analytics.html")

@app.get("/api/dashboard/analytics/data")
async def get_analytics_data():
    user = database.get_user_info()
    report = database.get_weekly_adherence_report()
    
    # 1. Calculate Overall Health Score (from Report)
    total_score = 0
    count = 0
    history = []
    
    for m in report['medicines']:
        total_score += m['adherence_pct']
        count += 1
        history.append({
            "medicine": m['name'],
            "time": "Last 7 Days",
            "status": "taken" if m['adherence_pct'] > 50 else "missed"
        })
        
    avg_score = int(total_score / count) if count > 0 else 100 # Default to 100 if no meds
    
    # 2. Generate Real Chart Data (Last 7 Days Intake Count)
    dates = []
    values = []
    today = datetime.datetime.now()
    
    # We need a helper or direct query here. 
    # For simplicity, we'll do a quick query in the loop (not efficient for big apps, fine for MVP)
    with database.get_db() as conn:
        for i in range(6, -1, -1):
            d = today - datetime.timedelta(days=i)
            d_str = d.strftime("%Y-%m-%d")
            dates.append(d.strftime("%a")) # Mon, Tue...
            
            # Count taken logs for this date
            # Note: intake_logs stores 'intake_time' as TIMESTAMP/DATETIME.
            # We need to filter by day. SQLite `date(intake_time)` works.
            row = conn.execute("SELECT count(*) FROM intake_logs WHERE date(intake_time) = ? AND status='taken'", (d_str,)).fetchone()
            val = row[0] if row else 0
            values.append(val)

    # 3. Health Journey / Comparison Data (Hardcoded from PDF Analysis for Demo)
    # in a real system, this would come from parsing the 'uploads/' folder 
    health_timeline = {
        "prev": {
            "date": "01-Dec-2025",
            "status": "CRITICAL",
            "condition": "Heart Attack (STEMI)",
            "vitals": "BP: 85/50 | EF: 25%",
            "color": "red"
        },
        "curr": {
            "date": "01-Jan-2026",
            "status": "MODERATE",
            "condition": "Diabetes & Hypertension",
            "vitals": "BP: 150/90 (Improved pump function)",
            "color": "orange"
        },
        "insight": "Patient has stabilized from a life-threatening cardiac event to chronic management. Focus shifted from survival (ICU) to maintenance (Diet/Meds)."
    }

    return {
        "user": user,
        "health_score": avg_score,
        "chart": { "labels": dates, "values": values },
        "history": history,
        "timeline": health_timeline
    }

@app.post("/api/analyze-prescriptions")
async def analyze_prescriptions(prev_rx: UploadFile = File(...), curr_rx: UploadFile = File(...)):
    def extract_text(upload_file: UploadFile):
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(upload_file.file.read()))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            print("PDF Extraction Error:", e)
            return "Unable to extract text from PDF."

    prev_text = extract_text(prev_rx)
    curr_text = extract_text(curr_rx)

    prompt = f"""You are an expert AI Medical Assistant. Compare the following two medical records (Previous vs Current).
Extract the primary condition and key vitals for both. Then provide a 2-sentence clinical insight summarizing the recovery trajectory.
You must return the response STRICTLY as a valid JSON object matching this exact structure. Do not use Markdown backticks. Do not include any extra text.
{{
    "timeline": {{
        "prev": {{ "condition": "String", "vitals": "String" }},
        "curr": {{ "condition": "String", "vitals": "String" }},
        "insight": "String"
    }}
}}

Previous Record:
{prev_text}

Current Record:
{curr_text}
"""

    try:
        response = requests.post("http://localhost:11434/api/generate", json={
            "model": "qwen3:8b",
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }, timeout=60)
        response.raise_for_status()
        llm_response = response.json().get("response", "")
        
        # Clean up in case model still outputs markdown
        if llm_response.startswith("```json"):
            llm_response = llm_response[7:-3]
            
        data = json.loads(llm_response)
        return data
        
    except Exception as e:
        print("NLP API Error:", e)
        return {
            "timeline": {
                "prev": { "condition": "Parse Error", "vitals": "N/A" },
                "curr": { "condition": "Parse Error", "vitals": "N/A" },
                "insight": f"System encountered an AI parsing error: {str(e)}"
            }
        }

@app.get("/api/dashboard/family/data")
async def family_data():
    medicines = database.get_all_medicines()
    alerts = database.get_missed_doses()
    user = database.get_user_info()
    refills = database.get_refill_requests(patient_id=user.get('user_id', 1))
    # We use a default pharmacy_id for MVP
    pharmacy_id = 1
    messages = database.get_caregiver_messages(pharmacy_id)
    return {"medicines": medicines, "alerts": alerts, "user": user, "refills": refills, "messages": messages}

@app.get("/api/dashboard/pharmacy/data")
async def pharmacy_data():
    pharmacy_id = 1 # Hardcoded for prototype
    inventory = database.get_pharmacy_inventory(pharmacy_id)
    requests = database.get_refill_requests(pharmacy_id=pharmacy_id)
    messages = database.get_caregiver_messages(pharmacy_id)
    
    # Calculate stats
    pending_count = sum(1 for r in requests if r['status'] in ['Requested', 'Approved'])
    completed_count = sum(1 for r in requests if r['status'] == 'Completed')
    low_stock_count = sum(1 for i in inventory if i['quantity'] < 20) # arbitrary threshold for MVP
    
    return {
        "inventory": inventory,
        "requests": requests,
        "messages": messages,
        "stats": {
            "pending_refills": pending_count,
            "completed_refills": completed_count,
            "low_stock_medicines": low_stock_count,
            "total_patients": 1 # MVP single user
        }
    }

class RefillStatusRequest(BaseModel):
    status: str

@app.post("/api/pharmacy/refill/{request_id}/status")
async def update_refill_status(request_id: int, req: RefillStatusRequest):
    database.update_refill_status(request_id, req.status)
    return {"status": "success"}

class CaregiverMessage(BaseModel):
    message: str
    sender: str # 'caregiver' or 'pharmacy'

@app.post("/api/pharmacy/message")
async def send_pharmacy_message(req: CaregiverMessage):
    user = database.get_user_info()
    caregiver_id = user.get('user_id', 1) if user else 1
    # Hardcoded pharmacy_id for MVP prototype
    database.send_caregiver_message(caregiver_id=caregiver_id, pharmacy_id=1, message=req.message, sender=req.sender)
    return {"status": "success"}

# --- Helper for PDF Analysis ---
def extract_and_analyze_pdf(file_path):
    try:
        reader = pypdf.PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
            
        # Heuristic Analysis
        result = {
            "condition": "Unknown",
            "vitals": "Not found"
        }
        
        # Simple parsing logic
        if "Heart Attack" in text or "Myocardial Infarction" in text:
            result['condition'] = "Heart Attack (STEMI)"
        elif "Diabetes" in text:
            result['condition'] = "Diabetes & Hypertension"
            
        # Vitals extraction (Naive)
        import re
        bp_match = re.search(r"BP:\s*([\d/]+)", text)
        if bp_match:
            result['vitals'] = f"BP: {bp_match.group(1)}"
            
        return result
    except Exception as e:
        print(f"PDF Error: {e}")
        return {"condition": "Error", "vitals": "Error"}

@app.post("/api/analyze-prescriptions")
async def analyze_prescriptions(
    prev_rx: UploadFile = File(...),
    curr_rx: UploadFile = File(...)
):
    # Save files
    os.makedirs("uploads", exist_ok=True)
    p_path = f"uploads/{prev_rx.filename}"
    c_path = f"uploads/{curr_rx.filename}"
    
    with open(p_path, "wb") as buffer:
        shutil.copyfileobj(prev_rx.file, buffer)
    with open(c_path, "wb") as buffer:
        shutil.copyfileobj(curr_rx.file, buffer)
        
    # Analyze
    prev_data = extract_and_analyze_pdf(p_path)
    curr_data = extract_and_analyze_pdf(c_path)
    
    # Construct Timeline
    timeline = {
        "prev": {
            "date": "Dec-2025", # Mock date for demo, usually regex extracted
            "status": "CRITICAL",
            "condition": prev_data['condition'],
            "vitals": prev_data['vitals'],
            "color": "red"
        },
        "curr": {
            "date": "Jan-2026",
            "status": "MODERATE",
            "condition": curr_data['condition'],
            "vitals": curr_data['vitals'],
            "color": "orange"
        },
        "insight": "Analysis shows significant stabilization. " + 
                   (f"Condition changed from {prev_data['condition']} to {curr_data['condition']}." if prev_data['condition'] != curr_data['condition'] else "Condition stable.")
    }
    
    return {"status": "success", "timeline": timeline}

@app.post("/api/parse-prescription")
async def parse_prescription_api(file: UploadFile = File(...)):
    try:
        # Save temp
        os.makedirs("uploads", exist_ok=True)
        path = f"uploads/setup_{file.filename}"
        with open(path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        reader = pypdf.PdfReader(path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
            
        # Parse Logic
        import re
        
        # Patient Name
        p_match = re.search(r"(?:Patient\s+Name|Name):\s*([^\n\r]+)", text, re.IGNORECASE)
        if not p_match:
            p_match = re.search(r"\bPatient:\s*([^\n\r]+)", text, re.IGNORECASE)
        patient_name = p_match.group(1).strip() if p_match else ""
        patient_name = re.sub(r'\s+Age.*', '', patient_name, flags=re.IGNORECASE)
        patient_name = re.sub(r'\s+ID.*', '', patient_name, flags=re.IGNORECASE)
        
        # Split text into lines
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        # Group lines by medicine blocks
        med_blocks = []
        current_block = None
        stop_headers = ["follow-up", "physician", "doctor", "date:", "diagnosis", "rx:"]
        
        for line in lines:
            if any(line.lower().startswith(header) for header in stop_headers):
                current_block = None
                continue
                
            is_new_med = False
            num_match = re.match(r'^(?:rx\s*)?\d+[\.\)\s\-:]+\s*(.*)', line, re.IGNORECASE)
            
            if num_match:
                rest = num_match.group(1).strip()
                if rest:
                    is_new_med = True
            elif any(p.lower() in line.lower() for p in ["tab.", "cap.", "tablet", "capsule", "syrup", "syp.", "inj.", "ointment", "oint."]):
                if not any(line.lower().startswith(x) for x in ["take", "duration", "every", "once", "twice", "qty"]):
                    is_new_med = True
                    
            if is_new_med:
                name_line = num_match.group(1).strip() if num_match else line
                current_block = {
                    "name_line": name_line,
                    "lines": [line]
                }
                med_blocks.append(current_block)
            elif current_block is not None:
                current_block["lines"].append(line)

        meds = []
        for block in med_blocks:
            name = block["name_line"]
            block_text = " ".join(block["lines"]).lower()
            times = []
            
            # 1-0-1 pattern
            patterns = {
                "1-0-1": ["09:00 AM", "09:00 PM"],
                "0-1-0": ["01:00 PM"],
                "0-0-1": ["09:00 PM"],
                "1-0-0": ["09:00 AM"],
                "1-1-1": ["09:00 AM", "01:00 PM", "09:00 PM"],
                "1-1-0": ["09:00 AM", "01:00 PM"],
                "0-1-1": ["01:00 PM", "09:00 PM"]
            }
            sched_match = re.search(r'(\d\s*[-–—]\s*\d\s*[-–—]\s*\d)', block_text)
            if sched_match:
                raw_sched = sched_match.group(1).replace('–', '-').replace('—', '-').replace(' ', '')
                if raw_sched in patterns:
                    times = patterns[raw_sched]
                    
            if not times:
                detected_meals = []
                if "before breakfast" in block_text or "empty stomach" in block_text:
                    detected_meals.append("08:00 AM")
                elif "breakfast" in block_text or "morning" in block_text:
                    detected_meals.append("09:00 AM")
                    
                if "before lunch" in block_text:
                    detected_meals.append("12:00 PM")
                elif "after lunch" in block_text or "lunch" in block_text or "afternoon" in block_text:
                    detected_meals.append("01:00 PM")
                    
                if "before dinner" in block_text:
                    detected_meals.append("08:00 PM")
                elif "after dinner" in block_text or "dinner" in block_text or "night" in block_text or "bedtime" in block_text:
                    detected_meals.append("09:00 PM")
                    
                if "evening" in block_text:
                    detected_meals.append("06:00 PM")
                    
                if detected_meals:
                    time_order = ["08:00 AM", "09:00 AM", "12:00 PM", "01:00 PM", "06:00 PM", "08:00 PM", "09:00 PM"]
                    detected_meals.sort(key=lambda x: time_order.index(x) if x in time_order else 99)
                    times = detected_meals
                    
            if not times:
                freq_times = {
                    "three times": ["09:00 AM", "01:00 PM", "09:00 PM"],
                    "thrice": ["09:00 AM", "01:00 PM", "09:00 PM"],
                    "twice daily": ["09:00 AM", "09:00 PM"],
                    "twice a day": ["09:00 AM", "09:00 PM"],
                    "once daily": ["09:00 AM"],
                    "once a day": ["09:00 AM"],
                    "daily": ["09:00 AM"],
                    "once weekly": ["09:00 AM (Weekly)"],
                    "weekly": ["09:00 AM (Weekly)"]
                }
                for k, v in freq_times.items():
                    if k in block_text:
                        times = v
                        break
                        
            if not times:
                times = ["09:00 AM"]
                
            name = re.sub(r'(Tab\.|Cap\.|Tablet|Capsule|Syp\.|Inj\.|Oint\.|Syrup|Ointment)', '', name, flags=re.IGNORECASE).strip()
            meds.append({"name": name, "times": ", ".join(times)})
            
        return {"status": "success", "data": {"name": patient_name, "medicines": meds}}
        
    except Exception as e:
        print(f"Parse Error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/dashboard/pharmacy/data")
async def pharmacy_data():
    # Only return medicines with low stock
    all_meds = database.get_all_medicines()
    refills = [m for m in all_meds if m['stock_count'] <= m['refill_threshold']]
    return {"refills": refills}

# --- Background Task for Alerts ---
import asyncio

last_notified = {}

async def adherence_monitor():
    """
    Checks for missed doses every 60 seconds.
    If a dose is missed > 30 mins, notifies family.
    """
    while True:
        try:
            alerts = database.get_missed_doses()
            caregiver_email = get_primary_caregiver_email()
            
            for alert in alerts:
                # Alert format: "You have missed your scheduled dose of {med} for {time}."
                # De-dupe notifications to avoid spam
                alert_key = f"{datetime.datetime.now().hour}_{alert}" 
                
                if alert_key not in last_notified:
                    print(f"[MONITOR] Sending Alert: {alert}")
                    notifications.notify_family_alert("MISSED DOSE ALERT", alert, caregiver_email)
                    last_notified[alert_key] = True
                    
                    # Clean up old keys
                    if len(last_notified) > 50:
                        last_notified.clear()
                        last_notified[alert_key] = True

            await asyncio.sleep(60) # CHeck every minute
        except Exception as e:
            print(f"Monitor Error: {e}")
            await asyncio.sleep(60)

@app.on_event("startup")
async def start_monitor():
    asyncio.create_task(adherence_monitor())

@app.post("/api/report/weekly/send")
async def send_weekly_report():
    report = database.get_weekly_adherence_report()
    user = database.get_user_info()
    
    # Use the helper to get the clean email
    target_contact = get_primary_caregiver_email()
    
    # 1. Construct Message
    lines = [f"WEEKLY REPORT for {user.get('name', 'Patient')} ({report['start_date']} to {report['end_date']})"]
    for m in report['medicines']:
        lines.append(f"- {m['name']}: {m['adherence_pct']}% Adherence ({m['status']})")
    
    full_msg = "\n".join(lines)
    
    # 2. Send to Specific Caregiver
    notifications.notify_family_alert("WEEKLY REPORT", full_msg, target_contact)
    
    notifications.log_event("REPORT", f"Weekly report sent for {user.get('name')} to {target_contact}")
    
    return {"status": "sent", "summary": full_msg, "target": target_contact}

# --- Background Task for Automated Reports ---
import asyncio

async def scheduler_task():
    """
    Simulates a cron job. Checks every 60 seconds if a scheduled report is due.
    In a real app, use APScheduler or Celery.
    """
    print("Background Scheduler Started...")
    while True:
        await asyncio.sleep(60) # Check every minute
        
        now = datetime.datetime.now()
        # MOCK LOGIC: We simulate that reports are sent at XX:00 (Top of the hour)
        # or just log that we are checking.
        
        # 1. Fetch Contacts with Daily/Weekly frequency
        try:
            contacts = database.get_contacts('family')
            if not contacts: continue
            
            for c in contacts:
                freq = c.get('report_frequency', 'weekly')
                should_send = False
                
                # DAILY: Send at 20:00 (8 PM)
                if freq == 'daily' and now.hour == 20 and now.minute == 0:
                    should_send = True
                    
                # WEEKLY: Send on Sunday at 20:00
                elif freq == 'weekly' and now.weekday() == 6 and now.hour == 20 and now.minute == 0:
                    should_send = True
                    
                # For DEMO: If frequency is daily, just log we are checking.
                
                if should_send:
                    # Trigger Report
                    # Re-use logic (refactor if clean, or just duplicate call for now)
                    # For simplicity, calling the logic directly:
                    report = database.get_weekly_adherence_report() # Logic is same (7 day lookback)
                    user = database.get_user_info()
                    msg = f"AUTOMATED {freq.upper()} REPORT for {user.get('name')}: \n" 
                    for m in report['medicines']:
                        msg += f"- {m['name']}: {m['adherence_pct']}%\n"
                    
                    notifications.notify_family_alert(f"AUTO REPORT ({freq})", msg, c['email_phone'])
                    notifications.log_event("SCHEDULER", f"Automated {freq} report sent to {c['name']}")
                    
        except Exception as e:
             print(f"Scheduler Error: {e}")

@app.on_event("startup")
async def start_scheduler():
    asyncio.create_task(scheduler_task())

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

# Force reload
