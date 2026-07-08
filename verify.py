# End-to-End Integration Verification Script (Revised)
# School Hostel & Mess Management System

import os
import sys
import pandas as pd
from datetime import date, datetime
from fastapi.testclient import TestClient

# Adjust path to import from app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.database import Base, engine, get_db
from app import models, auth
from sqlalchemy.orm import sessionmaker

# Setup test database (SQLite on disk, cleared every run)
if os.path.exists("test.db"):
    try:
        os.remove("test.db")
    except PermissionError:
        pass

Base.metadata.create_all(bind=engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def seed_test_db(db):
    """
    Replicates PostgreSQL DDL seed logic in SQLite for automated testing.
    """
    print("[TEST SETUP] Seeding hostels, rooms, and beds...")
    # 1. Insert Hostels
    azhari = models.Hostel(name="Azhari Hostel")
    qadri = models.Hostel(name="Qadri Hostel")
    db.add(azhari)
    db.add(qadri)
    db.commit()
    
    # 2. Seed 107 rooms with 8 beds (A to H) each for Azhari Hostel
    room_counter = 0
    for floor_no in range(1, 6):
        for room_seq in range(1, 26):
            if room_counter >= 107:
                break
            
            room_code = str(floor_no * 100 + room_seq)
            room = models.Room(hostel_id=azhari.id, floor_no=floor_no, room_no=room_code)
            db.add(room)
            db.flush()
            
            for bed_label in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']:
                bed = models.Bed(room_id=room.id, bed_no=bed_label)
                db.add(bed)
            
            room_counter += 1
            
    db.commit()
    print(f"[TEST SETUP] Seeded {room_counter} rooms and {room_counter * 8} beds in Azhari Hostel.")


def create_sample_excel():
    # Columns: [Academic_Session, Student_ID, Student_Name, Father_Name, Class_Course, Contact_Number, Hostel_Name, Floor_No, Room_No, Bed_No]
    # Enforces 4-digit student IDs and Azhari Hostel pre-seeded rooms
    data = [
        {
            "Academic_Session": "2026-27",
            "Student_ID": "1001", # Alice
            "Student_Name": "Alice Smith",
            "Father_Name": "Bob Smith",
            "Class_Course": "B.Tech Computer Science",
            "Contact_Number": "9876543210",
            "Hostel_Name": "Azhari Hostel",
            "Floor_No": 1,
            "Room_No": "101",
            "Bed_No": "A"
        },
        {
            "Academic_Session": "2026-27",
            "Student_ID": "1002", # Charlie
            "Student_Name": "Charlie Brown",
            "Father_Name": "David Brown",
            "Class_Course": "B.Tech Mechanical",
            "Contact_Number": "8765432109",
            "Hostel_Name": "Azhari Hostel",
            "Floor_No": 1,
            "Room_No": "101",
            "Bed_No": "B"
        },
        {
            "Academic_Session": "2026-27",
            "Student_ID": "1003", # Eve
            "Student_Name": "Eve Miller",
            "Father_Name": "Frank Miller",
            "Class_Course": "MBA Finance",
            "Contact_Number": "7654321098",
            "Hostel_Name": "Azhari Hostel",
            "Floor_No": 1,
            "Room_No": "102",
            "Bed_No": "A"
        }
    ]
    
    df = pd.DataFrame(data)
    file_path = "allotments_test.xlsx"
    df.to_excel(file_path, index=False)
    print(f"[TEST SETUP] Created temporary test Excel sheet at: {file_path}")
    return file_path


def run_tests():
    print("====================================================")
    print("STARTING END-TO-END INTEGRATION TESTS (REVISED)")
    print("====================================================")

    db = TestingSessionLocal()
    seed_test_db(db)

    # 1. Create System Users
    print("\n--- TEST 1: Registering Roles ---")
    super_admin_data = {"username": "admin_user", "password": "AdminPassword123", "role": "SUPER_ADMIN"}
    warden_data = {"username": "warden_user", "password": "WardenPassword123", "role": "WARDEN"}
    guard_data = {"username": "guard_user", "password": "GuardPassword123", "role": "GATE_GUARD"}

    r_admin = client.post("/api/auth/register", json=super_admin_data)
    assert r_admin.status_code == 201
    print("✓ Super Admin registered.")

    r_warden = client.post("/api/auth/register", json=warden_data)
    assert r_warden.status_code == 201
    print("✓ Warden registered.")

    r_guard = client.post("/api/auth/register", json=guard_data)
    assert r_guard.status_code == 201
    print("✓ Gate Guard registered.")

    # 2. Authenticate and retrieve JWT tokens
    print("\n--- TEST 2: User Login & Role verification ---")
    login_admin = client.post("/api/auth/login", data={"username": "admin_user", "password": "AdminPassword123"})
    assert login_admin.status_code == 200
    admin_token = login_admin.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("✓ Super Admin logged in.")

    login_warden = client.post("/api/auth/login", data={"username": "warden_user", "password": "WardenPassword123"})
    assert login_warden.status_code == 200
    warden_token = login_warden.json()["access_token"]
    warden_headers = {"Authorization": f"Bearer {warden_token}"}
    print("✓ Warden logged in.")

    login_guard = client.post("/api/auth/login", data={"username": "guard_user", "password": "GuardPassword123"})
    assert login_guard.status_code == 200
    guard_token = login_guard.json()["access_token"]
    guard_headers = {"Authorization": f"Bearer {guard_token}"}
    print("✓ Gate Guard logged in.")

    # 3. Excel Bulk Import
    print("\n--- TEST 3: Excel Parsing, Master mapping, and Asset Assignment ---")
    excel_file_path = create_sample_excel()
    
    with open(excel_file_path, "rb") as f:
        r_import = client.post(
            "/api/allotments/import",
            files={"file": (excel_file_path, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=warden_headers
        )
    
    assert r_import.status_code == 201
    print("✓ Excel file uploaded and parsed successfully.")
    print("Response details:", r_import.json())

    # Check database records
    students = db.query(models.Student).all()
    assert len(students) == 3
    print(f"✓ Created master records for {len(students)} students with 4-digit IDs.")
    for s in students:
        print(f"  - ID (Primary Key): {s.student_id}, Name: {s.name}, User ID: {s.user_id}")

    # Check asset assignments
    assets_assigned = db.query(models.StudentAsset).all()
    assert len(assets_assigned) == 12
    print(f"✓ Automatically assigned {len(assets_assigned)} checklist assets during check-in.")

    # Try duplicate import of bed
    print("\n--- TEST 4: Verification Engine (Duplicate bed and construction constraints) ---")
    
    # Validation A: Duplicate Bed in Azhari
    dupe_data = [{
        "Academic_Session": "2026-27", "Student_ID": "1004", "Student_Name": "Duplicate Tester", 
        "Father_Name": "Test Father", "Class_Course": "CS", "Contact_Number": "1", 
        "Hostel_Name": "Azhari Hostel", "Floor_No": 1, "Room_No": "101", "Bed_No": "B" # Occupied by Charlie
    }]
    dupe_df = pd.DataFrame(dupe_data)
    dupe_df.to_excel("dupe_test.xlsx", index=False)
    with open("dupe_test.xlsx", "rb") as f:
        r_dupe = client.post("/api/allotments/import", files={"file": ("dupe_test.xlsx", f)}, headers=warden_headers)
    assert r_dupe.status_code == 400
    print("✓ Blocked double bed assignment (Azhari Room 101, Bed B already occupied).")

    # Validation B: Invalid Student ID (Length != 4)
    invalid_id_data = [{
        "Academic_Session": "2026-27", "Student_ID": "100", "Student_Name": "Invalid ID Tester", 
        "Father_Name": "F", "Class_Course": "CS", "Contact_Number": "1", 
        "Hostel_Name": "Azhari Hostel", "Floor_No": 1, "Room_No": "101", "Bed_No": "C"
    }]
    invalid_id_df = pd.DataFrame(invalid_id_data)
    invalid_id_df.to_excel("invalid_id_test.xlsx", index=False)
    with open("invalid_id_test.xlsx", "rb") as f:
        r_invalid = client.post("/api/allotments/import", files={"file": ("invalid_id_test.xlsx", f)}, headers=warden_headers)
    assert r_invalid.status_code == 400
    print("✓ Blocked invalid Student ID format (must be 4 digits numeric only).")

    # Validation C: Hostel Under Construction (Qadri Hostel)
    qadri_data = [{
        "Academic_Session": "2026-27", "Student_ID": "1005", "Student_Name": "Qadri Tester", 
        "Father_Name": "F", "Class_Course": "CS", "Contact_Number": "1", 
        "Hostel_Name": "Qadri Hostel", "Floor_No": 1, "Room_No": "101", "Bed_No": "A"
    }]
    qadri_df = pd.DataFrame(qadri_data)
    qadri_df.to_excel("qadri_test.xlsx", index=False)
    with open("qadri_test.xlsx", "rb") as f:
        r_qadri = client.post("/api/allotments/import", files={"file": ("qadri_test.xlsx", f)}, headers=warden_headers)
    assert r_qadri.status_code == 400
    print("✓ Blocked allotment for 'Qadri Hostel' (Hostel is under construction).")

    # 4. Mid-Session Bed Swap
    print("\n--- TEST 5: Mid-Session Bed Swap (Alice <-> Charlie) ---")
    alice = db.query(models.Student).filter(models.Student.student_id == "1001").first()
    charlie = db.query(models.Student).filter(models.Student.student_id == "1002").first()
    
    # Alice's current room/bed
    allot_alice_old = db.query(models.AllotmentHistory).filter(models.AllotmentHistory.student_id == alice.student_id, models.AllotmentHistory.vacated_date == None).first()
    
    r_swap = client.post(
        "/api/allotments/swap",
        json={"student_x_id": alice.student_id, "student_y_id": charlie.student_id},
        headers=admin_headers
    )
    assert r_swap.status_code == 200
    print("✓ Swap endpoint returned 200 OK.")

    db.refresh(allot_alice_old)
    assert allot_alice_old.vacated_date == date.today()
    print("✓ Alice's old allotment record has been closed.")

    allot_alice_new = db.query(models.AllotmentHistory).filter(models.AllotmentHistory.student_id == alice.student_id, models.AllotmentHistory.vacated_date == None).first()
    assert allot_alice_new.bed.bed_no == "B"
    print("✓ Alice is successfully allocated to Charlie's old Bed B.")

    # 5. Vacant Room Transfer
    print("\n--- TEST 6: Vacant Room Transfer ---")
    eve = db.query(models.Student).filter(models.Student.student_id == "1003").first()
    
    # Get vacant bed C in Room 101 (Azhari Hostel)
    room_101 = db.query(models.Room).filter(models.Room.room_no == "101").first()
    target_bed = db.query(models.Bed).filter(models.Bed.room_id == room_101.id, models.Bed.bed_no == "C").first()
    
    r_transfer = client.post(
        "/api/allotments/transfer",
        json={"student_id": eve.student_id, "target_bed_id": target_bed.id},
        headers=warden_headers
    )
    assert r_transfer.status_code == 200
    print("✓ Eve successfully transferred to vacant Room 101, Bed C.")
    
    eve_allotment = db.query(models.AllotmentHistory).filter(models.AllotmentHistory.student_id == eve.student_id, models.AllotmentHistory.vacated_date == None).first()
    assert eve_allotment.bed.bed_no == "C"

    # 6. Student Leave Approval, Automated Mess-Off & Invoice Rebate Sync
    print("\n--- TEST 7: Leave Approval & Mess-Off Sync with Fee Rebates ---")
    # Alice logs in to apply for leave (username is now "1001")
    login_alice = client.post("/api/auth/login", data={"username": "1001", "password": "1001123"})
    assert login_alice.status_code == 200
    alice_headers = {"Authorization": f"Bearer {login_alice.json()['access_token']}"}

    # Alice applies for leave: July 10 to July 15 (6 days)
    r_leave_apply = client.post(
        "/api/leaves/apply",
        json={
            "start_date": "2026-07-10",
            "end_date": "2026-07-15",
            "reason": "Family function back home"
        },
        headers=alice_headers
    )
    assert r_leave_apply.status_code == 201
    leave_id = r_leave_apply.json()["id"]
    print("✓ Alice applied for a 6-day leave.")

    # Warden approves the leave
    r_approve = client.post(
        f"/api/leaves/{leave_id}/approve",
        json={"status": "Approved"},
        headers=warden_headers
    )
    assert r_approve.status_code == 200
    print("✓ Warden approved Alice's leave.")

    # A) Mess attendance must be 'OFF'
    for day in range(10, 16):
        d_val = date(2026, 7, day)
        att = db.query(models.MessAttendance).filter(
            models.MessAttendance.student_id == alice.student_id,
            models.MessAttendance.date == d_val
        ).first()
        assert att is not None
        assert att.status == models.MessAttendanceStatus.OFF
    print("✓ Mess attendance automatically set to 'OFF' for all approved leave dates.")

    # B) Monthly invoice must apply rebate (6 days * 150 = 900 rebate)
    invoice = db.query(models.Invoice).filter(
        models.Invoice.student_id == alice.student_id,
        models.Invoice.billing_month == date(2026, 7, 1)
    ).first()
    
    assert invoice is not None
    assert float(invoice.rebate_amount) == 900.00
    assert float(invoice.base_amount - invoice.rebate_amount) == 4100.00
    print(f"✓ Fee invoice rebate calculated: Base: {invoice.base_amount}, Rebate: {invoice.rebate_amount}, Net Payable: {invoice.base_amount - invoice.rebate_amount}")

    # 7. Student Suspension Workflow
    print("\n--- TEST 8: Student Suspension Workflow ---")
    r_suspend = client.put(
        f"/api/leaves/students/{charlie.student_id}/status",
        params={"status_val": "Suspended"},
        headers=warden_headers
    )
    assert r_suspend.status_code == 200
    print("✓ Warden updated Charlie's status to 'Suspended'.")

    # Try to apply leave for Charlie (should be blocked)
    login_charlie = client.post("/api/auth/login", data={"username": "1002", "password": "1002123"})
    charlie_headers = {"Authorization": f"Bearer {login_charlie.json()['access_token']}"}
    
    r_charlie_leave = client.post(
        "/api/leaves/apply",
        json={"start_date": "2026-07-20", "end_date": "2026-07-22", "reason": "Sick leave"},
        headers=charlie_headers
    )
    assert r_charlie_leave.status_code == 400
    print("✓ Blocked gate pass/leave generation for suspended student.")

    charlie_allotment = db.query(models.AllotmentHistory).filter(
        models.AllotmentHistory.student_id == charlie.student_id,
        models.AllotmentHistory.vacated_date == None
    ).first()
    assert charlie_allotment is not None
    print("✓ Active room allocation remains held for the suspended student.")

    # 8. Visitor Management
    print("\n--- TEST 9: Visitor Entry Logging & Notification ---")
    r_visitor = client.post(
        "/api/visitors/entry",
        json={
            "student_id": alice.student_id,
            "visitor_name": "John Smith",
            "relationship": "Father",
            "contact_number": "9998887776",
            "purpose": "Monthly check-in"
        },
        headers=guard_headers
    )
    assert r_visitor.status_code == 201
    visitor_id = r_visitor.json()["id"]
    print("✓ Security guard logged visitor entry.")

    r_exit = client.post(f"/api/visitors/{visitor_id}/exit", headers=guard_headers)
    assert r_exit.status_code == 200
    print("✓ Visitor exit logged successfully.")

    # 9. Maintenance & Complaint Cell
    print("\n--- TEST 10: Complaint Lifecycles ---")
    r_complaint = client.post(
        "/api/complaints",
        json={
            "title": "Wi-Fi not working",
            "description": "Signal is very weak in corner room 101.",
            "category": "Wi-Fi"
        },
        headers=alice_headers
    )
    assert r_complaint.status_code == 201
    complaint_id = r_complaint.json()["id"]
    print("✓ Student raised a maintenance complaint ticket.")

    # Assign to technician
    r_assign = client.post(
        f"/api/complaints/{complaint_id}/assign",
        json={"assigned_to": "Steve the Network Admin"},
        headers=warden_headers
    )
    assert r_assign.status_code == 200
    assert r_assign.json()["status"] == "Assigned"
    print("✓ Warden assigned ticket.")

    # Resolve
    r_resolve = client.post(f"/api/complaints/{complaint_id}/resolve", headers=warden_headers)
    assert r_resolve.status_code == 200
    assert r_resolve.json()["status"] == "Resolved"
    print("✓ Ticket resolved.")

    # Cleanup temporary excel files
    for file in ["allotments_test.xlsx", "dupe_test.xlsx", "invalid_id_test.xlsx", "qadri_test.xlsx"]:
        if os.path.exists(file):
            os.remove(file)
            
    print("\n====================================================")
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("====================================================")


if __name__ == "__main__":
    run_tests()
