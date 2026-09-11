from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()

class PhotoboothSession(Base):
    """Model for storing photobooth user sessions"""
    __tablename__ = 'photobooth_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    phone_number = Column(String(20), nullable=False)
    timestamp = Column(DateTime, default=datetime.now, nullable=False)
    video_path = Column(String(500), nullable=True)
    video_filename = Column(String(200), nullable=True)
    whatsapp_sent = Column(Boolean, default=False)
    whatsapp_sent_at = Column(DateTime, nullable=True)
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'phone_number': self.phone_number,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'video_path': self.video_path,
            'video_filename': self.video_filename,
            'whatsapp_sent': self.whatsapp_sent,
            'whatsapp_sent_at': self.whatsapp_sent_at.strftime('%Y-%m-%d %H:%M:%S') if self.whatsapp_sent_at else None
        }

class AdminUser(Base):
    """Model for admin authentication"""
    __tablename__ = 'admin_users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.now)

# Database setup
DATABASE_URL = "sqlite:///photobooth.db"
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def init_db():
    """Initialize database and create tables"""
    Base.metadata.create_all(bind=engine)
    print("✓ Database initialized successfully")

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_admin_user(username, password):
    """Create initial admin user (run once)"""
    from werkzeug.security import generate_password_hash
    
    db = SessionLocal()
    try:
        existing = db.query(AdminUser).filter_by(username=username).first()
        if existing:
            print(f"Admin user '{username}' already exists")
            return False
        
        admin = AdminUser(
            username=username,
            password_hash=generate_password_hash(password)
        )
        db.add(admin)
        db.commit()
        print(f"✓ Admin user '{username}' created successfully")
        return True
    except Exception as e:
        db.rollback()
        print(f"✗ Error creating admin: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    # Initialize database
    init_db()
    
    # Create default admin (change these credentials!)
    create_admin_user("admin", "admin123")
