# `core/tracker.py`

## Função no projeto

Resolve **identidade temporal**: o detector devolve caixas sem ID. O `CentroidTracker` associa caixas entre frames consecutivos e devolve `{ id: (cx, cy) }`. O contador usa esse ID para não contar o mesmo veículo dezenas de vezes.

Sem tracker, cada frame seria tratado como objetos novos.

## Dependências

- `numpy`
- `collections.OrderedDict` (stdlib)

## Função auxiliar `_distancia_pareada(a, b)`

### Entrada

- `a`: `np.ndarray` shape `(n, 2)` pontos existentes
- `b`: `np.ndarray` shape `(m, 2)` pontos novos

### Saída

- Matriz `D` shape `(n, m)` onde `D[i, j]` é distância euclidiana entre `a[i]` e `b[j]`.

### Implementação

```python
diff = a[:, None, :] - b[None, :, :]
return np.sqrt(np.sum(diff ** 2, axis=-1))
```

Broadcasting evita loop duplo em Python. Com dezenas de objetos por frame o ganho é relevante.

## Classe `CentroidTracker`

### Parâmetros do construtor

| Parâmetro | Padrão | Significado |
|-----------|--------|-------------|
| `max_desaparecido` | 30 | Frames sem associação antes de remover o ID |
| `distancia_maxima` | 100.0 | Distância máxima em pixels entre centroides para considerar mesmo objeto |

A 30 FPS, `max_desaparecido=30` ≈ 1 segundo de tolerância a oclusão breve.

`distancia_maxima` assume deslocamento pequeno entre frames. Vídeo redimensionado a 960 px de largura torna 100 px um passo razoável para estrada vista de cima.

### Estado interno

| Atributo | Tipo | Conteúdo |
|----------|------|----------|
| `_proximo_id` | int | Próximo ID livre (monotônico, nunca reutilizado no mesmo tracker) |
| `objetos` | `OrderedDict[int, tuple]` | `id → (cx, cy)` última posição conhecida |
| `desaparecidos` | `OrderedDict[int, int]` | `id →` contador de frames sem match |

`OrderedDict` preserva ordem de inserção. A ordem de `ids = list(self.objetos.keys())` alinha linhas da matriz `D` com IDs estáveis.

### `_registrar(centroide)`

- Atribui `self._proximo_id` ao novo centroide.
- Inicializa `desaparecidos[id] = 0`.
- Incrementa `_proximo_id`.

### `_remover(id_objeto)`

Remove o ID de `objetos` e `desaparecidos`.

---

## `atualizar(caixas: list) -> OrderedDict`

Método principal. Chamado **uma vez por frame** com a lista `caixas` do detector.

### Passo 0: centroides novos

Se `caixas` não está vazia:

```python
centroides_novos[i] = (x + w/2, y + h/2)
```

Formato float32 em array `(m, 2)`.

---

### Caso A: `len(caixas) == 0`

Nenhuma detecção neste frame.

Para cada ID em `desaparecidos`:

1. Incrementa contador.
2. Se `> max_desaparecido`, chama `_remover`.

Retorna `self.objetos` (pode estar vazio ou com objetos ainda "sumidos" mas não removidos).

---

### Caso B: tracker vazio (`len(self.objetos) == 0`)

Primeiro frame com detecções (ou após todos terem sido removidos).

Cada centroide novo recebe `_registrar`. Retorna `objetos`.

---

### Caso C: associação greedy (núcleo do algoritmo)

1. `ids = list(self.objetos.keys())`
2. `centroides_existentes` array `(n, 2)` das posições guardadas
3. `D = _distancia_pareada(existentes, novos)`
4. `indices_ordenados = np.argsort(D, axis=None)` achata a matriz e ordena índices por distância crescente

Loop sobre `indices_ordenados`:

- Converte índice plano em `(linha, coluna)` na matriz.
- Se linha ou coluna já usada, ignora.
- Se `D[linha, coluna] > distancia_maxima`, **interrompe** o loop (pares restantes seriam piores).
- Caso contrário: atualiza `objetos[ids[linha]]` com centroide novo, zera `desaparecidos`, marca linha e coluna usadas.

**Greedy:** não garante matching global ótimo (como Hungarian), mas é rápido e suficiente para poucos objetos.

---

### Pós-associação: existentes órfãos

Para cada índice `i` em `ids` sem linha usada:

- Incrementa `desaparecidos[id]`
- Remove se passou do limite

---

### Pós-associação: detecções novas órfãs

Para cada coluna `j` sem match:

- `_registrar(centroides_novos[j])` cria ID novo

---

### Retorno

Referência ao mesmo `self.objetos` (mutável). `app.py` passa para `contador.atualizar(objetos)` no mesmo frame.

## Fluxo de dados com vizinhos

```
detector.processar(frame)["caixas"]
        │
        ▼
tracker.atualizar(caixas)  →  { 0: (412.5, 220.0), 1: (90.0, 300.0), ... }
        │
        ▼
contador.atualizar(objetos)
```

O tracker **não** usa classe YOLO nem máscara MOG2. Só geometria da caixa.

## Integração com `app.py`

- Uma instância `CentroidTracker()` por stream HTTP.
- Modo comparativo: tracker OpenCV e tracker YOLO separados (IDs independentes, contagens independentes).
- Reinício do vídeo (`leitor.reiniciar`) **não** reseta o tracker automaticamente no código atual. IDs podem continuar incrementando após o loop. O contador é que `resetar()` no fim do arquivo.
- Mudança de ROI reseta só o `Contador`, não o tracker.

## Desenho na interface

Etapa 5 OpenCV e modo YOLO desenham círculo e texto `ID n` em `(cx, cy)` vindos deste dicionário.

## Limitações

| Cenário | Comportamento |
|---------|---------------|
| Dois carros cruzando perto | Pode trocar IDs entre eles |
| Oclusão longa (> ~1 s) | ID removido, reaparece com ID novo |
| Mesmo carro, caixa saltando muito | Pode falhar match se distância > 100 px num frame |
| Detecção intermitente | `desaparecidos` tolera buracos curtos |
| Aparência | Ignorada (não é DeepSORT) |

## Ajuste fino

| Sintoma | Ação |
|---------|------|
| IDs trocam com frequência | Reduzir FPS efetivo ou aumentar `distancia_maxima` |
| Mesmo veículo vira vários IDs | Aumentar `max_desaparecido` |
| IDs "fantasma" persistem | Diminuir `max_desaparecido` |

## Teste isolado (exemplo)

```python
from core.tracker import CentroidTracker

t = CentroidTracker()
o1 = t.atualizar([(10, 10, 40, 30)])
o2 = t.atualizar([(12, 12, 40, 30)])
print(o1.keys(), o2.keys())  # mesmo ID se movimento pequeno
```
