# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Durable execution of one task by one agent.

Ported from `lib/run-runtime.ts` and `lib/run-state.ts`. Two properties matter
and are preserved here: the run's state lives in the database so it survives a
dead worker, and every skill the agent loaded is hashed into the run so a
decision can be explained with the rules that were in force at the time.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from indico.core.db import db
from indico.core.logger import Logger
from indico.util.date_time import now_utc

from indico_agents.models.runs import AgentRun, RunState
from indico_agents.runtime import tasks as queue


logger = Logger.get('plugin.agents.runner')

SKILLS_PATH = Path(__file__).parent.parent / 'skills'

#: Populated by `register_agent`; maps a task kind to the agent handling it
_AGENTS = {}


class UnknownTaskKind(Exception):
    pass


@dataclass
class RunContext:
    """Everything an agent may use, passed explicitly.

    Agents receive a context rather than reaching for globals, which is what
    makes them testable and what keeps a tool call attributable to a run.
    """

    task: object
    run: AgentRun
    skills: dict

    @property
    def event_id(self):
        return self.task.event_id

    def note(self, message):
        self.run.summary = f'{self.run.summary}\n{message}'.strip()


def register_agent(agent):
    """Bind an agent to the task kinds it handles."""
    for kind in agent.task_kinds:
        _AGENTS[kind] = agent
    return agent


def get_agent(kind):
    try:
        return _AGENTS[kind]
    except KeyError:
        raise UnknownTaskKind(f'no agent registered for task kind {kind!r}') from None


def load_skills(names):
    """Load skill files and hash them.

    Skills are prose, versioned like code. Storing the hash rather than the text
    keeps the run row small while still pinning exactly what was loaded.
    """
    skills = {}
    for name in names:
        path = SKILLS_PATH / f'{name}.md'
        if not path.exists():
            logger.warning('skill %s not found at %s', name, path)
            continue
        content = path.read_text(encoding='utf-8')
        skills[name] = {'content': content, 'sha256': hashlib.sha256(content.encode()).hexdigest()}
    return skills


def run_task(task):
    """Run one task to completion, recording everything.

    Failures are not swallowed: they propagate to the caller, which returns the
    task to the queue with backoff. The run row stays as the record of what was
    attempted.
    """
    agent = get_agent(task.kind)
    skills = load_skills(agent.skills)
    run = AgentRun(task_id=task.id, agent_name=agent.name,
                   skill_versions={name: data['sha256'] for name, data in skills.items()})
    db.session.add(run)
    queue.mark_running(task)
    db.session.flush()

    context = RunContext(task=task, run=run, skills=skills)
    try:
        agent.run(context)
    except Exception as exc:
        run.state = RunState.failed
        run.error = str(exc)[:2000]
        run.ended_dt = now_utc()
        db.session.flush()
        raise
    if run.state == RunState.running:
        run.state = RunState.done
    run.ended_dt = now_utc()
    queue.complete(task)
    db.session.flush()
    return run
