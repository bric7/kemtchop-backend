# app/entities/suggestion.py
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.database import Base


class Suggestion(Base):
    """
    💡 Suggestion = Un plat visible dans l'app mais sans marmite active.

    Quand un utilisateur clique "Lancer cette marmite",
    la suggestion se transforme en CollectivePot.

    Architecture : Product → Suggestion → CollectivePot → Production → Order
    """
    __tablename__ = "suggestions"

    # 🔑 Identité
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)

    # 📅 Date cible souhaitée (optionnelle, peut être définie au lancement)
    suggested_date = Column(DateTime, nullable=True)

    # 👤 Qui a suggéré ? (nullable = suggestion admin)
    suggested_by_user_id = Column(String(255), nullable=True)

    # 📊 Compteurs
    interest_count = Column(Integer, default=0)  # Nombre de votes / "J'aime"

    # 🔄 État
    is_active = Column(Boolean, default=True, index=True)  # False si transformée ou retirée
    collective_pot_id = Column(UUID(as_uuid=True), ForeignKey("collective_pots.id"), nullable=True)

    # 📝 Notes
    notes = Column(Text, nullable=True)

    # 🕐 Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 🔗 Relations
    product = relationship("Product", back_populates="suggestions")
    collective_pot = relationship(
        "CollectivePot",
        back_populates="suggestion",
        uselist=False,
        foreign_keys=[collective_pot_id]  # ← C'est CETTE colonne qui lie Suggestion → CollectivePot
    )

    def __repr__(self):
        return f"<Suggestion product_id={self.product_id} active={self.is_active}>"