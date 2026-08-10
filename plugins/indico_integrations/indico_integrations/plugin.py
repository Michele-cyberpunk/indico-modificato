# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

from wtforms.fields import BooleanField

from indico.core.plugins import IndicoPlugin
from indico.util.i18n import _
from indico.web.forms.base import IndicoForm
from indico.web.forms.widgets import SwitchWidget


class IntegrationsSettingsForm(IndicoForm):
    outbox_enabled = BooleanField(_('Consegna outbox attiva'), widget=SwitchWidget(),
                                  description=_('Se disattivata i messaggi si accumulano senza essere inviati.'))


class IntegrationsPlugin(IndicoPlugin):
    """Integrazioni

    Outbox transazionale e adapter verso email, calendario, webinar, firma e
    contabilità.
    """

    configurable = True
    settings_form = IntegrationsSettingsForm
    default_settings = {'outbox_enabled': False}
