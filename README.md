# Traffic Planning - Leonida

Simulador de tráfego urbano em Python Arcade. O frontend desenha o mapa e
encaminha as interações ao `GameController`; o backend mantém a cidade, a
economia e a rede dirigida usada para calcular fluxo máximo com Ford-Fulkerson.

## Executar

Requer Python 3 e a biblioteca Arcade 3.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

Opcionalmente, carregue um mapa salvo ou use busca de caminhos por DFS:

```bash
python main.py --grafo data/mapa.json
python main.py --dfs
```

## Controles

A interface inferior tem três níveis: painel contextual, categorias e barra fixa
de status. Selecione **Estradas** ou **Construções e loteamento** para abrir as
respectivas opções; clique novamente na categoria para recolher o painel.

- **Vias:** escolha Rua de 1 faixa, Rua de 2 faixas, Avenida de 2 faixas ou
  Avenida de 4 faixas e arraste no mapa. Ruas têm capacidade-base de 400
  pessoas/h e avenidas de 1.600 pessoas/h, independentemente do número de faixas.
  Pontos próximos encaixam em cruzamentos, e cruzamentos com vias existentes
  são inseridos automaticamente.
- **Lotes:** escolha Casa, Comércio ou Indústria e mova o cursor perto de uma via
  para pré-visualizar o lote. A prévia indica posições válidas ou inválidas;
  pressione `R` para girar e clique para construir. Lotes exigem acesso à via e
  não podem sobrepor água, vias ou outros lotes.
- **Demolir:** clique em um lote existente ou em uma via.
- **Melhorar, Inverter e Alternar mão:** selecione a ação no painel de estradas
  e clique em uma via.
- **Câmera:** arraste com o botão direito ou do meio, use `WASD` para mover e a
  roda do mouse para controlar o zoom.
- **Barra de status:** pausa, avanço de ciclo e simulação de pico ficam à
  esquerda; orçamento e população são exibidos ao centro.
- **Salvar mapa:** grava o estado atual em `data/mapa.json`.

Ao carregar uma cidade antiga sem lotes físicos, o zoneamento inicial é
migrado para lotes individuais que respeitam as validações de terreno, acesso
à via e sobreposição.

## Estrutura

- `core/`: domínio, grafo, estratégia de caminhos aumentantes, serviços,
  economia, estados das vias e eventos.
- `ui/`: câmera, projeção, ferramentas de interação, painel e renderizadores.
- `bootstrap.py`: composition root que injeta as dependências no controller.
- `assets/` e `data/`: mapa base e grafo inicial.

Execute os testes focados com:

```bash
python -m unittest discover -s tests
```
