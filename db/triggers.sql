-- PostgreSQL Trigger Functions and Event Handlers
-- School Hostel & Mess Management System

-- 1. Prevent Suspended Students from Applying for Leaves
CREATE OR REPLACE FUNCTION fn_prevent_suspended_student_leaves()
RETURNS TRIGGER AS $$
DECLARE
    student_curr_status student_status;
BEGIN
    SELECT status INTO student_curr_status FROM students WHERE id = NEW.student_id;
    IF student_curr_status = 'Suspended' THEN
        RAISE EXCEPTION 'Student is currently Suspended. Gate pass / Leave application is blocked.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_prevent_suspended_leaves
BEFORE INSERT OR UPDATE ON leave_records
FOR EACH ROW
WHEN (NEW.status = 'Pending' OR NEW.status = 'Approved')
EXECUTE FUNCTION fn_prevent_suspended_student_leaves();


-- 2. Handle Student Lifecycle Status Changes (Suspension / Re-activation)
CREATE OR REPLACE FUNCTION fn_handle_student_status_change()
RETURNS TRIGGER AS $$
BEGIN
    -- If a student is suspended, freeze their daily active mess attendance from today onwards
    IF NEW.status = 'Suspended' AND OLD.status <> 'Suspended' THEN
        -- Insert/Update future mess attendance to 'SUSPENDED'
        -- For simplicity, we upsert future records for the next 30 days as 'SUSPENDED' or update existing future ones.
        -- We will update existing future records to 'SUSPENDED'
        UPDATE mess_attendance 
        SET status = 'SUSPENDED' 
        WHERE student_id = NEW.id AND date >= CURRENT_DATE;
        
    -- If a student is re-activated, restore suspended future mess attendance to 'ON'
    ELSIF NEW.status = 'Active' AND OLD.status = 'Suspended' THEN
        UPDATE mess_attendance 
        SET status = 'ON' 
        WHERE student_id = NEW.id AND date >= CURRENT_DATE AND status = 'SUSPENDED';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_student_status_change
AFTER UPDATE ON students
FOR EACH ROW
WHEN (OLD.status IS DISTINCT FROM NEW.status)
EXECUTE FUNCTION fn_handle_student_status_change();


-- 3. Automated Leave & Mess-Off Sync with Invoice Rebate Calculation
CREATE OR REPLACE FUNCTION fn_handle_leave_approval()
RETURNS TRIGGER AS $$
DECLARE
    d DATE;
    billing_month_start DATE;
    daily_rebate_rate NUMERIC(10, 2) := 150.00; -- Standard per-day mess rebate rate
    days_in_month INTEGER;
BEGIN
    -- Only run when status changes to 'Approved'
    IF NEW.status = 'Approved' AND (OLD.status IS DISTINCT FROM 'Approved') THEN
        
        -- Loop through dates and mark Mess Attendance as 'OFF'
        FOR d IN SELECT generate_series(NEW.start_date::timestamp, NEW.end_date::timestamp, '1 day'::interval)::date LOOP
            -- Upsert mess attendance for that day as 'OFF'
            INSERT INTO mess_attendance (student_id, date, status)
            VALUES (NEW.student_id, d, 'OFF')
            ON CONFLICT (student_id, date) 
            DO UPDATE SET status = 'OFF';
        END LOOP;

        -- Calculate fee rebate and apply to monthly invoices
        -- We group leave days by calendar month (since a leave can span across months, e.g., July 28 to Aug 3)
        FOR billing_month_start, days_in_month IN 
            SELECT 
                date_trunc('month', d)::date AS m_start,
                COUNT(*)::int AS num_days
            FROM generate_series(NEW.start_date::timestamp, NEW.end_date::timestamp, '1 day'::interval) d
            GROUP BY date_trunc('month', d)::date
        LOOP
            -- Check if invoice exists for this student and month
            -- If it doesn't exist, create it with base amount (default 5000) and computed rebate
            -- If it exists, update it by adding the computed rebate
            INSERT INTO invoices (student_id, billing_month, base_amount, rebate_amount, status)
            VALUES (
                NEW.student_id, 
                billing_month_start, 
                5000.00, 
                LEAST(5000.00, days_in_month * daily_rebate_rate), 
                'Unpaid'
            )
            ON CONFLICT (student_id, billing_month)
            DO UPDATE SET rebate_amount = LEAST(invoices.base_amount, invoices.rebate_amount + (days_in_month * daily_rebate_rate));
        END LOOP;
        
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_leave_approval_sync
AFTER UPDATE ON leave_records
FOR EACH ROW
EXECUTE FUNCTION fn_handle_leave_approval();


-- 4. Helper View for Kitchen Inventory / Daily Food Count Calculator
-- Calculates active mess counts per day
CREATE OR REPLACE VIEW view_daily_meal_count AS
SELECT 
    date,
    COUNT(*) FILTER (WHERE status = 'ON') AS meal_prep_count
FROM mess_attendance
GROUP BY date;
