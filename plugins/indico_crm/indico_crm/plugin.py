# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from flask import session
from wtforms.fields import BooleanField, StringField

from indico.core import signals
from indico.core.plugins import IndicoPlugin, url_for_plugin
from indico.util.i18n import _
from indico.web.forms.base import IndicoForm
from indico.web.forms.widgets import SwitchWidget
from indico.web.menu import SideMenuItem

from indico_crm import signals as crm_signals
from indico_crm.blueprint import blueprint


class CRMSettingsForm(IndicoForm):
    organization_name = StringField(_('Nome del provider'),
                                    description=_('Compare nei documenti e nelle comunicazioni.'))
    autolink_registrations = BooleanField(_('Collega automaticamente le iscrizioni'), widget=SwitchWidget(),
                                          description=_('Collega un iscritto a un contatto esistente solo quando '
                                                        'la corrispondenza è certa.'))
    autocreate_companies = BooleanField(_('Crea automaticamente le aziende'), widget=SwitchWidget(),
                                        description=_('Le aziende possono essere create dagli agenti; i '
                                                      'professionisti sanitari mai.'))


class CRMPlugin(IndicoPlugin):
    """CRM

    Aziende, contatti, professionisti sanitari, opportunità, consensi ed
    evidenze, incorporati in Indico e collegati agli eventi.
    """

    configurable = True
    settings_form = CRMSettingsForm
    default_settings = {
        'organization_name': '',
        'autolink_registrations': True,
        'autocreate_companies': True,
    }

    def init(self):
        super().init()
        self.connect(signals.event.registration_created, crm_signals.registration_created)
        self.connect(signals.event.registration_state_updated, crm_signals.registration_state_updated)
        self.connect(signals.event.registration_checkin_updated, crm_signals.registration_checkin_updated)
        self.connect(signals.event.created, crm_signals.event_created)
        # Without this the faculty never reached the CRM: the handler existed
        # and was documented, but nothing was ever connected to it.
        self.connect(signals.event.person_updated, crm_signals.event_person_updated)
        self.connect(signals.menu.items, self._extend_admin_menu, sender='admin-sidemenu')

    def get_blueprints(self):
        return blueprint

    def _extend_admin_menu(self, sender, **kwargs):
        if not session.user or not session.user.is_admin:
            return None
        return SideMenuItem('crm', _('CRM'), url_for_plugin('crm.contacts'), 60, section='customization')
