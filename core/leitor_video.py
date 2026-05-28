"""
leitor_video.py — Abstração sobre cv2.VideoCapture

`cv2.VideoCapture` é a porta de entrada do OpenCV para vídeo. Ele aceita um
caminho de arquivo (ou índice de webcam) e expõe um objeto que sabe ler
frames sequencialmente.

Esta classe não muda a lógica, só dá nomes em português e organiza o que
geralmente é espalhado em chamadas soltas.

----------------------------------------------------------------------------
Conceitos importantes
----------------------------------------------------------------------------

- Um vídeo é uma SEQUÊNCIA DE FRAMES (imagens) exibidas a uma taxa (FPS).
- Cada frame, no OpenCV, vem como um array numpy de shape (altura, largura, 3).
  Os 3 canais são B, G, R (nessa ordem — não R, G, B, é uma peculiaridade do
  OpenCV por motivos históricos).
- `cap.read()` devolve uma tupla `(ret, frame)`. `ret` é True se conseguiu ler;
  False quando o vídeo acabou ou houve erro.
"""

import cv2


class LeitorVideo:
    """Abre um arquivo de vídeo e oferece leitura sequencial de frames."""

    def __init__(self, caminho: str):
        """Abre o arquivo. Lança IOError se não conseguir."""
        self._cap = cv2.VideoCapture(caminho)
        if not self._cap.isOpened():
            raise IOError(f"Não foi possível abrir o vídeo: {caminho}")
        self.caminho = caminho

    # ------------------------------------------------------------------
    # Propriedades — leitura de metadados do vídeo
    # ------------------------------------------------------------------

    @property
    def fps(self) -> float:
        """Frames por segundo. Crítico pra calcular taxa de veículos/minuto.

        Alguns formatos de vídeo não trazem FPS confiável; nesse caso o OpenCV
        devolve 0. Caímos pra 25 (valor seguro pra vídeos NTSC/PAL típicos).
        """
        valor = self._cap.get(cv2.CAP_PROP_FPS)
        return valor if valor and valor > 0 else 25.0

    @property
    def largura(self) -> int:
        """Largura do frame em pixels."""
        return int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    @property
    def altura(self) -> int:
        """Altura do frame em pixels."""
        return int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    @property
    def total_frames(self) -> int:
        """Quantidade total de frames no vídeo (pode ser 0 em streams)."""
        return int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # ------------------------------------------------------------------
    # Operações principais
    # ------------------------------------------------------------------

    def ler_frame(self):
        """Lê o próximo frame. Retorna (sucesso, frame_bgr) ou (False, None)."""
        ret, frame = self._cap.read()
        return ret, frame

    def reiniciar(self):
        """Volta a leitura pro frame 0. Usado pra fazer loop do vídeo."""
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def fechar(self):
        """Libera o arquivo. Importante chamar; senão o handle fica aberto."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    # ------------------------------------------------------------------
    # Suporte ao `with` — boa prática pra liberar o arquivo automaticamente
    # ------------------------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.fechar()

    def __del__(self):
        # Tentativa de liberar mesmo se o usuário esquecer de chamar fechar()
        self.fechar()
