# app/entities/daily_offer.py
from sqlalchemy import Column, String, Integer, Float, DateTime, Date, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.database import Base
from app.enums import ProductionStatus


class DailyOffer(Base):
    """
    🍲 DailyOffer = Offre de plat pour une journée spécifique.
    Déclenchement automatique de la production dès que le seuil (minimum_threshold) est atteint.
    """
    __tablename__ = "daily_offers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    suggestion_id = Column(UUID(as_uuid=True), ForeignKey("suggestions.id"), nullable=True)

    # 📅 Date prévue de consommation
    target_date = Column(Date, nullable=False, index=True)

    # 🎯 Seuils et Capacité
    minimum_threshold = Column(Integer, nullable=False, default=4) # ex: 4 portions minimum
    max_capacity = Column(Integer, nullable=True)                  # ex: max 20 portions

    # 💰 Prix unique par portion
    price_per_unit = Column(Float, nullable=False)

    # 📊 Suivi des réservations
    reserved_portions = Column(Integer, nullable=False, default=0)
    current_revenue = Column(Float, nullable=False, default=0.0)

    # 🔄 État de l'offre
    status = Column(
        String(32),
        nullable=False,
        default=ProductionStatus.PROPOSED.value,
        index=True
    )

    # 🎁 Extras & Notes
    bonus_description = Column(String(255), nullable=True)
    admin_notes = Column(String, nullable=True)

    # 🕐 Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    triggered_at = Column(DateTime, nullable=True) # Moment où le seuil a été atteint

    # 🔗 Relations
    product = relationship("Product", back_populates="daily_offers")
    suggestion = relationship("Suggestion", uselist=False)
    orders = relationship("Order", back_populates="daily_offer")
    production = relationship("Production", back_populates="daily_offer", uselist=False, cascade="all, delete-orphan")

    # ✅ Contraintes
    __table_args__ = (
        CheckConstraint("minimum_threshold > 0", name="chk_do_min_threshold_positive"),
        CheckConstraint("reserved_portions >= 0", name="chk_do_reserved_portions_non_negative"),
        CheckConstraint("price_per_unit > 0", name="chk_do_price_positive"),
    )

    # 🧠 Logique Métier
    @property
    def status_enum(self) -> ProductionStatus:
        return ProductionStatus(self.status)

    @property
    def is_threshold_reached(self) -> bool:
        """Indique si la production est confirmée (seuil atteint)"""
        return self.reserved_portions >= self.minimum_threshold

    @property
    def remaining_to_trigger(self) -> int:
        """Portions restant à commander pour déclencher la préparation"""
        return max(0, self.minimum_threshold - self.reserved_portions)

    @property
    def remaining_capacity(self) -> int:
        """Portions restant disponibles à la vente"""
        if self.max_capacity is None:
            return 999
        return max(0, self.max_capacity - self.reserved_portions)

    @property
    def progress_percentage(self) -> float:
        """Pour l'affichage visuel de progression vers le déclenchement"""
        if self.minimum_threshold <= 0:
            return 0.0
        return min(100.0, (self.reserved_portions / self.minimum_threshold) * 100.0)

    def can_transition_to(self, new_status: ProductionStatus) -> bool:
        return new_status in ProductionStatus.get_transitions(self.status_enum)

    def __repr__(self):
        product_name = self.product.name if self.product else '?'
        return f"<DailyOffer {product_name} - {self.target_date} [{self.reserved_portions}/{self.minimum_threshold}]>"
