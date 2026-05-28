"""
detector_yolo.py — Detecção de veículos com YOLOv8 (deep learning)

Este módulo é a CONTRAPARTE do `detector_classico.py`. Os dois recebem um frame
e devolvem uma lista de caixas (x, y, w, h), então podem ser usados de forma
intercambiável pelo resto do pipeline (tracker + contador). A diferença é COMO
cada um encontra os veículos:

    - detector_classico: subtração de fundo + morfologia + contornos.
      Só sabe "isto se moveu". Não sabe o que é.
    - detector_yolo:     uma rede neural treinada que olha o frame e diz
      "aqui tem um car com 92% de confiança, ali um truck com 81%".

----------------------------------------------------------------------------
O que é o YOLO (You Only Look Once)
----------------------------------------------------------------------------

Detectores antigos passavam uma "janela deslizante" pela imagem, classificando
cada recorte — caríssimo. O YOLO faz tudo numa ÚNICA passada pela rede (daí o
nome): divide a imagem em uma grade e, pra cada célula, prevê de uma vez
    - caixas candidatas (posição + tamanho),
    - a confiança de haver um objeto ali,
    - e a probabilidade de cada classe.
Por isso é rápido o bastante pra rodar em vídeo.

COCO: o modelo `yolov8n.pt` já vem TREINADO no dataset COCO (80 classes de
objetos do dia a dia). Não precisamos treinar nada — só filtrar as classes que
interessam: car, motorcycle, bus, truck.

NMS (Non-Max Suppression): a rede tende a prever várias caixas sobrepostas pro
mesmo objeto. O NMS mantém a de maior confiança e descarta as que se sobrepõem
muito (IoU alto). O ultralytics já aplica NMS internamente.

----------------------------------------------------------------------------
Por que "nano" (yolov8n)?
----------------------------------------------------------------------------

A família YOLOv8 vem em tamanhos n < s < m < l < x. O `n` (nano) é o menor e
mais rápido, ideal pra rodar em CPU comum na apresentação. Tem menos precisão
que os maiores, mas é suficiente pra contar carros — e essa diferença de
precisão x velocidade é, em si, um bom assunto pra discutir.
"""

import os
import threading

import cv2

from ultralytics import YOLO


# IDs das classes de veículos no dataset COCO (a ordem é fixa no COCO).
#   2 = car, 3 = motorcycle, 5 = bus, 7 = truck
CLASSES_VEICULOS = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

# Caminho do modelo pré-treinado. Mantemos uma cópia local em `modelos/` pra
# não depender de internet na hora da apresentação (o ultralytics baixaria
# automaticamente na primeira execução, mas preferimos garantir offline).
CAMINHO_MODELO = os.path.join("modelos", "yolov8n.pt")


# ----------------------------------------------------------------------------
# Carregamento do modelo — uma única vez, compartilhado entre streams
# ----------------------------------------------------------------------------
# Carregar a rede custa tempo e memória. Carregamos UMA vez (lazy: só quando o
# primeiro stream YOLO começa) e reaproveitamos. O lock evita que dois streams
# que começam ao mesmo tempo carreguem o modelo em duplicidade.
_modelo = None
_lock_modelo = threading.Lock()


def _obter_modelo() -> YOLO:
    """Devolve a instância única do modelo YOLO, carregando-a se preciso."""
    global _modelo
    if _modelo is None:
        with _lock_modelo:
            if _modelo is None:  # checagem dupla: outro thread pode ter carregado
                # Se a cópia local não existe, passamos só o nome — aí o
                # ultralytics tenta baixar (exige internet nessa primeira vez).
                origem = CAMINHO_MODELO if os.path.exists(CAMINHO_MODELO) else "yolov8n.pt"
                _modelo = YOLO(origem)
    return _modelo


class DetectorYOLO:
    """Detecta veículos num frame usando YOLOv8 pré-treinado em COCO."""

    # Confiança mínima pra aceitar uma detecção. Abaixo disso, provavelmente é
    # um falso positivo. 0.4 é um equilíbrio razoável pro yolov8n.
    CONFIANCA_MINIMA = 0.4

    def __init__(self, confianca_minima: float = CONFIANCA_MINIMA):
        self.confianca_minima = confianca_minima
        # Dispara o carregamento já na criação (mais previsível que adiar).
        self.modelo = _obter_modelo()

    def processar(self, frame) -> dict:
        """Roda o YOLO num frame e devolve as detecções de veículos.

        Retorna:
            {
                'caixas':    list de (x, y, w, h)  — pro tracker (mesmo formato
                                                      do detector clássico)
                'deteccoes': list de dicts {classe, confianca, caixa}
                             — informação rica pra exibir na interface
            }
        """
        # predict() roda a inferência. Parâmetros:
        #   conf:    descarta detecções abaixo desse limiar de confiança.
        #   classes: filtra direto na rede só as classes que queremos (veículos).
        #   verbose: False pra não poluir o terminal a cada frame.
        resultados = self.modelo.predict(
            frame,
            conf=self.confianca_minima,
            classes=list(CLASSES_VEICULOS.keys()),
            verbose=False,
        )

        caixas = []
        deteccoes = []

        # predict() devolve uma lista (um item por imagem); passamos 1 frame só.
        resultado = resultados[0]
        for box in resultado.boxes:
            # Coordenadas no formato canto-a-canto (x1,y1) = topo-esquerda,
            # (x2,y2) = baixo-direita. Convertemos pra (x, y, w, h) que é o
            # formato que o tracker e o contador esperam.
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
