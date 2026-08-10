# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""The certificate document itself.

The layout starts from Indico's own *Certificate of Attendance* template and
adds what makes it an ECM certificate: credits, the rule version that produced
them, a unique number, and a QR code that resolves to the public verification
page.

The rendered bytes are hashed and the hash is stored on the certificate, so a
document that turns up later can be checked against what was issued.
"""

import base64
import hashlib
from datetime import date

from indico.core.logger import Logger

from indico_ecm.services.documents import qr_png, render_pdf


logger = Logger.get('plugin.ecm.certificate')


CERTIFICATE_HTML = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<style>
  @page {{ size: A4 landscape; margin: 18mm 20mm; }}
  body {{ font-family: "DejaVu Serif", Georgia, serif; color: #1a1a1a; }}
  .frame {{ border: 2px solid #1e40af; padding: 14mm 16mm; height: 100%; position: relative; }}
  .provider {{ font-size: 11pt; letter-spacing: .08em; text-transform: uppercase; color: #1e40af; }}
  h1 {{ font-size: 26pt; margin: 6mm 0 2mm; font-weight: normal; }}
  .subtitle {{ font-size: 11pt; color: #555; margin-bottom: 8mm; }}
  .name {{ font-size: 22pt; margin: 4mm 0; }}
  .detail {{ font-size: 12pt; line-height: 1.7; }}
  .detail b {{ font-weight: bold; }}
  .credits {{ font-size: 16pt; margin-top: 6mm; }}
  .footer {{ position: absolute; bottom: 0; left: 16mm; right: 16mm;
             display: flex; justify-content: space-between; align-items: flex-end;
             font-size: 9pt; color: #444; }}
  .qr {{ text-align: center; font-size: 8pt; }}
  .qr img {{ width: 26mm; height: 26mm; }}
  .number {{ font-family: "DejaVu Sans Mono", monospace; }}
</style>
</head>
<body>
<div class="frame">
  <div class="provider">{provider_name}{provider_code}</div>
  <h1>Attestato di partecipazione ECM</h1>
  <div class="subtitle">Educazione Continua in Medicina</div>

  <div class="detail">Si attesta che</div>
  <div class="name">{participant_name}</div>
  <div class="detail">
    {profession_line}
    ha partecipato all'evento formativo<br>
    <b>{event_title}</b><br>
    {event_dates}{event_place}
  </div>

  <div class="credits">
    Crediti ECM assegnati: <b>{credits}</b> — ore formative: <b>{hours}</b>
  </div>

  <div class="footer">
    <div>
      Attestato n. <span class="number">{number}</span><br>
      Rilasciato il {issued_on}<br>
      {activity_line}Regole applicate: {rule_version}
    </div>
    <div class="qr">
      <img src="data:image/png;base64,{qr}"><br>
      verifica online
    </div>
  </div>
</div>
</body>
</html>"""


def build_context(certificate, *, provider, participant_name, event, verification_url,
                  profession='', discipline='', issued_on=None):
    """Everything the certificate prints, resolved before rendering."""
    assignment = certificate.assignment
    outcome = assignment.outcome or {}
    minutes = float(outcome.get('attended_minutes') or 0)
    profession_line = ''
    if profession:
        profession_line = f'{profession}{" — " + discipline if discipline else ""},<br>'
    dates = ''
    if event is not None and event.start_dt:
        start = event.start_dt.strftime('%d/%m/%Y')
        end = event.end_dt.strftime('%d/%m/%Y') if event.end_dt else start
        dates = f'del {start}' if start == end else f'dal {start} al {end}'
    place = ''
    if event is not None and getattr(event, 'venue_name', ''):
        place = f', {event.venue_name}'
    activity_line = ''
    if assignment.accreditation and assignment.accreditation.activity_code:
        activity_line = f'Evento accreditato n. {assignment.accreditation.activity_code}<br>'
    return {
        'provider_name': provider.name if provider else '',
        'provider_code': f' — provider n. {provider.provider_code}' if provider and provider.provider_code else '',
        'participant_name': participant_name,
        'profession_line': profession_line,
        'event_title': event.title if event is not None else '',
        'event_dates': dates,
        'event_place': place,
        'credits': f'{assignment.credits:g}' if assignment.credits is not None else '0',
        'hours': f'{minutes / 60:.1f}'.replace('.', ','),
        'number': certificate.number,
        'issued_on': (issued_on or date.today()).strftime('%d/%m/%Y'),
        'activity_line': activity_line,
        'rule_version': assignment.rule_version or '—',
        'qr': base64.b64encode(qr_png(verification_url)).decode(),
    }


def render_certificate(certificate, **kwargs):
    """Render the certificate and return `(pdf_bytes, sha256)`."""
    html = CERTIFICATE_HTML.format(**build_context(certificate, **kwargs))
    pdf = render_pdf(html)
    digest = hashlib.sha256(pdf).hexdigest()
    logger.info('rendered certificate %s (%d bytes)', certificate.number, len(pdf))
    return pdf, digest
