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

from indico_ecm.blueprint import blueprint


class ECMSettingsForm(IndicoForm):
    certificate_prefix = StringField(_('Prefisso attestati'),
                                     description=_('Usato per la numerazione, es. ECM-2026-000431.'))
    verification_base_url = StringField(_('URL di verifica'),
                                        description=_('Compare nel QR degli attestati.'))
    block_certificate_without_survey = BooleanField(_("Blocca l'attestato senza questionario"),
                                                    widget=SwitchWidget())


class ECMPlugin(IndicoPlugin):
    """ECM

    Accreditamento, presenze per sessione, regole crediti deterministiche,
    assegnazioni e attestati verificabili.
    """

    configurable = True
    settings_form = ECMSettingsForm
    default_settings = {
        'certificate_prefix': 'ECM',
        'verification_base_url': '',
        'block_certificate_without_survey': True,
    }

    def init(self):
        super().init()
        self.connect(signals.menu.items, self._extend_event_menu, sender='event-management-sidemenu')
        self.connect(signals.menu.items, self._extend_admin_menu, sender='admin-sidemenu')

    def get_blueprints(self):
        return blueprint

    def _extend_event_menu(self, sender, event, **kwargs):
        if not event.can_manage(session.user):
            return None
        return SideMenuItem('ecm', _('ECM'), url_for_plugin('ecm.event_overview', event), section='reports',
                            weight=20)

    def _extend_admin_menu(self, sender, **kwargs):
        if not session.user or not session.user.is_admin:
            return None
        return SideMenuItem('ecm_admin', _('ECM'), url_for_plugin('ecm.providers'), 65,
                            section='customization')
