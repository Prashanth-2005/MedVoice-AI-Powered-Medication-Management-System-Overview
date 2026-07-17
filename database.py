import sqlite3
import datetime

DB_NAME = "medicine_assistant.db"

def get_db_connection():
    # Increase timeout to handle concurrent locking (background scheduler + user request)
    conn = sqlite3.connect(DB_NAME, timeout=30.0) 
    conn.row_factory = sqlite3.Row
    try:
        # WAL mode handles concurrency better
        conn.execute("PRAGMA journal_mode=WAL;")
    except:
        pass
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. User Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            disability_type TEXT,
            preferred_language TEXT DEFAULT 'en-US',
            caregiver_pin TEXT
        )
    ''')
    
    # 2. Medicine Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            daily_dosage INTEGER DEFAULT 1, 
            total_tablets INTEGER DEFAULT 30, 
            stock_count INTEGER DEFAULT 0,
            refill_threshold INTEGER DEFAULT 5,
            schedule_time TEXT, -- e.g., "08:00, 20:00"
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    # 3. Intake Log Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS intake_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_id INTEGER,
            intake_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'taken', -- taken, missed
            FOREIGN KEY (medicine_id) REFERENCES medicines (id)
        )
    ''')

    # 4. Contact Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            contact_type TEXT, -- family, pharmacy
            name TEXT,
            email_phone TEXT,
            report_frequency TEXT DEFAULT 'weekly', -- daily, weekly, monthly
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    # 5. Location History Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS location_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            latitude REAL,
            longitude REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # 6. Pharmacies Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS pharmacies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pharmacy_name TEXT NOT NULL,
            license_number TEXT,
            contact TEXT,
            email TEXT,
            address TEXT,
            latitude REAL,
            longitude REAL,
            operating_hours TEXT
        )
    ''')

    # 7. Patient Pharmacy Mapping Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS patient_pharmacy_mapping (
            patient_id INTEGER,
            pharmacy_id INTEGER,
            PRIMARY KEY (patient_id, pharmacy_id)
        )
    ''')

    # 8. Caregiver Messages Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS caregiver_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caregiver_id INTEGER,
            pharmacy_id INTEGER,
            message TEXT,
            sender TEXT, -- 'caregiver' or 'pharmacy'
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 9. Pharmacy Inventory Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS pharmacy_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pharmacy_id INTEGER,
            medicine_name TEXT,
            quantity INTEGER,
            expiry_date TEXT,
            availability_status TEXT
        )
    ''')

    # 10. Refill Requests Table
    # If the old table exists with medicine_id column, drop it to ensure the dashboard schema is correct
    try:
        c.execute("SELECT medicine_id FROM refill_requests LIMIT 1")
        c.execute("DROP TABLE refill_requests")
    except sqlite3.OperationalError:
        pass

    c.execute('''
        CREATE TABLE IF NOT EXISTS refill_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            pharmacy_id INTEGER,
            medicine_name TEXT,
            required_quantity INTEGER,
            status TEXT DEFAULT 'Requested', -- Requested, Approved, Processing, Ready for Pickup, Completed, Rejected
            request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    
    # Seed a default user if none exists
    user_check = c.execute('SELECT count(*) FROM users').fetchone()[0]
    if user_check == 0:
        c.execute("INSERT INTO users (name, disability_type) VALUES ('Alex', 'Visual Impairment')")
        print("Default user created.")
        
    conn.close()
    print("Database initialized with Master Schema.")
    add_mock_data()

