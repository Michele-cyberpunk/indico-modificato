# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from flask import session
from wtforms.fields import BooleanField, IntegerField, StringField
from wtforms.validators import NumberRange

from indico.core import signals
from indico.core.plugins import IndicoPlugin, url_for_plugin
from indico.util.i18n import _
from indico.web.forms.base import IndicoForm
from indico.web.forms.widgets import SwitchWidget
from indico.web.menu import SideMenuItem

from indico_agents.blueprint import blueprint


class AgentsSettingsForm(IndicoForm):
    enabled = BooleanField(_('Agenti attivi'), widget=SwitchWidget(),
                           description=_('Interruttore generale: se disattivato nessun agente parte, ma il '
                                         'gestionale continua a funzionare.'))
    batch_size = IntegerField(_('Task per ciclo'), [NumberRange(min=1, max=100)],
                              description=_('Quanti task il dispatcher avvia a ogni minuto.'))
    max_cost_cents_per_event = IntegerField(_('Budget per evento (centesimi)'), [NumberRange(min=0)],
                                            description=_('Tetto di spesa complessivo degli agenti su un evento.'))
    model_provider = StringField(_('Fornitore del modello'),
                                 description=_('Nome di un adapter installato. Vuoto significa nessun '
                                               'modello: gli agenti restano deterministici e gli '
                                               'strumenti che redigono testo rispondono "non '
                                               'configurato". I crediti non passano mai da un modello.'))
    model_name = StringField(_('Modello'),
                             description=_('Usato solo dagli agenti che redigono testo.'))
    egress_allowlist = StringField(_('Destinazioni consentite'),
                                   description=_('Host separati da virgola che gli agenti possono '
                                                 'raggiungere. Vuoto significa nessuna uscita: un host '
                                                 'non elencato viene rifiutato prima della chiamata.'))
    research_provider = StringField(_('Fornitore di ricerca esterna'),
                                    description=_('Vuoto significa nessuna ricerca esterna: gli strumenti '
                                                  'di arricchimento rispondono "non configurato".'))


class AgentsPlugin(IndicoPlugin):
    """Agenti

    Coda di lavoro con leasing, esecuzioni durabili, strumenti autorizzati,
    skill versionate, approvazioni umane e audit.
    """

    configurable = True
    settings_form = AgentsSettingsForm
    default_settings = {
        'enabled': False,
        'batch_size': 10,
        'max_cost_cents_per_event': 0,
        'model_name': '',
        'research_provider': '',
        'registry_provider': '',
        'model_provider': '',
        'egress_allowlist': '',
    }

    def init(self):
        super().init()
        # importing the modules registers the agents and the tools
        from indico_agents.agents import credit_agent, event_agent, registration_agent  # noqa: F401
        from indico_agents.governance import appliers  # noqa: F401
        from indico_agents.runtime import dispatch  # noqa: F401
        from indico_agents.tools import comms, crm, ecm, operations  # noqa: F401
        self.connect(signals.menu.items, self._extend_admin_menu, sender='admin-sidemenu')

    def get_blueprints(self):
        return blueprint

    def _extend_admin_menu(self, sender, **kwargs):
        if not session.user or not session.user.is_admin:
            return None
        return SideMenuItem('agents', _('Agenti'), url_for_plugin('agents.dashboard'), 55,
                            section='customization')
