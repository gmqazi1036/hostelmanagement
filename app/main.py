from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, allotment, leave, visitor, complaint, asset, invoice
from app.database import Base, engine, SessionLocal
from app import models

# 1. Auto-create database tables at boot time
Base.metadata.create_all(bind=engine)

# 2. Auto-seed database if running on SQLite (zero-config demo fallback)
if "sqlite" in str(engine.url):
    db = SessionLocal()
    try:
        if db.query(models.Hostel).count() == 0:
            print("[BOOTSTRAP] Auto-seeding SQLite database for demo...")
            azhari = models.Hostel(name="Azhari Hostel")
            qadri = models.Hostel(name="Qadri Hostel")
            db.add(azhari)
            db.add(qadri)
            db.commit()
            
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
            print(f"[BOOTSTRAP] Successfully seeded {room_counter} rooms and {room_counter * 8} beds.")
    except Exception as e:
        print(f"[BOOTSTRAP ERROR] Seeding failed: {str(e)}")
        db.rollback()
    finally:
        db.close()

app = FastAPI(
    title="School Hostel & Mess Management System API",
    description="A robust, secure, and transaction-safe API for managing hostel rooms, mid-session dynamics, leaves, automatic rebate calculations, visitors, assets, and complaints.",
    version="1.0.0"
)

# Enable CORS for web portals and mobile apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(allotment.router)
app.include_router(leave.router)
app.include_router(visitor.router)
app.include_router(complaint.router)
app.include_router(asset.router)
app.include_router(invoice.router)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "School Hostel & Mess Management Backend",
        "documentation": "/docs"
    }
