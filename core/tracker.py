"""
Centroid Tracker

----------------------------------------------------------------------------
O problema que o tracker resolve
----------------------------------------------------------------------------

O detector clássico (ou o YOLO) devolve a cada frame uma lista de caixas
"este frame tem caixas nas posições A, B, C". Mas ele NÃO diz se a caixa A
deste frame é o MESMO veículo da caixa A do frame anterior, ou se é um carro
diferente. Sem essa associação, contaríamos o mesmo veículo centenas de
vezes (uma por frame em que ele aparece).

Tracker = algoritmo que recebe as detecções de cada frame e atribui IDs
consistentes a objetos físicos ao longo do tempo.

----------------------------------------------------------------------------
Qual é a ideia do Centroid Tracker?
----------------------------------------------------------------------------

CENTROIDE de uma caixa (x, y, w, h) = ponto (x + w/2, y + h/2).
É o centro geométrico da bounding box.

Premissa: entre dois frames consecutivos (separados por ~33ms a 30 FPS), um
veículo se desloca pouco em pixels. Logo, o centroide DESTE frame que mais
parecido com o centroide do frame ANTERIOR provavelmente é o mesmo veículo.

Algoritmo (a cada frame):
    1. Calcula os centroides de todas as caixas detectadas neste frame.
    2. Compara cada um com os centroides dos objetos já rastreados (que
       guardamos da última iteração).
    3. Constrói uma matriz de distâncias (N existentes x M novos).
    4. Greedy: associa o par com menor distância, marca os dois como "usados"
       e repete até todos serem associados - desde que a distância seja
       razoável (abaixo de um limiar).
    5. Existentes sem par são marcados como "desaparecidos". Depois de N
       frames sumido, removemos o ID.
    6. Novos centroides sem par viram IDs novos.

----------------------------------------------------------------------------
Limitações conhecidas
----------------------------------------------------------------------------

- Se dois carros próximos trocarem de posição entre frames, podemos trocar
  os IDs.
- Se um carro desaparecer atrás de outro e reaparecer, ele vai ganhar um ID
  novo.
- Não usa aparência (cor, forma), só posição. Trackers modernos como DeepSORT
  usam embeddings de aparência pra resolver esses casos.
"""

from collections import OrderedDict
import numpy as np


