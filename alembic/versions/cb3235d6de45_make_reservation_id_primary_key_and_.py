"""Make reservation_id primary key and drop listing_id

Revision ID: cb3235d6de45
Revises: 241be339ad1c
Create Date: 2025-07-16 17:33:05.947896

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "cb3235d6de45"
down_revision: Union[str, Sequence[str], None] = "241be339ad1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
