# app/models/industrial_core.py
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database import Base
import datetime

class Hub(Base):
    __tablename__ = "hubs"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False) # ex: "Yaoundé-Bastos", "Douala-Akwa"
    city = Column(String, nullable=False)               # ex: "Yaoundé"
    capacity_slots = Column(Integer, default=5)         # Nombre max de productions simultanées

class Recipe(Base):
    __tablename__ = "recipes" # L'ancienne table Product reconvertie en R&D
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # ex: "Ndolé Crevettes"
    description = Column(String)
    cooking_time_minutes = Column(Integer, default=120) 
    ideal_temperature = Column(Float, default=85.0)

class DailyMenu(Base):
    __tablename__ = "daily_menus" # L'offre commerciale visible sur le Mobile
    
    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    hub_id = Column(Integer, ForeignKey("hubs.id"))
    date = Column(Date, nullable=False)
    price = Column(Float, nullable=False)
    is_hero = Column(Boolean, default=False)
    
    # Liens
    recipe = relationship("Recipe")
    hub = relationship("Hub")

class Production(Base):
    __tablename__ = "productions" # LA MARMITE PHYSIQUE (L'entité centrale de l'ERP)
    
    id = Column(Integer, primary_key=True, index=True)
    daily_menu_id = Column(Integer, ForeignKey("daily_menus.id"))
    hub_id = Column(Integer, ForeignKey("hubs.id"))
    
    chef_name = Column(String, nullable=False)          # ex: "Amadou"
    status = Column(String, default="voting")          # voting, setup, cooking, packaging, dispatched, completed
    
    min_threshold = Column(Integer, default=30)         # Seuil critique de déclenchement
    max_capacity = Column(Integer, default=90)          # Capacité physique max de la marmite
    current_reserved = Column(Integer, default=0)       # Nombre de portions validées
    
    # Planning Horaire (La Roadmap de la Marmite)
    setup_at = Column(DateTime)                         # Préparation / Mise en place
    cooking_started_at = Column(DateTime)               # Feu allumé
    packaging_started_at = Column(DateTime)             # Conditionnement
    dispatched_at = Column(DateTime)                    # Départ du Hub
    
    daily_menu = relationship("DailyMenu")