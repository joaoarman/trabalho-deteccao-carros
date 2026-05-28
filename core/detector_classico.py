"""
detector_classico.py — Pipeline OpenCV puro para detectar veículos em movimento

Este módulo concentra a parte de VISÃO COMPUTACIONAL CLÁSSICA. Recebe um frame
e devolve uma lista de bounding boxes (caixas) onde algo está se movendo.

----------------------------------------------------------------------------
Pipeline aplicado a cada frame
----------------------------------------------------------------------------

    frame original
        │
        ▼
    Background Subtraction (MOG2)
        │  Resultado: máscara binária — branco = movimento, preto = fundo
        ▼
    Threshold (remove sombras)
        │  Resultado: máscara estritamente preto/branco
        ▼
    Morfologia (opening + closing)
        │  Resultado: máscara limpa, sem ruído isolado
        ▼
    findContours
        │  Resultado: lista de curvas fechadas
        ▼
    Filtragem por área
        │  Resultado: só contornos com tamanho compatível com veículo
        ▼
    boundingRect → caixas (x, y, w, h)

----------------------------------------------------------------------------
Algoritmos por trás
----------------------------------------------------------------------------

MOG2 (Mixture of Gaussians 2):
    Para cada pixel da imagem, mantém uma "história" das últimas N intensidades
    e modela essa história como uma MISTURA DE GAUSSIANAS (várias curvas
    normais sobrepostas). Quando chega um pixel novo, o algoritmo pergunta:
    "esse valor é compatível com alguma das gaussianas que aprendi?"
        - Sim → faz parte do fundo (preto na máscara).
        - Não → faz parte do primeiro plano (branco na máscara).
    Vantagem sobre métodos mais simples: lida bem com fundo que muda devagar
    (luz que muda, folhas balançando) porque as gaussianas se adaptam.

Morfologia matemática:
    Operações em imagens binárias usando um "kernel" (forma de referência).
    - EROSÃO: pixel fica branco só se TODOS os pixels sob o kernel forem brancos.
              Efeito: encolhe regiões brancas, elimina pontos isolados.
    - DILATAÇÃO: pixel fica branco se PELO MENOS UM pixel sob o kernel for branco.
                 Efeito: cresce regiões brancas, fecha buracos pequenos.
    - OPENING = erosão seguida de dilatação. Remove ruído sem encolher objetos.
    - CLOSING = dilatação seguida de erosão. Fecha buracos sem inflar objetos.

findContours:
    Algoritmo que percorre a máscara binária e identifica curvas fechadas
    (bordas de regiões brancas conectadas). Retorna cada contorno como um
    array de pontos. Usamos cv2.boundingRect() pra obter o menor retângulo
    que envolve cada contorno.
"""

import cv2


class DetectorClassico:
    """Detecta movimento em frames consecutivos usando OpenCV clássico."""

    # -----------------------------------------------------------------------
    # Constantes nomeadas — explicitas no topo facilitam ajuste e explicação
    # -----------------------------------------------------------------------

    # Área mínima de um contorno (em pixels²) pra ser considerado veículo.
    # Abaixo disso é ruído ou sombra de pessoa/folha. Esse valor depende da
    # resolução e do ângulo da câmera — pode precisar ser ajustado por vídeo.
    AREA_MINIMA_PADRAO = 1500

    # Área máxima — descarta blobs gigantes (ex: vários carros grudados).
    AREA_MAXIMA_PADRAO = 80000

    # Threshold de binarização após o MOG2. O MOG2 marca pixels de sombra com
    # valor 127 (cinza) e movimento real com 255 (branco). Cortar em 200
    # descarta as sombras.
    LIMIAR_BINARIO = 200

    # Tamanho do kernel da morfologia. Maior = limpeza mais agressiva, mas
    # pode "engolir" detalhes finos. 5x5 é um bom equilíbrio em 720p.
    TAMANHO_KERNEL = 5

    def __init__(
        self,
        area_minima: int = AREA_MINIMA_PADRAO,
        area_maxima: int = AREA_MAXIMA_PADRAO,
    ):
        self.area_minima = area_minima
        self.area_maxima = area_maxima

        # ----- Background subtraction (MOG2) -----
        # history: nº de frames usados pra modelar o fundo. Mais = mais estável
        #          mas demora mais pra se adaptar a mudanças.
        # varThreshold: limiar de "estranheza". Quanto menor, mais sensível
        #               (mais falsos positivos).
        # detectShadows=True: marca sombras com valor 127 (descartadas depois).
        self.subtrator = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=40, detectShadows=True
        )

        # Kernel elíptico — mais "natural" pra objetos arredondados que retangular.
        self.kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (self.TAMANHO_KERNEL, self.TAMANHO_KERNEL)
        )

    # -----------------------------------------------------------------------
    # Processamento principal
    # -----------------------------------------------------------------------

    def processar(self, frame):
        """Roda o pipeline completo num frame.

        Retorna um dicionário com TODAS as etapas intermediárias, pra que a
        interface possa mostrar qualquer uma sob demanda:

            {
                'mascara_bruta'   : ndarray (HxW)    — saída direta do MOG2
                'mascara_binaria' : ndarray (HxW)    — após threshold (sem sombras)
                'mascara_limpa'   : ndarray (HxW)    — após morfologia
                'contornos'       : list de ndarrays — curvas fechadas
                'caixas'          : list de tuplas   — (x, y, w, h) filtradas
            }
        """

        # ----- 1. Background Subtraction -----
        # Resultado: pixels do primeiro plano = 255, fundo = 0, sombras = 127.
        mascara_bruta = self.subtrator.apply(frame)

        # ----- 2. Threshold pra eliminar sombras -----
        # Qualquer pixel acima de 200 vira 255 (branco); o resto vira 0 (preto).
        _, mascara_binaria = cv2.threshold(
            mascara_bruta, self.LIMIAR_BINARIO, 255, cv2.THRESH_BINARY
        )

        # ----- 3. Morfologia -----
        # OPENING (erosão + dilatação): remove ruído isolado.
        mascara_limpa = cv2.morphologyEx(
            mascara_binaria, cv2.MORPH_OPEN, self.kernel
        )
        # CLOSING (dilatação + erosão): junta partes do mesmo objeto que
        # ficaram separadas. Aplicado 2 vezes pra fechar bem.
        mascara_limpa = cv2.morphologyEx(
            mascara_limpa, cv2.MORPH_CLOSE, self.kernel, iterations=2
        )

        # ----- 4. Contornos -----
        # cv2.RETR_EXTERNAL: ignora contornos internos (buracos dentro de objetos).
        # cv2.CHAIN_APPROX_SIMPLE: compacta a curva — guarda só os "vértices",
        #                          economizando memória.
        contornos, _ = cv2.findContours(
            mascara_limpa, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # ----- 5. Filtragem por área + bounding box -----
        caixas = []
        contornos_validos = []
        for c in contornos:
            area = cv2.contourArea(c)
            if self.area_minima <= area <= self.area_maxima:
                x, y, w, h = cv2.boundingRect(c)
                caixas.append((x, y, w, h))
                contornos_validos.append(c)

        return {
            "mascara_bruta": mascara_bruta,
            "mascara_binaria": mascara_binaria,
            "mascara_limpa": mascara_limpa,
            "contornos": contornos_validos,
            "caixas": caixas,
        }