def add_mock_data():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get Default User
    user = c.execute("SELECT user_id FROM users LIMIT 1").fetchone()
    if not user:
        return
    uid = user[0]

    # 1. Update User to Raju Kumar
    c.execute("UPDATE users SET name='Raju Kumar', disability_type='Cancer' WHERE user_id=?", (uid,))
    
    # Check if medicines empty
    c.execute('SELECT count(*) FROM medicines')
    if c.fetchone()[0] == 0:
        c.execute('''
            INSERT INTO medicines (user_id, name, daily_dosage, total_tablets, stock_count, refill_threshold, schedule_time)
            VALUES 
            (?, 'Glimepiride', 1, 30, 20, 5, '01:00 PM'),
            (?, 'Budesonide', 1, 30, 15, 5, '09:00 AM'),
            (?, 'Amlodipine', 1, 30, 4, 5, '09:00 AM')
        ''', (uid, uid, uid))
        
        # Add Mock Contacts
        c.execute('''
            INSERT INTO contacts (user_id, contact_type, name, email_phone)
            VALUES 
            (?, 'pharmacy', 'CVS Pharmacy', 'pharmacy@example.com'),
            (?, 'family', 'Alice (Sister)', 'alice@example.com')
        ''', (uid, uid))

    # Seed default pharmacy with ID 1
    c.execute('''
        INSERT OR IGNORE INTO pharmacies (id, pharmacy_name, license_number, contact, email, address, latitude, longitude, operating_hours)
        VALUES (1, 'Apollo Pharmacy', 'LIC123456', '9876543210', 'apollo@example.com', '123 Main St, Bangalore', 12.9716, 77.5946, '9 AM - 9 PM')
    ''')
    
    # Map default patient to pharmacy 1
    c.execute('INSERT OR IGNORE INTO patient_pharmacy_mapping (patient_id, pharmacy_id) VALUES (?, 1)', (uid,))
    
    # Seed pharmacy inventory
    c.execute('SELECT count(*) FROM pharmacy_inventory')
    if c.fetchone()[0] == 0:
        c.execute('''
            INSERT INTO pharmacy_inventory (pharmacy_id, medicine_name, quantity, expiry_date, availability_status)
            VALUES 
            (1, 'Glimepiride', 100, '2027-12-31', 'In Stock'),
            (1, 'Budesonide', 80, '2027-06-30', 'In Stock'),
            (1, 'Amlodipine', 15, '2026-11-30', 'Low Stock')
        ''')
        
    # Seed caregiver messages
    c.execute('SELECT count(*) FROM caregiver_messages')
    if c.fetchone()[0] == 0:
        c.execute('''
            INSERT INTO caregiver_messages (caregiver_id, pharmacy_id, message, sender, timestamp)
            VALUES 
            (?, 1, 'Hi, I need a refill for Amlodipine.', 'caregiver', '2026-06-19 10:00:00'),
            (?, 1, 'Sure, we have initiated the request. Please authorize it on your dashboard.', 'pharmacy', '2026-06-19 10:05:00')
        ''', (uid, uid))
        
    # Seed refill request
    c.execute('SELECT count(*) FROM refill_requests')
    if c.fetchone()[0] == 0:
        c.execute('''
            INSERT INTO refill_requests (patient_id, pharmacy_id, medicine_name, required_quantity, status, request_date)
            VALUES (?, 1, 'Amlodipine', 30, 'Requested', '2026-06-19 10:02:00')
        ''', (uid,))
        
    print("Mock data added and seeded.")
    conn.commit()
    conn.close()

from contextlib import contextmanager

# ... (init_db etc remains, but let's provide the helper)

@contextmanager
def get_db():
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

# ...

def find_medicine_by_name(query_name):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM medicines WHERE lower(name) LIKE ?", ('%' + query_name.lower() + '%',))
        res = c.fetchone()
        medicine = dict(res) if res else None
    return medicine

def log_intake(medicine_id, status='taken'):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE medicines SET stock_count = stock_count - 1 WHERE id = ?", (medicine_id,))
        c.execute("INSERT INTO intake_logs (medicine_id, status) VALUES (?, ?)", (medicine_id, status))
        
        c.execute("SELECT stock_count, name, refill_threshold FROM medicines WHERE id = ?", (medicine_id,))
        res = c.fetchone()
        updated_medicine = dict(res) if res else None
        
    return updated_medicine

def update_location(user_id, lat, lon):
    with get_db() as conn:
        conn.execute("INSERT INTO location_history (user_id, latitude, longitude) VALUES (?, ?, ?)", (user_id, lat, lon))

def get_latest_location(user_id):
    with get_db() as conn:
        res = conn.execute("SELECT latitude, longitude, timestamp FROM location_history WHERE user_id=? ORDER BY timestamp DESC LIMIT 1", (user_id,)).fetchone()
        return dict(res) if res else None

def parse_time_str(t_str):
    t_str = t_str.strip().upper()
    formats = ['%H:%M', '%I:%M %p', '%I:%M%p', '%H:%M:%S']
    for fmt in formats:
        try:
            return datetime.datetime.strptime(t_str, fmt)
        except ValueError:
            continue
    return None

