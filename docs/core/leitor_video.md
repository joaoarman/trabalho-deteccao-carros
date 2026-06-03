# `core/leitor_video.py`

## Função no projeto

Camada fina sobre `cv2.VideoCapture`. Todo frame que entra no pipeline passa por `LeitorVideo.ler_frame()`. O stream MJPEG em `app.py` usa esta classe no gerador `_gerar_stream`.

## Dependências

- `opencv-python` (`cv2`)

## Classe `LeitorVideo`

### Estado interno

| Atributo | Tipo | Descrição |
|----------|------|-----------|
| `_cap` | `cv2.VideoCapture` | Handle do OpenCV |
| `caminho` | `str` | Caminho passado no construtor (referência) |

### `__init__(caminho: str)`

1. Chama `cv2.VideoCapture(caminho)`.
2. Se `isOpened()` for falso, lança `IOError` com mensagem incluindo o caminho.
3. Armazena `caminho` em `self.caminho`.

Não valida extensão nem codec. Isso fica no upload do Flask.

### Propriedades de metadados

Todas leem via `self._cap.get(cv2.CAP_PROP_*)` e convertem para `int` ou `float`.

#### `fps` → `float`

- Lê `CAP_PROP_FPS`.
- Se o valor for `0`, negativo ou ausente, retorna **25.0**.
- Motivo: muitos MP4 de câmera não gravam FPS confiável no container. O throttle do stream usa `delay_alvo = 1.0 / fps`. Sem fallback o delay seria infinito.

#### `largura` / `altura` → `int`

- `CAP_PROP_FRAME_WIDTH` e `CAP_PROP_FRAME_HEIGHT`.
- Usados em `app.py` **antes** do redimensionamento para decidir escala (máx. 960 px de largura).

#### `total_frames` → `int`

- `CAP_PROP_FRAME_COUNT`.
- Pode ser `0` em streams ao vivo. O projeto não usa este valor no fluxo principal hoje.

### `ler_frame()`

Chama `self._cap.read()` e devolve a tupla sem alteração:

| `ret` | `frame` |
|-------|---------|
| `True` | `numpy.ndarray` BGR, shape `(H, W, 3)`, dtype `uint8` |
| `False` | `None` (fim do arquivo ou falha de leitura) |

**Convenção BGR:** canal 0 azul, 1 verde, 2 vermelho. É o padrão do OpenCV, não RGB.

### `reiniciar()`

Define `CAP_PROP_POS_FRAMES` para `0`.

No `_gerar_stream`, quando `ret` é falso:

```python
leitor.reiniciar()
contador.resetar()
continue
```

O vídeo roda em loop infinito na interface.

### `fechar()`

Se `_cap` não for `None`, chama `release()` e zera `_cap`.

### Gerenciamento de recurso

| Mecanismo | Comportamento |
|-----------|---------------|
| `with LeitorVideo(path) as lv:` | `__enter__` retorna `self`, `__exit__` chama `fechar()` |
| `__del__` | Chama `fechar()` se o objeto for coletado sem fechar |
| `finally` em `_gerar_stream` | Garante `fechar()` ao encerrar o stream HTTP |

## Uso em `app.py`

Trecho simplificado do ciclo:

```python
leitor = LeitorVideo(caminho_video)
fps = leitor.fps
largura_original = leitor.largura
altura_original = leitor.altura
# ... redimensiona frame se largura > 960 ...
ret, frame = leitor.ler_frame()
```

Cada cliente `<img src="/stream/...">` mantém seu próprio `LeitorVideo`. Dois streams no comparativo significam duas leituras independentes do mesmo arquivo em disco.

## O que este módulo não faz

- Não redimensiona frames (feito em `app.py` com `cv2.resize`).
- Não decodifica para RGB nem normaliza pixels.
- Não implementa seek por timestamp nem frame N específico além de `reiniciar()` no início.
- Não suporta câmera USB (`0`) no código atual, só caminho de arquivo.

## Teste isolado (exemplo)

```python
from core.leitor_video import LeitorVideo

with LeitorVideo("samples/highway-1.mp4") as lv:
    print(lv.fps, lv.largura, lv.altura)
    for _ in range(5):
        ok, frame = lv.ler_frame()
        if not ok:
            break
        print(frame.shape)
```

## Falhas comuns

| Sintoma | Causa provável |
|---------|----------------|
| `IOError` ao abrir | Caminho errado, arquivo corrompido ou codec sem suporte no OpenCV |
| Vídeo acelerado no navegador | FPS metadado errado (fallback 25 pode não bater com o real) |
| `ret=False` imediato | Arquivo vazio ou formato não legível |
