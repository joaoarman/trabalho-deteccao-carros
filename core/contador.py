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

        # IDs já contados. Evita contar o mesmo veículo a cada frame em que ele
        # continua dentro da área.
        self._ja_contados = set()

        # Timestamps (em segundos) de cada contagem, pra calcular taxa/minuto.
        self._momentos = []

    def _dentro(self, ponto) -> bool:
        """Testa se `ponto` (px, py) está dentro do polígono (ray casting).

        Ideia: imagine um raio horizontal saindo de P e indo para a direita
        (y = py, x >= px). O raio não é desenhado. Para cada aresta do
        polígono, verificamos se ele a cruzaria. Número ímpar de cruzamentos
        significa dentro. Número par, inclusive zero, significa fora.
        """
        if self.poligono is None or len(self.poligono) < 3:
            return False

        px, py = ponto
        dentro = False
        n = len(self.poligono)

        # Percorre arestas fechadas do vértice j ao vértice i, começando
        # pela aresta que liga o último vértice ao primeiro.
        j = n - 1
        for i in range(n):
            xi, yi = self.poligono[i]
            xj, yj = self.poligono[j]

            # Condição 1: a aresta cruza a horizontal y = py?
            # (um extremo acima de py, o outro abaixo ou no mesmo nível)
            cruza_altura = (yi > py) != (yj > py)

            # Condição 2: em y = py, em qual x a aresta cruza? Interpolação
            # linear entre (xi, yi) e (xj, yj). Só conta se x > px, ou seja,
            # o cruzamento está à direita do ponto (no caminho do raio).
            x_cruzamento = (xj - xi) * (py - yi) / (yj - yi) + xi
            cruza = cruza_altura and (px < x_cruzamento)

            if cruza:
                dentro = not dentro  # alterna a cada aresta cruzada (par ou ímpar)
            j = i

        return dentro

    def atualizar(self, objetos_rastreados: dict):
        """Recebe {id: centroide} do tracker e conta quem entrou na área."""
        if self.poligono is None:
            return

        for id_obj, centro in objetos_rastreados.items():
            # Se já contamos esse ID, ignoramos. Cada veículo entra na conta só uma vez.
            if id_obj in self._ja_contados:
                continue
            if self._dentro(centro):
                self.total += 1
                self._ja_contados.add(id_obj)
                self._momentos.append(time.time())

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
