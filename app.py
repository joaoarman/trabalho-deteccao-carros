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


app = Flask(__name__)
app.secret_key = "desenvolvimento-trabalho-contador-veiculos"

PASTA_UPLOADS = "uploads"
os.makedirs(PASTA_UPLOADS, exist_ok=True)
app.config["UPLOAD_FOLDER"] = PASTA_UPLOADS
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

EXTENSOES_PERMITIDAS = {"mp4", "avi", "mov", "mkv", "webm"}

LARGURA_PROCESSAMENTO = 960

MODOS_STREAM = {"opencv", "yolo"}

estado_videos = {}
_lock_estado = threading.Lock()


def extensao_valida(nome_arquivo: str) -> bool:
    if "." not in nome_arquivo:
        return False
    return nome_arquivo.rsplit(".", 1)[1].lower() in EXTENSOES_PERMITIDAS


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
    params_iniciais = estado_videos[video_id].get("params_detector", {})
    detector = _criar_detector(modo, params_iniciais)
    tracker = CentroidTracker()

    params_aplicados = dict(params_iniciais)

    # Converte o polígono normalizado (0..1) em coords de pixel no frame redimensionado
    roi_normalizada = estado_videos[video_id].get("roi")
    poligono_pixels = _converter_poligono(roi_normalizada, largura, altura)

    contador = Contador(poligono_pixels)
    estado_videos[video_id]["contadores"][modo] = contador

    try:
        while True:
            inicio_frame = time.time()

            with _lock_estado:
                flags = estado_videos.get(video_id, {}).get("reiniciar_streams", {})
                if flags.pop(modo, False):
                    leitor.reiniciar()
                    contador.resetar()
                    tracker = CentroidTracker()
                    if modo == "opencv":
                        detector = _criar_detector(modo, params_aplicados)
                    elif modo == "yolo":
                        estado_videos[video_id]["deteccoes"] = []

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

            # Aplica parâmetros atualizados ao vivo se o usuário mudou.
            params_atuais = estado_videos[video_id].get("params_detector", {})
            if modo == "opencv" and params_atuais != params_aplicados:
                detector.atualizar_params(
                    history=params_atuais.get("history"),
                    var_threshold=params_atuais.get("var_threshold"),
                    detect_shadows=params_atuais.get("detect_shadows"),
                    area_minima=params_atuais.get("area_minima"),
                    area_maxima=params_atuais.get("area_maxima"),
                    limiar_binario=params_atuais.get("limiar_binario"),
                    tamanho_kernel=params_atuais.get("tamanho_kernel"),
                )
                params_aplicados = dict(params_atuais)
            elif modo == "yolo":
                padrao_yolo = DetectorYOLO.params_padrao()
                conf_nova = params_atuais.get(
                    "confianca_minima", padrao_yolo["confianca_minima"]
                )
                conf_velha = params_aplicados.get(
                    "confianca_minima", padrao_yolo["confianca_minima"]
                )
                if conf_nova != conf_velha:
                    detector.atualizar_params(confianca_minima=conf_nova)
                    params_aplicados["confianca_minima"] = conf_nova

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
                etapa = estado_videos[video_id].get("etapa", 5)
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


def _criar_detector(modo, params=None):
    params = params or {}
    if modo == "yolo":
        padrao = DetectorYOLO.params_padrao()
        conf = params.get("confianca_minima", padrao["confianca_minima"])
        return DetectorYOLO(confianca_minima=conf)
    padrao = DetectorClassico.params_padrao()
    detector = DetectorClassico()
    detector.atualizar_params(
        history=params.get("history", padrao["history"]),
        var_threshold=params.get("var_threshold", padrao["var_threshold"]),
        detect_shadows=params.get("detect_shadows", padrao["detect_shadows"]),
        area_minima=params.get("area_minima", padrao["area_minima"]),
        area_maxima=params.get("area_maxima", padrao["area_maxima"]),
        limiar_binario=params.get("limiar_binario", padrao["limiar_binario"]),
        tamanho_kernel=params.get("tamanho_kernel", padrao["tamanho_kernel"]),
    )
    return detector


def garantir_estado(video_id: str):
    with _lock_estado:
        if video_id not in estado_videos:
            estado_videos[video_id] = {
                "caminho": None,
                "roi": None,
                "etapa": 5,
                "contadores": {},
                "deteccoes": [],
                "params_detector": _params_detector_padrao(),
                "reiniciar_streams": {"opencv": False, "yolo": False},
            }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
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
    estado = estado_videos.get(video_id)
    if not estado or not estado.get("caminho"):
        flash("Vídeo não encontrado. Faça o upload primeiro.")
        return redirect(url_for("index"))

    return render_template(
        "configurar.html",
        video_id=video_id,
        nome_arquivo=os.path.basename(estado["caminho"]),
        roi_inicial=estado.get("roi"),
    )


