from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime
from sqlalchemy.sql import func
from .database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    capacity = Column(Float, nullable=False)
    active = Column(Boolean, default=True)
    default_ready = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    external_id = Column(String, nullable=False)
    address = Column(String)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    window_start = Column(Float, nullable=True)
    window_end = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Depot(Base):
    __tablename__ = "depot"

    id = Column(Integer, primary_key=True)
    address = Column(String)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
