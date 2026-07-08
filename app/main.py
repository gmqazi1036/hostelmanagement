from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, allotment, leave, visitor, complaint, asset, invoice

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
