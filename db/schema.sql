-- Database Schema DDL for School Hostel & Mess Management System
-- Database Dialect: PostgreSQL

CREATE TYPE user_role AS ENUM ('SUPER_ADMIN', 'WARDEN', 'GATE_GUARD', 'STUDENT');
CREATE TYPE student_status AS ENUM ('Active', 'Suspended', 'Left', 'Graduated');
CREATE TYPE leave_status AS ENUM ('Pending', 'Approved', 'Rejected');
CREATE TYPE mess_status AS ENUM ('ON', 'OFF', 'SUSPENDED');
CREATE TYPE invoice_status AS ENUM ('Unpaid', 'Paid');
CREATE TYPE complaint_status AS ENUM ('Pending', 'Assigned', 'Resolved');
CREATE TYPE asset_condition AS ENUM ('Good', 'Damaged', 'Lost');

-- 1. Users Table (Authentication and Authorization)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role user_role NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for username lookup
CREATE INDEX idx_users_username ON users(username);

-- 2. Students Master Table
CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
    student_id VARCHAR(50) UNIQUE NOT NULL, -- The academic registry student ID (e.g. STU1001)
    name VARCHAR(100) NOT NULL,
    father_name VARCHAR(100) NOT NULL,
    class_course VARCHAR(100) NOT NULL,
    contact_number VARCHAR(20) NOT NULL,
    status student_status NOT NULL DEFAULT 'Active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for quick search on registry Student ID
CREATE INDEX idx_students_student_id ON students(student_id);

-- 3. Academic Sessions Master Table
CREATE TABLE academic_sessions (
    id SERIAL PRIMARY KEY,
    session_name VARCHAR(20) UNIQUE NOT NULL, -- e.g. "2024-25"
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Hostels Master Table
CREATE TABLE hostels (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Rooms Table
CREATE TABLE rooms (
    id SERIAL PRIMARY KEY,
    hostel_id INTEGER NOT NULL REFERENCES hostels(id) ON DELETE CASCADE,
    floor_no INTEGER NOT NULL,
    room_no VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_hostel_room UNIQUE (hostel_id, room_no)
);

-- 6. Beds Table
CREATE TABLE beds (
    id SERIAL PRIMARY KEY,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    bed_no VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_room_bed UNIQUE (room_id, bed_no)
);

-- 7. Allotment History (Tracks actual bed occupancy over time and across sessions)
CREATE TABLE allotment_history (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    bed_id INTEGER NOT NULL REFERENCES beds(id) ON DELETE CASCADE,
    session_id INTEGER NOT NULL REFERENCES academic_sessions(id) ON DELETE CASCADE,
    allotment_date DATE NOT NULL DEFAULT CURRENT_DATE,
    vacated_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_vacated_date CHECK (vacated_date IS NULL OR vacated_date >= allotment_date)
);

-- CRITICAL Constraint: A student can have at most one active (unvacated) allotment per session
CREATE UNIQUE INDEX uq_student_active_session_allotment 
ON allotment_history (student_id, session_id) 
WHERE (vacated_date IS NULL);

-- CRITICAL Constraint: A bed can have at most one active (unvacated) allotment per session
CREATE UNIQUE INDEX uq_bed_active_session_allotment 
ON allotment_history (bed_id, session_id) 
WHERE (vacated_date IS NULL);

-- Indexes for active/historical lookups
CREATE INDEX idx_allotment_active ON allotment_history(student_id) WHERE (vacated_date IS NULL);
CREATE INDEX idx_allotment_history_student ON allotment_history(student_id);

-- 8. Leave Records / Gate Passes
CREATE TABLE leave_records (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    reason TEXT NOT NULL,
    status leave_status NOT NULL DEFAULT 'Pending',
    approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL, -- Warden's user ID
    approved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_leave_dates CHECK (end_date >= start_date)
);

CREATE INDEX idx_leave_records_student ON leave_records(student_id);
CREATE INDEX idx_leave_records_status ON leave_records(status);

-- 9. Mess Attendance Table (Daily status per student)
CREATE TABLE mess_attendance (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    status mess_status NOT NULL DEFAULT 'ON',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_student_date_attendance UNIQUE (student_id, date)
);

CREATE INDEX idx_mess_attendance_date ON mess_attendance(date);
CREATE INDEX idx_mess_attendance_student_date ON mess_attendance(student_id, date);

-- 10. Invoices Table (Monthly Mess & Hostel Bills)
CREATE TABLE invoices (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    billing_month DATE NOT NULL, -- Represented as the first day of the month (e.g. 2026-07-01)
    base_amount NUMERIC(10, 2) NOT NULL DEFAULT 5000.00,
    rebate_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    status invoice_status NOT NULL DEFAULT 'Unpaid',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_student_month UNIQUE (student_id, billing_month)
);

CREATE INDEX idx_invoices_student_month ON invoices(student_id, billing_month);

-- 11. Complaints and Maintenance Tickets
CREATE TABLE complaints (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    title VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(50) NOT NULL, -- e.g. Plumbing, Electrical, Wi-Fi
    status complaint_status NOT NULL DEFAULT 'Pending',
    assigned_to VARCHAR(100), -- Name of worker or technician
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_complaints_status ON complaints(status);

-- 12. Visitor Management Logs
CREATE TABLE visitors (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    visitor_name VARCHAR(100) NOT NULL,
    relationship VARCHAR(50) NOT NULL,
    contact_number VARCHAR(20) NOT NULL,
    entry_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    exit_time TIMESTAMP WITH TIME ZONE,
    purpose TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 13. Assets Master Table
CREATE TABLE assets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

-- 14. Student Allocated Assets
CREATE TABLE student_assets (
    id SERIAL PRIMARY KEY,
    allotment_id INTEGER NOT NULL REFERENCES allotment_history(id) ON DELETE CASCADE,
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    serial_no VARCHAR(100), -- Key number, mattress barcode, table identifier
    condition asset_condition NOT NULL DEFAULT 'Good',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_allotment_asset UNIQUE (allotment_id, asset_id)
);
