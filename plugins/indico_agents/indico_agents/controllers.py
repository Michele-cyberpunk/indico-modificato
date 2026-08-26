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
                                        capabilities=capabilities.current())


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
