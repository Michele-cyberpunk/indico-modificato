# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""A draft the mail client opens, attachments already inside.

Ported from `src/lib/email/sender.ts` of the Cyberbrain event manager, which
solved the same problem from a desktop app: build a MIME message as a `.eml`
file and let the default client open it. Here the file is downloaded instead of
written to disk, but the message is the same and so are the reasons the original
gives for not doing it any other way:

* Not a `mailto:` or an Outlook Web compose link. Neither can carry an
  attachment — a URL is not allowed to reference a local file — so the letters
  would have to be attached by hand every time.
* Not COM automation of Outlook. It drives only the old Win32 Outlook, not the
  current one.

A `.eml` is opened as a draft by every mail client registered for it, the
attachments already in place, and nothing is sent until a person presses send.
That last part is the point: this platform prepares, a person sends.

Pure functions, no Indico imports.
"""

import re
from email.message import EmailMessage
from email.utils import formatdate


DEFAULT_ATTACHMENT_TYPE = ('application', 'octet-stream')

#: Extensions this platform actually produces, so the client shows the right icon
CONTENT_TYPES = {
    '.docx': ('application', 'vnd.openxmlformats-officedocument.wordprocessingml.document'),
    '.xlsx': ('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
    '.pdf': ('application', 'pdf'),
    '.zip': ('application', 'zip'),
    '.csv': ('text', 'csv'),
    '.txt': ('text', 'plain'),
    '.html': ('text', 'html'),
}


def content_type_for(filename):
    """The MIME type of a produced file, from its extension."""
    name = (filename or '').lower()
    for extension, pair in CONTENT_TYPES.items():
        if name.endswith(extension):
            return pair
    return DEFAULT_ATTACHMENT_TYPE


def _addresses(raw):
    """Split a recipient field written the way people write it."""
    return [part.strip() for part in re.split(r'[;,]', raw or '') if part.strip()]


def build_eml(*, to='', subject='', html_body='', text_body='', cc='', bcc='', sender='',
              attachments=(), date=None):
    """Build the draft, returning the bytes of a `.eml` file.

    `attachments` is a sequence of `(filename, content)` or
    `(filename, content, content_type)`.
    """
    message = EmailMessage()
    message['Subject'] = subject or ''
    if sender:
        message['From'] = sender
    if to:
        message['To'] = ', '.join(_addresses(to))
    if cc:
        message['Cc'] = ', '.join(_addresses(cc))
    if bcc:
        message['Bcc'] = ', '.join(_addresses(bcc))
    message['Date'] = formatdate(date, localtime=date is not None)
    # Marks the message as a draft for the clients that honour it.
    message['X-Unsent'] = '1'

    plain = text_body or _to_plain_text(html_body)
    message.set_content(plain)
    if html_body:
        message.add_alternative(html_body, subtype='html')

    for attachment in attachments:
        filename, content = attachment[0], attachment[1]
        maintype, subtype = (attachment[2] if len(attachment) > 2 and attachment[2]
                             else content_type_for(filename))
        message.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)

    return message.as_bytes()


_TAG = re.compile(r'<[^>]+>')
_BREAK = re.compile(r'</p\s*>|<br\s*/?>', re.IGNORECASE)


def _to_plain_text(html):
    """A readable plain-text part, for clients that show it instead of the HTML."""
    if not html:
        return ''
    text = _BREAK.sub('\n', html)
    text = _TAG.sub('', text)
    text = (text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"')
            .replace('&lt;', '<').replace('&gt;', '>').replace('&#39;', "'"))
    lines = [line.strip() for line in text.split('\n')]
    return '\n'.join(line for line in lines if line) + '\n'


_UNSAFE = re.compile(r'[<>:"/\\|?*]')


def draft_filename(subject, *, fallback='bozza'):
    """The name of the downloaded file, from the subject of the message."""
    name = _UNSAFE.sub('', (subject or '').strip())
    name = re.sub(r'\s+', ' ', name).strip()
    return f'{name[:80] or fallback}.eml'


def from_message(message, *, to='', cc='', sender='', attachments=()):
    """Build a draft from what `templates.render` returned."""
    return draft_filename(message.get('subject', '')), build_eml(
        to=to, cc=cc, sender=sender, subject=message.get('subject', ''),
        html_body=message.get('body', ''), attachments=attachments)