def get_missed_doses():
    missed_alerts = []
    now = datetime.datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    
    with get_db() as conn:
        c = conn.cursor()
        medicines = c.execute('SELECT * FROM medicines').fetchall()
        
        for med in medicines:
            if not med['schedule_time']: continue
            times = [t.strip() for t in med['schedule_time'].split(',')]
            for time_str in times:
                dt_sched = parse_time_str(time_str)
                if not dt_sched: continue
                
                # Check if hour passed
                if now.hour > dt_sched.hour:
                    logs_count = c.execute('''
                        SELECT count(*) FROM intake_logs 
                        WHERE medicine_id = ? AND date(intake_time) = ?
                    ''', (med['id'], today_str)).fetchone()[0]
                    
                    passed_slots = 0
                    for t_check in times:
                        dt_check = parse_time_str(t_check)
                        if dt_check and dt_check.hour < now.hour:
                            passed_slots += 1
                    
                    if logs_count < passed_slots:
                        display_time = dt_sched.strftime("%I:%M %p")
                        missed_alerts.append(f"You have missed your scheduled dose of {med['name']} for {display_time}.")
                        break

    return missed_alerts

def get_db_connection():
    # Increase timeout to handle concurrent locking (background scheduler + user request)
    conn = sqlite3.connect(DB_NAME, timeout=30.0) 
    conn.row_factory = sqlite3.Row
    try:
        # WAL mode handles concurrency better
        conn.execute("PRAGMA journal_mode=WAL;")
    except:
        pass
    return conn


def get_active_reminders():
    reminders = []
    now = datetime.datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    
    with get_db() as conn:
        c = conn.cursor()
        medicines = c.execute('SELECT * FROM medicines').fetchall()
        
        for med in medicines:
            if not med['schedule_time']: continue
            times = [t.strip() for t in med['schedule_time'].split(',')]
            for time_str in times:
                dt_sched = parse_time_str(time_str)
                if not dt_sched: continue
                
                # STRICT TIME CHECK:
                is_active_hour = (now.hour == dt_sched.hour)
                is_time_arrived = (now.minute >= dt_sched.minute)
                
                if is_active_hour and is_time_arrived:
                    logs_today = c.execute('''
                        SELECT count(*) FROM intake_logs 
                        WHERE medicine_id = ? AND date(intake_time) = ?
                    ''', (med['id'], today_str)).fetchone()[0]
                    
                    slots_due = 0
                    for t_check in times:
                        dt_check = parse_time_str(t_check)
                        if dt_check:
                            if now.hour > dt_check.hour:
                                slots_due += 1
                            elif now.hour == dt_check.hour and now.minute >= dt_check.minute:
                                slots_due += 1
                    
                    if logs_today < slots_due:
                        display_time = dt_sched.strftime("%I:%M %p")
                        reminders.append(f"It is {display_time}. Your medication time has arrived. Please take {med['name']}.")
                        break
    return reminders

def get_all_medicines():
    with get_db() as conn:
        rows = conn.execute('SELECT * FROM medicines').fetchall()
        medicines = [dict(row) for row in rows]
    return medicines

def get_user_info():
    with get_db() as conn:
        user_row = conn.execute('SELECT * FROM users LIMIT 1').fetchone()
        user = dict(user_row) if user_row else {}
    return user

def get_patient_summary():
    """Returns a dictionary of patient data sections for granular AI responses."""
    user = get_user_info()
    if not user:
        return {}
    
    medicines = get_all_medicines()
    med_list = []
    low_stock = []
    
    # Yesterday/Today's intake status
    now = datetime.datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    
    with get_db() as conn:
        for m in medicines:
            # Basic Info
            status = f"- {m['name']}: {m['daily_dosage']} daily (Schedule: {m['schedule_time']})"
            stock_info = f" | Stock: {m['stock_count']} left"
            
            # Intake today
            count = conn.execute("SELECT count(*) FROM intake_logs WHERE medicine_id=? AND date(intake_time)=? AND status='taken'", (m['id'], today_str)).fetchone()[0]
            intake_info = f" | Taken today: {count}"
            
            med_list.append(status + stock_info + intake_info)
            
            # Low stock check
            if m['stock_count'] <= m['refill_threshold']:
                low_stock.append(f"{m['name']} (only {m['stock_count']} left)")

    meds_text = "\n".join(med_list) if med_list else "No current prescriptions."
    low_stock_text = ", ".join(low_stock) if low_stock else "All medications have sufficient stock."

    # Caregiver Context
    contacts = get_contacts(contact_type='family')
    caregiver_text = "No specific caregiver notes."
    if contacts:
        caregivers = [f"{c['name']} ({c['report_frequency']} reports)" for c in contacts]
        caregiver_text = "Primary Caregivers: " + ", ".join(caregivers)

    return {
        "identity": f"Name: {user.get('name')}\nCondition: {user.get('disability_type')}",
        "medications": meds_text,
        "alerts": f"Low Stock: {low_stock_text}",
        "caregiver": caregiver_text,
        "language": user.get('preferred_language', 'en-US')
    }

