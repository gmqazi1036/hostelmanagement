# School Hostel & Mess Management System (Backend API)

A robust, highly scalable, and normalized backend architecture for managing school hostels, mid-session bed assignments, automated leaves, mess attendances, visitor logs, complaints, and asset tracking.

## Technology Stack
- **Framework**: Python (FastAPI)
- **Database**: PostgreSQL (Production) / SQLite (Testing/Development)
- **ORM & Connection Pooling**: SQLAlchemy
- **Data Validation & Verification**: Pydantic v2
- **Excel Parsing Engine**: Pandas & OpenPyxl
- **Security & Authorization**: JWT (JSON Web Tokens) & Bcrypt password hashing

---

## Key Features & Business Logic Implemented

1. **Excel Parser & Data Validation Engine**:
   - Parses Excel/CSV student allocations bulk sheets.
   - Enforces unique checks: No duplicate Bed assignments or duplicate student records in a single session.
   - Master record translator: Links returning students to existing master records and creates new student/user profiles for first-time enrollments.
   
2. **Multi-Year Historical Data Retention**:
   - Relational database schema tracks changes in room allocations across academic years using the `allotment_history` table.
   
3. **Mid-Session Room Dynamics**:
   - **Bed Swap**: Safely exchanges room/bed allocations between two students inside an atomic database transaction. Retains historical vacated dates for auditable history.
   - **Vacant Room Transfer**: Instantly transfers a student to any available empty bed.

4. **Student Lifecycle Workflow**:
   - Lifecycles: `Active`, `Suspended`, `Left`, `Graduated`.
   - **Suspension Action**: Suspended students are instantly blocked from gate pass applications and have their future daily mess attendance frozen to `SUSPENDED`. However, their room allotment remains held until they are explicitly evicted.

5. **Automated Leave & Mess-Off Sync (Trigger Logic)**:
   - When a warden marks a Student's Leave/Gate Pass as "Approved" for a date range:
     1. Mess attendance is set to `OFF` for all dates in the range.
     2. Daily mess meal counts automatically subtract the student.
     3. An invoice rebate is calculated (daily rebate rate = 150.00) and deducted from the student's monthly bill automatically.

6. **Complementary Modules**:
   - **Complaint Cell**: Digital ticketing cell with Category and Status (`Pending`, `Assigned`, `Resolved`).
   - **Visitor Management**: Log incoming parent/visitor details and triggers a student SMS/notification.
   - **Asset Checklist**: Tracks checklist items (Bed Frame, Mattress, Study Table, Room Key) assigned to student room allotments to audit during year-end check-out.

---

## File Structure

```
/HostelManagement
├── db/
│   ├── schema.sql         # SQL DDL Script (PostgreSQL definition)
│   └── triggers.sql       # PostgreSQL Trigger Functions and Event Handlers
├── app/
│   ├── config.py          # Environment settings loader
│   ├── database.py        # SQLAlchemy engine and session setup
│   ├── models.py          # Database ORM models
│   ├── schemas.py         # Pydantic schema validation structures
│   ├── auth.py            # JWT token validation & security dependencies
│   ├── routers/
│   │   ├── auth.py        # Login, registrations
│   │   ├── allotment.py   # Excel parsing, mid-session swaps, capacity details
│   │   ├── leave.py       # Gate passes, student suspensions
│   │   ├── visitor.py     # Visitor logs
│   │   ├── complaint.py   # Maintenance workflows
│   │   └── asset.py       # Check-in asset checks
│   └── main.py            # FastAPI registration entrypoint
├── requirements.txt       # Dependencies list
├── verify.py              # Automated test client script (SQLite in-memory)
└── README.md              # Documentation
```

---

## Setup & Local Installation

### Prerequisites
- Python 3.12+
- PostgreSQL (for production database)

### Installation
1. Install package requirements:
   ```bash
   pip3 install -r requirements.txt
   ```

2. (Optional) Run the automated validation script to verify all core routes, database relations, and rebate calculations:
   ```bash
   DATABASE_URL=sqlite:///test.db python3 verify.py
   ```

---

## Database Migration (PostgreSQL Setup)

To deploy the production-ready PostgreSQL tables and triggers:
1. Log into your PostgreSQL instance:
   ```bash
   psql -U postgres -h localhost -d your_database
   ```
2. Execute the schema definition script:
   ```bash
   \i db/schema.sql
   ```
3. Deploy the database-level triggers:
   ```bash
   \i db/triggers.sql
   ```

---

## Running the API Server

Launch the FastAPI application using `uvicorn`:
```bash
python3 -m uvicorn app.main:app --reload --port 8000
```
Once started, the Interactive Documentation (Swagger UI) is available at:
- **Swagger Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Role-Based Route Securitization

- **SUPER_ADMIN**: Can register system users, execute bed swaps, inspect logs.
- **WARDEN**: Can approve/reject leaves, update student statuses (suspensions), assign maintenance tasks, view capacity.
- **GATE_GUARD**: Can log visitor entries/exits and verify student pass statuses.
- **STUDENT**: Can apply for leaves, raise complaints, view allocated assets, check monthly invoices.
