"""One-task execution capability for positive RAPT Sparge commands.

A lift acknowledgement is not a grant for arbitrary direct BA service calls.
Only the registered, explicitly confirmed Supervised Apply executor can issue
positive preboil writes; the lower source and live-readback gates still apply to
every individual write. No capability persists after execution or across tasks.
"""

from __future__ import annotations

from contextvars import ContextVar

from ..supervised_apply import register_supervised_executor
from . import brewzilla_orchestration as base
from . import brewzilla_rapt_sparge_controller as sparge
from . import brewzilla_source_authority_runtime as source
from . import brewzilla_supervised_runtime_guard as supervised

_INSTALLED = False
_PREVIOUS_WRITE = None
_PREVIOUS_EXECUTE = None
_SUPERVISED_S PARGE = None
