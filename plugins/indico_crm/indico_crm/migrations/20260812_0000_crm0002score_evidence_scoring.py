"""Evidence scoring

Revision ID: crm0002score
Revises: crm0001initi
Create Date: 2026-08-12
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'crm0002score'
down_revision = 'crm0001initi'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('evidence', sa.Column('band', sa.String(), nullable=False, server_default=''),
                  schema='plugin_crm')
    op.add_column('evidence', sa.Column('rationale', sa.String(), nullable=False, server_default=''),
                  schema='plugin_crm')
    op.add_column('evidence', sa.Column('proofs', sa.JSON(), nullable=False, server_default='[]'),
                  schema='plugin_crm')
    for column in ('band', 'rationale', 'proofs'):
        op.alter_column('evidence', column, server_default=None, schema='plugin_crm')


def downgrade():
    for column in ('proofs', 'rationale', 'band'):
        op.drop_column('evidence', column, schema='plugin_crm')
