class GameError(Exception):
    """Erro de regra de negocio, mostrado ao jogador."""


class InsufficientFunds(GameError):
    pass
