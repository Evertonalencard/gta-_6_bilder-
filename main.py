"""API do simulador de cidade (SimCity + Fluxo Maximo). Rodar: uvicorn main:app --reload"""
from typing import Literal, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from city import City, GameError, cidade_exemplo

app = FastAPI(title="Traffic Planning - Ford-Fulkerson")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

state = {"city": cidade_exemplo()}
Metodo = Literal["bfs", "dfs"]


def game() -> City:
    return state["city"]


def guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except GameError as e:
        raise HTTPException(400, str(e))


class ConstruirIn(BaseModel):
    tipo: Literal["casa", "comercio", "industria"]

class ViaIn(BaseModel):
    u: int
    v: int
    tipo: Literal["rua", "avenida"] = "rua"
    faixas: int = 1
    mao_unica: bool = False

class MelhoriaIn(BaseModel):
    tipo: Optional[Literal["rua", "avenida"]] = None
    faixas: Optional[int] = None

class MaoIn(BaseModel):
    mao_unica: bool

class CenarioAIn(BaseModel):
    via: int
    modo: Literal["interditar", "faixa"] = "interditar"
    sentido: Optional[Literal["fw", "bw"]] = None
    cenario: Literal["normal", "evento"] = "evento"
    veiculos: int = 3000
    metodo: Metodo = "bfs"

class CenarioBIn(BaseModel):
    x: int = Field(600, gt=0)
    cenario: Literal["normal", "evento"] = "evento"
    veiculos: int = 3000
    metodo: Metodo = "bfs"

class TempoIn(BaseModel):
    pico: bool = False
    veiculos: int = 3000


def demanda(cenario, veiculos):
    c = game()
    return guard(c.demanda_evento, veiculos) if cenario == "evento" else c.demanda_diaria()


@app.get("/api/cidade")
def get_cidade():
    return game().to_dict()

@app.post("/api/reiniciar")
def reiniciar():
    state["city"] = cidade_exemplo()
    return game().to_dict()

@app.post("/api/nos/{node_id}/construir")
def construir(node_id: int, body: ConstruirIn):
    guard(game().construir, node_id, body.tipo)
    return game().to_dict()

@app.post("/api/vias")
def criar_via(body: ViaIn):
    r = guard(game().construir_via, body.u, body.v, body.tipo, body.faixas, body.mao_unica)
    return {"via": r.__dict__, "verba": game().verba}

@app.post("/api/vias/{road_id}/melhorar")
def melhorar(road_id: int, body: MelhoriaIn):
    r = guard(game().melhorar_via, road_id, body.tipo, body.faixas)
    return {"via": r.__dict__, "verba": game().verba}

@app.post("/api/vias/{road_id}/inverter")
def inverter(road_id: int):
    r = guard(game().inverter_via, road_id)
    return {"via": r.__dict__}

@app.post("/api/vias/{road_id}/mao")
def mao(road_id: int, body: MaoIn):
    r = guard(game().definir_mao, road_id, body.mao_unica)
    return {"via": r.__dict__, "verba": game().verba}

@app.get("/api/fluxo")
def fluxo(cenario: Literal["normal", "evento"] = "evento", veiculos: int = 3000, metodo: Metodo = "bfs"):
    """Fluxo maximo + cores (verde/amarelo/vermelho) + vias saturadas + corte minimo."""
    res, _ = game().analisar(*demanda(cenario, veiculos), metodo=metodo)
    return res

@app.post("/api/cenarios/a")
def cenario_a(body: CenarioAIn):
    f, s = demanda(body.cenario, body.veiculos)
    return guard(game().cenario_a, f, s, body.via, body.modo, body.sentido, body.metodo)

@app.post("/api/cenarios/b")
def cenario_b(body: CenarioBIn):
    f, s = demanda(body.cenario, body.veiculos)
    return guard(game().cenario_b, f, s, body.x, body.metodo)

@app.post("/api/avancar-tempo")
def avancar(body: TempoIn):
    c = game()
    out = {"ciclo": guard(c.avancar_ciclo)}
    if body.pico:
        out["pico"] = guard(c.horario_pico, body.veiculos)
    out["verba"] = c.verba
    return out
