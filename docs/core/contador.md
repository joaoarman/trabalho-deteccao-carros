# `core/contador.py`

## Função no projeto

Implementa a **regra de negócio da contagem**: quando um veículo (identificado pelo tracker) deve incrementar o total. Usa o centroide do objeto e um polígono em pixels (ROI).

Expõe `total` acumulado e `por_minuto()` (janela móvel de 60 segundos) consumidos por `GET /api/contador` e desenhados no vídeo.

## Dependências

- `time` (stdlib)

## Classe `Contador`

### `__init__(poligono=None)`

| Atributo | Tipo inicial | Função |
|----------|--------------|--------|
| `poligono` | `list` ou `None` | Vértices `[(x,y), ...]` em pixels |
| `total` | `0` | Contagem acumulada desde último `resetar()` |
| `_ja_contados` | `set()` | IDs do tracker já contados |
| `_momentos` | `list` | Timestamps `time.time()` de cada contagem |

Se `poligono` for `None` ou tiver menos de 3 pontos, `_dentro` sempre retorna falso e `atualizar` não incrementa (exceto que `atualizar` retorna cedo se `poligono is None`).

### Origem do polígono em `app.py`

1. Usuário desenha ROI normalizada (0..1) no canvas.
2. `_converter_poligono` multiplica por `largura` e `altura` do frame processado.
3. Se não houver ROI válida, fallback: faixa horizontal central (35% a 65% da altura, largura total).

O contador sempre trabalha em **pixels do frame redimensionado**, não em coordenadas normalizadas.

---

## `_dentro(ponto) -> bool`

### Algoritmo: ray casting (regra par-ímpar)

Dado `ponto = (px, py)` e polígono com `n` vértices:

1. Inicializa `dentro = False`.
2. Para cada aresta do polígono (vértice `i`, vértice anterior `j`):
   - Testa se a aresta cruza a semi-reta horizontal à direita de `P`.
   - Condição implementada:

```python
cruza = ((yi > py) != (yj > py)) and (
    px < (xj - xi) * (py - yi) / (yj - yi) + xi
)
```

3. Se `cruza`, alterna `dentro = not dentro`.

Resultado final: `True` se número de cruzamentos for ímpar (dentro), `False` se par (fora).

### Detalhes numéricos

- Divisão por `(yj - yi)`: aresta horizontal quase paralela ao raio pode ser instável. Polígonos desenhados pelo usuário raramente têm arestas horizontais problemáticas em massa.
- Usa **centroide** `(cx, cy)`, não a caixa inteira. Veículo grande pode ter centroide fora visualmente "dentro" da faixa estreita mesmo com parte do carro na área.

---

## `atualizar(objetos_rastreados: dict)`

Entrada: mesmo dicionário retornado por `CentroidTracker.atualizar`, por exemplo `{ 3: (512.0, 240.0), 7: (100.0, 400.0) }`.

Fluxo por `(id_obj, centro)`:

1. Se `id_obj in _ja_contados` → ignora (já contou este veículo).
2. Se `_dentro(centro)`:
   - `total += 1`
   - adiciona `id_obj` a `_ja_contados`
   - `append(time.time())` em `_momentos`

### Regra: primeira entrada, não cruzamento de borda

O código **não** exige que o objeto estivesse fora no frame anterior. Basta a primeira vez que o centroide está dentro.

Motivo de produto: se o usuário marca a cena inteira como ROI, não existe região "fora". Veículos já dentro no primeiro frame seriam incontáveis com regra de transição.

Consequência: ao iniciar o stream, veículos parados dentro da área podem ser contados no primeiro frame em que o tracker os vê.

### Interação com tracker

- ID removido e recriado pelo tracker (oclusão longa) pode ser contado **de novo** (novo ID).
- Mesmo ID permanecendo dentro da área nunca incrementa de novo.

---

## `por_minuto() -> int`

1. `agora = time.time()`
2. Filtra `_momentos` mantendo só timestamps com `agora - t < 60.0`
3. Retorna `len(_momentos)` após filtro

É taxa na **última janela de 60 segundos reais**, não média desde o início do vídeo. Se o processamento estiver lento (YOLO em CPU), os timestamps ainda são de relógio de parede entre chamadas a `atualizar`.

Chamado a cada poll do frontend e a cada frame desenhado no overlay.

---

## `resetar()`

Zera `total`, limpa `_ja_contados` e `_momentos`.

Chamado em `app.py` quando:

- O vídeo chega ao fim e `leitor.reiniciar()` roda.
- A ROI muda (`roi_atual != roi_normalizada`) e o polígono do contador é atualizado.

**Não** é chamado ao trocar etapa OpenCV na UI.

---

## Integração com `app.py`

```python
contador = Contador(poligono_pixels)
estado_videos[video_id]["contadores"][modo] = contador

# por frame:
contador.atualizar(objetos)

# API:
jsonify({"total": contador.total, "por_minuto": contador.por_minuto()})
```

Modo comparativo mantém dois contadores no mesmo `video_id`:

```python
estado["contadores"]["opencv"]
estado["contadores"]["yolo"]
```

Cada stream grava no seu modo ao iniciar `_gerar_stream`.

### Atualização de ROI ao vivo

Se o usuário salva novo polígono durante o stream:

```python
contador.poligono = _converter_poligono(roi_atual, largura, altura)
contador.resetar()
```

Contagem recomeça do zero com a nova área. IDs antigos no tracker podem ainda existir, mas `_ja_contados` vazio permite recontar se o centroide ainda estiver dentro (comportamento a observar em testes).

---

## Overlay no vídeo

`_desenhar_area` e `_desenhar_contador` em `app.py` leem `contador.poligono`, `contador.total` e `contador.por_minuto()` para desenhar polígono translúcido e faixa de texto.

---

## Exemplo de comportamento

| Frame | ID 5 centroide | `_ja_contados` | `total` |
|-------|----------------|----------------|---------|
| 1 | fora | {} | 0 |
| 2 | dentro | {5} | 1 |
| 3 | dentro | {5} | 1 |
| 4 | fora | {5} | 1 |
| 5 | dentro de novo | {5} | 1 (não incrementa) |

Se ID 5 for removido e ID 8 aparecer no mesmo carro após oclusão, ID 8 pode incrementar de novo.

---

## Limitações

- Contagem por centroide, não por interseção caixa-polígono.
- Polígonos auto-intersectados ou muito irregulares podem confundir ray casting.
- `total` não diminui até `resetar()`.
- Sem persistência: reiniciar servidor zera estado.
- Comparativo: dois contadores independentes, diferença numérica é esperada.

## Teste isolado (exemplo)

```python
from core.contador import Contador

roi = [(0, 100), (500, 100), (500, 200), (0, 200)]
c = Contador(roi)
c.atualizar({1: (250.0, 150.0)})
c.atualizar({1: (250.0, 150.0)})
print(c.total)  # 1
print(c.por_minuto())
```
