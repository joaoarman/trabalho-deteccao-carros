import cv2


class DetectorClassico:

    AREA_MINIMA_PADRAO = 1500 # px² - menor que isso é ignorado

    AREA_MAXIMA_PADRAO = 80000 # px² - maior que isso é ignorado

    LIMIAR_BINARIO = 254

    TAMANHO_KERNEL = 5

    def __init__(self):
        self.area_minima = self.AREA_MINIMA_PADRAO
        self.area_maxima = self.AREA_MAXIMA_PADRAO
        self.limiar_binario = self.LIMIAR_BINARIO
        self.tamanho_kernel = self.TAMANHO_KERNEL

        self.subtrator = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=40, detectShadows=True
        )

        self.kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (self.tamanho_kernel, self.tamanho_kernel)
        )

    def atualizar_params(
        self,
        history=None,
        var_threshold=None,
        detect_shadows=None,
        area_minima=None,
        area_maxima=None,
        limiar_binario=None,
        tamanho_kernel=None,
    ):
        if history is not None:
            self.subtrator.setHistory(history)
        if var_threshold is not None:
            self.subtrator.setVarThreshold(var_threshold)
        if detect_shadows is not None:
            self.subtrator.setDetectShadows(detect_shadows)
        if area_minima is not None:
            self.area_minima = area_minima
        if area_maxima is not None:
            self.area_maxima = area_maxima
        if limiar_binario is not None:
            self.limiar_binario = limiar_binario
        if tamanho_kernel is not None:
            self.tamanho_kernel = tamanho_kernel
            self.kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (self.tamanho_kernel, self.tamanho_kernel)
            )

    def processar(self, frame):
        # --- Etapa 1: Background Subtraction ---
        # MOG2 compara o frame com o modelo de fundo aprendido e devolve uma
        # máscara onde 255 = foreground, 127 = sombra, 0 = fundo.
        mascara_bruta = self.subtrator.apply(frame)

        # Threshold descarta as sombras (127) — só fica o foreground real (255).
        _, mascara_binaria = cv2.threshold(
            mascara_bruta, self.limiar_binario, 255, cv2.THRESH_BINARY
        )

        # --- Etapa 2: Morfologia ---
        # OPEN (erosão + dilatação): elimina ruído pequeno e pontos isolados.
        # CLOSE (dilatação + erosão): fecha buracos dentro dos objetos detectados.
        mascara_limpa = cv2.morphologyEx(
            mascara_binaria, cv2.MORPH_OPEN, self.kernel
        )
        mascara_limpa = cv2.morphologyEx(
            mascara_limpa, cv2.MORPH_CLOSE, self.kernel, iterations=2
        )

        # --- Etapa 3: Detecção de contornos ---
        # Encontra as curvas fechadas dos objetos brancos na máscara limpa.
        # RETR_EXTERNAL ignora contornos internos (buracos); CHAIN_APPROX_SIMPLE
        # comprime segmentos retos pra economizar memória.
        contornos, _ = cv2.findContours(
            mascara_limpa, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # --- Etapa 4: Filtro por área ---
        # Descarta contornos muito pequenos (ruído residual) e muito grandes
        # (reflexos, sombras extensas). O que sobra são os candidatos a veículo.
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
