"""Preserve optional source listing details for property analysis."""
from alembic import op
import sqlalchemy as sa

revision = "2b58c4d7e901"
down_revision = "78c5b9de2866"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("rental_listings", sa.Column("property_details", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("rental_listings", "property_details")
