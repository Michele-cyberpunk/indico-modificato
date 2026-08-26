# This file is part of the ECM extension for Indico.
# Copyright (C) 2026 - present
#
# Licensed under the MIT License; see the LICENSE file for details.

"""Where a call is allowed to go.

The original denies the network to its sandbox outright, which it can afford
because the sandbox exists to run generated code. Nothing here runs generated
code, so a container-level deny-all would be protecting an empty room while the
calls that *do* leave — a model provider, a registry lookup — went out
unchecked.

So the control is put where the risk actually is: an allowlist of hosts, derived
from what an administrator configured, checked before every outbound call. A
host nobody configured is refused, and the refusal names the host so the reason
is obvious in an incident.

This is not a substitute for network policy at the deployment layer. It is the
half that belongs in the application, and it is the half that knows *why* a host
is allowed.

Pure: no Indico imports, no network, no clock.
"""

from dataclasses import dataclass
from urllib.parse import urlsplit


class EgressDenied(Exception):
    """A call tried to reach a host this install has not authorised."""


#: Hosts that are never allowed, whatever the settings say. These are the
#: addresses that make a server-side request forgery useful: link-local metadata
#: services and the loopback interface hand out credentials and internal APIs.
NEVER = (
    '169.254.169.254',   # cloud instance metadata
    'metadata.google.internal',
    'localhost',
    '127.0.0.1',
    '::1',
    '0.0.0.0',  # noqa: S104 — matched as a destination, not bound to
)


@dataclass(frozen=True)
class Allowlist:
    """The hosts this install may reach, and why each one is there."""

    #: host -> the capability that justifies it
    hosts: dict

    def check(self, url):
        """Raise unless `url` may be called.

        Returns the host on success so a caller can log what it reached.
        """
        parts = urlsplit(url if '//' in url else f'//{url}')
        host = (parts.hostname or '').lower()
        if not host:
            raise EgressDenied(f'indirizzo senza host: {url!r}')
        if parts.scheme and parts.scheme not in ('https', ''):
            raise EgressDenied(f'solo https è ammesso in uscita, non {parts.scheme!r}')
        if host in NEVER or _is_private(host):
            raise EgressDenied(f'{host} è un indirizzo interno: mai raggiungibile da un agente')
        if host not in self.hosts:
            raise EgressDenied(
                f'{host} non è fra le destinazioni autorizzate su questo impianto. '
                'Un amministratore deve configurare la fonte che lo usa prima che un agente '
                'possa chiamarlo.')
        return host

    def allows(self, url):
        try:
            self.check(url)
        except EgressDenied:
            return False
        return True

    def why(self, host):
        """Which capability justifies a host being reachable."""
        return self.hosts.get(host.lower(), '')


def _is_private(host):
    """Whether a host is an address on a private network.

    Only literal addresses are judged here: resolving a name to decide would be
    a lie, because the name can resolve differently a second later. Names are
    controlled by the allowlist instead.
    """
    import ipaddress

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (address.is_private or address.is_loopback or address.is_link_local
            or address.is_reserved or address.is_unspecified)


def build(entries):
    """An allowlist from `(host, capability)` pairs, ignoring blanks.

    Built from configuration rather than declared in code: the set of reachable
    hosts is a property of the install, and hard-coding it would mean editing
    Python to add a supplier.
    """
    hosts = {}
    for host, capability in entries:
        cleaned = (host or '').strip().lower()
        if not cleaned:
            continue
        # tolerate a full URL where a host was meant
        cleaned = urlsplit(cleaned if '//' in cleaned else f'//{cleaned}').hostname or cleaned
        hosts[cleaned] = capability
    return Allowlist(hosts=hosts)


#: Nothing configured: every outbound call is refused. This is the default, and
#: on an install with no external sources it is also the correct end state.
DENY_ALL = Allowlist(hosts={})
