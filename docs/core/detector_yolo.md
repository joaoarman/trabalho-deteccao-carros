# `core/detector_yolo.py`

## Função no projeto

Detecção de veículos com **YOLOv8n** (Ultralytics), pré-treinado no dataset COCO. Filtra só classes relacionadas a veículos e devolve caixas no mesmo formato do detector clássico para o tracker.

Informação extra (`classe`, `confianca`) alimenta a lista lateral na tela YOLO via `estado_videos[video_id]["deteccoes"]` em `app.py`.

## Dependências

- `ultralytics` (YOLO)
- `opencv-python` (frame BGR de entrada)
- Opcional: arquivo `modelos/yolov8n.pt` no disco

## Constantes do módulo

### `CLASSES_VEICULOS`

Mapeamento ID COCO → nome em inglês (como no dataset):

| ID | Nome |
|----|------|
| 2 | car |
| 3 | motorcycle |
| 5 | bus |
| 7 | truck |

Outras classes COCO (pessoa, bicicleta, etc.) são ignoradas na inferência com `classes=list(CLASSES_VEICULOS.keys())`.

### Modelo

| Constante | Valor |
|-----------|--------|
| `NOME_MODELO` | `yolov8n.pt` |
| `CAMINHO_MODELO` | `modelos/yolov8n.pt` |

`yolov8n` é a variante nano: menor e mais rápida, menos precisa que `s/m/l/x`.

## Singleton `_obter_modelo()`

### Por que existe

Carregar pesos da rede custa tempo e centenas de MB de RAM. Vários streams YOLO (ou reconexões) devem compartilhar **uma** instância `YOLO`.

### Implementação

Variáveis de módulo:

- `_modelo: YOLO | None`
- `_lock_modelo: threading.Lock`

Fluxo (double-checked locking):

1. Se `_modelo` já existe, retorna.
2. Adquire lock.
3. Testa de novo (outra thread pode ter carregado).
4. Define `origem`:
   - Se `os.path.exists(CAMINHO_MODELO)` → usa caminho local.
   - Senão → passa só `NOME_MODELO` e Ultralytics pode **baixar** na primeira vez (precisa de internet).
5. `_modelo = YOLO(origem)` e retorna.

### Thread safety

Seguro para dois streams `yolo` simultâneos (modo comparativo). O lock só envolve o carregamento inicial.

## Classe `DetectorYOLO`

### `CONFIANCA_MINIMA = 0.4`

Detecções com confiança abaixo disso são descartadas pelo `predict(conf=...)`.

### `__init__(confianca_minima=0.4)`

- Guarda `self.confianca_minima`.
- `self.modelo = _obter_modelo()` (referência compartilhada).

Cada stream pode ter `DetectorYOLO` próprio, mas todos apontam para o mesmo `_modelo` global.

### `processar(frame) -> dict`

#### Chamada à rede

```python
resultados = self.modelo.predict(
    frame,
    conf=self.confianca_minima,
    classes=list(CLASSES_VEICULOS.keys()),
    verbose=False,
)
```

| Argumento | Papel |
|-----------|--------|
| `frame` | BGR NumPy, mesmo formato do OpenCV |
| `conf` | Limiar de confiança mínima |
| `classes` | Restringe saída às IDs de veículo |
| `verbose` | Suprime log por frame no terminal |

`predict` devolve lista com um item por imagem. O código usa `resultados[0]`.

#### Loop em `resultado.boxes`

Para cada `box` (detecção):

1. **Coordenadas** `box.xyxy[0]` → `(x1, y1, x2, y2)` floats.
2. Converte para formato do projeto:
   - `x, y = int(x1), int(y1)`
   - `w, h = int(x2 - x1), int(y2 - y1)`
3. **Classe** `int(box.cls[0])` → nome via `CLASSES_VEICULOS.get(..., "veiculo")`.
4. **Confiança** `float(box.conf[0])`.

#### Retorno

```python
{
    "caixas": [(x, y, w, h), ...],
    "deteccoes": [
        {
            "classe": str,
            "confianca": float,
            "caixa": (x, y, w, h),
        },
        ...
    ],
}
```

| Chave | Consumidor |
|-------|------------|
| `caixas` | `CentroidTracker.atualizar` |
| `deteccoes` | `app.py` grava em `estado_videos` → `GET /api/deteccoes` |

NMS (Non-Max Suppression) é aplicado dentro do Ultralytics. Caixas sobrepostas do mesmo objeto tendem a colapsar na de maior score.

## Integração com `app.py`

```python
detector = DetectorYOLO()  # se modo == "yolo"
resultado = detector.processar(frame)
objetos = tracker.atualizar(resultado["caixas"])
contador.atualizar(objetos)
estado_videos[video_id]["deteccoes"] = resultado["deteccoes"]
frame_display = _renderizar_yolo(frame, resultado, objetos, contador)
```

`_renderizar_yolo` desenha cada item de `deteccoes` com rótulo `classe confiança` e ainda desenha centroides do tracker.

## API `/api/deteccoes`

`app.py` ordena por confiança decrescente e corta em 10 itens. O frontend monta a lista HTML a cada 500 ms.

## Desempenho

- Em CPU, inferência pode ser **mais lenta** que o FPS do vídeo. O stream não dorme além do necessário (`atraso` negativo em `_gerar_stream`).
- GPU acelera se PyTorch/CUDA estiver disponível (configuração do ambiente, não do repositório).
- Modelo compartilhado: segunda conexão YOLO não paga custo de carregamento de pesos de novo.

## Diferença em relação ao detector clássico

| Aspecto | Clássico | YOLO |
|---------|----------|------|
| Sinal detectado | Movimento | Aparência + classe |
| Objeto parado | Não detecta | Detecta se visível |
| Tipo de objeto | Desconhecido | car, bus, etc. |
| Etapas intermediárias | Máscaras MOG2 | Não expõe |
| Estado entre frames | MOG2 | Nenhum no wrapper (rede é por frame) |
| Custo | Baixo | Maior |

Contagens no comparativo **não** precisam coincidir: caixas e momentos de detecção diferem.

## Ajuste fino

| Parâmetro | Efeito |
|-----------|--------|
| `confianca_minima` menor | Mais detecções, mais falsos positivos |
| `confianca_minima` maior | Menos detecções, pode perder veículos distantes |
| Trocar para `yolov8s.pt` etc. | Mais precisão, mais lento (exige mudar constantes e arquivo) |

## Limitações

- Só as quatro classes listadas. Bicicleta (COCO 1) não entra.
- Erros em oclusão forte, veículos muito pequenos ou ângulos incomuns.
- IDs de tracker ainda vêm do centroid tracker, não do YOLO (sem track nativo integrado neste projeto).
- Primeira execução sem `modelos/yolov8n.pt` depende de download.

## Teste isolado (exemplo)

```python
import cv2
from core.detector_yolo import DetectorYOLO

cap = cv2.VideoCapture("samples/highway-1.mp4")
det = DetectorYOLO()
ok, frame = cap.read()
if ok:
    r = det.processar(frame)
    for d in r["deteccoes"]:
        print(d["classe"], d["confianca"])
cap.release()
```
