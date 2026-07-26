"""Paper-only wallet execution service."""

from .application import WalletService
from .core import RiskPolicy
from .domain import PaperIntent, PaperSignal, WalletExecution

__all__ = [
    "PaperIntent",
    "PaperSignal",
    "RiskPolicy",
    "WalletExecution",
    "WalletService",
]

__version__ = "0.1.0"
