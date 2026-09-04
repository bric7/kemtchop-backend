"""sync_reels_columns

Revision ID: f3d4a8b7c2e1
Revises: d2999a3bf96a
Create Date: 2026-09-04 10:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f3d4a8b7c2e1'
down_revision: Union[str, Sequence[str], None] = 'e6a3e202248b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Récupérer l'inspecteur pour vérifier l'existence des colonnes avant ajout
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('reels')]

    # Liste des colonnes à ajouter si elles manquent
    if 'daily_offer_id' not in columns:
        op.add_column('reels', sa.Column('daily_offer_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key('fk_reels_daily_offer', 'reels', 'daily_offers', ['daily_offer_id'], ['id'], ondelete='SET NULL')

    if 'product_name' not in columns:
        op.add_column('reels', sa.Column('product_name', sa.String(length=255), nullable=True))

    if 'category' not in columns:
        op.add_column('reels', sa.Column('category', sa.String(length=100), nullable=True))

    if 'price' not in columns:
        op.add_column('reels', sa.Column('price', sa.Float(), nullable=True))

    if 'price_solo' not in columns:
        op.add_column('reels', sa.Column('price_solo', sa.Float(), nullable=True))

    if 'price_duo' not in columns:
        op.add_column('reels', sa.Column('price_duo', sa.Float(), nullable=True))

    if 'price_family' not in columns:
        op.add_column('reels', sa.Column('price_family', sa.Float(), nullable=True))

    if 'family_size' not in columns:
        op.add_column('reels', sa.Column('family_size', sa.Integer(), server_default='3', nullable=True))

    if 'complements' not in columns:
        op.add_column('reels', sa.Column('complements', sa.String(length=255), nullable=True))

    if 'is_available' not in columns:
        op.add_column('reels', sa.Column('is_available', sa.Boolean(), server_default='true', nullable=True))

    if 'image_url' not in columns:
        op.add_column('reels', sa.Column('image_url', sa.String(length=500), nullable=True))

    if 'is_active' not in columns:
        op.add_column('reels', sa.Column('is_active', sa.Boolean(), server_default='true', nullable=True))

    if 'priority' not in columns:
        op.add_column('reels', sa.Column('priority', sa.Integer(), server_default='0', nullable=True))

def downgrade() -> None:
    # Opération inverse : suppression des colonnes ajoutées
    op.drop_constraint('fk_reels_daily_offer', 'reels', type_='foreignkey')
    op.drop_column('reels', 'priority')
    op.drop_column('reels', 'is_active')
    op.drop_column('reels', 'image_url')
    op.drop_column('reels', 'is_available')
    op.drop_column('reels', 'complements')
    op.drop_column('reels', 'family_size')
    op.drop_column('reels', 'price_family')
    op.drop_column('reels', 'price_duo')
    op.drop_column('reels', 'price_solo')
    op.drop_column('reels', 'price')
    op.drop_column('reels', 'category')
    op.drop_column('reels', 'product_name')
    op.drop_column('reels', 'daily_offer_id')
