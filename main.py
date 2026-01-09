from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.auth.routes import router as auth_router
from app.chat.routes import router as chat_router
from app.auth.dependencies import get_current_user, require_superadmin, require_customer
from app.models import User, UserRole

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered e-commerce backend with Gemini & Magento 2 - JWT Authentication",
    version=settings.APP_VERSION
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(chat_router)


@app.get("/")
def home():
    """Welcome endpoint"""
    return {
        "message": "Welcome, I'm Telia",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "authentication": "JWT Bearer Token"
    }


@app.get("/protected")
def protected_route(current_user: User = Depends(get_current_user)):
    """
    Example of a protected route
    Requires authentication
    """
    return {
        "message": f"Hello {current_user.username}!",
        "user_id": current_user.id,
        "role": current_user.role.value,
        "email": current_user.email
    }


@app.get("/admin-only")
def admin_only_route(current_user: User = Depends(require_superadmin)):
    """
    Example of a superadmin-only route
    Requires superadmin role
    """
    return {
        "message": f"Welcome superadmin {current_user.username}!",
        "access_level": "superadmin",
        "user_id": current_user.id
    }


@app.get("/customer-area")
def customer_area_route(current_user: User = Depends(require_customer)):
    """
    Example of a customer area route
    Accessible by customers and superadmins
    """
    return {
        "message": f"Welcome to customer area, {current_user.username}!",
        "role": current_user.role.value,
        "user_id": current_user.id
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
