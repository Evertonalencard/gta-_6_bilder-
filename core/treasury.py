from . import config as cfg
from . import events as ev
from .errors import InsufficientFunds


class Treasury:
    """Information Expert do orcamento ("Verba")."""

    def __init__(self, bus, saldo=cfg.VERBA_INICIAL):
        self.bus, self.saldo = bus, float(saldo)

    def gastar(self, valor: float, motivo=""):
        if valor > self.saldo:
            raise InsufficientFunds(f"Verba insuficiente: custa {valor:.0f}, saldo {self.saldo:.0f}.")
        self.saldo -= valor
        self.bus.publish(ev.BUDGET_CHANGED, saldo=self.saldo, motivo=motivo)

    def receber(self, valor: float, motivo=""):
        self.saldo += valor
        self.bus.publish(ev.BUDGET_CHANGED, saldo=self.saldo, motivo=motivo)
