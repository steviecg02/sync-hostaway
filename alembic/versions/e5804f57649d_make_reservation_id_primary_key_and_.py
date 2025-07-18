"""Make reservation_id primary key and drop listing_id

Revision ID: e5804f57649d
Revises: cb3235d6de45
Create Date: 2025-07-16 17:39:45.600693

"""

import sqlalchemy as sa

from alembic import op  # type: ignore[attr-defined]

# revision identifiers, used by Alembic.
revision = "e5804f57649d"
down_revision = "cb3235d6de45"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""
    schema = "hostaway"
    table = "messages"

    # Drop FK on listing_id
    op.drop_constraint("messages_listing_id_fkey", table, type_="foreignkey", schema=schema)

    # Drop listing_id column
    op.drop_column(table, "listing_id", schema=schema)

    # Drop unique constraint on reservation_id
    op.drop_constraint("uq_message_threads_reservation_id", table, type_="unique", schema=schema)

    # Drop old primary key (on id)
    op.drop_constraint("messages_pkey", table, type_="primary", schema=schema)

    # Add new primary key on reservation_id
    op.create_primary_key("messages_pkey", table, ["reservation_id"], schema=schema)


def downgrade() -> None:
    """Downgrade schema."""
    schema = "hostaway"
    table = "messages"

    # Re-add listing_id column
    op.add_column(table, sa.Column("listing_id", sa.Integer(), nullable=False), schema=schema)

    # Recreate FK
    op.create_foreign_key(
        "messages_listing_id_fkey",
        table,
        "listings",
        local_cols=["listing_id"],
        remote_cols=["id"],
        source_schema=schema,
        referent_schema=schema,
        ondelete="CASCADE",
    )

    # Drop new PK
    op.drop_constraint("messages_pkey", table, type_="primary", schema=schema)

    # Restore PK on id
    op.create_primary_key("messages_pkey", table, ["id"], schema=schema)

    # Restore unique constraint on reservation_id
    op.create_unique_constraint(
        "uq_message_threads_reservation_id", table, ["reservation_id"], schema=schema
    )