@app.route("/processar/<video_id>/<modo>")
def processar(video_id, modo):
    estado = estado_videos.get(video_id)
    if not estado or not estado.get("caminho"):
        flash("Vídeo não encontrado. Faça o upload primeiro.")
        return redirect(url_for("index"))

    templates_por_modo = {
        "opencv": "processar_opencv.html",
        "yolo": "processar_yolo.html",
    }
    template = templates_por_modo.get(modo)
    if template is None:
        flash(f"Modo inválido: {modo}")
        return redirect(url_for("configurar", video_id=video_id))

    garantir_estado(video_id)
    params_detector = estado_videos[video_id]["params_detector"]

    return render_template(
        template,
        video_id=video_id,
        nome_arquivo=os.path.basename(estado["caminho"]),
        modo=modo,
        params_detector=params_detector,
    )


@app.route("/video/<video_id>")
def servir_video(video_id):
    estado = estado_videos.get(video_id)
    if not estado or not estado.get("caminho"):
        abort(404)
    return send_file(estado["caminho"])


@app.route("/api/roi/<video_id>", methods=["POST"])
def api_salvar_roi(video_id):
    dados = request.get_json(silent=True) or {}
    pontos = dados.get("pontos", [])

    if not (isinstance(pontos, list) and len(pontos) >= 3):
        return jsonify({"ok": False, "erro": "Envie ao menos 3 pontos (polígono)."}), 400

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
    dados = request.get_json(silent=True) or {}
    try:
        etapa = int(dados.get("etapa", 5))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "erro": "Etapa inválida."}), 400
    if etapa < 1 or etapa > 5:
        return jsonify({"ok": False, "erro": "Etapa fora do intervalo 1..5."}), 400

    garantir_estado(video_id)
    estado_videos[video_id]["etapa"] = etapa
    return jsonify({"ok": True})


@app.route("/api/contador/<video_id>/<modo>")
def api_contador(video_id, modo):
    estado = estado_videos.get(video_id) or {}
    contador = estado.get("contadores", {}).get(modo)
    if contador is None:
        return jsonify({"total": 0, "por_minuto": 0})
    return jsonify({"total": contador.total, "por_minuto": contador.por_minuto()})


@app.route("/api/deteccoes/<video_id>")
def api_deteccoes(video_id):
    estado = estado_videos.get(video_id) or {}
    deteccoes = estado.get("deteccoes", [])
    itens = sorted(deteccoes, key=lambda d: d["confianca"], reverse=True)[:10]
    return jsonify({
        "deteccoes": [
            {"classe": d["classe"], "confianca": round(d["confianca"], 2)}
            for d in itens
        ]
    })


def _params_detector_padrao():
    return {**DetectorClassico.params_padrao(), **DetectorYOLO.params_padrao()}


@app.route("/api/params/<video_id>", methods=["GET"])
def api_get_params(video_id):
    estado = estado_videos.get(video_id) or {}
    return jsonify(estado.get("params_detector") or _params_detector_padrao())


@app.route("/api/params/<video_id>", methods=["POST"])
def api_set_params(video_id):
    dados = request.get_json(silent=True) or {}

    inteiros_positivos = {
        "history": (1, 5000),
        "area_minima": (1, 500000),
        "area_maxima": (1, 500000),
        "limiar_binario": (1, 255),
        "tamanho_kernel": (1, 31),
    }
    numeros_positivos = {
        "var_threshold": (0.1, 1000),
        "confianca_minima": (0.01, 0.99),
    }

    convertidos = {}
    erros = []

    for campo, (minimo, maximo) in inteiros_positivos.items():
        valor = dados.get(campo)
        if valor is None:
            continue
        try:
            valor = int(valor)
            if not (minimo <= valor <= maximo):
                raise ValueError
            convertidos[campo] = valor
        except (TypeError, ValueError):
            erros.append(f"{campo} deve ser inteiro entre {minimo} e {maximo}")

    for campo, (minimo, maximo) in numeros_positivos.items():
        valor = dados.get(campo)
        if valor is None:
            continue
        try:
            valor = float(valor)
            if not (minimo <= valor <= maximo):
                raise ValueError
            convertidos[campo] = valor
        except (TypeError, ValueError):
            erros.append(f"{campo} deve ser número entre {minimo} e {maximo}")

    detect_shadows = dados.get("detect_shadows")
    if detect_shadows is not None:
        if not isinstance(detect_shadows, bool):
            erros.append("detect_shadows deve ser true ou false")
        else:
            convertidos["detect_shadows"] = detect_shadows

    if erros:
        return jsonify({"ok": False, "erros": erros}), 400

    garantir_estado(video_id)
    params = estado_videos[video_id]["params_detector"]
    params.update(convertidos)

    return jsonify({"ok": True, "params_detector": params})


