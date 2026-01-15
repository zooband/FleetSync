from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.auth_core import auth_middleware
from app.routers import auth, centers, drivers, fleets, incidents, orders, vehicles, managers

app = FastAPI(swagger_ui_parameters={"persistAuthorization": True})

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


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    components = openapi_schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "Token",
    }

    # 默认所有接口都需要 Bearer token；具体接口可覆盖。
    openapi_schema["security"] = [{"BearerAuth": []}]

    # 登录接口不需要鉴权
    login_path = openapi_schema.get("paths", {}).get("/api/auth/login")
    if login_path and "post" in login_path:
        login_path["post"]["security"] = []

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
