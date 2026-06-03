import cv2


class LeitorVideo:

    def __init__(self, caminho: str):
        self._cap = cv2.VideoCapture(caminho)
        if not self._cap.isOpened():
            raise IOError(f"Não foi possível abrir o vídeo: {caminho}")
        self.caminho = caminho

    @property
    def fps(self) -> float:
        valor = self._cap.get(cv2.CAP_PROP_FPS)
        return valor if valor and valor > 0 else 25.0

    @property
    def largura(self) -> int:
        return int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    @property
    def altura(self) -> int:
        return int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    @property
    def total_frames(self) -> int:
        return int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))

    def ler_frame(self):
        ret, frame = self._cap.read()
        return ret, frame

    def reiniciar(self):
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def fechar(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.fechar()

    def __del__(self):
        self.fechar()
