"""
Servidor Flask do Contador de Veículos

Ponto de entrada da aplicação. Responsabilidades:

    1. Receber o upload do vídeo e armazená-lo.
    2. Servir a interface (templates HTML).
    3. Servir o vídeo bruto pra pré-visualização no <video> do navegador.
    4. Servir o STREAM MJPEG do vídeo já processado (pipeline OpenCV).
    5. Expor uma pequena API JSON pra:
        - salvar a ROI selecionada pelo usuário
        - mudar a etapa de visualização ao vivo
        - consultar o contador atual

Estado em memória (estado_videos):
    Mapeia video_id → dicionário com caminho do arquivo, linha de ROI, etapa
    atual e instância do Contador.
"""

import os
import time
import uuid
import threading

import cv2
import numpy as np
from flask import (
    Flask,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.utils import secure_filename

from core.contador import Contador
from core.detector_classico import DetectorClassico
from core.detector_yolo import DetectorYOLO
from core.leitor_video import LeitorVideo
from core.tracker import CentroidTracker


# ============================================================================
# CONFIGURAÇÃO DO APP
# ============================================================================

app = Flask(__name__)
app.secret_key = "desenvolvimento-trabalho-contador-veiculos"

PASTA_UPLOADS = "uploads"
os.makedirs(PASTA_UPLOADS, exist_ok=True)
app.config["UPLOAD_FOLDER"] = PASTA_UPLOADS
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB

EXTENSOES_PERMITIDAS = {"mp4", "avi", "mov", "mkv", "webm"}

# Largura máxima de processamento. Vídeos maiores que isso são redimensionados
# antes de entrar no pipeline. Reduz custo computacional sem perda significativa
# de precisão pra contagem.
LARGURA_PROCESSAMENTO = 960


def extensao_valida(nome_arquivo: str) -> bool:
    """Retorna True se o nome do arquivo termina com uma extensão permitida."""
    if "." not in nome_arquivo:
        return False
    return nome_arquivo.rsplit(".", 1)[1].lower() in EXTENSOES_PERMITIDAS


# ============================================================================
# ESTADO GLOBAL (em memória)
# ============================================================================
# Estrutura por vídeo:
#     {
#         'caminho':    str       - caminho do arquivo em uploads/
#         'roi':        list|None - polígono [[x,y], ...] em coords NORMALIZADAS
#         'etapa':      int       - etapa (1 a 5) que o usuário quer ver (só OpenCV)
#         'contadores': dict      - modo ('opencv'/'yolo') -> Contador
#                                   Guardamos um por modo porque o comparativo
#                                   roda os dois ao mesmo tempo, cada um com a
#                                   sua própria contagem.
#         'deteccoes':  list      - detecções do último frame YOLO (classe +
#                                   confiança), pra alimentar a lista na tela.
#     }
#
# A lock protege escritas concorrentes (cada stream roda em thread separada).
estado_videos = {}
_lock_estado = threading.Lock()


def garantir_estado(video_id: str):
    """Cria entrada padrão pra um video_id se ainda não existe."""
    with _lock_estado:
        if video_id not in estado_videos:
            estado_videos[video_id] = {
                "caminho": None,
                "roi": None,
                "etapa": 1,
                "contadores": {},
                "deteccoes": [],
            }


# ============================================================================
# ROTAS - Interface (HTML)
# ============================================================================

@app.route("/")
def index():
    """Tela inicial com formulário de upload."""
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    """Recebe o vídeo enviado, valida e redireciona pra tela de configuração."""
    if "video" not in request.files:
        flash("Nenhum arquivo enviado.")
        return redirect(url_for("index"))

    arquivo = request.files["video"]
    if arquivo.filename == "":
        flash("Nenhum arquivo selecionado.")
        return redirect(url_for("index"))
    if not extensao_valida(arquivo.filename):
        flash("Formato não suportado. Use mp4, avi, mov, mkv ou webm.")
        return redirect(url_for("index"))

    video_id = uuid.uuid4().hex[:12]
    nome_seguro = secure_filename(arquivo.filename)
    nome_final = f"{video_id}_{nome_seguro}"
    caminho = os.path.join(app.config["UPLOAD_FOLDER"], nome_final)
    arquivo.save(caminho)

    garantir_estado(video_id)
    estado_videos[video_id]["caminho"] = caminho

    return redirect(url_for("configurar", video_id=video_id))


@app.route("/configurar/<video_id>")
def configurar(video_id):
    """Tela onde o usuário desenha a ROI e escolhe o modo de processamento."""
    # `roi_inicial` repovoa o polígono já desenhado antes (fluxo "Alterar área").
    roi_inicial = None
    if video_id != "demo":
        estado = estado_videos.get(video_id)
        if not estado or not estado.get("caminho"):
            flash("Vídeo não encontrado. Faça o upload primeiro.")
            return redirect(url_for("index"))
        nome_arquivo = os.path.basename(estado["caminho"])
        roi_inicial = estado.get("roi")
    else:
        nome_arquivo = "demo.mp4"

    return render_template(
        "configurar.html",
        video_id=video_id,
        nome_arquivo=nome_arquivo,
        roi_inicial=roi_inicial,
        # `eh_demo` desativa partes que dependem de vídeo real (stream, preview).
        eh_demo=(video_id == "demo"),
    )


@app.route("/processar/<video_id>/<modo>")
def processar(video_id, modo):
    """Tela de processamento. modo ∈ {opencv, yolo, comparativo}."""
    if video_id != "demo":
        estado = estado_videos.get(video_id)
        if not estado or not estado.get("caminho"):
            flash("Vídeo não encontrado. Faça o upload primeiro.")
            return redirect(url_for("index"))
        nome_arquivo = os.path.basename(estado["caminho"])
    else:
        nome_arquivo = "demo.mp4"

    templates_por_modo = {
        "opencv": "processar_opencv.html",
        "yolo": "processar_yolo.html",
        "comparativo": "processar_comparativo.html",
    }
    template = templates_por_modo.get(modo)
    if template is None:
        flash(f"Modo inválido: {modo}")
        return redirect(url_for("configurar", video_id=video_id))

    return render_template(
        template,
        video_id=video_id,
        nome_arquivo=nome_arquivo,
        modo=modo,
        eh_demo=(video_id == "demo"),
    )


# ============================================================================
# ROTAS - Servir arquivos de vídeo
# ============================================================================

@app.route("/video/<video_id>")
def servir_video(video_id):
    """Serve o arquivo de vídeo bruto (pra usar em <video> no HTML).

    Sem esta rota o navegador não conseguiria carregar o vídeo enviado, já
    que ele está fora da pasta `static/`.
    """
    estado = estado_videos.get(video_id)
    if not estado or not estado.get("caminho"):
        abort(404)
    return send_file(estado["caminho"])


# ============================================================================
# API JSON - pequena camada pra o JS conversar com o backend
# ============================================================================

@app.route("/api/roi/<video_id>", methods=["POST"])
def api_salvar_roi(video_id):
    """Recebe o polígono de ROI desenhado pelo usuário (em coords normalizadas)."""
    dados = request.get_json(silent=True) or {}
    pontos = dados.get("pontos", [])

    # Aceita um polígono: ao menos 3 pontos pra formar uma área fechada.
    if not (isinstance(pontos, list) and len(pontos) >= 3):
        return jsonify({"ok": False, "erro": "Envie ao menos 3 pontos (polígono)."}), 400

    # Valida que são coords normalizadas (0 ≤ x,y ≤ 1)
    try:
        roi = [[float(p["x"]), float(p["y"])] for p in pontos]
    except (KeyError, TypeError, ValueError):
        return jsonify({"ok": False, "erro": "Formato inválido."}), 400
    for x, y in roi:
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            return jsonify({"ok": False, "erro": "Coordenadas fora de 0..1."}), 400

    garantir_estado(video_id)
    estado_videos[video_id]["roi"] = roi
    return jsonify({"ok": True})


@app.route("/api/etapa/<video_id>", methods=["POST"])
def api_definir_etapa(video_id):
    """Define qual etapa (1..5) o stream deve renderizar."""
    dados = request.get_json(silent=True) or {}
    try:
        etapa = int(dados.get("etapa", 1))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "erro": "Etapa inválida."}), 400
    if etapa < 1 or etapa > 5:
        return jsonify({"ok": False, "erro": "Etapa fora do intervalo 1..5."}), 400

    garantir_estado(video_id)
    estado_videos[video_id]["etapa"] = etapa
    return jsonify({"ok": True})


