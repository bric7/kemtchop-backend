# app/entities/__init__.py
from .product import Product
from .campaign import Campaign
from .daily_menu import DailyMenu
from .order import Order
from .production import Production  # ✅ NOUVEAU

__all__ = [
    "Product",
    "Campaign", 
    "DailyMenu",
    "Order",
    "Production"  # ✅ NOUVEAU
]