def _distancia_pareada(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Calcula a matriz de distâncias euclidianas entre dois conjuntos de pontos.

    Argumentos:
        a: array shape (n, 2) - n pontos 2D
        b: array shape (m, 2) - m pontos 2D

    Retorna:
        matriz shape (n, m) onde D[i,j] = distância euclidiana entre a[i] e b[j].

    Como funciona o truque com numpy:
        a[:, None, :]   transforma (n,2) em (n,1,2)
        b[None, :, :]   transforma (m,2) em (1,m,2)
        a - b           usa BROADCASTING e gera (n,m,2) com as diferenças
        ** 2            eleva ao quadrado cada componente
        sum(axis=-1)    soma os 2 componentes
        sqrt            tira a raiz

    Isso evita um for duplo em Python e roda muito mais rápido.
    """
    diff = a[:, None, :] - b[None, :, :]
    return np.sqrt(np.sum(diff ** 2, axis=-1))


class CentroidTracker:
    """Rastreia objetos pelo centroide ao longo de frames consecutivos."""

    def __init__(self, max_desaparecido: int = 30, distancia_maxima: float = 100.0):
        """
        max_desaparecido:  por quantos frames um objeto pode "sumir" antes de
                           ser removido do tracker. A 30 FPS, 30 frames = 1 seg.
        distancia_maxima:  pixels de distância máxima pra considerar que dois
                           centroides são o mesmo objeto entre frames.
        """
        self._proximo_id = 0
        # OrderedDict mantém a ordem de inserção - útil pra reconstruir o
        # mapeamento "índice na matriz <-> ID do objeto".
        self.objetos: "OrderedDict[int, tuple]" = OrderedDict()  # id -> (cx, cy)
        self.desaparecidos: "OrderedDict[int, int]" = OrderedDict()  # id -> nº frames sumido

        self.max_desaparecido = max_desaparecido
        self.distancia_maxima = distancia_maxima

    # ----------------------------------------------------------------------
    # Operações internas
    # ----------------------------------------------------------------------

    def _registrar(self, centroide: tuple):
        """Adiciona um novo objeto ao tracker com ID inédito."""
        self.objetos[self._proximo_id] = centroide
        self.desaparecidos[self._proximo_id] = 0
        self._proximo_id += 1

    def _remover(self, id_objeto: int):
        """Esquece um objeto (passou tempo demais sem reaparecer)."""
        del self.objetos[id_objeto]
        del self.desaparecidos[id_objeto]

    # ----------------------------------------------------------------------
    # Atualização - o método principal, chamado a cada frame
    # ----------------------------------------------------------------------

    def atualizar(self, caixas: list) -> "OrderedDict[int, tuple]":
        """Recebe as caixas detectadas neste frame e devolve {id: centroide}."""

        # CASO 1: nenhuma detecção neste frame.
        # Incrementa o "desaparecido" de todos os objetos rastreados e remove
        # quem passou do limite.
        if len(caixas) == 0:
            for id_obj in list(self.desaparecidos.keys()):
                self.desaparecidos[id_obj] += 1
                if self.desaparecidos[id_obj] > self.max_desaparecido:
                    self._remover(id_obj)
            return self.objetos

        # Calcula centroides das caixas detectadas
        centroides_novos = np.array(
            [(x + w / 2.0, y + h / 2.0) for (x, y, w, h) in caixas],
            dtype=np.float32,
        )

        # CASO 2: tracker está vazio (primeiro frame com detecções).
        # Registra todos como novos.
        if len(self.objetos) == 0:
            for c in centroides_novos:
                self._registrar((float(c[0]), float(c[1])))
            return self.objetos

        # CASO 3: temos objetos existentes E novas detecções. Associar.
        ids = list(self.objetos.keys())
        centroides_existentes = np.array(list(self.objetos.values()), dtype=np.float32)

        # Matriz de distâncias (existentes x novos)
        D = _distancia_pareada(centroides_existentes, centroides_novos)

        # Ordena todos os pares por distância crescente e vai associando,
        # desde que nem o objeto existente nem o novo já tenham sido associados.
        indices_ordenados = np.argsort(D, axis=None)

        linhas_usadas = set()    # IDs já associados (índices em `ids`)
        colunas_usadas = set()   # detecções já associadas

        for indice_plano in indices_ordenados:
            # Converte índice 1D em (linha, coluna) na matriz D
            linha = int(indice_plano // D.shape[1])
            coluna = int(indice_plano % D.shape[1])

            if linha in linhas_usadas or coluna in colunas_usadas:
                continue
            # Se a menor distância restante já passou do limiar, paramos -
            # qualquer associação daqui pra frente seria forçada.
            if D[linha, coluna] > self.distancia_maxima:
                break

            id_obj = ids[linha]
            self.objetos[id_obj] = (
                float(centroides_novos[coluna][0]),
                float(centroides_novos[coluna][1]),
            )
            self.desaparecidos[id_obj] = 0
            linhas_usadas.add(linha)
            colunas_usadas.add(coluna)

        # Existentes que NÃO foram associados → ficaram desaparecidos
        for i, id_obj in enumerate(ids):
            if i not in linhas_usadas:
                self.desaparecidos[id_obj] += 1
                if self.desaparecidos[id_obj] > self.max_desaparecido:
                    self._remover(id_obj)

        # Novas detecções que NÃO foram associadas → objetos novos
        for j in range(len(centroides_novos)):
            if j not in colunas_usadas:
                self._registrar(
                    (float(centroides_novos[j][0]), float(centroides_novos[j][1]))
                )

        return self.objetos