def get_patient_summary_text():
    """Returns a consolidated text summary for the Gemini prompt."""
    data = get_patient_summary()
    if not data: return "No patient profile found."
    
    summary = f"--- PATIENT IDENTITY ---\n{data['identity']}\n\n"
    summary += f"--- MEDICATIONS & STOCK ---\n{data['medications']}\n\n"
    summary += f"--- CRITICAL ALERTS ---\n{data['alerts']}\n\n"
    summary += f"--- CAREGIVER INFO ---\n{data['caregiver']}\n"
    return summary

def get_contacts(contact_type=None):
    with get_db() as conn:
        if contact_type:
            rows = conn.execute('SELECT * FROM contacts WHERE contact_type = ?', (contact_type,)).fetchall()
        else:
            rows = conn.execute('SELECT * FROM contacts').fetchall()
        contacts = [dict(row) for row in rows]
    return contacts

def get_weekly_adherence_report(user_id=None):
    report = {}
    with get_db() as conn:
        c = conn.cursor()
        seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        medicines = c.execute('SELECT * FROM medicines').fetchall()
        
        report = {
            "start_date": seven_days_ago,
            "end_date": datetime.datetime.now().strftime('%Y-%m-%d'),
            "medicines": []
        }
        
        for med in medicines:
            log_count = c.execute('''
                SELECT count(*) FROM intake_logs 
                WHERE medicine_id = ? AND date(intake_time) >= ?
            ''', (med['id'], seven_days_ago)).fetchone()[0]
            
            expected = med['daily_dosage'] * 7
            adherence = 0
            if expected > 0:
                adherence = int((log_count / expected) * 100)
                if adherence > 100: adherence = 100
                
            status = "Excellent"
            if adherence < 80: status = "Good"
            if adherence < 50: status = "Needs Improvement"
            if adherence < 20: status = "Critical Attention Needed"
            
            report["medicines"].append({
                "name": med['name'],
                "taken": log_count,
                "expected": expected,
                "adherence_pct": adherence,
                "status": status
            })
    return report