@app.route("/api/reiniciar/<video_id>", methods=["POST"])
def api_reiniciar(video_id):
    dados = request.get_json(silent=True) or {}
    modos = dados.get("modos")
    if modos is None and dados.get("modo"):
        modos = [dados["modo"]]
    if not isinstance(modos, list) or not modos:
        return jsonify({"ok": False, "erro": "Envie modos: ['opencv'] e/ou ['yolo']."}), 400

    modos_validos = []
    for modo in modos:
        if modo not in MODOS_STREAM:
            return jsonify({"ok": False, "erro": f"Modo inválido: {modo}"}), 400
        modos_validos.append(modo)

    garantir_estado(video_id)
    with _lock_estado:
        flags = estado_videos[video_id].setdefault(
            "reiniciar_streams", {"opencv": False, "yolo": False}
        )
        for modo in modos_validos:
            flags[modo] = True

    return jsonify({"ok": True, "modos": modos_validos})


COR_LINHA = (37, 99, 235)
COR_CAIXA = (16, 185, 129)
COR_TRAJETO = (245, 158, 11)
COR_TEXTO = (255, 255, 255)
COR_TEXTO_FUNDO = (15, 23, 42)


def _renderizar_etapa(etapa, frame, resultado, objetos, contador):
    if etapa == 1:
        display = frame.copy()

    elif etapa == 2:
        display = cv2.cvtColor(resultado["mascara_bruta"], cv2.COLOR_GRAY2BGR)

    elif etapa == 3:
        display = cv2.cvtColor(resultado["mascara_limpa"], cv2.COLOR_GRAY2BGR)

    elif etapa == 4:
        display = frame.copy()
        cv2.drawContours(display, resultado["contornos"], -1, COR_CAIXA, 2)
        for (x, y, w, h) in resultado["caixas"]:
            cv2.rectangle(display, (x, y), (x + w, y + h), COR_CAIXA, 2)

    else:
        display = frame.copy()
        for (x, y, w, h) in resultado["caixas"]:
            cv2.rectangle(display, (x, y), (x + w, y + h), COR_CAIXA, 2)
        for id_obj, (cx, cy) in objetos.items():
            cv2.circle(display, (int(cx), int(cy)), 5, COR_TRAJETO, -1)
            cv2.putText(
                display, f"ID {id_obj}", (int(cx) + 8, int(cy) - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, COR_TRAJETO, 2
            )

    _desenhar_area(display, contador)
    _desenhar_contador(display, contador, f"Etapa {etapa}")
    return display


def _renderizar_yolo(frame, resultado, objetos, contador):
    display = frame.copy()

    for det in resultado["deteccoes"]:
        x, y, w, h = det["caixa"]
        etiqueta = f"{det['classe']} {det['confianca']:.2f}"
        cv2.rectangle(display, (x, y), (x + w, y + h), COR_CAIXA, 2)

        (largura_texto, altura_texto), _ = cv2.getTextSize(
            etiqueta, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
        )
        cv2.rectangle(
            display, (x, y - altura_texto - 6), (x + largura_texto + 4, y),
            COR_CAIXA, -1
        )
        cv2.putText(display, etiqueta, (x + 2, y - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COR_TEXTO_FUNDO, 1)

    for id_obj, (cx, cy) in objetos.items():
        cv2.circle(display, (int(cx), int(cy)), 5, COR_TRAJETO, -1)

    _desenhar_area(display, contador)
    _desenhar_contador(display, contador, "YOLO")
    return display


def _desenhar_area(display, contador):
    if contador.poligono is None or len(contador.poligono) < 3:
        return
    pts = np.array(contador.poligono, dtype=np.int32).reshape((-1, 1, 2))
    overlay = display.copy()
    cv2.fillPoly(overlay, [pts], COR_LINHA)
    cv2.addWeighted(overlay, 0.25, display, 0.75, 0, display)
    cv2.polylines(display, [pts], isClosed=True, color=COR_LINHA, thickness=3)


def _desenhar_contador(imagem, contador, rotulo):
    texto_total = f"Total: {contador.total}"
    texto_taxa = f"{contador.por_minuto()} / min"

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
    if not roi_normalizada or len(roi_normalizada) < 3:
        y_topo = int(0.35 * altura)
        y_base = int(0.65 * altura)
        return [(0, y_topo), (largura, y_topo), (largura, y_base), (0, y_base)]
    return [(int(x * largura), int(y * altura)) for (x, y) in roi_normalizada]


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        threaded=True,
        use_reloader=False,
    )
