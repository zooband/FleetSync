from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth_core import auth_middleware
from app.routers import auth, centers, drivers, fleets, incidents, orders, vehicles, managers

app = FastAPI()

app.middleware("http")(auth_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(drivers.router)
app.include_router(vehicles.router)
app.include_router(orders.router)
app.include_router(incidents.router)
app.include_router(fleets.router)
app.include_router(centers.router)
app.include_router(managers.router)
