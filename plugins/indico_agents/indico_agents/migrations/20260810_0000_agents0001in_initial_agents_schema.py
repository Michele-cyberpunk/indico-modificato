"""Initial agents schema

Revision ID: agents0001in
Revises:
Create Date: 2026-08-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from indico.core.db.sqlalchemy import UTCDateTime


# revision identifiers, used by Alembic.
revision = 'agents0001in'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.schema.CreateSchema('plugin_agents'))
    op.create_table(
        'agent_tasks',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('subject_type', sa.String(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.events.id'), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.SMALLINT(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('run_after', UTCDateTime, nullable=False),
        sa.Column('lease_owner', sa.String(), nullable=True),
        sa.Column('lease_expires_dt', UTCDateTime, nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('max_attempts', sa.Integer(), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=False),
        sa.Column('origin', sa.SMALLINT(), nullable=False),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        sa.Column('updated_dt', UTCDateTime, nullable=True),
        sa.CheckConstraint('(lease_owner IS NULL) = (lease_expires_dt IS NULL)', name='ck_agent_tasks_lease_pair'),
        sa.CheckConstraint('status IN (2, 3) OR lease_expires_dt IS NULL', name='ck_agent_tasks_no_stale_lease'),
        sa.CheckConstraint('attempts >= 0 AND max_attempts > 0', name='ck_agent_tasks_valid_attempts'),
        sa.CheckConstraint('plugin_agents.agent_tasks.origin IN (__[POSTCOMPILE_param_1])', name='ck_agent_tasks_valid_enum_origin'),
        sa.CheckConstraint('plugin_agents.agent_tasks.status IN (__[POSTCOMPILE_param_1])', name='ck_agent_tasks_valid_enum_status'),
        schema='plugin_agents',
    )
    op.create_index('ix_agent_tasks_claimable', 'agent_tasks', ['status', 'run_after', 'priority'], schema='plugin_agents')
    op.create_index('ix_agent_tasks_event_id', 'agent_tasks', ['event_id'], schema='plugin_agents')
    op.create_index('ix_agent_tasks_kind', 'agent_tasks', ['kind'], schema='plugin_agents')
    op.create_index('ix_agent_tasks_subject', 'agent_tasks', ['subject_type', 'subject_id'], schema='plugin_agents')
    op.create_index('ix_uq_agent_tasks_pending', 'agent_tasks', ['kind', 'subject_type', 'subject_id'], schema='plugin_agents', postgresql_where=sa.text('status IN (1, 2, 3)'), unique=True)
    op.create_table(
        'agent_runs',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('plugin_agents.agent_tasks.id'), nullable=False),
        sa.Column('agent_name', sa.String(), nullable=False),
        sa.Column('state', sa.SMALLINT(), nullable=False),
        sa.Column('skill_versions', sa.JSON(), nullable=False),
        sa.Column('model_name', sa.String(), nullable=False),
        sa.Column('state_data', sa.JSON(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('tokens_used', sa.Integer(), nullable=False),
        sa.Column('cost_cents', sa.Integer(), nullable=False),
        sa.Column('started_dt', UTCDateTime, nullable=False),
        sa.Column('ended_dt', UTCDateTime, nullable=True),
        sa.Column('error', sa.Text(), nullable=False),
        sa.CheckConstraint('plugin_agents.agent_runs.state IN (__[POSTCOMPILE_param_1])', name='ck_agent_runs_valid_enum_state'),
        schema='plugin_agents',
    )
    op.create_index('ix_agent_runs_agent_name', 'agent_runs', ['agent_name'], schema='plugin_agents')
    op.create_index('ix_agent_runs_task', 'agent_runs', ['task_id'], schema='plugin_agents')
    op.create_table(
        'approvals',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('plugin_agents.agent_runs.id'), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('subject_type', sa.String(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.events.id'), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('proposed_change', sa.JSON(), nullable=False),
        sa.Column('state', sa.SMALLINT(), nullable=False),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        sa.Column('expires_dt', UTCDateTime, nullable=True),
        sa.Column('decided_dt', UTCDateTime, nullable=True),
        sa.Column('decided_by_id', sa.Integer(), sa.ForeignKey('users.users.id'), nullable=True),
        sa.Column('decision_note', sa.Text(), nullable=False),
        sa.Column('applied_dt', UTCDateTime, nullable=True),
        sa.CheckConstraint('plugin_agents.approvals.state IN (__[POSTCOMPILE_param_1])', name='ck_approvals_valid_enum_state'),
        schema='plugin_agents',
    )
    op.create_index('ix_approvals_action', 'approvals', ['action'], schema='plugin_agents')
    op.create_index('ix_approvals_decided_by_id', 'approvals', ['decided_by_id'], schema='plugin_agents')
    op.create_index('ix_approvals_event_id', 'approvals', ['event_id'], schema='plugin_agents')
    op.create_index('ix_approvals_run_id', 'approvals', ['run_id'], schema='plugin_agents')
    op.create_index('ix_approvals_state', 'approvals', ['state', 'created_dt'], schema='plugin_agents')
    op.create_table(
        'policy_decisions',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('plugin_agents.agent_runs.id'), nullable=True),
        sa.Column('agent_name', sa.String(), nullable=False),
        sa.Column('tool_name', sa.String(), nullable=False),
        sa.Column('allowed', sa.Boolean(), nullable=False),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        schema='plugin_agents',
    )
    op.create_index('ix_policy_decisions_run', 'policy_decisions', ['run_id'], schema='plugin_agents')
    op.create_table(
        'tool_calls',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('plugin_agents.agent_runs.id'), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('tool_name', sa.String(), nullable=False),
        sa.Column('arguments', sa.JSON(), nullable=False),
        sa.Column('result_summary', sa.Text(), nullable=False),
        sa.Column('is_write', sa.Boolean(), nullable=False),
        sa.Column('succeeded', sa.Boolean(), nullable=False),
        sa.Column('error', sa.Text(), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        schema='plugin_agents',
    )
    op.create_index('ix_tool_calls_run', 'tool_calls', ['run_id', 'sequence'], schema='plugin_agents')
    op.create_index('ix_tool_calls_tool_name', 'tool_calls', ['tool_name'], schema='plugin_agents')


def downgrade():
    op.drop_table('tool_calls', schema='plugin_agents')
    op.drop_table('policy_decisions', schema='plugin_agents')
    op.drop_table('approvals', schema='plugin_agents')
    op.drop_table('agent_runs', schema='plugin_agents')
    op.drop_table('agent_tasks', schema='plugin_agents')
    op.execute(sa.schema.DropSchema('plugin_agents'))
