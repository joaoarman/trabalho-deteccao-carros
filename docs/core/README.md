# Pacote `core`

Documentação detalhada da lógica de visão computacional. O Flask em `app.py` apenas orquestra estes módulos (leitura, detecção, tracking, contagem e desenho).

## Pipeline por frame

```
LeitorVideo.ler_frame()
        │
        ▼
DetectorClassico.processar()  ou  DetectorYOLO.processar()
        │                              │
        │  caixas: [(x,y,w,h), ...]    │  + deteccoes (só YOLO, para UI)
        ▼
CentroidTracker.atualizar(caixas)
        │
        │  objetos: { id: (cx, cy), ... }
        ▼
Contador.atualizar(objetos)
        │
        ▼
total, por_minuto()
```

Os dois detectores devolvem `caixas` no mesmo formato. O tracker e o contador não precisam saber qual detector foi usado.

## Arquivos

| Arquivo | Documentação |
|---------|----------------|
| `core/__init__.py` | Marca o pacote. Sem lógica. |
| `core/leitor_video.py` | [leitor_video.md](leitor_video.md) |
| `core/detector_classico.py` | [detector_classico.md](detector_classico.md) |
| `core/detector_yolo.py` | [detector_yolo.md](detector_yolo.md) |
| `core/tracker.py` | [tracker.md](tracker.md) |
| `core/contador.py` | [contador.md](contador.md) |

## Quem instancia o quê (`app.py`)

| Componente | Quantidade por stream | Observação |
|------------|----------------------|------------|
| `LeitorVideo` | 1 | Um por conexão `/stream/...` |
| `DetectorClassico` ou `DetectorYOLO` | 1 | Escolhido pelo parâmetro `modo` |
| `CentroidTracker` | 1 | Estado de IDs isolado por stream |
| `Contador` | 1 por modo | Chave `contadores["opencv"]` ou `["yolo"]` |

No modo **comparativo** o navegador abre dois streams. Cada um cria seu próprio detector, tracker e contador. A ROI e o `video_id` são compartilhados em `estado_videos`.

## Contrato entre módulos

### Formato de caixa

Tupla `(x, y, w, h)` em pixels do frame **já redimensionado** (largura máxima 960 em `app.py`):

- `(x, y)` canto superior esquerdo
- `w`, `h` largura e altura

### Formato de objeto rastreado

`OrderedDict` mapeando `id: int` → `(cx, cy)` em float.

### Formato de polígono (contador)

Lista de vértices `[(x1, y1), (x2, y2), ...]` em pixels do mesmo frame processado. Mínimo 3 pontos. `None` ou lista curta desativa contagem.

## Ordem de leitura sugerida

1. [leitor_video.md](leitor_video.md) (entrada de dados)
2. [detector_classico.md](detector_classico.md) ou [detector_yolo.md](detector_yolo.md) (detecção)
3. [tracker.md](tracker.md) (identidade entre frames)
4. [contador.md](contador.md) (regra de negócio da contagem)