@app.route("/api/contador/<video_id>/<modo>")
def api_contador(video_id, modo):
    """Devolve {total, por_minuto} do contador de um modo ('opencv' ou 'yolo')."""
    estado = estado_videos.get(video_id) or {}
    contador = estado.get("contadores", {}).get(modo)
    if contador is None:
        return jsonify({"total": 0, "por_minuto": 0})
    return jsonify({"total": contador.total, "por_minuto": contador.por_minuto()})


@app.route("/api/deteccoes/<video_id>")
def api_deteccoes(video_id):
    """Devolve as detecções do último frame YOLO (classe + confiança).

    Usado pela tela do YOLO pra listar o que a rede está vendo agora. Ordenamos
    por confiança decrescente e limitamos a 10 itens pra não poluir a tela.
    """
    estado = estado_videos.get(video_id) or {}
    deteccoes = estado.get("deteccoes", [])
    itens = sorted(deteccoes, key=lambda d: d["confianca"], reverse=True)[:10]
    return jsonify({
        "deteccoes": [
            {"classe": d["classe"], "confianca": round(d["confianca"], 2)}
            for d in itens
        ]
    })


# ============================================================================
# STREAMING MJPEG - um gerador genérico serve OpenCV e YOLO
# ============================================================================
#
# Os dois modos compartilham quase todo o fluxo (abrir vídeo, redimensionar,
# rastrear, contar, codificar JPEG, respeitar o FPS). O QUE MUDA é só:
#     - qual DETECTOR encontra as caixas (clássico vs YOLO), e
#     - como o frame é DESENHADO (etapas do pipeline vs caixas + classes).
# Por isso temos um único `_gerar_stream` parametrizado pelo `modo`, em vez de
# duplicar a lógica.

