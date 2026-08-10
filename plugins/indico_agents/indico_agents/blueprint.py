# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from indico.core.plugins import IndicoPluginBlueprint

from indico_agents.controllers import RHAgentsDashboard, RHApprovalDecision, RHToggleAgents


blueprint = IndicoPluginBlueprint('agents', __name__, url_prefix='/admin/agents')

blueprint.add_url_rule('/', 'dashboard', RHAgentsDashboard)
blueprint.add_url_rule('/toggle', 'toggle', RHToggleAgents, methods=('POST',))
blueprint.add_url_rule('/approvals/<int:approval_id>', 'approval_decision', RHApprovalDecision,
                       methods=('POST',))
