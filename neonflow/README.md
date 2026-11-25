# NeonFlow — Traffic Planning (Ford-Fulkerson)

## Arquivos
- `neonflow.html`: o planejador completo. Abra direto no navegador, funciona offline. É uma boa cópia de segurança para o dia da apresentação.
- `ford_fulkerson.py`: o mesmo algoritmo em Python puro, sem bibliotecas de grafos, para conferir os números.
- `mapa-south-beach.json`: o mapa padrão (28 cruzamentos, 41 ruas, 75 arcos orientados).

```bash
python3 ford_fulkerson.py mapa-south-beach.json                      # fluxo, saturadas, corte mínimo
python3 ford_fulkerson.py mapa-south-beach.json --metodo bfs         # Edmonds-Karp
python3 ford_fulkerson.py mapa-south-beach.json --interditar r40     # Cenário A (MacArthur)
python3 ford_fulkerson.py mapa-south-beach.json --interditar r12 --fator 0.5
python3 ford_fulkerson.py mapa-south-beach.json --obra 800           # Cenário B
```
Qualquer mapa criado no site pode ser exportado (aba **Arquivo → Copiar JSON**) e rodado no script.

## Como cada requisito do enunciado foi atendido
| Requisito | Onde |
|---|---|
| Grafo G=(V,E), arcos de mão única com c(u,v) | Cada rua de mão dupla vira 2 arcos (u→v e v→u). |
| Recorte real com 15 a 20 cruzamentos ou mais | South Beach, Miami Beach (a cidade real que inspirou a Vice City): 28 cruzamentos. |
| Capacidades realistas | Via local 600, avenida de 2 faixas 1.600, avenida de 3 faixas 2.400, ponte de 4 faixas 3.200 veíc/h. |
| Ford-Fulkerson do zero com a rede residual explícita | `RedeResidual` (JS e Python): cada arco tem um par reverso; c_f = c − f. |
| Listar as vias saturadas | Aba **Gargalos** (mais o corte mínimo, que prova o ótimo: Σ = fluxo máximo). |
| Cenário A: interdição ou −50% | Aba **Cenário A**, com a perda percentual e o ranking das ruas mais críticas. |
| Cenário B: +X na melhor rua | Aba **Cenário B**: testa +X em cada arco saturado e recomenda o de maior ganho. |
| Extra | Animação passo a passo dos caminhos aumentantes, DFS e BFS, visualização da rede residual, editor de ruas. |

## Roteiro da apresentação
O roteiro de 3 a 5 minutos está no documento "NeonFlow — Roteiro de apresentação".

Atalhos do planejador: V mover · R nova rua · C cruzamento · O origem · D destino · X apagar · Ctrl+Z desfazer · Esc cancelar ou limpar simulação · roda do mouse para zoom.
