"""
Centroid Tracker: associa detecções frame a frame pelo centro da caixa,
atribuindo IDs estáveis (sem isso, o contador contaria o mesmo carro várias vezes).

Compara posições com distância euclidiana (linha reta em pixels):
  d = sqrt((x2 - x1)² + (y2 - y1)²)
"""

from collections import OrderedDict
import numpy as np


def _distancia_pareada(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Matriz D[i,j]: distância euclidiana entre o ponto a[i] e o ponto b[j]."""
    diff = a[:, None, :] - b[None, :, :]
    return np.sqrt(np.sum(diff ** 2, axis=-1))


class CentroidTracker:
    """Centroide = (x + w/2, y + h/2). Entre frames, o mais próximo é o mesmo veículo."""

    def __init__(self, max_desaparecido: int = 30, distancia_maxima: float = 100.0):
        self._proximo_id = 0
        self.objetos: "OrderedDict[int, tuple]" = OrderedDict()  # id -> (cx, cy)
        self.desaparecidos: "OrderedDict[int, int]" = OrderedDict()  # id -> frames sem match
        self.max_desaparecido = max_desaparecido  # tolerância a oclusão ou falha do detector
        self.distancia_maxima = distancia_maxima  # limiar em pixels pra aceitar um match

    def atualizar_params(self, max_desaparecido=None, distancia_maxima=None):
        if max_desaparecido is not None:
            self.max_desaparecido = max_desaparecido
        if distancia_maxima is not None:
            self.distancia_maxima = distancia_maxima

    def _registrar(self, centroide: tuple):
        self.objetos[self._proximo_id] = centroide
        self.desaparecidos[self._proximo_id] = 0
        self._proximo_id += 1

    def _remover(self, id_objeto: int):
        del self.objetos[id_objeto]
        del self.desaparecidos[id_objeto]

    def atualizar(self, caixas: list) -> "OrderedDict[int, tuple]":
        """Entrada: caixas (x,y,w,h) do detector. Saída: {id: centroide}."""

        # Etapa 1: sem detecções no frame. Ninguém para associar e os objetos rastreados somem
        if len(caixas) == 0:
            for id_obj in list(self.desaparecidos.keys()):
                self.desaparecidos[id_obj] += 1
                if self.desaparecidos[id_obj] > self.max_desaparecido:
                    self._remover(id_obj)
            return self.objetos

        # Etapa 2: centroides das caixas deste frame (centro geométrico de cada detecção)
        centroides_novos = np.array(
            [(x + w / 2.0, y + h / 2.0) for (x, y, w, h) in caixas],
            dtype=np.float32,
        )

        # Etapa 3: primeiro frame com detecções. Cada centroide vira um ID novo
        if len(self.objetos) == 0:
            for c in centroides_novos:
                self._registrar((float(c[0]), float(c[1])))
            return self.objetos

        # Etapa 4: matriz de distâncias euclidianas. Cada linha é um objeto rastreado,
        # cada coluna é uma detecção nova. D[i,j] é quantos pixels o centro se moveu
        ids = list(self.objetos.keys())
        centroides_existentes = np.array(list(self.objetos.values()), dtype=np.float32)
        D = _distancia_pareada(centroides_existentes, centroides_novos)

        # Etapa 5: associação greedy, menor distância primeiro. Mesmo ID se d <= limiar
        indices_ordenados = np.argsort(D, axis=None)
        linhas_usadas = set()
        colunas_usadas = set()

        for indice_plano in indices_ordenados:
            linha = int(indice_plano // D.shape[1])
            coluna = int(indice_plano % D.shape[1])

            if linha in linhas_usadas or coluna in colunas_usadas:
                continue
            if D[linha, coluna] > self.distancia_maxima:
                break  # distâncias restantes são maiores (lista ordenada)

            id_obj = ids[linha]
            self.objetos[id_obj] = (
                float(centroides_novos[coluna][0]),
                float(centroides_novos[coluna][1]),
            )
            self.desaparecidos[id_obj] = 0
            linhas_usadas.add(linha)
            colunas_usadas.add(coluna)

        # Etapa 6: rastreados sem par não apareceram neste frame (desaparecido++)
        for i, id_obj in enumerate(ids):
            if i not in linhas_usadas:
                self.desaparecidos[id_obj] += 1
                if self.desaparecidos[id_obj] > self.max_desaparecido:
                    self._remover(id_obj)

        # Etapa 7: detecções sem par são veículo novo na cena (novo ID)
        for j in range(len(centroides_novos)):
            if j not in colunas_usadas:
                self._registrar(
                    (float(centroides_novos[j][0]), float(centroides_novos[j][1]))
                )

        return self.objetos
