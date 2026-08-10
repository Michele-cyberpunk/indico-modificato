# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from flask import jsonify, request, session

from indico.core.db import db
from indico.core.plugins import WPJinjaMixinPlugin
from indico.modules.admin import RHAdminBase
from indico.modules.admin.views import WPAdmin

from indico_agents.governance import approvals as approval_service
from indico_agents.governance.kill_switch import agents_enabled, set_agents_enabled
from indico_agents.models.approvals import Approval, ApprovalState
from indico_agents.models.runs import AgentRun
from indico_agents.models.tasks import AgentTask, TaskStatus
from indico_agents.runtime import tasks as queue


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
                                        enabled=agents_enabled())


class RHToggleAgents(RHAdminBase):
    """The kill switch."""

    def _process(self):
        enabled = request.json.get('enabled', False) if request.is_json else False
        set_agents_enabled(enabled, user=session.user)
        return jsonify(enabled=agents_enabled())


class RHApprovalDecision(RHAdminBase):
    """Approve or reject a proposed action."""

    def _process_args(self):
        self.approval = Approval.get_or_404(request.view_args['approval_id'])

    def _process(self):
        decision = (request.json or {}).get('decision')
        note = (request.json or {}).get('note', '')
        if decision == 'approve':
            approval_service.approve(self.approval, user=session.user, note=note)
        elif decision == 'reject':
            approval_service.reject(self.approval, user=session.user, note=note)
        else:
            return jsonify(error='decision must be approve or reject'), 400
        db.session.commit()
        return jsonify(state=self.approval.state.name)