MODOS_STREAM = {"opencv", "yolo"}


@app.route("/stream/<video_id>/<modo>")
def stream(video_id, modo):
    """Resposta MJPEG: cada frame processado vai como JPEG individual.

    O navegador interpreta `multipart/x-mixed-replace` substituindo a imagem
    anterior pela nova continuamente - efeito de vídeo ao vivo. `modo` escolhe
    o detector ('opencv' ou 'yolo').
    """
    estado = estado_videos.get(video_id)
    if not estado or not estado.get("caminho"):
        abort(404)
    if modo not in MODOS_STREAM:
        abort(404)

    return Response(
        _gerar_stream(video_id, estado["caminho"], modo),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


def _criar_detector(modo):
    """Devolve o detector certo pro modo. Cada stream tem o seu (estado próprio)."""
    if modo == "yolo":
        return DetectorYOLO()
    return DetectorClassico()


def _gerar_stream(video_id, caminho_video, modo):
    """Generator que produz frames processados em loop, pro modo escolhido.

    É o ORQUESTRADOR do pipeline: roda numa thread do Flask enquanto o navegador
    mantém a conexão aberta. Ao desconectar, o generator é interrompido e o
    `finally` libera o vídeo.
    """
    try:
        leitor = LeitorVideo(caminho_video)
    except IOError:
        return

    fps = leitor.fps
    delay_alvo = 1.0 / fps  # tempo desejado entre frames (pra não acelerar o vídeo)

    largura_original = leitor.largura
    altura_original = leitor.altura

    # Se o vídeo é grande, escala pra reduzir custo. Mantém proporção.
    if largura_original > LARGURA_PROCESSAMENTO:
        fator = LARGURA_PROCESSAMENTO / largura_original
        largura = LARGURA_PROCESSAMENTO
        altura = int(altura_original * fator)
    else:
        largura, altura = largura_original, altura_original

    # Componentes do pipeline - um conjunto por stream (estado isolado).
    detector = _criar_detector(modo)
    tracker = CentroidTracker()

    # Converte o polígono normalizado (0..1) em coords de pixel no frame redimensionado
    roi_normalizada = estado_videos[video_id].get("roi")
    poligono_pixels = _converter_poligono(roi_normalizada, largura, altura)

    contador = Contador(poligono_pixels)
    estado_videos[video_id]["contadores"][modo] = contador

    try:
        while True:
            inicio_frame = time.time()

            ret, frame = leitor.ler_frame()
            if not ret:
                # Acabou o vídeo: reinicia (loop infinito) e ressincroniza
                leitor.reiniciar()
                contador.resetar()
                continue

            if frame.shape[1] != largura:
                frame = cv2.resize(frame, (largura, altura))

            # Atualiza a área de ROI ao vivo se o usuário mudou. Como a área
            # mudou, zeramos o contador pra não herdar IDs "já contados" da
            # área antiga (que dariam contagens incoerentes).
            roi_atual = estado_videos[video_id].get("roi")
            if roi_atual != roi_normalizada:
                roi_normalizada = roi_atual
                contador.poligono = _converter_poligono(roi_atual, largura, altura)
                contador.resetar()

            # ----- A parte que muda por modo: detectar + rastrear + contar -----
            resultado = detector.processar(frame)
            objetos = tracker.atualizar(resultado["caixas"])
            contador.atualizar(objetos)

            # ----- E a parte que muda por modo: desenhar -----
            if modo == "yolo":
                # Publica as detecções pra lista na tela conseguir lê-las.
                estado_videos[video_id]["deteccoes"] = resultado["deteccoes"]
                frame_display = _renderizar_yolo(frame, resultado, objetos, contador)
            else:
                # OpenCV: mostra a etapa do pipeline que o usuário selecionou.
                etapa = estado_videos[video_id].get("etapa", 1)
                frame_display = _renderizar_etapa(
                    etapa, frame, resultado, objetos, contador
                )

            # Codifica como JPEG (qualidade 80 = bom equilíbrio tamanho/qualidade)
            ok, buffer = cv2.imencode(
                ".jpg", frame_display, [cv2.IMWRITE_JPEG_QUALITY, 80]
            )
            if not ok:
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
            )

            # Throttle pra respeitar o FPS original do vídeo. (No YOLO em CPU a
            # inferência pode ser mais lenta que o FPS; aí o atraso é negativo e
            # simplesmente seguimos sem dormir - o vídeo roda no ritmo possível.)
            transcorrido = time.time() - inicio_frame
            atraso = delay_alvo - transcorrido
            if atraso > 0:
                time.sleep(atraso)

    finally:
        leitor.fechar()


