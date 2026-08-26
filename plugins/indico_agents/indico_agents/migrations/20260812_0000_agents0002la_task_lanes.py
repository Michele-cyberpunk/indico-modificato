"""Task lanes

Revision ID: agents0002la
Revises: agents0001in
Create Date: 2026-08-12
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'agents0002la'
down_revision = 'agents0001in'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('agent_tasks',
                  sa.Column('lane', sa.String(), nullable=False, server_default='visible'),
                  schema='plugin_agents')
    op.alter_column('agent_tasks', 'lane', server_default=None, schema='plugin_agents')
    op.create_index('ix_agent_tasks_lane', 'agent_tasks', ['lane'], schema='plugin_agents')


def downgrade():
    op.drop_index('ix_agent_tasks_lane', table_name='agent_tasks', schema='plugin_agents')
    op.drop_column('agent_tasks', 'lane', schema='plugin_agents')
