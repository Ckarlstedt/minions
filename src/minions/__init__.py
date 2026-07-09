"""GRU & Minions: trustworthy repository investigation for frontier agents.

GRU (a frontier reasoning agent) delegates investigation questions to a
minion (a small local model) which explores the repository with read-only
tools and returns a compact, citation-verified report.
"""

from minions.config import Settings, load_settings
from minions.report import InvestigationReport
from minions.service import InvestigationService

__version__ = "0.1.0"

__all__ = [
    "InvestigationReport",
    "InvestigationService",
    "Settings",
    "__version__",
    "load_settings",
]
