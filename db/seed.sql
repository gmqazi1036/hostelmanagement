-- Seed Script for School Hostel & Mess Management System
-- Populates Azhari Hostel (107 rooms, 8 beds each) and Qadri Hostel (Under Construction)

-- 1. Insert Hostels
INSERT INTO hostels (name) VALUES ('Azhari Hostel') ON CONFLICT (name) DO NOTHING;
INSERT INTO hostels (name) VALUES ('Qadri Hostel') ON CONFLICT (name) DO NOTHING;

-- 2. Populate Rooms and Beds for Azhari Hostel (107 Rooms, 8 Beds each = 856 Beds)
DO $$
DECLARE
    azhari_hostel_id INT;
    floor_no INT;
    room_seq INT;
    room_code VARCHAR(20);
    inserted_room_id INT;
    bed_label CHAR(1);
    room_counter INT := 0;
BEGIN
    -- Get ID of Azhari Hostel
    SELECT id INTO azhari_hostel_id FROM hostels WHERE name = 'Azhari Hostel';

    -- Generate rooms dynamically across 5 floors (up to 107 rooms)
    FOR floor_no IN 1..5 LOOP
        FOR room_seq IN 1..25 LOOP
            -- Break if we have generated all 107 rooms
            IF room_counter >= 107 THEN
                EXIT;
            END IF;
            
            room_code := (floor_no * 100 + room_seq)::VARCHAR;
            
            -- Insert Room
            INSERT INTO rooms (hostel_id, floor_no, room_no)
            VALUES (azhari_hostel_id, floor_no, room_code)
            ON CONFLICT (hostel_id, room_no) DO UPDATE SET floor_no = EXCLUDED.floor_no
            RETURNING id INTO inserted_room_id;
            
            -- Insert 8 beds for this room (A to H)
            FOREACH bed_label IN ARRAY ARRAY['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'] LOOP
                INSERT INTO beds (room_id, bed_no)
                VALUES (inserted_room_id, bed_label)
                ON CONFLICT (room_id, bed_no) DO NOTHING;
            END LOOP;
            
            room_counter := room_counter + 1;
        END LOOP;
    END LOOP;
    
    RAISE NOTICE 'Seeded % rooms with 8 beds each in Azhari Hostel successfully.', room_counter;
END $$;
