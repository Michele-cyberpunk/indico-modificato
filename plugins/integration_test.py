# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Integration tests against a real Indico and a real PostgreSQL.

These are the tests the pure suites cannot replace: three of the bugs this
platform had were invisible until SQL actually ran (a `FOR UPDATE` on an
aggregate, a check constraint tripped by an autoflush, a `filter()` after a
`LIMIT`). They only run when an Indico environment is configured:

    export INDICO_CONFIG=/path/to/indico.conf     # pointing at a scratch database
    pytest plugins/integration_test.py -v

Without `INDICO_CONFIG` every test is skipped, so the pure suites stay runnable
anywhere.
"""

import io
import os
import re
import uuid
import zipfile
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest


pytestmark = pytest.mark.skipif(not os.environ.get('INDICO_CONFIG'),
                                reason='serve INDICO_CONFIG e un database di prova')


class _Scenario:
    """The fixture's objects, re-queried on every access.

    A test client request opens and closes its own session, which detaches
    anything the fixture created. Looking the row up again by id is simpler than
    reattaching, and it also proves the data really is in the database.
    """

    _LOADERS = {
        'event': ('indico.modules.events.models.events', 'Event'),
        'registration': ('indico.modules.events.registration.models.registrations', 'Registration'),
        'user': ('indico.modules.users.models.users', 'User'),
        'provider': ('indico_ecm.models.provider', 'Provider'),
        'accreditation': ('indico_ecm.models.provider', 'EventAccreditation'),
        'block': ('indico.modules.events.sessions.models.blocks', 'SessionBlock'),
        'contact': ('indico_crm.models.contacts', 'Contact'),
    }

    def __init__(self, ids):
        self.ids = ids

    def __getitem__(self, key):
        import importlib

        module_name, class_name = self._LOADERS[key]
        model = getattr(importlib.import_module(module_name), class_name)
        return model.get(self.ids[key])


class _EmptyManifest:
    """Stand-in for the webpack manifest, which is not built in a test run."""

    _entries = {}

    def __getitem__(self, key):
        return []


@pytest.fixture(scope='module')
def app():
    from indico.web.flask.app import make_app
    from indico.web.flask.wrappers import IndicoFlask

    IndicoFlask.manifest = property(lambda self: _EmptyManifest())
    application = make_app()
    application.config['TESTING'] = True
    return application


@pytest.fixture
def context(app):
    with app.app_context():
        yield


@pytest.fixture
def unique():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def scenario(context, unique):
    """A complete accredited event with one compliant participant."""
    import pytz

    from indico.core.db import db
    from indico.modules.categories.models.categories import Category
    from indico.modules.events.models.events import Event, EventType
    from indico.modules.events.registration.models.forms import RegistrationForm
    from indico.modules.events.registration.models.registrations import Registration, RegistrationState
    from indico.modules.events.sessions.models.blocks import SessionBlock
    from indico.modules.events.sessions.models.sessions import Session
    from indico.modules.events.surveys.models.submissions import SurveySubmission
    from indico.modules.events.surveys.models.surveys import Survey
    from indico.modules.events.timetable.models.entries import TimetableEntry, TimetableEntryType
    from indico.modules.users.models.users import User

    from indico_crm.models.contacts import Contact
    from indico_crm.models.hcp_profiles import HCPProfile, VerificationStatus
    from indico_ecm.models.assessments import AssessmentResult
    from indico_ecm.models.attendance import SessionAttendance
    from indico_ecm.models.credits import CreditRuleVersion
    from indico_ecm.models.provider import AccreditationState, ActivityFormat, EventAccreditation, Provider
    from indico_ecm.services.credit_rules import CreditsMode, RuleSet
    from indico_ecm.services.rules_repository import dump_ruleset

    user = User(first_name='Test', last_name=f'Utente{unique}', email=f'test+{unique}@example.org',
                is_admin=True)
    db.session.add(user)
    db.session.commit()

    tz = pytz.timezone('Europe/Rome')
    start = tz.localize(datetime(2026, 9, 15, 9, 0))
    event = Event(category=Category.get(0), creator=user, title=f'Evento di prova {unique}',
                  start_dt=start, end_dt=start + timedelta(hours=7), timezone='Europe/Rome',
                  type_=EventType.conference)
    db.session.add(event)
    db.session.commit()

    session_obj = Session(event=event, title='Sessione')
    db.session.add(session_obj)
    db.session.commit()
    block = SessionBlock(session=session_obj, title='Mattina', duration=timedelta(hours=6))
    db.session.add(block)
    db.session.commit()
    db.session.add(TimetableEntry(event=event, session_block=block,
                                  type=TimetableEntryType.SESSION_BLOCK, start_dt=start))
    db.session.commit()

    provider = Provider(name=f'Provider {unique}', provider_code=f'P{unique}',
                        settings={'certificate_prefix': f'T{unique[:3].upper()}'})
    db.session.add(provider)
    version = f'test-{unique}'
    db.session.add(CreditRuleVersion(version=version, valid_from=date(2026, 1, 1),
                                     payload=dump_ruleset(RuleSet(version=version,
                                                                  accredited_credits=Decimal(9),
                                                                  credits_mode=CreditsMode.fixed))))
    accreditation = EventAccreditation(event=event, provider=provider, activity_code=f'AG-{unique}',
                                       activity_format=ActivityFormat.residential,
                                       state=AccreditationState.accredited, credits=9,
                                       max_participants=100, rule_version=version)
    db.session.add(accreditation)
    db.session.commit()

    regform = RegistrationForm(event=event, title='Iscrizione', currency='EUR')
    db.session.add(regform)
    db.session.commit()
    registration = Registration(registration_form_id=regform.id, event_id=event.id, user_id=user.id,
                                first_name='Mario', last_name='Rossi', email=user.email,
                                currency='EUR', state=RegistrationState.complete,
                                base_price=0, price_adjustment=0)
    db.session.add(registration)
    db.session.commit()

    contact = Contact(first_name='Mario', last_name='Rossi', email=user.email, user_id=user.id)
    db.session.add(contact)
    db.session.commit()
    db.session.add(HCPProfile(contact_id=contact.id, tax_code=f'TEST{unique.upper()}',
                              profession='Medico chirurgo', discipline='Cardiologia',
                              verification_status=VerificationStatus.verified))
    db.session.add(SessionAttendance(registration_id=registration.id, event_id=event.id,
                                     session_block_id=block.id, check_in_dt=block.start_dt,
                                     check_out_dt=block.end_dt))
    db.session.add(AssessmentResult(registration_id=registration.id, event_id=event.id,
                                    correct_answers=9, total_questions=10))
    survey = Survey(event=event, title='Questionario')
    db.session.add(survey)
    db.session.commit()
    db.session.add(SurveySubmission(survey=survey, user=user, is_submitted=True,
                                    submitted_dt=block.end_dt))
    db.session.commit()

    return _Scenario({'event': event.id, 'registration': registration.id, 'user': user.id,
                     'provider': provider.id, 'accreditation': accreditation.id, 'block': block.id,
                     'contact': contact.id})


# --- the regulatory pipeline ------------------------------------------------

def test_attendance_comes_from_the_real_timetable(scenario):
    from indico_ecm.services import attendance as attendance_service

    program = attendance_service.build_program(scenario['event'])
    assert len(program) == 1
    assert program[0].minutes == 360


def test_a_compliant_participant_is_eligible(scenario):
    from indico_ecm.services import eligibility as eligibility_service

    outcome = eligibility_service.evaluate_registration(scenario['registration'])
    assert outcome.eligible
    assert outcome.credits == Decimal(9)
    assert outcome.attended_minutes == Decimal(360)
    assert outcome.reasons == ()


def test_leaving_early_denies_the_credits(scenario):
    from indico.core.db import db

    from indico_ecm.models.attendance import SessionAttendance
    from indico_ecm.services import eligibility as eligibility_service
    from indico_ecm.services.credit_rules import Reason

    row = SessionAttendance.query.filter_by(registration_id=scenario['registration'].id).one()
    row.check_out_dt = row.check_in_dt + timedelta(hours=3)
    db.session.flush()
    outcome = eligibility_service.evaluate_registration(scenario['registration'])
    assert not outcome.eligible
    assert Reason.attendance_below_threshold in outcome.reasons
    assert outcome.credits == Decimal(0)


def test_credits_cannot_be_approved_by_a_machine(scenario):
    from indico_ecm.services import eligibility as eligibility_service

    assignment = eligibility_service.propose_assignment(scenario['registration'])
    with pytest.raises(eligibility_service.NotAuthorized):
        eligibility_service.approve_assignment(assignment, user=None)


def test_a_certificate_needs_an_approved_assignment(scenario):
    from indico_ecm.services import certificates as certificate_service
    from indico_ecm.services import eligibility as eligibility_service

    assignment = eligibility_service.propose_assignment(scenario['registration'])
    with pytest.raises(certificate_service.CertificateError):
        certificate_service.prepare_certificate(assignment, provider=scenario['provider'])


def test_the_whole_pipeline_produces_a_verifiable_certificate(scenario):
    from indico.core.db import db

    from indico_ecm.services import certificates as certificate_service
    from indico_ecm.services import eligibility as eligibility_service

    assignment = eligibility_service.propose_assignment(scenario['registration'])
    eligibility_service.approve_assignment(assignment, user=scenario['user'])
    certificate = certificate_service.prepare_certificate(assignment, provider=scenario['provider'])
    certificate_service.issue_certificate(certificate, user=scenario['user'], file_content=b'PDF')
    db.session.flush()

    result = certificate_service.verify(certificate.verification_token)
    assert result['valid']
    assert result['credits'] == '9'
    assert 'name' not in result and 'email' not in result  # no personal data


def test_certificate_numbering_is_sequential_and_unique(scenario):
    from indico_ecm.services.certificates import next_number

    year = 2026
    numbers = [next_number(scenario['provider'], year) for _ in range(3)]
    assert numbers == sorted(numbers)
    assert len(set(numbers)) == 3
    assert numbers[0].endswith('000001')


def test_the_certificate_pdf_renders(scenario):
    from indico_ecm.services import certificates as certificate_service
    from indico_ecm.services import eligibility as eligibility_service
    from indico_ecm.services.certificate_render import render_certificate

    assignment = eligibility_service.propose_assignment(scenario['registration'])
    eligibility_service.approve_assignment(assignment, user=scenario['user'])
    certificate = certificate_service.prepare_certificate(assignment, provider=scenario['provider'])
    pdf, digest = render_certificate(certificate, provider=scenario['provider'],
                                     participant_name='Mario Rossi', event=scenario['event'],
                                     verification_url='https://example.org/verify/x')
    assert pdf.startswith(b'%PDF')
    assert len(digest) == 64


# --- the work queue ---------------------------------------------------------

@pytest.fixture
def clean_queue(context):
    from indico.core.db import db

    from indico_agents.models.tasks import AgentTask
    AgentTask.query.delete()
    db.session.commit()
    yield
    AgentTask.query.delete()
    db.session.commit()


def test_an_identical_pending_task_is_not_duplicated(clean_queue):
    from indico_agents.models.tasks import AgentTask
    from indico_agents.runtime import tasks as queue

    first = queue.schedule_task('check', 'registration', 1)
    second = queue.schedule_task('check', 'registration', 1)
    assert first.id == second.id
    assert AgentTask.query.count() == 1


def test_two_workers_do_not_claim_the_same_task(clean_queue):
    from indico.core.db import db

    from indico_agents.runtime import tasks as queue

    queue.schedule_task('check', 'registration', 2)
    db.session.commit()
    first = queue.claim_due(10, owner='worker-a')
    db.session.commit()
    second = queue.claim_due(10, owner='worker-b')
    assert len(first) == 1
    assert second == []


def test_claiming_by_kind_works(clean_queue):
    from indico.core.db import db

    from indico_agents.runtime import tasks as queue

    queue.schedule_task('wanted', 'registration', 3)
    queue.schedule_task('unwanted', 'registration', 4)
    db.session.commit()
    claimed = queue.claim_due(10, owner='w', kinds=['wanted'])
    assert [task.kind for task in claimed] == ['wanted']


def test_a_failure_comes_back_with_backoff(clean_queue):
    from indico.core.db import db

    from indico_agents.models.tasks import TaskStatus
    from indico_agents.runtime import tasks as queue
    from indico.util.date_time import now_utc

    queue.schedule_task('check', 'registration', 5)
    db.session.commit()
    task = queue.claim_due(1, owner='w')[0]
    db.session.commit()
    queue.fail(task, 'errore simulato')
    db.session.commit()
    assert task.status == TaskStatus.pending
    assert task.run_after > now_utc()
    assert task.lease_owner is None


def test_a_dead_worker_releases_its_task(clean_queue):
    from indico.core.db import db
    from indico.util.date_time import now_utc

    from indico_agents.models.tasks import TaskStatus
    from indico_agents.runtime import tasks as queue

    queue.schedule_task('check', 'registration', 6)
    db.session.commit()
    task = queue.claim_due(1, owner='worker-morto')[0]
    task.lease_expires_dt = now_utc() - timedelta(minutes=1)
    db.session.commit()
    reclaimed = queue.reclaim_expired()
    db.session.commit()
    assert [t.id for t in reclaimed] == [task.id]
    assert task.status == TaskStatus.pending


# --- authorization ----------------------------------------------------------

def test_every_authorized_tool_exists(context):
    from indico_agents.governance.policy_rules import TOOL_POLICIES
    from indico_agents.tools import comms, crm, ecm, operations  # noqa: F401
    from indico_agents.tools.base import _REGISTRY

    assert set(TOOL_POLICIES) - set(_REGISTRY) == set()


def test_every_approval_action_has_an_applier(context):
    from indico_agents.governance import appliers  # noqa: F401
    from indico_agents.governance.approvals import _APPLIERS
    from indico_agents.governance.policy_rules import APPROVAL_ACTIONS

    assert APPROVAL_ACTIONS - set(_APPLIERS) == set()


# --- the pages --------------------------------------------------------------

@pytest.fixture
def client(app, scenario):
    test_client = app.test_client()
    with app.app_context(), test_client.session_transaction() as flask_session:
        flask_session['_user_id'] = scenario['user'].id
    return test_client


@pytest.fixture
def csrf(client, scenario):
    page = client.get(f'/event/{scenario["event"].id}/manage/ecm/')
    return re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()


@pytest.mark.parametrize('path', (
    '/', '/accreditation', '/attendance', '/participants', '/certificates', '/invitations',
))
def test_event_pages_render(client, scenario, path):
    response = client.get(f'/event/{scenario["event"].id}/manage/ecm{path}')
    assert response.status_code == 200


@pytest.mark.parametrize('path', (
    '/admin/ecm/providers', '/admin/ecm/import', '/admin/ecm/automator', '/admin/crm/contacts',
    '/admin/crm/companies', '/admin/crm/opportunities', '/admin/agents/',
))
def test_admin_pages_render(client, path):
    assert client.get(path).status_code == 200


# --- from a document to an event folder ---------------------------------------

SPONSOR_EMAIL = '''Buongiorno,
vi confermiamo l'evento 0116_GDBO previsto per il 15/09/2026 presso l'Hotel Excelsior di Milano.
Il programma prevede interventi su scompenso cardiaco e stenosi aortica.
Relatori confermati: Dott. Mario Rossi e Prof. Gian Luca De Angelis.
Cordiali saluti.'''


def test_the_automator_shows_what_it_extracted_and_where_from(client, csrf):
    response = client.post('/admin/ecm/automator',
                           data={'csrf_token': csrf, 'text': SPONSOR_EMAIL,
                                 'event_name': 'Cardio Update', 'sponsor': 'Acme Pharma',
                                 'place': 'Hotel Excelsior', 'city': 'Milano'})
    assert response.status_code == 200
    body = response.data.decode()
    assert '0116_GDBO' in body
    assert '2026-09-15' in body
    # the surname particle is kept: the person is not called "Gian Luca De"
    assert 'Gian Luca De Angelis' in body
    assert '0915 CARDIO' in body  # the provider's folder convention
    assert 'info_evento.txt' in body


def test_the_automator_hands_back_the_event_folder(client, csrf):
    response = client.post('/admin/ecm/automator',
                           data={'csrf_token': csrf, 'text': SPONSOR_EMAIL, 'download': '1',
                                 'event_name': 'Cardio Update', 'sponsor': 'Acme Pharma',
                                 'place': 'Hotel Excelsior', 'city': 'Milano'})
    assert response.status_code == 200
    assert response.mimetype == 'application/zip'
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        names = archive.namelist()
        folder = names[0].split('/')[0]
        assert folder.startswith('0915 CARDIO ')
        assert {name.split('/', 1)[1] for name in names} == {
            'info_evento.txt', 'briefing.txt', 'agenda.txt', 'report_template.txt', 'email_draft.html'}
        info = archive.read(f'{folder}/info_evento.txt').decode()
        assert '0116_GDBO' in info and 'Acme Pharma' in info


def test_an_unreadable_attachment_does_not_lose_the_rest(client, csrf):
    response = client.post('/admin/ecm/automator',
                           data={'csrf_token': csrf, 'text': SPONSOR_EMAIL,
                                 'documents': (io.BytesIO(b'\x00\x01\x02'), 'slide.pptx')},
                           content_type='multipart/form-data')
    assert response.status_code == 200
    assert '0116_GDBO' in response.data.decode()
    assert 'formato non supportato' in response.data.decode()


def test_without_material_the_automator_builds_nothing(client, csrf):
    response = client.post('/admin/ecm/automator', data={'csrf_token': csrf, 'text': ''})
    assert response.status_code == 302


def test_evaluating_from_the_page_creates_proposals(client, csrf, scenario):
    from indico_ecm.models.credits import CreditAssignment

    response = client.post(f'/event/{scenario["event"].id}/manage/ecm/evaluate',
                           data={'csrf_token': csrf}, follow_redirects=True)
    assert response.status_code == 200
    assert CreditAssignment.query.filter_by(event_id=scenario['event'].id).count() >= 1


def test_importing_hospitals_and_generating_letters(client, csrf, scenario):
    from indico_ecm.models.operations import InvitationBatch

    csv_content = ('Nome Ospedale;N° Medici;Reparto;Ruolo;Destinatario;Costo Camera (€);N° Pranzi\n'
                   'Ospedale San Raffaele;3;Cardiologia;Relatore;Dott. Bianchi;120;2\n')
    response = client.post(f'/event/{scenario["event"].id}/manage/ecm/invitations',
                           data={'csrf_token': csrf,
                                 'spreadsheet': (io.BytesIO(csv_content.encode()), 'ospedali.csv')},
                           content_type='multipart/form-data', follow_redirects=True)
    assert response.status_code == 200
    rows = InvitationBatch.query.filter_by(event_id=scenario['event'].id).all()
    assert len(rows) == 1
    assert rows[0].physician_count == 3

    letters = client.get(f'/event/{scenario["event"].id}/manage/ecm/invitations/letters')
    assert letters.status_code == 200
    assert letters.data[:2] == b'PK'  # a zip archive


def test_the_public_verification_page_is_open(client, scenario):
    from indico.core.db import db

    from indico_ecm.services import certificates as certificate_service
    from indico_ecm.services import eligibility as eligibility_service

    assignment = eligibility_service.propose_assignment(scenario['registration'])
    eligibility_service.approve_assignment(assignment, user=scenario['user'])
    certificate = certificate_service.prepare_certificate(assignment, provider=scenario['provider'])
    certificate_service.issue_certificate(certificate, user=scenario['user'], file_content=b'PDF')
    db.session.commit()

    anonymous = client.application.test_client()
    response = anonymous.get(f'/ecm/verify/{certificate.verification_token}?format=json')
    assert response.status_code == 200
    assert response.get_json()['valid'] is True


def test_checking_in_records_attendance(client, csrf, scenario):
    from indico_ecm.models.attendance import SessionAttendance

    before = SessionAttendance.query.filter_by(registration_id=scenario['registration'].id).count()
    response = client.post(f'/event/{scenario["event"].id}/manage/ecm/attendance/checkin',
                           data={'csrf_token': csrf, 'registration_id': scenario['registration'].id,
                                 'direction': 'in'})
    assert response.status_code == 200
    after = SessionAttendance.query.filter_by(registration_id=scenario['registration'].id).count()
    assert after == before + 1
