# API, servidor Flask e frontend

Este documento descreve como o navegador, o `app.py` e o `static/js/app.js` se comunicam, do upload até os dois streams no modo comparativo.

---

## Arquitetura em camadas

```
┌─────────────────────────────────────────────────────────────┐
│  Templates HTML (Jinja2) + style.css                        │
│  app.js (ROI, etapas, polling)                              │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP (HTML, JSON, MJPEG, arquivo)
┌──────────────────────────▼──────────────────────────────────┐
│  app.py                                                     │
│  rotas de página · API JSON · streams · estado_videos       │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  core/ (LeitorVideo, detectores, tracker, contador)         │
└─────────────────────────────────────────────────────────────┘
```

---

## Estado global `estado_videos`

Chave: `video_id` (12 caracteres hex gerados no upload).

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `caminho` | str | Arquivo em `uploads/{video_id}_{nome}` |
| `roi` | list ou None | Polígono `[[x,y], ...]` com coordenadas **normalizadas** 0..1 |
| `etapa` | int 1..5 | Etapa visual do pipeline OpenCV no stream |
| `contadores` | dict | `opencv` e/ou `yolo` → instância `Contador` |
| `deteccoes` | list | Último frame YOLO: `{classe, confianca, caixa}` |

`_lock_estado` protege criação de entradas. Streams rodam em threads separadas (`threaded=True`) e leem/escrevem `estado_videos` sem lock em cada frame (aceitável neste protótipo em memória).

---

## Fluxo completo do usuário

### 1. Upload (`/` + `POST /upload`)

- **Página:** `index.html` com formulário multipart campo `video`.
- **JS:** `inicializarUpload()` habilita drag-and-drop e exibe nome/tamanho.
- **Backend:** valida extensão, gera `video_id`, salva em `uploads/`, preenche `estado_videos[video_id].caminho`, redireciona para `/configurar/<video_id>`.

### 2. Configuração (`/configurar/<video_id>`)

- **Página:** `configurar.html`.
- **Vídeo bruto:** `<video src="/video/<video_id>">` via rota `servir_video` (arquivo fora de `static/`).
- **ROI:** canvas transparente sobre o vídeo. Cliques viram pontos `{x, y}` em fração 0..1.
- **JS:** `inicializarSelecaoROI()` sincroniza tamanho do bitmap com o CSS (`ResizeObserver`), ajusta `aspect-ratio` do container ao vídeo, envia polígono com `POST /api/roi/<video_id>` quando há ≥ 3 pontos.
- **Backend:** valida pontos e grava em `estado_videos[video_id].roi`.
- **Modos:** links para `/processar/<video_id>/opencv`, `yolo` ou `comparativo`.

### 3. Processamento (`/processar/<video_id>/<modo>`)

| Modo | Template | Stream(s) | JS inicializado |
|------|----------|-----------|-----------------|
| opencv | `processar_opencv.html` | `/stream/.../opencv` | `inicializarPipelineOpenCV` |
| yolo | `processar_yolo.html` | `/stream/.../yolo` | `inicializarYOLO` |
| comparativo | `processar_comparativo.html` | dois `<img>` opencv + yolo | `inicializarComparativo` |

Cada template define `window.VIDEO_ID` no bloco de script e carrega `app.js`.

---

## Rotas de arquivo e stream

### `GET /video/<video_id>`

Serve o MP4 (ou outro formato) original para preview e desenho da ROI. Necessário porque uploads não ficam em `static/`.

### `GET /stream/<video_id>/<modo>`

- `modo` ∈ `opencv` | `yolo`
- Resposta: tipo `multipart/x-mixed-replace` com `boundary=frame`
- Cada parte: cabeçalho MIME + JPEG do frame processado
- O navegador exibe em `<img class="stream" src="...">` sem JavaScript no vídeo em si

**Loop interno (`_gerar_stream`):**

1. Abre `LeitorVideo`, calcula largura/altura de processamento (máx. 960 px).
2. Cria detector, tracker, contador com ROI em pixels.
3. Por frame: ler → redimensionar → detectar → rastrear → contar → renderizar → `imencode` JPEG → `yield` → `sleep` para respeitar FPS.
4. Fim do arquivo: `reiniciar()` + `contador.resetar()`.
5. ROI alterada via API: atualiza polígono e `resetar()` contador.
6. Cliente desconecta: `finally` fecha o leitor.

**Renderização OpenCV (etapas 1 a 5):**

