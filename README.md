# Hello, world! em Python

Projeto mínimo em Python, com ambiente virtual para manter as dependências
isoladas do restante do sistema.

## Pré-requisitos

- Python 3 instalado.
- No Windows, use o comando `py` (Python Launcher). No macOS e Linux, use
  `python3`.

Confira a instalação:

```bash
python3 --version
```

No Windows:

```powershell
py --version
```

## Criar e ativar o ambiente virtual

Execute os comandos na pasta do projeto.

### macOS e Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows — PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear a ativação por causa da política de execução, abra
um terminal Command Prompt (cmd.exe) e use:

```bat
py -m venv .venv
.venv\Scripts\activate.bat
```

## Instalar dependências

Com o ambiente virtual ativado, instale os pacotes listados em
`requirements.txt`:

```bash
python -m pip install -r requirements.txt
```

O arquivo está vazio de dependências externas porque este exemplo usa apenas
a biblioteca padrão do Python. Ao adicionar um pacote, inclua seu nome em
`requirements.txt` e execute novamente o comando acima.

## Executar

Com o ambiente virtual ativado:

```bash
python main.py
```

Saída esperada:

```text
Hello, world!
```

Para sair do ambiente virtual:

```bash
deactivate
```
