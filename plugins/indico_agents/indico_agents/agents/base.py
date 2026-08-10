# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Base class for agents.

An agent is a named handler for one or more task kinds, with a declared
autonomy level and a declared set of skills. The level is not decoration: the
policy layer reads it before allowing a write, so an agent cannot exceed the
autonomy it was registered with even if its own logic tries to.
"""

from enum import IntEnum


class AutonomyLevel(IntEnum):
    """How far an agent may go on its own."""

    #: Read, analyse, report. Writes nothing.
    read_only = 0
    #: Produces drafts and proposals that a person applies.
    drafting = 1
    #: Acts on non-regulatory data (tasks, notes, CRM fields), with audit.
    acting = 2
    #: Acts autonomously within explicit policy. No ECM agent uses this.
    autonomous = 3


class Agent:
    #: Stable identifier, stored on every run
    name: str = ''
    #: Task kinds this agent handles
    task_kinds: tuple = ()
    #: Skill files loaded before running
    skills: tuple = ()
    autonomy: AutonomyLevel = AutonomyLevel.read_only
    #: Human-readable purpose, shown in the dashboard
    purpose: str = ''

    def run(self, context):
        raise NotImplementedError

    def __repr__(self):
        return f'<Agent({self.name}, L{int(self.autonomy)})>'
