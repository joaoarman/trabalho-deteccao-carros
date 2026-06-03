# `core/detector_classico.py`

## Função no projeto

Implementa detecção por **movimento** (visão computacional clássica). Não classifica tipo de veículo. Qualquer região que se desloca e passa no filtro de área vira uma bounding box.

Contrasta com `detector_yolo.py`, que usa rede neural e nomes de classe COCO.

## Dependências

- `opencv-python` (`cv2`)

## Classe `DetectorClassico`

### Constantes de classe

| Nome | Valor | Papel |
|------|-------|-------|
| `AREA_MINIMA_PADRAO` | 1500 | Área mínima do contorno em px² |
| `AREA_MAXIMA_PADRAO` | 80000 | Área máxima do contorno em px² |
| `LIMIAR_BINARIO` | 254 | Threshold após MOG2 para cortar sombras |
| `TAMANHO_KERNEL` | 5 | Lado do kernel elíptico de morfologia |

Valores calibrados para frames com largura ~960 px após redimensionamento em `app.py`. Outras resoluções podem exigir ajuste via construtor.

### `__init__(area_minima=..., area_maxima=...)`

Cria dois objetos persistentes entre frames:

#### `self.subtrator` (MOG2)

```python
cv2.createBackgroundSubtractorMOG2(
    history=500,
    varThreshold=40,
    detectShadows=True,
)
```

| Parâmetro | Efeito |
|-----------|--------|
| `history` | Quantos frames entram no modelo de fundo. Mais frames = fundo mais estável, adaptação mais lenta |
| `varThreshold` | Quão diferente um pixel precisa ser para virar primeiro plano. Menor = mais sensível (mais ruído) |
| `detectShadows` | Pixels de sombra saem com valor **127** na máscara (não 255) |

O subtrator mantém estado interno. A mesma instância deve processar o vídeo em ordem. Um stream novo em `app.py` cria um `DetectorClassico` novo.

#### `self.kernel`

Kernel elíptico 5×5 para `morphologyEx`. Forma elíptica costuma suavizar blobs de veículos melhor que retângulo.

### `processar(frame)`: pipeline completo

Entrada: `frame` BGR `uint8`, mesmo tamanho em todos os frames do stream.

Saída: dicionário com chaves fixas (sempre presentes).

---

#### Etapa 1: Background subtraction

```python
mascara_bruta = self.subtrator.apply(frame)
```

- Tipo: imagem monocromática `uint8`, mesma altura e largura do frame.
- Valores típicos:
  - **0** fundo
  - **127** sombra (se `detectShadows=True`)
  - **255** primeiro plano (movimento)

Primeiros frames do vídeo ainda "aprendem" o fundo. Detecções podem ser instáveis no começo.

---

#### Etapa 2: Threshold binário

```python
_, mascara_binaria = cv2.threshold(
    mascara_bruta, self.LIMIAR_BINARIO, 255, cv2.THRESH_BINARY
)
```

- Tudo **abaixo de 254** vira 0 (preto).
- Tudo **≥ 254** vira 255 (branco).
- Remove sombras (127) e deixa só movimento forte.

`mascara_binaria` é exposta no retorno mas a UI atual não tem etapa dedicada só a ela.

---

#### Etapa 3: Morfologia

```python
mascara_limpa = cv2.morphologyEx(mascara_binaria, cv2.MORPH_OPEN, self.kernel)
mascara_limpa = cv2.morphologyEx(mascara_limpa, cv2.MORPH_CLOSE, self.kernel, iterations=2)
```

| Operação | Sequência OpenCV | Efeito prático |
|----------|------------------|----------------|
| OPEN | erosão + dilatação | Remove pontos brancos isolados (ruído) |
| CLOSE (×2) | dilatação + erosão | Fecha buracos dentro do mesmo objeto |

Resultado: `mascara_limpa`, usada na **etapa 3** da interface OpenCV.

---

#### Etapa 4: Contornos

```python
contornos, _ = cv2.findContours(
    mascara_limpa, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
)
```

| Flag | Significado |
|------|-------------|
| `RETR_EXTERNAL` | Só contorno externo de cada blob (ignora buracos internos) |
| `CHAIN_APPROX_SIMPLE` | Compacta a curva (menos pontos armazenados) |

`contornos` é lista de arrays NumPy. Usada na **etapa 4** para desenho com `cv2.drawContours`.

---

#### Etapa 5: Filtro de área e bounding boxes

Para cada contorno `c`:

1. `area = cv2.contourArea(c)`
2. Se `area_minima <= area <= area_maxima`:
   - `x, y, w, h = cv2.boundingRect(c)`
   - Adiciona `(x, y, w, h)` em `caixas`
   - Guarda `c` em `contornos_validos`

Contornos fora da faixa são descartados (sombras grandes, pássaros, reflexos pequenos, etc.).

---

### Dicionário de retorno

```python
{
    "mascara_bruta": ndarray,      # H×W, saída MOG2
    "mascara_binaria": ndarray,    # H×W, pós-threshold
    "mascara_limpa": ndarray,      # H×W, pós-morfologia
    "contornos": list,             # só contornos que viraram caixa
    "caixas": list,                # [(x,y,w,h), ...]
}
```

## Integração com `app.py`

| Uso | Onde |
|-----|------|
| `detector.processar(frame)` | `_gerar_stream`, modo `opencv` |
| `resultado["caixas"]` | Entrada do `CentroidTracker` |
| `resultado["mascara_bruta"]` | Etapa 2 em `_renderizar_etapa` |
| `resultado["mascara_limpa"]` | Etapa 3 |
| `resultado["contornos"]` + `caixas` | Etapa 4 |
| Etapa 5 | Frame + caixas + objetos do tracker |

O contador roda em **todas** as etapas (o tracker sempre recebe `caixas`), mas o usuário só vê a contagem desenhada no overlay das etapas renderizadas.

## Integração com etapas da UI (1 a 5)

| Etapa UI | Chave(s) usadas |
|----------|-----------------|
| 1 | Nenhuma do detector (frame cru) |
| 2 | `mascara_bruta` convertida para BGR |
| 3 | `mascara_limpa` convertida para BGR |
| 4 | `contornos`, `caixas` sobre o frame |
| 5 | `caixas` + saída do tracker |

`POST /api/etapa` altera `estado_videos[id]["etapa"]`. O stream lê esse valor a cada frame.

## Ajuste fino

| Objetivo | O que mudar |
|----------|-------------|
| Menos ruído | Aumentar `area_minima` ou `varThreshold` no MOG2 |
| Pegar veículos menores | Diminuir `area_minima` |
| Fundo que muda rápido | Diminuir `history` do MOG2 |
| Blobs fragmentados | Aumentar iterações de CLOSE ou kernel |

## Limitações

- Não distingue veículo de pedestre ou animal em movimento.
- Câmera fixa com fundo relativamente estável funciona melhor.
- Chuva, reflexos, árvores e sombras fortes geram falsos positivos.
- Vários veículos muito próximos podem virar um único contorno grande (uma caixa só).
- Estado do MOG2: reiniciar o vídeo sem nova instância do detector mantém modelo de fundo antigo até `app.py` criar novo stream (nova instância).

## Teste isolado (exemplo)

```python
import cv2
from core.detector_classico import DetectorClassico

cap = cv2.VideoCapture("samples/highway-1.mp4")
det = DetectorClassico()
while True:
    ok, frame = cap.read()
    if not ok:
        break
    r = det.processar(frame)
    print(len(r["caixas"]), "caixas")
cap.release()
```
