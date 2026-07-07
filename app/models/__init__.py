# app/models/__init__.py

# 1. Réexporte les entités principales depuis le dossier entities
from ..entities.product import Product
from ..entities.order import Order
from ..entities.collective_pot import CollectivePot
from ..entities.suggestion import Suggestion
from ..entities.production import Production

# 2. Importe les modèles spécifiques qui sont dans le dossier models/
# (On utilise try/except pour éviter les erreurs si un fichier manque temporairement)

try:
    from .user import User
except ImportError:
    User = None  # Sera géré si le fichier n'existe pas

try:
    from .reel import Reel
except ImportError:
    Reel = None

try:
    from .delivery_settings import DeliverySettings
except ImportError:
    DeliverySettings = None

try:
    from .user_event import UserEvent
except ImportError:
    UserEvent = None

try:
    from .password_reset import PasswordResetToken
except ImportError:
    PasswordResetToken = None

__all__ = [
    "Product", "Order", "CollectivePot", "Suggestion", "Production",
    "User", "Reel", "DeliverySettings", "UserEvent", "PasswordResetToken"
]