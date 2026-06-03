# Contador de Veículos

Trabalho da cadeira **Tópicos Especiais em Computação** (tema IA / Ciência de Dados). O sistema conta veículos que entram numa região escolhida no vídeo e mostra total acumulado e taxa por minuto.

## O que o projeto faz

1. O usuário envia um vídeo pela interface web.
2. Desenha um polígono (área de interesse) sobre o preview.
3. Escolhe um modo de processamento:
   - **OpenCV clássico**: subtração de fundo, morfologia, contornos e tracking, com visualização das etapas intermediárias.
   - **YOLO**: detecção com rede pré-treinada (classes car, truck, bus, motorcycle do COCO).
   - **Comparativo**: os dois pipelines lado a lado no mesmo vídeo.
4. Acompanha o vídeo processado em tempo quase real (stream MJPEG) e os números do contador.

A contagem usa o **centroide** de cada objeto rastreado. Cada ID é contado uma vez na primeira entrada na área.

## Tecnologias

| Camada | Stack |
|--------|--------|
| Backend | Python 3.10+, Flask |
| Visão | OpenCV, NumPy |
| Deep learning | Ultralytics YOLOv8 (modelo `yolov8n`) |
| Frontend | HTML (Jinja2), CSS, JavaScript |

## Como rodar

### Pré-requisitos

- Python 3.10 ou superior
- `pip` atualizado

### Passos

```bash
git clone <url-do-repositorio>
cd trabalho-deteccao-carros

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

python app.py
```

Abra no navegador: **http://127.0.0.1:5000**

Na primeira execução do modo YOLO, o Ultralytics pode baixar `yolov8n.pt` se o arquivo não estiver em `modelos/`.

### Vídeos de teste

A pasta [`samples/`](samples/) traz arquivos `highway-1.mp4` até `highway-5.mp4` para testar upload e contagem sem gravar material próprio.

### Verificação rápida das dependências

```bash
python <<'PY'
import cv2, numpy, flask
print('OK')
PY
```

## Fluxo completo (resumo)

```
Upload (/)  →  salva em uploads/, gera video_id
      ↓
Configurar (/configurar/<id>)  →  preview /video/<id>, desenha ROI → POST /api/roi
      ↓
Processar (/processar/<id>/<modo>)  →  <img src="/stream/<id>/opencv|yolo">
      ↓
Por frame no servidor: LeitorVideo → Detector → Tracker → Contador → JPEG no MJPEG
      ↓
Painel lateral: polling GET /api/contador e (no YOLO) GET /api/deteccoes
```

No modo OpenCV, `POST /api/etapa` troca qual etapa do pipeline aparece no stream (1 a 5). No comparativo, dois streams rodam em paralelo com contadores independentes.

## Estrutura do repositório

```
app.py                 # Flask, API, streams MJPEG
core/                  # Leitor, detectores, tracker, contador
templates/             # Páginas HTML
static/css, static/js  # Estilo e interação
uploads/               # Vídeos enviados (criada em runtime)
samples/               # Vídeos de exemplo
docs/                  # Documentação detalhada
```

## Documentação detalhada

- **[Pacote `core`](docs/core/README.md)** - visão do pipeline e índice dos módulos
  - [leitor_video](docs/core/leitor_video.md)
  - [detector_classico](docs/core/detector_classico.md)
  - [detector_yolo](docs/core/detector_yolo.md)
  - [tracker](docs/core/tracker.md)
  - [contador](docs/core/contador.md)
- **[API e frontend](docs/api-frontend.md)** - rotas Flask, estado em memória, streams MJPEG, endpoints JSON e comportamento do `app.js`.

## Estrutura de processamento (OpenCV)

| Etapa | O que aparece |
|-------|----------------|
| 1 | Frame original |
| 2 | Máscara MOG2 |
| 3 | Máscara após morfologia |
| 4 | Contornos e caixas |
| 5 | Tracking, IDs, ROI e contador |