# ============================================================================
# RENDERIZAÇÃO POR ETAPA - converte intermediários em imagem exibível
# ============================================================================

# Cores BGR (OpenCV usa BGR, não RGB!)
COR_LINHA = (37, 99, 235)        # azul primário da interface
COR_CAIXA = (16, 185, 129)       # verde sucesso
COR_TRAJETO = (245, 158, 11)     # laranja
COR_TEXTO = (255, 255, 255)
COR_TEXTO_FUNDO = (15, 23, 42)   # quase preto, alto contraste

def _renderizar_etapa(etapa, frame, resultado, objetos, contador):
    """Decide o que mostrar baseado na etapa selecionada pelo usuário."""

    if etapa == 1:
        # Frame original cru
        display = frame.copy()

    elif etapa == 2:
        # Máscara bruta do MOG2 (com sombras em cinza)
        display = cv2.cvtColor(resultado["mascara_bruta"], cv2.COLOR_GRAY2BGR)

    elif etapa == 3:
        # Máscara após morfologia (limpa)
        display = cv2.cvtColor(resultado["mascara_limpa"], cv2.COLOR_GRAY2BGR)

    elif etapa == 4:
        # Frame original com contornos e bounding boxes desenhados por cima
        display = frame.copy()
        cv2.drawContours(display, resultado["contornos"], -1, COR_CAIXA, 2)
        for (x, y, w, h) in resultado["caixas"]:
            cv2.rectangle(display, (x, y), (x + w, y + h), COR_CAIXA, 2)

    else:  # etapa == 5: tracking + contagem
        display = frame.copy()
        for (x, y, w, h) in resultado["caixas"]:
            cv2.rectangle(display, (x, y), (x + w, y + h), COR_CAIXA, 2)
        # Desenha centroides e IDs
        for id_obj, (cx, cy) in objetos.items():
            cv2.circle(display, (int(cx), int(cy)), 5, COR_TRAJETO, -1)
            cv2.putText(
                display, f"ID {id_obj}", (int(cx) + 8, int(cy) - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, COR_TRAJETO, 2
            )

    # SEMPRE desenha a área de ROI e o contador no canto
    _desenhar_area(display, contador)
    _desenhar_contador(display, contador, f"Etapa {etapa}")
    return display


def _renderizar_yolo(frame, resultado, objetos, contador):
    """Desenha o frame do modo YOLO: caixas com classe + confiança e contador.

    Diferente do modo clássico (que tem etapas intermediárias), o YOLO já
    entrega objetos com rótulo. Mostramos cada detecção com sua classe e
    confiança, mais o tracking e a área de contagem.
    """
    display = frame.copy()

    # Uma caixa por detecção, com etiqueta "classe 0.92".
    for det in resultado["deteccoes"]:
        x, y, w, h = det["caixa"]
        etiqueta = f"{det['classe']} {det['confianca']:.2f}"
        cv2.rectangle(display, (x, y), (x + w, y + h), COR_CAIXA, 2)

        # Fundo da etiqueta pra o texto ficar legível sobre qualquer cor.
        (largura_texto, altura_texto), _ = cv2.getTextSize(
            etiqueta, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
        )
        cv2.rectangle(
            display, (x, y - altura_texto - 6), (x + largura_texto + 4, y),
            COR_CAIXA, -1
        )
        cv2.putText(display, etiqueta, (x + 2, y - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COR_TEXTO_FUNDO, 1)

    # Centroides + IDs do tracker (mesma ideia da etapa 5 do clássico).
    for id_obj, (cx, cy) in objetos.items():
        cv2.circle(display, (int(cx), int(cy)), 5, COR_TRAJETO, -1)

    _desenhar_area(display, contador)
    _desenhar_contador(display, contador, "YOLO")
    return display


def _desenhar_area(display, contador):
    """Desenha a área de contagem (polígono translúcido + contorno)."""
    if contador.poligono is None or len(contador.poligono) < 3:
        return
    pts = np.array(contador.poligono, dtype=np.int32).reshape((-1, 1, 2))
    # Preenchimento translúcido: pinta a área numa cópia e mistura com o
    # frame (addWeighted), pra destacar a região sem esconder o vídeo.
    overlay = display.copy()
    cv2.fillPoly(overlay, [pts], COR_LINHA)
    cv2.addWeighted(overlay, 0.25, display, 0.75, 0, display)
    # Contorno fechado por cima
    cv2.polylines(display, [pts], isClosed=True, color=COR_LINHA, thickness=3)


def _desenhar_contador(imagem, contador, rotulo):
    """Desenha uma faixa no canto superior esquerdo com o contador.

    `rotulo` identifica o que está sendo mostrado (ex: "Etapa 5", "YOLO").
    """
    texto_total = f"Total: {contador.total}"
    texto_taxa = f"{contador.por_minuto()} / min"

    # Fundo semi-transparente
    overlay = imagem.copy()
    cv2.rectangle(overlay, (10, 10), (230, 100), COR_TEXTO_FUNDO, -1)
    cv2.addWeighted(overlay, 0.6, imagem, 0.4, 0, imagem)

    cv2.putText(imagem, rotulo, (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, COR_TEXTO, 2)
    cv2.putText(imagem, texto_total, (20, 65),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, COR_TEXTO, 2)
    cv2.putText(imagem, texto_taxa, (20, 90),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, COR_TEXTO, 1)


def _converter_poligono(roi_normalizada, largura, altura):
    """Converte o polígono normalizado (0..1) pra pixels.

    Retorna uma lista de vértices [(x, y), ...]. Se nenhuma área válida foi
    desenhada, usa um default: uma faixa central horizontal cobrindo toda a
    largura (35%..65% da altura). Funciona como uma "linha grossa" no meio da
    cena - útil pro demo funcionar mesmo sem o usuário desenhar nada.
    """
    if not roi_normalizada or len(roi_normalizada) < 3:
        y_topo = int(0.35 * altura)
        y_base = int(0.65 * altura)
        return [(0, y_topo), (largura, y_topo), (largura, y_base), (0, y_base)]
    return [(int(x * largura), int(y * altura)) for (x, y) in roi_normalizada]


# ============================================================================
# EXECUÇÃO
# ============================================================================

if __name__ == "__main__":
    # threaded=True permite o stream rodar em paralelo com as requisições da API.
    # debug=True habilita auto-reload e página de erro detalhada.
    # use_reloader=False evita que o servidor abra duas instâncias em debug, o
    # que duplicaria os streams.
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        threaded=True,
        use_reloader=False,
    )
