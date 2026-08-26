# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from flask import flash, jsonify, redirect, request, session

from indico.core.db import db
from indico.core.plugins import WPJinjaMixinPlugin, url_for_plugin
from indico.modules.admin import RHAdminBase
from indico.modules.admin.views import WPAdmin
from indico.util.i18n import _

from indico_agents.governance import approvals as approval_service
from indico_agents.governance import capabilities
from indico_agents.governance.kill_switch import agents_enabled, set_agents_enabled
from indico_agents.models.approvals import Approval, ApprovalState
from indico_agents.models.runs import AgentRun
from indico_agents.models.tasks import AgentTask, TaskStatus
from indico_agents.runtime import tasks as queue
from indico_agents.runtime import llm, model_registry
from indico_agents.runtime.lanes import LANES


class WPAgents(WPJinjaMixinPlugin, WPAdmin):
    sidemenu_option = 'agents'


class RHAgentsDashboard(RHAdminBase):
    """Queue state, recent runs and pending approvals in one page."""

    def _process(self):
        recent_runs = AgentRun.query.order_by(AgentRun.started_dt.desc()).limit(25).all()
        failed = (AgentTask.query
                  .filter_by(status=TaskStatus.failed)
                  .order_by(AgentTask.updated_dt.desc())
                  .limit(25)
                  .all())
        pending = (Approval.query
                   .filter_by(state=ApprovalState.pending)
                   .order_by(Approval.created_dt)
                   .limit(50)
                   .all())
        return WPAgents.render_template('dashboard.html', 'agents', stats=queue.queue_stats(),
                                        runs=recent_runs, failed_tasks=failed, approvals=pending,
                                        enabled=agents_enabled(), lanes=LANES,
                                        capabilities=capabilities.current(),
                                        spend=_spend_summary(),
                                        models=model_registry.summary(_models()))


class RHToggleAgents(RHAdminBase):
    """The kill switch."""

    def _process(self):
        payload = request.json if request.is_json else request.form
        enabled = payload.get('enabled') in (True, 'true', '1', 'on')
        set_agents_enabled(enabled, user=session.user)
        if request.is_json:
            return jsonify(enabled=agents_enabled())
        return redirect(url_for_plugin('agents.dashboard'))


class RHApprovalDecision(RHAdminBase):
    """Approve or reject a proposed action.

    Approving applies the change: if the applier fails, the transaction is rolled
    back and the proposal stays pending, because a reviewer must never be told
    something happened when it did not.
    """

    def _process_args(self):
        self.approval = Approval.get_or_404(request.view_args['approval_id'])

    def _process(self):
        payload = request.json if request.is_json else request.form
        decision = payload.get('decision')
        note = payload.get('note', '')
        try:
            if decision == 'approve':
                approval_service.approve(self.approval, user=session.user, note=note)
            elif decision == 'reject':
                approval_service.reject(self.approval, user=session.user, note=note)
            else:
                raise approval_service.ApprovalError('decisione non valida')
        except Exception as exc:
            db.session.rollback()
            if request.is_json:
                return jsonify(error=str(exc)), 400
            flash(str(exc), 'error')
            return redirect(url_for_plugin('agents.dashboard'))
        db.session.commit()
        if request.is_json:
            return jsonify(state=self.approval.state.name)
        flash(_('Decisione registrata: {state}.').format(state=self.approval.state.name), 'success')
        return redirect(url_for_plugin('agents.dashboard'))


def _models():
    """The models this install has configured."""
    from indico_agents.plugin import AgentsPlugin

    return model_registry.parse(AgentsPlugin.settings.get('model_providers'))


def _spend_summary():
    """What the models have cost so far, and the ceiling they run against.

    A ceiling with no gauge is a promise nobody can check, so the two are shown
    together.
    """
    from indico_agents.plugin import AgentsPlugin

    totals = (db.session.query(db.func.coalesce(db.func.sum(AgentRun.cost_cents), 0),
                               db.func.coalesce(db.func.sum(AgentRun.tokens_used), 0),
                               db.func.count(AgentRun.id))
              .filter(AgentRun.cost_cents > 0)
              .one())
    return {'total_cents': int(totals[0] or 0), 'tokens': int(totals[1] or 0),
            'runs': int(totals[2] or 0),
            'ceiling_cents': int(AgentsPlugin.settings.get('max_cost_cents_per_event') or 0)}


class RHAgentModels(RHAdminBase):
    """The models this install may use, and what each one is for.

    Lives beside the kill switch and the capability table because they answer
    the same question — what can this platform reach — and splitting them across
    two areas would make the answer take two places to look.
    """

    def _render(self):
        entries = _models()
        # a row whose adapter is missing is kept, because configuring before
        # installing is legitimate — but it is labelled, not left looking fine
        return WPAgents.render_template('models.html', 'agents', models=entries,
                                        defaults=_default_indexes(entries),
                                        kinds=list(model_registry.ModelKind),
                                        adapters=llm.available_providers(),
                                        ceiling_cents=_spend_summary()['ceiling_cents'])

    def _process_GET(self):
        return self._render()

    def _process_POST(self):
        from indico_agents.plugin import AgentsPlugin

        entries = _models()
        action = request.form.get('action', 'add')
        try:
            if action == 'add':
                entries = model_registry.add(entries, model_registry.ModelEntry(
                    adapter=request.form.get('adapter', '').strip(),
                    kind=model_registry.ModelKind(request.form.get('kind', 'text')),
                    model=request.form.get('model', '').strip(),
                    host=request.form.get('host', '').strip(),
                    note=request.form.get('note', '').strip()),
                    known_adapters=set(llm.available_providers()))
            elif action == 'toggle':
                entries = model_registry.toggle(entries, request.form.get('index', type=int) or 0)
            elif action == 'remove':
                entries = model_registry.remove(entries, request.form.get('index', type=int) or 0)
        except (model_registry.ModelConfigError, ValueError) as exc:
            flash(str(exc), 'error')
            return redirect(url_for_plugin('agents.models'))

        AgentsPlugin.settings.set('model_providers', model_registry.serialise(entries))
        flash(_('Configurazione dei modelli aggiornata.'), 'success')
        return redirect(url_for_plugin('agents.models'))


def _default_indexes(entries):
    """Which rows a tool would actually get, one per kind.

    Worked out here rather than in the template: "the first enabled row of this
    kind" is a rule, and rules belong where they can be read and tested.
    """
    chosen = set()
    for kind in model_registry.ModelKind:
        default = model_registry.default_for(entries, kind)
        if default is not None:
            chosen.add(entries.index(default))
    return chosen