def reset_and_fill_db(user_data, medicines_data, contact_data=None, pin=None):
    """
    Clears existing data and sets up new user profile + prescriptions + contacts.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Clear Tables (for MVP single user mode)
    c.execute("DELETE FROM intake_logs")
    c.execute("DELETE FROM medicines")
    c.execute("DELETE FROM contacts")
    c.execute("DELETE FROM users")
    
    # 2. Add User with PIN and Preferred Language
    c.execute("INSERT INTO users (name, disability_type, preferred_language, caregiver_pin) VALUES (?, ?, ?, ?)", 
              (user_data.get('name'), user_data.get('disability_type'), user_data.get('preferred_language', 'en-US'), pin))
    user_id = c.lastrowid
    
    # 3. Add Contact (Caregiver)
    if contact_data:
        contact_str = f"EMAIL: {contact_data.get('email')} | MSG: {contact_data.get('phone')}"
        freq = contact_data.get('frequency', 'weekly')
        
        c.execute("INSERT INTO contacts (user_id, contact_type, name, email_phone, report_frequency) VALUES (?, ?, ?, ?, ?)",
                 (user_id, 'family', contact_data.get('name'), contact_str, freq))
        print(f"Added Caregiver: {contact_data.get('name')} (Freq: {freq})")

    # 4. Add Medicines
    for med in medicines_data:
        c.execute('''
            INSERT INTO medicines (user_id, name, daily_dosage, total_tablets, stock_count, refill_threshold, schedule_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            med['name'],
            med['daily_dosage'],
            med['total_tablets'],
            med['stock_count'],
            5, # Default threshold
            med['schedule_time']
        ))
    conn.commit()
    conn.close()

def get_refill_requests(patient_id=None, pharmacy_id=None):
    with get_db() as conn:
        c = conn.cursor()
        if patient_id is not None:
            rows = c.execute('''
                SELECT r.id, r.medicine_name, r.required_quantity, r.status, r.request_date,
                       COALESCE(p.pharmacy_name, 'Apollo Pharmacy') as pharmacy_name
                FROM refill_requests r
                LEFT JOIN pharmacies p ON r.pharmacy_id = p.id
                WHERE r.patient_id = ?
                ORDER BY r.request_date DESC
            ''', (patient_id,)).fetchall()
        elif pharmacy_id is not None:
            rows = c.execute('''
                SELECT r.id, r.medicine_name, r.required_quantity, r.status, r.request_date,
                       u.name as patient_name
                FROM refill_requests r
                LEFT JOIN users u ON r.patient_id = u.user_id
                WHERE r.pharmacy_id = ? OR r.pharmacy_id IS NULL
                ORDER BY r.request_date DESC
            ''', (pharmacy_id,)).fetchall()
        else:
            rows = c.execute('''
                SELECT r.id, r.medicine_name, r.required_quantity, r.status, r.request_date,
                       COALESCE(p.pharmacy_name, 'Apollo Pharmacy') as pharmacy_name, 
                       u.name as patient_name
                FROM refill_requests r
                LEFT JOIN pharmacies p ON r.pharmacy_id = p.id
                LEFT JOIN users u ON r.patient_id = u.user_id
                ORDER BY r.request_date DESC
            ''').fetchall()
        return [dict(row) for row in rows]

def create_refill_request(patient_id, pharmacy_id, medicine_name, required_quantity):
    with get_db() as conn:
        conn.execute('''
            INSERT INTO refill_requests (patient_id, pharmacy_id, medicine_name, required_quantity, status)
            VALUES (?, ?, ?, ?, 'Requested')
        ''', (patient_id, pharmacy_id, medicine_name, required_quantity))

def get_caregiver_messages(pharmacy_id):
    with get_db() as conn:
        c = conn.cursor()
        rows = c.execute('''
            SELECT m.id, m.caregiver_id, m.pharmacy_id, m.message, m.sender, m.timestamp,
                   u.name as caregiver_name, p.pharmacy_name
            FROM caregiver_messages m
            LEFT JOIN users u ON m.caregiver_id = u.user_id
            LEFT JOIN pharmacies p ON m.pharmacy_id = p.id
            WHERE m.pharmacy_id = ?
            ORDER BY m.timestamp ASC
        ''', (pharmacy_id,)).fetchall()
        return [dict(row) for row in rows]

def send_caregiver_message(caregiver_id, pharmacy_id, message, sender):
    with get_db() as conn:
        conn.execute('''
            INSERT INTO caregiver_messages (caregiver_id, pharmacy_id, message, sender)
            VALUES (?, ?, ?, ?)
        ''', (caregiver_id, pharmacy_id, message, sender))

def get_pharmacy_inventory(pharmacy_id):
    with get_db() as conn:
        c = conn.cursor()
        rows = c.execute('SELECT * FROM pharmacy_inventory WHERE pharmacy_id = ?', (pharmacy_id,)).fetchall()
        return [dict(row) for row in rows]

def update_refill_status(request_id, status):
    with get_db() as conn:
        conn.execute('UPDATE refill_requests SET status = ? WHERE id = ?', (status, request_id))
        if status == 'Completed':
            row = conn.execute('SELECT patient_id, pharmacy_id, medicine_name, required_quantity FROM refill_requests WHERE id = ?', (request_id,)).fetchone()
            if row:
                # 1. Replenish patient's local stock
                conn.execute('UPDATE medicines SET stock_count = stock_count + ? WHERE user_id = ? AND name = ?', 
                             (row['required_quantity'], row['patient_id'], row['medicine_name']))
                # 2. Decrement pharmacy's own inventory stock
                conn.execute("UPDATE pharmacy_inventory SET quantity = CASE WHEN quantity >= ? THEN quantity - ? ELSE 0 END WHERE pharmacy_id = ? AND ? LIKE '%' || medicine_name || '%'",
                             (row['required_quantity'], row['required_quantity'], row['pharmacy_id'], row['medicine_name']))

def register_pharmacy(data_dict):
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO pharmacies (pharmacy_name, license_number, contact, email, address, latitude, longitude, operating_hours)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data_dict.get('pharmacy_name'),
            data_dict.get('license_number'),
            data_dict.get('contact'),
            data_dict.get('email'),
            data_dict.get('address'),
            data_dict.get('latitude'),
            data_dict.get('longitude'),
            data_dict.get('operating_hours')
        ))
        return c.lastrowid

def get_all_pharmacies():
    with get_db() as conn:
        c = conn.cursor()
        rows = c.execute('SELECT * FROM pharmacies').fetchall()
        return [dict(row) for row in rows]

def map_patient_to_pharmacy(patient_id, pharmacy_id):
    with get_db() as conn:
        conn.execute('DELETE FROM patient_pharmacy_mapping WHERE patient_id = ?', (patient_id,))
        conn.execute('INSERT INTO patient_pharmacy_mapping (patient_id, pharmacy_id) VALUES (?, ?)', (patient_id, pharmacy_id))
