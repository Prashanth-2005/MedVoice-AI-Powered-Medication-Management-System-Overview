MedVoice – AI-Powered Medication Management System
Overview

MedVoice is an AI-powered voice-based medication management system designed to assist visually impaired and elderly individuals in managing medications independently. The platform combines Computer Vision, Optical Character Recognition (OCR), Artificial Intelligence, Voice Technologies, Caregiver Monitoring, and Pharmacy Refill Management to create a complete healthcare assistance ecosystem.

The system verifies medicines using camera-based recognition, provides multilingual voice guidance, tracks medication adherence, monitors medicine stock, and coordinates caregivers and pharmacies to ensure uninterrupted treatment.

Key Features
Patient Portal
Voice-based medication assistance
Camera-based medicine scanning
PaddleOCR medicine recognition
Prescription verification
Qwen AI-powered healthcare guidance
Multilingual voice interaction
Medication intake confirmation
Automated medication logging
Caregiver Portal
Real-time medication monitoring
Adherence tracking
Missed dose detection
Emergency notifications
Medication reports
Refill approval management
Pharmacy Portal
Pharmacy inventory management
Refill request handling
Medicine availability tracking
Caregiver-pharmacy communication
Automated stock updates
Nearby pharmacy coordination

System Architecture
Patient Portal
      ↓
Camera Module
      ↓
OpenCV Processing
      ↓
PaddleOCR
      ↓
Prescription Verification
      ↓
Qwen 3 LLM (Ollama)
      ↓
Voice Guidance
      ↓
Medication Logging
      ↓
Adherence Monitoring
      ↓
Caregiver Portal
      ↓
Refill Prediction Engine
      ↓
Pharmacy Portal
      ↓
Treatment Continuity

Technology Stack
Frontend
HTML5
CSS3
JavaScript
Backend
FastAPI
Python
Artificial Intelligence
Qwen 3 LLM
Ollama
Computer Vision
OpenCV
PaddleOCR
Voice Technologies
SpeechRecognition
Edge-TTS
Database
SQLite

Installation
Clone Repository
git clone https://github.com/dineshofficialwrk-dev/MedVoice.git
cd MedVoice
Create Virtual Environment
python -m venv .venv
Activate Environment

Windows:

.venv\Scripts\activate
Install Dependencies
pip install -r requirements.txt
Run Application
uvicorn app:app --reload
