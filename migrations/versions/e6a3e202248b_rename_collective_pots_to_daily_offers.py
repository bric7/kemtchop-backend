"""rename_collective_pots_to_daily_offers

Revision ID: e6a3e202248b
Revises: d2999a3bf96a
Create Date: 2026-08-29 14:52:11.700542

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e6a3e202248b'
down_revision: Union[str, Sequence[str], None] = 'd2999a3bf96a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Rename the main table
    op.rename_table('collective_pots', 'daily_offers')

    # 2. Rename columns and indexes if needed
    op.alter_column('daily_offers', 'current_orders', new_column_name='reserved_portions')
    op.alter_column('daily_offers', 'minimum_orders', new_column_name='minimum_threshold')
    op.alter_column('daily_offers', 'max_orders', new_column_name='max_capacity')
    op.alter_column('daily_offers', 'funded_at', new_column_name='triggered_at')

    # Add missing column price_per_unit
    op.add_column('daily_offers', sa.Column('price_per_unit', sa.Float(), nullable=True))
    op.execute("UPDATE daily_offers SET price_per_unit = preorder_price")
    op.alter_column('daily_offers', 'price_per_unit', nullable=False)

    # Drop old price columns and discount_percentage
    op.drop_column('daily_offers', 'preorder_price')
    op.drop_column('daily_offers', 'live_price')
    op.drop_column('daily_offers', 'sponsor_pack_price')
    op.drop_column('daily_offers', 'discount_percentage')

    # Rename indexes
    op.execute("ALTER INDEX IF EXISTS ix_collective_pots_status RENAME TO ix_daily_offers_status")
    op.execute("ALTER INDEX IF EXISTS ix_collective_pots_target_date RENAME TO ix_daily_offers_target_date")

    # 3. Update 'orders' table
    op.add_column('orders', sa.Column('daily_offer_id', sa.UUID(), nullable=True))
    op.execute("UPDATE orders SET daily_offer_id = collective_pot_id")

    # Drop old FK and column
    op.drop_constraint('orders_collective_pot_id_fkey', 'orders', type_='foreignkey')
    op.drop_index('ix_orders_collective_pot_id', table_name='orders')
    op.drop_column('orders', 'collective_pot_id')

    # Add new FK
    op.create_foreign_key('orders_daily_offer_id_fkey', 'orders', 'daily_offers', ['daily_offer_id'], ['id'], ondelete='CASCADE')
    op.create_index(op.f('ix_orders_daily_offer_id'), 'orders', ['daily_offer_id'], unique=False)

    # 4. Update 'productions' table
    op.add_column('productions', sa.Column('daily_offer_id', sa.UUID(), nullable=True))
    op.execute("UPDATE productions SET daily_offer_id = collective_pot_id")
    op.alter_column('productions', 'daily_offer_id', nullable=False)

    # Drop old FK and column
    op.drop_constraint('productions_collective_pot_id_fkey', 'productions', type_='foreignkey')
    op.drop_column('productions', 'collective_pot_id')

    # Add new FK
    op.create_foreign_key('productions_daily_offer_id_fkey', 'productions', 'daily_offers', ['daily_offer_id'], ['id'], ondelete='CASCADE')
    op.create_unique_constraint('productions_daily_offer_id_key', 'productions', ['daily_offer_id'])

    # 5. Clean up other detected changes
    op.alter_column('orders', 'product_name', existing_type=sa.VARCHAR(), nullable=True)
    op.alter_column('orders', 'zone', existing_type=sa.VARCHAR(), nullable=True)

    # Product table type updates
    op.alter_column('products', 'video_url', existing_type=sa.TEXT(), type_=sa.String(length=500), existing_nullable=True)
    op.alter_column('products', 'price_solo', existing_type=sa.NUMERIC(precision=10, scale=2), type_=sa.Float(), existing_nullable=True)
    op.alter_column('products', 'price_duo', existing_type=sa.NUMERIC(precision=10, scale=2), type_=sa.Float(), existing_nullable=True)
    op.alter_column('products', 'price_family', existing_type=sa.NUMERIC(precision=10, scale=2), type_=sa.Float(), existing_nullable=True)


def downgrade() -> None:
    pass
