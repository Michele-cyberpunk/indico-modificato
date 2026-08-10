# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Global stop for the agent layer.

One switch that stops every agent without stopping the platform. It is checked
by the dispatcher before each tick and by the runner before each run, so
flipping it takes effect within a minute and never leaves a run half-applied:
work already claimed finishes, nothing new starts.
"""

from indico.core.logger import Logger


logger = Logger.get('plugin.agents.kill_switch')


def agents_enabled():
    from indico_agents.plugin import AgentsPlugin
    return bool(AgentsPlugin.settings.get('enabled'))


def set_agents_enabled(enabled, *, user=None):
    from indico_agents.plugin import AgentsPlugin
    AgentsPlugin.settings.set('enabled', bool(enabled))
    logger.warning('agent layer %s by %s', 'enabled' if enabled else 'DISABLED',
                   user.full_name if user else 'system')
    return enabled
