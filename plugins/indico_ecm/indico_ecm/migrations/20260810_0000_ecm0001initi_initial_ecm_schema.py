"""Initial ecm schema

Revision ID: ecm0001initi
Revises:
Create Date: 2026-08-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql  # noqa: F401

from indico.core.db.sqlalchemy import UTCDateTime


# revision identifiers, used by Alembic.
revision = 'ecm0001initi'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.schema.CreateSchema('plugin_ecm'))
    op.create_table(
        'providers',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('provider_code', sa.String(), nullable=False),
        sa.Column('region', sa.String(), nullable=False),
        sa.Column('tax_code', sa.String(), nullable=False),
        sa.Column('contact_email', sa.String(), nullable=False),
        sa.Column('settings', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        schema='plugin_ecm',
    )
    op.create_table(
        'certificate_sequences',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('provider_id', sa.Integer(), sa.ForeignKey('plugin_ecm.providers.id'), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('last_number', sa.Integer(), nullable=False),
        schema='plugin_ecm',
    )
    op.create_index('ix_uq_certificate_sequences', 'certificate_sequences', ['provider_id', 'year'], schema='plugin_ecm', unique=True)
    op.create_table(
        'event_accreditations',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.events.id'), nullable=False),
        sa.Column('provider_id', sa.Integer(), sa.ForeignKey('plugin_ecm.providers.id'), nullable=False),
        sa.Column('activity_code', sa.String(), nullable=False),
        sa.Column('activity_format', sa.SMALLINT(), nullable=False),
        sa.Column('state', sa.SMALLINT(), nullable=False),
        sa.Column('credits', sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column('max_participants', sa.Integer(), nullable=True),
        sa.Column('accredited_professions', sa.JSON(), nullable=False),
        sa.Column('accredited_disciplines', sa.JSON(), nullable=False),
        sa.Column('learning_objectives', sa.JSON(), nullable=False),
        sa.Column('rule_version', sa.String(), nullable=False),
        sa.Column('submitted_dt', UTCDateTime, nullable=True),
        sa.Column('accredited_dt', UTCDateTime, nullable=True),
        sa.Column('closed_dt', UTCDateTime, nullable=True),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.CheckConstraint('credits >= 0', name='ck_event_accreditations_positive_credits'),
        sa.CheckConstraint('max_participants IS NULL OR max_participants > 0', name='ck_event_accreditations_positive_quota'),
        sa.CheckConstraint('plugin_ecm.event_accreditations.activity_format IN (__[POSTCOMPILE_param_1])', name='ck_event_accreditations_valid_enum_activity_format'),
        sa.CheckConstraint('plugin_ecm.event_accreditations.state IN (__[POSTCOMPILE_param_1])', name='ck_event_accreditations_valid_enum_state'),
        schema='plugin_ecm',
    )
    op.create_index('ix_event_accreditations_provider_id', 'event_accreditations', ['provider_id'], schema='plugin_ecm')
    op.create_index('ix_uq_event_accreditations_event', 'event_accreditations', ['event_id'], schema='plugin_ecm', unique=True)
    op.create_table(
        'event_operations',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.events.id'), nullable=False),
        sa.Column('event_code', sa.String(), nullable=False),
        sa.Column('folder_name', sa.String(), nullable=False),
        sa.Column('schedule_text', sa.String(), nullable=False),
        sa.Column('accreditation_contact', sa.String(), nullable=False),
        sa.Column('accreditation_to', sa.String(), nullable=False),
        sa.Column('accreditation_cc', sa.String(), nullable=False),
        sa.Column('accreditation_bcc', sa.String(), nullable=False),
        sa.Column('accreditation_subject', sa.String(), nullable=False),
        sa.Column('accreditation_body', sa.Text(), nullable=False),
        sa.Column('platform_email', sa.String(), nullable=False),
        sa.Column('designer_email', sa.String(), nullable=False),
        sa.Column('hostess_email', sa.String(), nullable=False),
        sa.Column('date_changed', sa.Boolean(), nullable=False),
        sa.Column('previous_date', sa.Date(), nullable=True),
        sa.Column('venue_changed', sa.Boolean(), nullable=False),
        sa.Column('include_in_report', sa.Boolean(), nullable=False),
        sa.Column('programme_ref', sa.String(), nullable=False),
        sa.Column('task_email_note', sa.Text(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('hospitality_budget', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('legacy_data', sa.JSON(), nullable=False),
        sa.Column('updated_dt', UTCDateTime, nullable=False),
        schema='plugin_ecm',
    )
    op.create_index('ix_event_operations_code', 'event_operations', ['event_code'], schema='plugin_ecm')
    op.create_index('ix_uq_event_operations_event', 'event_operations', ['event_id'], schema='plugin_ecm', unique=True)
    op.create_table(
        'invitation_rows',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.events.id'), nullable=False),
        sa.Column('hospital', sa.String(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('recipient', sa.String(), nullable=False),
        sa.Column('recipient_email', sa.String(), nullable=False),
        sa.Column('cc_email', sa.String(), nullable=False),
        sa.Column('department', sa.String(), nullable=False),
        sa.Column('specialty', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('physician_count', sa.Integer(), nullable=False),
        sa.Column('sponsor', sa.String(), nullable=False),
        sa.Column('costs', sa.JSON(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('letter_generated_dt', UTCDateTime, nullable=True),
        sa.Column('sent_dt', UTCDateTime, nullable=True),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        schema='plugin_ecm',
    )
    op.create_index('ix_invitation_rows_company_id', 'invitation_rows', ['company_id'], schema='plugin_ecm')
    op.create_index('ix_invitation_rows_event', 'invitation_rows', ['event_id'], schema='plugin_ecm')
    op.create_table(
        'credit_assignments',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('registration_id', sa.Integer(), sa.ForeignKey('event_registration.registrations.id'), nullable=False),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.events.id'), nullable=False),
        sa.Column('accreditation_id', sa.Integer(), sa.ForeignKey('plugin_ecm.event_accreditations.id'), nullable=False),
        sa.Column('hcp_contact_id', sa.Integer(), nullable=True),
        sa.Column('state', sa.SMALLINT(), nullable=False),
        sa.Column('credits', sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column('rule_version', sa.String(), nullable=False),
        sa.Column('outcome', sa.JSON(), nullable=False),
        sa.Column('proposed_dt', UTCDateTime, nullable=False),
        sa.Column('proposed_by_agent_run_id', sa.Integer(), nullable=True),
        sa.Column('approved_dt', UTCDateTime, nullable=True),
        sa.Column('approved_by_id', sa.Integer(), sa.ForeignKey('users.users.id'), nullable=True),
        sa.Column('revoked_dt', UTCDateTime, nullable=True),
        sa.Column('revoked_reason', sa.Text(), nullable=False),
        sa.CheckConstraint('(state = 2) = (approved_dt IS NOT NULL)', name='ck_credit_assignments_dt_set_when_approved'),
        sa.CheckConstraint('credits >= 0', name='ck_credit_assignments_positive_credits'),
        sa.CheckConstraint('plugin_ecm.credit_assignments.state IN (__[POSTCOMPILE_param_1])', name='ck_credit_assignments_valid_enum_state'),
        schema='plugin_ecm',
    )
    op.create_index('ix_credit_assignments_accreditation_id', 'credit_assignments', ['accreditation_id'], schema='plugin_ecm')
    op.create_index('ix_credit_assignments_approved_by_id', 'credit_assignments', ['approved_by_id'], schema='plugin_ecm')
    op.create_index('ix_credit_assignments_event_id', 'credit_assignments', ['event_id'], schema='plugin_ecm')
    op.create_index('ix_credit_assignments_hcp_contact_id', 'credit_assignments', ['hcp_contact_id'], schema='plugin_ecm')
    op.create_index('ix_credit_assignments_proposed_by_agent_run_id', 'credit_assignments', ['proposed_by_agent_run_id'], schema='plugin_ecm')
    op.create_index('ix_uq_credit_assignments', 'credit_assignments', ['registration_id'], schema='plugin_ecm', postgresql_where=sa.text('state != 3'), unique=True)
    op.create_table(
        'credit_rule_versions',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('region', sa.String(), nullable=False),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_to', sa.Date(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.users.id'), nullable=True),
        schema='plugin_ecm',
    )
    op.create_index('ix_credit_rule_versions_created_by_id', 'credit_rule_versions', ['created_by_id'], schema='plugin_ecm')
    op.create_index('ix_uq_credit_rule_versions', 'credit_rule_versions', ['version'], schema='plugin_ecm', unique=True)
    op.create_table(
        'event_deliverables',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.events.id'), nullable=False),
        sa.Column('deliverable', sa.String(), nullable=False),
        sa.Column('state', sa.String(), nullable=False),
        sa.Column('lead_days', sa.Integer(), nullable=True),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.users.id'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('done_dt', UTCDateTime, nullable=True),
        sa.Column('updated_dt', UTCDateTime, nullable=False),
        schema='plugin_ecm',
    )
    op.create_index('ix_event_deliverables_event_id', 'event_deliverables', ['event_id'], schema='plugin_ecm')
    op.create_index('ix_event_deliverables_owner_id', 'event_deliverables', ['owner_id'], schema='plugin_ecm')
    op.create_index('ix_uq_event_deliverables', 'event_deliverables', ['event_id', 'deliverable'], schema='plugin_ecm', unique=True)
    op.create_table(
        'special_reminders',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.events.id'), nullable=True),
        sa.Column('event_code', sa.String(), nullable=False),
        sa.Column('task', sa.String(), nullable=False),
        sa.Column('remind_on', sa.Date(), nullable=False),
        sa.Column('assignee_id', sa.Integer(), sa.ForeignKey('users.users.id'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('source_deliverable', sa.String(), nullable=False),
        sa.Column('dismissed_dt', UTCDateTime, nullable=True),
        sa.Column('dismissed_by_id', sa.Integer(), sa.ForeignKey('users.users.id'), nullable=True),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        schema='plugin_ecm',
    )
    op.create_index('ix_special_reminders_assignee_id', 'special_reminders', ['assignee_id'], schema='plugin_ecm')
    op.create_index('ix_special_reminders_dismissed_by_id', 'special_reminders', ['dismissed_by_id'], schema='plugin_ecm')
    op.create_index('ix_special_reminders_due', 'special_reminders', ['remind_on', 'dismissed_dt'], schema='plugin_ecm')
    op.create_index('ix_special_reminders_event_id', 'special_reminders', ['event_id'], schema='plugin_ecm')
    op.create_table(
        'assessment_results',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('registration_id', sa.Integer(), sa.ForeignKey('event_registration.registrations.id'), nullable=False),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.events.id'), nullable=False),
        sa.Column('survey_submission_id', sa.Integer(), sa.ForeignKey('event_surveys.submissions.id'), nullable=True),
        sa.Column('attempt', sa.Integer(), nullable=False),
        sa.Column('correct_answers', sa.Integer(), nullable=False),
        sa.Column('total_questions', sa.Integer(), nullable=False),
        sa.Column('answer_detail', sa.JSON(), nullable=False),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        sa.CheckConstraint('total_questions > 0', name='ck_assessment_results_positive_total'),
        sa.CheckConstraint('correct_answers >= 0 AND correct_answers <= total_questions', name='ck_assessment_results_valid_score'),
        schema='plugin_ecm',
    )
    op.create_index('ix_assessment_results_event_id', 'assessment_results', ['event_id'], schema='plugin_ecm')
    op.create_index('ix_assessment_results_registration', 'assessment_results', ['registration_id', 'created_dt'], schema='plugin_ecm')
    op.create_index('ix_assessment_results_registration_id', 'assessment_results', ['registration_id'], schema='plugin_ecm')
    op.create_index('ix_assessment_results_survey_submission_id', 'assessment_results', ['survey_submission_id'], schema='plugin_ecm')
    op.create_table(
        'certificates',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('assignment_id', sa.Integer(), sa.ForeignKey('plugin_ecm.credit_assignments.id'), nullable=False),
        sa.Column('number', sa.String(), nullable=False),
        sa.Column('state', sa.SMALLINT(), nullable=False),
        sa.Column('receipt_file_id', sa.Integer(), sa.ForeignKey('event_registration.receipt_files.file_id'), nullable=True),
        sa.Column('content_hash', sa.String(), nullable=False),
        sa.Column('verification_token', sa.String(), nullable=False),
        sa.Column('issued_dt', UTCDateTime, nullable=True),
        sa.Column('issued_by_id', sa.Integer(), sa.ForeignKey('users.users.id'), nullable=True),
        sa.Column('revoked_dt', UTCDateTime, nullable=True),
        sa.Column('revoked_reason', sa.Text(), nullable=False),
        sa.Column('supersedes_id', sa.Integer(), sa.ForeignKey('plugin_ecm.certificates.id'), nullable=True),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        sa.CheckConstraint('plugin_ecm.certificates.state IN (__[POSTCOMPILE_param_1])', name='ck_certificates_valid_enum_state'),
        schema='plugin_ecm',
    )
    op.create_index('ix_certificates_assignment_id', 'certificates', ['assignment_id'], schema='plugin_ecm')
    op.create_index('ix_certificates_issued_by_id', 'certificates', ['issued_by_id'], schema='plugin_ecm')
    op.create_index('ix_certificates_receipt_file_id', 'certificates', ['receipt_file_id'], schema='plugin_ecm')
    op.create_index('ix_certificates_supersedes_id', 'certificates', ['supersedes_id'], schema='plugin_ecm')
    op.create_index('ix_certificates_verification_token', 'certificates', ['verification_token'], schema='plugin_ecm')
    op.create_index('ix_uq_certificates_number', 'certificates', ['number'], schema='plugin_ecm', unique=True)
    op.create_table(
        'session_attendance',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('registration_id', sa.Integer(), sa.ForeignKey('event_registration.registrations.id'), nullable=False),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.events.id'), nullable=False),
        sa.Column('session_block_id', sa.Integer(), sa.ForeignKey('events.session_blocks.id'), nullable=True),
        sa.Column('check_in_dt', UTCDateTime, nullable=False),
        sa.Column('check_out_dt', UTCDateTime, nullable=True),
        sa.Column('source', sa.SMALLINT(), nullable=False),
        sa.Column('device_ref', sa.String(), nullable=False),
        sa.Column('is_adjusted', sa.Boolean(), nullable=False),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.users.id'), nullable=True),
        sa.CheckConstraint('plugin_ecm.session_attendance.source IN (__[POSTCOMPILE_param_1])', name='ck_session_attendance_valid_enum_source'),
        sa.CheckConstraint('check_out_dt IS NULL OR check_out_dt >= check_in_dt', name='ck_session_attendance_valid_period'),
        schema='plugin_ecm',
    )
    op.create_index('ix_session_attendance_created_by_id', 'session_attendance', ['created_by_id'], schema='plugin_ecm')
    op.create_index('ix_session_attendance_event_id', 'session_attendance', ['event_id'], schema='plugin_ecm')
    op.create_index('ix_session_attendance_registration', 'session_attendance', ['registration_id', 'check_in_dt'], schema='plugin_ecm')
    op.create_index('ix_session_attendance_registration_id', 'session_attendance', ['registration_id'], schema='plugin_ecm')
    op.create_index('ix_session_attendance_session_block_id', 'session_attendance', ['session_block_id'], schema='plugin_ecm')
    op.create_table(
        'attendance_adjustments',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('attendance_id', sa.Integer(), sa.ForeignKey('plugin_ecm.session_attendance.id'), nullable=True),
        sa.Column('registration_id', sa.Integer(), sa.ForeignKey('event_registration.registrations.id'), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('previous_values', sa.JSON(), nullable=False),
        sa.Column('new_values', sa.JSON(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.users.id'), nullable=False),
        schema='plugin_ecm',
    )
    op.create_index('ix_attendance_adjustments_attendance_id', 'attendance_adjustments', ['attendance_id'], schema='plugin_ecm')
    op.create_index('ix_attendance_adjustments_created_by_id', 'attendance_adjustments', ['created_by_id'], schema='plugin_ecm')
    op.create_index('ix_attendance_adjustments_registration_id', 'attendance_adjustments', ['registration_id'], schema='plugin_ecm')


def downgrade():
    op.drop_table('attendance_adjustments', schema='plugin_ecm')
    op.drop_table('session_attendance', schema='plugin_ecm')
    op.drop_table('certificates', schema='plugin_ecm')
    op.drop_table('assessment_results', schema='plugin_ecm')
    op.drop_table('special_reminders', schema='plugin_ecm')
    op.drop_table('event_deliverables', schema='plugin_ecm')
    op.drop_table('credit_rule_versions', schema='plugin_ecm')
    op.drop_table('credit_assignments', schema='plugin_ecm')
    op.drop_table('invitation_rows', schema='plugin_ecm')
    op.drop_table('event_operations', schema='plugin_ecm')
    op.drop_table('event_accreditations', schema='plugin_ecm')
    op.drop_table('certificate_sequences', schema='plugin_ecm')
    op.drop_table('providers', schema='plugin_ecm')
    op.execute(sa.schema.DropSchema('plugin_ecm'))
