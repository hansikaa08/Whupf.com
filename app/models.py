from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base= declarative_base()

class User(Base):
    __tablename__="users"
    id=Column(Integer, primary_key=True)
    email=Column(String)
    phone=Column(String)

class Notification(Base):
    __tablename__="notifications"
    id=Column(Integer, primary_key=True, index=True)
    user_id=Column(Integer)
    message=Column(String)
    notification_type=Column(String)
    status=Column(String, default="pending")

