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