| Etapa | Exibição |
|-------|----------|
| 1 | Frame original |
| 2 | Máscara MOG2 em BGR |
| 3 | Máscara após morfologia |
| 4 | Frame + contornos + caixas |
| 5 | Frame + caixas + centroides com ID + ROI + contador |

Sempre desenha polígono da ROI e faixa com totais.

**Renderização YOLO:**

- Caixas com rótulo `classe confiança`
- Centroides do tracker
- ROI e contador
- Atualiza `estado_videos[video_id].deteccoes` para a API

---

## API JSON

### `POST /api/roi/<video_id>`

**Body:** `{ "pontos": [ {"x": 0.1, "y": 0.2}, ... ] }`

- Mínimo 3 pontos
- `x`, `y` entre 0 e 1
- Resposta: `{ "ok": true }` ou erro 400

### `POST /api/etapa/<video_id>`

**Body:** `{ "etapa": 5 }`

- Só afeta stream OpenCV
- Lido a cada frame em `_gerar_stream`

### `GET /api/contador/<video_id>/<modo>`

**Resposta:** `{ "total": N, "por_minuto": M }`

- `modo`: `opencv` ou `yolo`
- Se o stream ainda não iniciou, retorna zeros

### `GET /api/deteccoes/<video_id>`

**Resposta:** `{ "deteccoes": [ {"classe": "car", "confianca": 0.92}, ... ] }`

- Até 10 itens, ordenados por confiança
- Alimenta lista lateral na tela YOLO

---

## Frontend (`static/js/app.js`)

### Variáveis globais dos templates

- `window.VIDEO_ID`: identificador nas chamadas fetch
- `window.ROI_INICIAL`: polígono salvo ao voltar em "Alterar área" (pares `[x, y]`)

### Polling (500 ms)

O vídeo processado vem pelo MJPEG. Números e listas usam polling:

| Tela | Endpoints |
|------|-----------|
| OpenCV | `/api/contador/.../opencv` |
| YOLO | contador + `/api/deteccoes/...` em paralelo (`Promise.all`) |
| Comparativo | dois contadores, força etapa 5 no OpenCV via `POST /api/etapa` |

### OpenCV: navegação de etapas

- Clique ou setas ← → chamam `selecionarEtapa(n)` e `POST /api/etapa`
- Tecla `A` volta para `/configurar/<id>` (novo stream zera contador ao reprocessar)

### ROI: detalhe importante

Coordenadas são **normalizadas** no cliente e convertidas a pixels no servidor com a resolução **após** redimensionamento (largura máx. 960). O canvas deve ter o mesmo tamanho visual do vídeo (`aspect-ratio` + `ResizeObserver`) para o clique bater com a ROI aplicada no pipeline.

### Fallback de ROI no servidor

Se o usuário iniciar processamento sem 3 pontos salvos, `_converter_poligono` usa faixa horizontal central (35% a 65% da altura, largura total).

---

## Templates

| Arquivo | Função |
|---------|--------|
| `base.html` | Layout, CSS, flash messages, bloco `scripts` |
| `index.html` | Upload |
| `configurar.html` | Preview + canvas ROI + links de modo |
| `processar_opencv.html` | Stream + lista de etapas + contador |
| `processar_yolo.html` | Stream + lista de detecções + contador |
| `processar_comparativo.html` | Dois streams lado a lado + dois contadores |

`style.css` define layout em grade, cores das caixas (espelhadas nas constantes BGR de `app.py`) e estados de etapa ativa.

---

## Execução do servidor

```bash
python app.py
```

- `host=127.0.0.1`, `port=5000`
- `debug=True`, `use_reloader=False` (evita duplicar processos e streams)
- `threaded=True` (stream + API em paralelo)

---

## Modo comparativo em detalhe

Dois clientes HTTP abrem `/stream/.../opencv` e `/stream/.../yolo` ao mesmo tempo. Cada conexão:

- Instancia seu próprio `DetectorClassico` ou `DetectorYOLO`
- Instancia `CentroidTracker` e `Contador` separados
- Grava em `contadores["opencv"]` e `contadores["yolo"]`

O comparativo força etapa 5 no OpenCV para mostrar tracking+contagem alinhado ao YOLO. As contagens **não** são garantidas iguais: detectores e regras de caixa diferem.

---

## Limitações do desenho atual

- Estado só em RAM: reiniciar o servidor perde uploads e ROI.
- Sem autenticação nem limpeza automática de `uploads/`.
- YOLO em CPU pode ficar mais lento que o FPS do vídeo (stream segue o ritmo possível).
- Polling de 500 ms não é tempo real estrito, mas suficiente para o painel numérico.
