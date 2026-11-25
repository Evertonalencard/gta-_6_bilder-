"""State: o estado da via decide sua capacidade e como evolui no tempo."""
from abc import ABC, abstractmethod


class RoadState(ABC):
    nome = "normal"
    fator = 1.0

    @abstractmethod
    def tick(self) -> "RoadState":
        ...

    @property
    def ativo(self) -> bool:
        return self.fator < 1.0


class NormalState(RoadState):
    def tick(self):
        return self


class _TimedState(RoadState):
    def __init__(self, restante: int):
        self.restante = restante

    def tick(self):
        return NormalState() if self.restante <= 1 else type(self)(self.restante - 1)


class ObrasState(_TimedState):
    nome, fator = "obra", 0.0           # via interditada


class AcidenteState(_TimedState):
    nome, fator = "acidente", 0.5       # uma faixa bloqueada
