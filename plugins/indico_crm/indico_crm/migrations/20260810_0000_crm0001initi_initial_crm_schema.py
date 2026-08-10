"""Initial crm schema

Revision ID: crm0001initi
Revises:
Create Date: 2026-08-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql  # noqa: F401

from indico.core.db.sqlalchemy import UTCDateTime


# revision identifiers, used by Alembic.
revision = 'crm0001initi'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.schema.CreateSchema('plugin_crm'))
    op.create_table(
        'object_links',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('crm_type', sa.SMALLINT(), nullable=False),
        sa.Column('crm_id', sa.Integer(), nullable=False),
        sa.Column('indico_type', sa.SMALLINT(), nullable=False),
        sa.Column('indico_id', sa.Integer(), nullable=False),
        sa.Column('relation', sa.String(), nullable=False),
        sa.Column('source', sa.SMALLINT(), nullable=False),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        sa.CheckConstraint('plugin_crm.object_links.crm_type IN (__[POSTCOMPILE_param_1])', name='ck_object_links_valid_enum_crm_type'),
        sa.CheckConstraint('plugin_crm.object_links.indico_type IN (__[POSTCOMPILE_param_1])', name='ck_object_links_valid_enum_indico_type'),
        sa.CheckConstraint('plugin_crm.object_links.source IN (__[POSTCOMPILE_param_1])', name='ck_object_links_valid_enum_source'),
        schema='plugin_crm',
    )
    op.create_index('ix_object_links_indico', 'object_links', ['indico_type', 'indico_id'], schema='plugin_crm')
    op.create_index('ix_uq_object_links', 'object_links', ['crm_type', 'crm_id', 'indico_type', 'indico_id', 'relation'], schema='plugin_crm', unique=True)
    op.create_table(
        'companies',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('kind', sa.SMALLINT(), nullable=False),
        sa.Column('vat_id', sa.String(), nullable=True),
        sa.Column('tax_code', sa.String(), nullable=True),
        sa.Column('sdi_code', sa.String(), nullable=False),
        sa.Column('pec', sa.String(), nullable=False),
        sa.Column('website', sa.String(), nullable=False),
        sa.Column('address', sa.JSON(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        sa.Column('updated_dt', UTCDateTime, nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.users.id'), nullable=True),
        sa.CheckConstraint('plugin_crm.companies.kind IN (__[POSTCOMPILE_param_1])', name='ck_companies_valid_enum_kind'),
        schema='plugin_crm',
    )
    op.create_index('ix_companies_created_by_id', 'companies', ['created_by_id'], schema='plugin_crm')
    op.create_index('ix_companies_name', 'companies', ['name'], schema='plugin_crm')
    op.create_index('ix_uq_companies_vat_id', 'companies', ['vat_id'], schema='plugin_crm', postgresql_where=sa.text('vat_id IS NOT NULL AND NOT is_deleted'), unique=True)
    op.create_table(
        'evidence',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('subject_type', sa.SMALLINT(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('statement', sa.Text(), nullable=False),
        sa.Column('attribute', sa.String(), nullable=False),
        sa.Column('kind', sa.SMALLINT(), nullable=False),
        sa.Column('source_ref', sa.String(), nullable=False),
        sa.Column('confidence', sa.Integer(), nullable=False),
        sa.Column('recorded_by_id', sa.Integer(), sa.ForeignKey('users.users.id'), nullable=True),
        sa.Column('agent_run_id', sa.Integer(), nullable=True),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        sa.Column('superseded_by_id', sa.Integer(), sa.ForeignKey('plugin_crm.evidence.id'), nullable=True),
        sa.CheckConstraint('recorded_by_id IS NOT NULL OR agent_run_id IS NOT NULL', name='ck_evidence_has_author'),
        sa.CheckConstraint('confidence BETWEEN 0 AND 100', name='ck_evidence_valid_confidence'),
        sa.CheckConstraint('plugin_crm.evidence.kind IN (__[POSTCOMPILE_param_1])', name='ck_evidence_valid_enum_kind'),
        sa.CheckConstraint('plugin_crm.evidence.subject_type IN (__[POSTCOMPILE_param_1])', name='ck_evidence_valid_enum_subject_type'),
        schema='plugin_crm',
    )
    op.create_index('ix_evidence_agent_run_id', 'evidence', ['agent_run_id'], schema='plugin_crm')
    op.create_index('ix_evidence_recorded_by_id', 'evidence', ['recorded_by_id'], schema='plugin_crm')
    op.create_index('ix_evidence_subject', 'evidence', ['subject_type', 'subject_id'], schema='plugin_crm')
    op.create_index('ix_evidence_superseded_by_id', 'evidence', ['superseded_by_id'], schema='plugin_crm')
    op.create_table(
        'contacts',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('first_name', sa.String(), nullable=False),
        sa.Column('last_name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('phone', sa.String(), nullable=False),
        sa.Column('job_title', sa.String(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.users.id'), nullable=True),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('plugin_crm.companies.id'), nullable=True),
        sa.Column('source', sa.SMALLINT(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        sa.Column('updated_dt', UTCDateTime, nullable=True),
        sa.CheckConstraint('plugin_crm.contacts.source IN (__[POSTCOMPILE_param_1])', name='ck_contacts_valid_enum_source'),
        schema='plugin_crm',
    )
    op.create_index('ix_contacts_company_id', 'contacts', ['company_id'], schema='plugin_crm')
    op.create_index('ix_contacts_last_name', 'contacts', ['last_name'], schema='plugin_crm')
    op.create_index('ix_contacts_user_id', 'contacts', ['user_id'], schema='plugin_crm')
    op.create_index('ix_uq_contacts_email', 'contacts', [], schema='plugin_crm', postgresql_where=sa.text('email != '' AND NOT is_deleted'), unique=True)
    op.create_table(
        'opportunities',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('plugin_crm.companies.id'), nullable=False),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.events.id'), nullable=True),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.users.id'), nullable=True),
        sa.Column('value', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('stage', sa.SMALLINT(), nullable=False),
        sa.Column('probability', sa.Integer(), nullable=False),
        sa.Column('expected_close_date', sa.Date(), nullable=True),
        sa.Column('next_action', sa.String(), nullable=False),
        sa.Column('next_action_dt', UTCDateTime, nullable=True),
        sa.Column('closed_dt', UTCDateTime, nullable=True),
        sa.Column('close_reason', sa.String(), nullable=False),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        sa.CheckConstraint('value >= 0', name='ck_opportunities_positive_value'),
        sa.CheckConstraint('plugin_crm.opportunities.stage IN (__[POSTCOMPILE_param_1])', name='ck_opportunities_valid_enum_stage'),
        sa.CheckConstraint('probability BETWEEN 0 AND 100', name='ck_opportunities_valid_probability'),
        schema='plugin_crm',
    )
    op.create_index('ix_opportunities_company_id', 'opportunities', ['company_id'], schema='plugin_crm')
    op.create_index('ix_opportunities_event_id', 'opportunities', ['event_id'], schema='plugin_crm')
    op.create_index('ix_opportunities_owner_id', 'opportunities', ['owner_id'], schema='plugin_crm')
    op.create_table(
        'activities',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('kind', sa.SMALLINT(), nullable=False),
        sa.Column('status', sa.SMALLINT(), nullable=False),
        sa.Column('subject', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('contact_id', sa.Integer(), sa.ForeignKey('plugin_crm.contacts.id'), nullable=True),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('plugin_crm.companies.id'), nullable=True),
        sa.Column('opportunity_id', sa.Integer(), sa.ForeignKey('plugin_crm.opportunities.id'), nullable=True),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.events.id'), nullable=True),
        sa.Column('assignee_id', sa.Integer(), sa.ForeignKey('users.users.id'), nullable=True),
        sa.Column('due_dt', UTCDateTime, nullable=True),
        sa.Column('done_dt', UTCDateTime, nullable=True),
        sa.Column('created_dt', UTCDateTime, nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.users.id'), nullable=True),
        sa.Column('created_by_agent_run_id', sa.Integer(), nullable=True),
        sa.CheckConstraint('(status = 2) = (done_dt IS NOT NULL)', name='ck_activities_dt_set_when_done'),
        sa.CheckConstraint('contact_id IS NOT NULL OR company_id IS NOT NULL OR opportunity_id IS NOT NULL OR event_id IS NOT NULL', name='ck_activities_has_subject'),
        sa.CheckConstraint('plugin_crm.activities.kind IN (__[POSTCOMPILE_param_1])', name='ck_activities_valid_enum_kind'),
        sa.CheckConstraint('plugin_crm.activities.status IN (__[POSTCOMPILE_param_1])', name='ck_activities_valid_enum_status'),
        schema='plugin_crm',
    )
    op.create_index('ix_activities_assignee_id', 'activities', ['assignee_id'], schema='plugin_crm')
    op.create_index('ix_activities_company_id', 'activities', ['company_id'], schema='plugin_crm')
    op.create_index('ix_activities_contact_id', 'activities', ['contact_id'], schema='plugin_crm')
    op.create_index('ix_activities_created_by_agent_run_id', 'activities', ['created_by_agent_run_id'], schema='plugin_crm')
    op.create_index('ix_activities_created_by_id', 'activities', ['created_by_id'], schema='plugin_crm')
    op.create_index('ix_activities_event_id', 'activities', ['event_id'], schema='plugin_crm')
    op.create_index('ix_activities_opportunity_id', 'activities', ['opportunity_id'], schema='plugin_crm')
    op.create_table(
        'consents',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('contact_id', sa.Integer(), sa.ForeignKey('plugin_crm.contacts.id'), nullable=False),
        sa.Column('kind', sa.SMALLINT(), nullable=False),
        sa.Column('granted', sa.Boolean(), nullable=False),
        sa.Column('effective_dt', UTCDateTime, nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('policy_version', sa.String(), nullable=False),
        sa.Column('proof', sa.JSON(), nullable=False),
        sa.CheckConstraint('plugin_crm.consents.kind IN (__[POSTCOMPILE_param_1])', name='ck_consents_valid_enum_kind'),
        schema='plugin_crm',
    )
    op.create_index('ix_consents_contact_id', 'consents', ['contact_id'], schema='plugin_crm')
    op.create_index('ix_consents_contact_kind', 'consents', ['contact_id', 'kind'], schema='plugin_crm')
    op.create_table(
        'hcp_profiles',
        sa.Column('contact_id', sa.Integer(), sa.ForeignKey('plugin_crm.contacts.id'), nullable=False, primary_key=True),
        sa.Column('tax_code', sa.String(), nullable=False),
        sa.Column('profession', sa.String(), nullable=False),
        sa.Column('discipline', sa.String(), nullable=False),
        sa.Column('registry_board', sa.String(), nullable=False),
        sa.Column('registry_number', sa.String(), nullable=False),
        sa.Column('registry_region', sa.String(), nullable=False),
        sa.Column('employment_type', sa.SMALLINT(), nullable=False),
        sa.Column('healthcare_org_id', sa.Integer(), sa.ForeignKey('plugin_crm.companies.id'), nullable=True),
        sa.Column('verification_status', sa.SMALLINT(), nullable=False),
        sa.Column('verified_dt', UTCDateTime, nullable=True),
        sa.Column('verified_by_id', sa.Integer(), sa.ForeignKey('users.users.id'), nullable=True),
        sa.Column('eligibility_flags', sa.JSON(), nullable=False),
        sa.CheckConstraint('plugin_crm.hcp_profiles.employment_type IN (__[POSTCOMPILE_param_1])', name='ck_hcp_profiles_valid_enum_employment_type'),
        sa.CheckConstraint('plugin_crm.hcp_profiles.verification_status IN (__[POSTCOMPILE_param_1])', name='ck_hcp_profiles_valid_enum_verification_status'),
        schema='plugin_crm',
    )
    op.create_index('ix_hcp_profiles_healthcare_org_id', 'hcp_profiles', ['healthcare_org_id'], schema='plugin_crm')
    op.create_index('ix_hcp_profiles_verified_by_id', 'hcp_profiles', ['verified_by_id'], schema='plugin_crm')
    op.create_index('ix_uq_hcp_profiles_registry', 'hcp_profiles', ['registry_board', 'registry_region', 'registry_number'], schema='plugin_crm', postgresql_where=sa.text('registry_number != '''), unique=True)
    op.create_index('ix_uq_hcp_profiles_tax_code', 'hcp_profiles', [], schema='plugin_crm', postgresql_where=sa.text('tax_code != '''), unique=True)
    op.create_table(
        'organization_links',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('contact_id', sa.Integer(), sa.ForeignKey('plugin_crm.contacts.id'), nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('plugin_crm.companies.id'), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=False),
        sa.CheckConstraint('end_date IS NULL OR start_date IS NULL OR end_date >= start_date', name='ck_organization_links_valid_period'),
        schema='plugin_crm',
    )
    op.create_index('ix_organization_links_company_id', 'organization_links', ['company_id'], schema='plugin_crm')
    op.create_index('ix_organization_links_contact_id', 'organization_links', ['contact_id'], schema='plugin_crm')


def downgrade():
    op.drop_table('organization_links', schema='plugin_crm')
    op.drop_table('hcp_profiles', schema='plugin_crm')
    op.drop_table('consents', schema='plugin_crm')
    op.drop_table('activities', schema='plugin_crm')
    op.drop_table('opportunities', schema='plugin_crm')
    op.drop_table('contacts', schema='plugin_crm')
    op.drop_table('evidence', schema='plugin_crm')
    op.drop_table('companies', schema='plugin_crm')
    op.drop_table('object_links', schema='plugin_crm')
    op.execute(sa.schema.DropSchema('plugin_crm'))
