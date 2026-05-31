# Contador de Veículos

Sistema de contagem de veículos por minuto em vídeos, desenvolvido como trabalho da cadeira de **Tópicos Especiais em Computação** (tema: IA / Ciência de Dados).

O sistema implementa **duas abordagens** de detecção e permite compará-las:

1. **OpenCV clássico** - pipeline de visão computacional tradicional (background subtraction → morfologia → contornos → tracking).
2. **YOLOv8 (deep learning)** - modelo pré-treinado no dataset COCO, capaz de detectar `car`, `truck`, `bus` e `motorcycle`.

A interface web (Flask) permite ao usuário enviar um vídeo, selecionar uma região de interesse (ROI), escolher o modo de processamento e acompanhar a contagem em tempo real.

---

## Setup do ambiente

### Pré-requisitos

- Python 3.10 ou superior
- `pip` instalado e atualizado

### 1. Clonar o repositório e entrar na pasta

```bash
git clone <url-do-repositorio>
cd trabalho-topicos
```

### 2. Criar e ativar o ambiente virtual

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (cmd):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

Quando ativado, o nome do ambiente aparece no início do prompt do terminal (ex: `(venv) $`).

### 3. Atualizar o pip e instalar as dependências

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Verificar que tudo está funcionando

```bash
python -c "import cv2, numpy, flask; print('OK - bibliotecas carregadas')"
```

Se aparecer `OK - bibliotecas carregadas`, o ambiente está pronto.

### 5. Sair do ambiente virtual (quando terminar)

```bash
deactivate
```

---

## Estrutura

O projeto é desenvolvido por etapas. A documentação detalhada de cada etapa fica em `docs/`. As decisões globais, convenções e visão do sistema estão no [`CLAUDE.md`](./CLAUDE.md) na raiz.

---

## Documentação

- [`CLAUDE.md`](./CLAUDE.md) - fonte de verdade do projeto (contexto, decisões, fluxo, convenções)
- [`docs/`](./docs/) - um arquivo `.md` por etapa do desenvolvimento, com explicação didática dos conceitos
