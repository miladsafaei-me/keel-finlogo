"""keel-finlogo: a shared repository of financial-platform logos and country flags.

Public surface::

    from keel_finlogo import resolve_logo, resolve_flag, has_logo

Every image ships as a Django static asset under
``keel_finlogo/logos/<category>/<slug>/`` and ``keel_finlogo/flags/<iso2>/``; a
consumer only needs ``keel_finlogo`` in ``INSTALLED_APPS`` for
``collectstatic`` to pick the files up. ``resolve_logo``/``resolve_flag`` turn a
slug into a ``{% static %}`` URL, consulting ``manifest.json`` for which sizes
actually exist.
"""

from .resolve import has_logo, resolve_flag, resolve_logo

__all__ = ["has_logo", "resolve_flag", "resolve_logo"]

__version__ = "0.1.0"
