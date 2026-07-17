"""
Advanced AI Assistant Engine for MedVoice.
Handles both medical RAG-based reasoning and general conversational help.
"""
from vector_store import MedicalVectorStore
import notifications
import random
import os
from dotenv import load_dotenv
import google.generativeai as genai

# Correcting the missing import that caused the crash
from database import get_patient_summary_text

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Configuration Error: {e}")

# Initialize Vector Store (Singleton-like fallback)
try:
    store = MedicalVectorStore()
except Exception as e:
    print(f"Vector Store Init Warning: {e}")
    store = None

# General Conversation Patterns
CONVERSATIONAL_FALLBACKS = [
    "I'm here to help! As your MedVoice assistant, I can track your medicine, order refills, or answer health questions. What's on your mind?",
    "I'm your dedicated health assistant. I can help you stay on track with your prescriptions or answer general questions.",
    "That's an interesting question! While I'm primarily focused on your health and medications, I'm happy to chat. How can I assist you today?"
]

def get_medical_advice(command, patient_data=None):
    """
    Main Entry Point for AI Responses.
    1. Try Gemini AI with full context.
    2. Fallback to specific granular sections based on keywords.
    """
    # Get language preference (default to English)
    lang = patient_data.get('language', 'en-US') if isinstance(patient_data, dict) else 'en-US'
    is_tamil = "ta" in lang.lower()
    
    # Retrieve patient summary text for prompt context
    from database import get_patient_summary_text
    patient_text = get_patient_summary_text()

    # --- Phase 1: Try Gemini AI ---
    if GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel("gemini-1.5-flash-latest")
            
            # Dynamic Language Instruction
            lang_instruction = "Respond ONLY in Tamil (தமிழ்)." if is_tamil else "Respond ONLY in English."
            
            prompt = f"""You are MedVoice, a helpful, friendly, and highly concise voice assistant for a visually impaired patient.
User Language: {'Tamil' if is_tamil else 'English'}
{lang_instruction}

Your goal is to answer their question using ONLY the provided patient profile and stock information.
Keep your answers brief, as they will be spoken out loud (1-2 sentences ideally).
If they ask for medical advice beyond their profile (e.g. diagnosing a new severe pain), tell them to contact a doctor or caregiver.
Do not use markdown like **bold**, use plain text suitable for speaking in {'Tamil' if is_tamil else 'English'}.

PATIENT CONTEXT:
{patient_text}

PATIENT QUESTION: {command}
"""
            response = model.generate_content(prompt)
            if response.text:
                return response.text.strip()
        except Exception as e:
            print(f"Gemini API Error: {e}")

    # Restoring missing variables for local logic
    query_lower = command.lower()

    # --- Phase 2: Granular Local Fallback ---
    if not patient_data or not isinstance(patient_data, dict):
        return "I'm sorry, I don't have access to your medical profile right now." if not is_tamil else "என்னிடம் உங்கள் மருத்துவ விவரங்கள் தற்போது இல்லை."

    # Labels based on language
    labels = {
        "caregiver": "Regarding your caregivers: " if not is_tamil else "உங்கள் உதவியாளர்கள்: ",
        "meds": "Your current medications and stock: " if not is_tamil else "உங்கள் மருந்துகள்: ",
        "identity": "According to your profile: " if not is_tamil else "உங்கள் விவரங்களின்படி: ",
        "help": "I'm here to help. You are " if not is_tamil else "நான் உங்களுக்கு உதவ இருக்கிறேன். நீங்கள் "
    }

    # Specific Caregiver Intent
    if any(w in query_lower for w in ["caregiver", "giver", "care", "dinesh", "உதவியாளர்"]):
        return f"{labels['caregiver']} {patient_data.get('caregiver', '')}"

    # Specific Medication/Stock Intent
    if any(w in query_lower for w in ["medicine", "tablet", "stock", "left", "remaining", "low", "pill", "list", "மருந்து", "மாத்திரை"]):
        return f"{labels['meds']} {patient_data.get('medications', '')}"

    # Specific Condition/Name Intent
    if any(w in query_lower for w in ["condition", "diagnosis", "diagnosed", "name", "who am i", "age", "நோய்", "பெயர்"]):
        return f"{labels['identity']} {patient_data.get('identity', '')}"

    # --- Phase 3: Medical RAG ---
    if store:
        try:
            matches = store.search(command, k=1)
            medical_keywords = [
                "pain", "headache", "fever", "cold", "hurt", "sick", "symptom", "paracetamol", "advice", "வலி", "காய்ச்சல்",
                "missed", "forgot", "skipped", "dose", "metformin", "amlodipine", "used", "about", "pressure", "sugar", "diabetes"
            ]
            if matches and any(kw in query_lower for kw in medical_keywords):
                knowledge = matches[0]['content']
                return _process_medical_reasoning(command, knowledge)
        except Exception as e:
            print(f"RAG Search Error: {e}")

    # General Awareness/Health Intent (The user is asking generally about themselves)
    if any(w in query_lower for w in ["me", "my", "i", "help", "what", "patient", "உதவி", "எனது"]):
        return f"{labels['help']} {patient_data.get('identity', 'Unknown')}. {patient_data.get('alerts', '')}"

    return _get_general_response(command)

def _process_medical_reasoning(command, knowledge):
    """Detects risk and provides reasoned medical advice. (Reload trigger)"""
    query_lower = command.lower()
    is_missed_dose = any(word in query_lower for word in ["missed", "forgot", "skipped"])
    
    if is_missed_dose:
        risk_level = "MODERATE"
        if any(word in query_lower for word in ["chest pain", "dizzy", "breath"]):
            risk_level = "CRITICAL"
        
        advice = f"🚨 {risk_level} RISK DETECTED\n\n{knowledge}\n\n"
        advice += "I have logged this event and notified your caregiver. "
        if risk_level == "CRITICAL":
            advice += "PLEASE CALL EMERGENCY SERVICES IMMEDIATELY."
        
        notifications.log_event("AI_RISK", f"{risk_level}: {command}")
        return advice
    
    return knowledge

def _get_general_response(command):
    """Handles non-medical queries with helpful conversation."""
    query_lower = command.lower()
    
    # Specific common questions
    if any(w in query_lower for w in ["who are you", "what are you", "your name"]):
        return "I am MedVoice, your AI-powered health companion. I help you manage medications and stay healthy."
    
    if any(w in query_lower for w in ["hello", "hi", "hey"]):
        return "Hello! I hope you're having a good day. How can I help you with your health today?"
    
    if any(w in query_lower for w in ["thank", "thanks"]):
        return "You're very welcome! I'm always here to help."
        
    if "why" in query_lower and "sorry" in query_lower:
        return "I apologize if I seemed confused. I'm still learning, but I'll do my best to answer clearly! What can I help you with?"

    # Final fallback
    return "I'm your dedicated health assistant. I can help you stay on track with your prescriptions or answer general questions. What can I do for you?"
