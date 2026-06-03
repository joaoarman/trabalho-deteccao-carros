import os
import threading

from ultralytics import YOLO


CLASSES_VEICULOS = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

NOME_MODELO = "yolo26n.pt"
CAMINHO_MODELO = os.path.join("modelos", NOME_MODELO)

_modelo = None
_lock_modelo = threading.Lock()


def _obter_modelo() -> YOLO:
    global _modelo
    if _modelo is None:
        with _lock_modelo:
            if _modelo is None:
                origem = CAMINHO_MODELO if os.path.exists(CAMINHO_MODELO) else NOME_MODELO
                _modelo = YOLO(origem)
    return _modelo


class DetectorYOLO:

    CONFIANCA_MINIMA = 0.4

    @classmethod
    def params_padrao(cls):
        return {"confianca_minima": cls.CONFIANCA_MINIMA}

    def __init__(self, confianca_minima: float = CONFIANCA_MINIMA):
        self.confianca_minima = confianca_minima
        self.modelo = _obter_modelo()

    def atualizar_params(self, confianca_minima=None):
        if confianca_minima is not None:
            self.confianca_minima = confianca_minima

    def processar(self, frame) -> dict:
        resultados = self.modelo.predict(
            frame,
            conf=self.confianca_minima,
            classes=list(CLASSES_VEICULOS.keys()),
            verbose=False,
        )

        caixas = []
        deteccoes = []

        resultado = resultados[0]
        for box in resultado.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            x, y = int(x1), int(y1)
            w, h = int(x2 - x1), int(y2 - y1)

            id_classe = int(box.cls[0])
            confianca = float(box.conf[0])
            nome_classe = CLASSES_VEICULOS.get(id_classe, "veiculo")

            caixas.append((x, y, w, h))
            deteccoes.append(
                {"classe": nome_classe, "confianca": confianca, "caixa": (x, y, w, h)}
            )

        return {"caixas": caixas, "deteccoes": deteccoes}
