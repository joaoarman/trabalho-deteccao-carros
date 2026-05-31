"""
Conta veículos que entram numa ÁREA (polígono) de interesse

----------------------------------------------------------------------------
Como saber se um ponto está dentro de um polígono - RAY CASTING
----------------------------------------------------------------------------

Algoritmo clássico (também chamado de "regra par-ímpar"):

    A partir do ponto P, dispare um raio horizontal indo pra direita (x → +∞).
    Conte quantas ARESTAS do polígono esse raio cruza.
        - número ÍMPAR de cruzamentos  →  P está DENTRO
        - número PAR (inclui zero)      →  P está FORA

Intuição: cada vez que o raio atravessa a borda, ele alterna entre "fora" e
"dentro". Saindo de fora (no infinito à direita), um número ímpar de trocas
significa que na origem do raio estávamos dentro.

----------------------------------------------------------------------------
Quando contar
----------------------------------------------------------------------------

Contamos um veículo UMA vez: na primeira vez que o centroide dele é visto
dentro da área. Guardamos o ID em `_ja_contados` pra não contar de novo
enquanto ele permanece (ou volta) na área.

Escolhemos "primeira vez dentro" em vez de "transição de fora pra dentro" de
propósito: assim a contagem também funciona quando o usuário seleciona a cena
inteira como área (não existiria um "fora" pra transicionar).

----------------------------------------------------------------------------
Taxa "por minuto"
----------------------------------------------------------------------------

Guardamos o timestamp de cada contagem. A taxa atual = nº de veículos contados
nos últimos 60 segundos (janela móvel), mais informativa que total/tempo.
"""

import time


class Contador:
    """Conta veículos cujo centroide entra numa área poligonal de interesse."""

    def __init__(self, poligono=None):
        """
        poligono: lista de vértices [(x1, y1), (x2, y2), ...] em PIXELS, com ao
                  menos 3 pontos, ou None se ainda não foi definida (não conta).
        """
        self.poligono = poligono
        self.total = 0

        # IDs já contados - evita contar o mesmo veículo a cada frame em que ele
        # continua dentro da área.
        self._ja_contados = set()

        # Timestamps (em segundos) de cada contagem, pra calcular taxa/minuto.
        self._momentos = []

    # ----------------------------------------------------------------------
    # Geometria - ray casting (point-in-polygon)
    # ----------------------------------------------------------------------

    def _dentro(self, ponto) -> bool:
        """Retorna True se `ponto` (px, py) está dentro do polígono."""
        if self.poligono is None or len(self.poligono) < 3:
            return False

        px, py = ponto
        dentro = False
        n = len(self.poligono)

        # `j` começa no último vértice sendo que cada aresta vai do vértice j ao vértice i.
        j = n - 1
        for i in range(n):
            xi, yi = self.poligono[i]
            xj, yj = self.poligono[j]

            # 1) a aresta cruza a altura py?  2) o cruzamento está à direita de px?
            cruza = ((yi > py) != (yj > py)) and (
                px < (xj - xi) * (py - yi) / (yj - yi) + xi
            )
            if cruza:
                dentro = not dentro  # alterna a cada aresta cruzada
            j = i

        return dentro

    # ----------------------------------------------------------------------
    # Atualização
    # ----------------------------------------------------------------------

    def atualizar(self, objetos_rastreados: dict):
        """Recebe {id: centroide} do tracker e conta quem entrou na área."""
        if self.poligono is None:
            return

        for id_obj, centro in objetos_rastreados.items():
            # Já contado antes? Ignora - contamos cada veículo só uma vez.
            if id_obj in self._ja_contados:
                continue
            if self._dentro(centro):
                self.total += 1
                self._ja_contados.add(id_obj)
                self._momentos.append(time.time())

    # ----------------------------------------------------------------------
    # Consulta
    # ----------------------------------------------------------------------

    def por_minuto(self) -> int:
        """Quantos veículos foram contados nos últimos 60 segundos."""
        agora = time.time()
        # Mantem apenas os timestamps dos últimos 60 segundos
        self._momentos = [t for t in self._momentos if agora - t < 60.0]
        return len(self._momentos)

    def resetar(self):
        """Zera o contador. Útil quando o vídeo dá loop ou a área muda."""
        self.total = 0
        self._ja_contados.clear()
        self._momentos.clear()
