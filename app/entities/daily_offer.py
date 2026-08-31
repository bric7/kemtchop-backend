# app/entities/daily_offer.py
import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base
from app.enums import ProductionStatus

class DailyOffer(Base):
    __tablename__ = "daily_offers"
    
    # ✅ Contrainte d'unicité : Un produit ne peut avoir qu'une seule offre par date
    __table_args__ = (
        UniqueConstraint('product_id', 'target_date', name='uq_product_date'),
    )
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    target_date = Column(Date, nullable=False, index=True)
    
    # Seuil et capacité
    minimum_threshold = Column(Integer, default=4, nullable=False)
    max_capacity = Column(Integer, default=20, nullable=False)
    
    # Prix et revenus
    price_per_unit = Column(Float, nullable=False)
    current_revenue = Column(Float, default=0.0, nullable=False)
    
    # Compteurs
    reserved_portions = Column(Integer, default=0, nullable=False)
    
    # Statut et traçabilité
    status = Column(String(50), default=ProductionStatus.PROPOSED.value, nullable=False)
    triggered_at = Column(DateTime, nullable=True)
    
    # ✅ NOUVEAUX CHAMPS : Traçabilité du déclenchement
    triggered_by_admin = Column(Boolean, default=False, nullable=False)
    admin_override_reason = Column(String(255), nullable=True)
    
    # Métadonnées
    bonus_description = Column(String(255), nullable=True)
    admin_notes = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relations
    product = relationship("Product")
    orders = relationship("Order", backref="daily_offer", lazy="dynamic")
    
    @property
    def is_threshold_reached(self) -> bool:
        return self.reserved_portions >= self.minimum_threshold
    
    @property
    def remaining_to_trigger(self) -> int:
        return max(0, self.minimum_threshold - self.reserved_portions)
    
    @property
    def remaining_capacity(self) -> int:
        return max(0, self.max_capacity - self.reserved_portions)
    
    @property
    def progress_percentage(self) -> float:
        if self.minimum_threshold == 0:
            return 100.0
        return min(100.0, (self.reserved_portions / self.minimum_threshold) * 100)
    

    @property
    def status_enum(self) -> ProductionStatus:
        return ProductionStatus(self.status)
    
    def can_transition_to(self, new_status: ProductionStatus) -> bool:
        """Vérifie si la transition d'état est valide selon la machine d'état v3.0"""
        current = self.status_enum
        
        # Transitions autorisées
        valid_transitions = {
            ProductionStatus.PROPOSED: [ProductionStatus.RESERVATION, ProductionStatus.CONFIRMED, ProductionStatus.CANCELLED],
            ProductionStatus.RESERVATION: [ProductionStatus.CONFIRMED, ProductionStatus.CANCELLED],
            ProductionStatus.CONFIRMED: [ProductionStatus.COOKING, ProductionStatus.CANCELLED],
            ProductionStatus.COOKING: [ProductionStatus.READY, ProductionStatus.CANCELLED],
            ProductionStatus.READY: [ProductionStatus.COMPLETED],
            ProductionStatus.COMPLETED: [],
            ProductionStatus.CANCELLED: [],
        }
        
        return new_status in valid_transitions.get(current, [])

    # ✅ CORRECTION FINALE : Suppression des backrefs pour éviter les conflits avec les modèles Product et Order
    product = relationship("Product")
    orders = relationship("Order", lazy="dynamic")