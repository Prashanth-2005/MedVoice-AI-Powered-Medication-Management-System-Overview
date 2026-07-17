import datetime

import smtplib
from email.mime.text import MIMEText
try:
    from twilio.rest import Client
except ImportError:
    Client = None # Fallback if library missing

# CONFIGURATION (USER MUST UPDATE THESE)
EMAIL_CONFIG = {
    "sender_email": "dineshwarrior36@gmail.com",
    "app_password": "mnup shnt yfgo anla" # 16-digit App Password
}

TWILIO_CONFIG = {
    "account_sid": "YOUR_TWILIO_SID",
    "auth_token": "YOUR_TWILIO_AUTH_TOKEN",
    "from_number": "+1234567890"
}

LOG_FILE = "system_events.log"

def log_event(source, message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{source.upper()}] {message}"
    print(entry)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")

def send_email(to_email, subject, message):
    """
    Sends an email using Gmail SMTP.
    """
    # Check if credentials are set, otherwise use Mock Mode
    if "YOUR_" in EMAIL_CONFIG["app_password"]:
        log_event("EMAIL_MOCK", f"Credentials missing. SIMULATING EMAIL to {to_email}")
        print(f"--- EMAIL CONTENT START ---\nSubject: {subject}\nTo: {to_email}\n\n{message}\n--- EMAIL CONTENT END ---")
        return

    try:
        msg = MIMEText(message)
        msg["Subject"] = subject
        msg["From"] = EMAIL_CONFIG["sender_email"]
        msg["To"] = to_email

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_CONFIG["sender_email"], EMAIL_CONFIG["app_password"])
            server.send_message(msg)
        
        log_event("EMAIL_GATEWAY", f"Sent email to {to_email}")
    except Exception as e:
        log_event("EMAIL_FAIL", f"Failed to send email: {e}")
        print(f"EMAIL FAILED: {e}")

def send_sms(to_number, message):
    """
    Sends an SMS using Twilio.
    """
    if not Client:
        log_event("SMS_ERROR", "Twilio library not installed.")
        return

    if "YOUR_" in TWILIO_CONFIG["account_sid"]:
        # Fallback for SMS as well
        log_event("SMS_MOCK", f"Credentials missing. SIMULATING SMS to {to_number}")
        print(f"--- SMS CONTENT ({to_number}) ---\n{message}\n-------------------------")
        return

    try:
        client = Client(TWILIO_CONFIG["account_sid"], TWILIO_CONFIG["auth_token"])
        client.messages.create(
            body=message,
            from_=TWILIO_CONFIG["from_number"],
            to=to_number
        )
        log_event("SMS_GATEWAY", f"Sent SMS to {to_number}")
    except Exception as e:
        log_event("SMS_FAIL", f"Failed to send SMS: {e}")
        print(f"SMS FAILED: {e}")

def notify_pharmacy_refill(medicine_name, quantity, pharmacy_contact):
    msg = f"REFILL REQUEST: {quantity} units of {medicine_name} required for Patient Alex."
    # Check if contact is email or phone
    if "@" in pharmacy_contact:
        send_email(pharmacy_contact, f"Refill Order: {medicine_name}", msg)
    else:
        send_sms(pharmacy_contact, msg)

def notify_family_alert(alert_type, details, family_contact):
    msg = f"ALERT ({alert_type}): {details}"
    if "@" in family_contact:
        send_email(family_contact, f"Family Alert: {alert_type}", msg)
    else:
        send_sms(family_contact, msg)

def notify_payment_request(medicine_name, amount, family_contact):
    """
    sends a payment link to the family member for the refilled medicine.
    """
    payment_link = f"https://pay.medvoice.app/pay?amt={amount}&ref={medicine_name[:3].upper()}"
    subject = f"PAYMENT DUE: {medicine_name} Refill"
    msg = f"""
    INVOICE GENERATED
    -----------------
    Medicine: {medicine_name}
    Amount: Rs.{amount}
    
    The pharmacy has processed the refill request. 
    Please complete the payment to ensure delivery.
    
    Pay Now: {payment_link}
    """
    
    log_event("PAYMENT", f"Payment request of Rs.{amount} sent to {family_contact}")
    
    if "@" in family_contact:
        send_email(family_contact, subject, msg)
    else:
        send_sms(family_contact, f"Payment Due: ₹{amount} for {medicine_name}. Link: {payment_link}")

def send_emergency_alert(patient_name, condition, family_contact):
    """
    Triggers an immediate high-priority alert to the caregiver.
    """
    subject = "🚨 URGENT: EMERGENCY ALERT FROM MEDVOICE"
    msg = f"""
    CRITICAL ALERT
    --------------
    Patient: {patient_name}
    Condition: {condition}
    
    The patient has triggered an emergency request through MedVoice.
    Please contact them or emergency services immediately.
    """
    
    log_event("EMERGENCY", f"EMERGENCY TRIGGERED for {patient_name}. Notifying {family_contact}")
    
    if "@" in family_contact:
        send_email(family_contact, subject, msg)
    else:
        # SMS is usually faster for emergencies
        send_sms(family_contact, f"🚨 EMERGENCY: {patient_name} ({condition}) needs help immediately! Check on them now.")
