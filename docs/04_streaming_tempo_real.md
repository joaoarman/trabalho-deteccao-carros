# Etapa 4 — Streaming em Tempo Real (MJPEG + AJAX)

## 1. O que é

Para a interface mostrar o vídeo sendo processado **enquanto o processamento acontece**, precisamos resolver dois problemas técnicos:

1. **Como enviar frames processados continuamente do Python pro navegador?**
2. **Como permitir que o usuário interaja (troque etapa, leia contador) sem reiniciar o vídeo?**

Esta etapa documenta as escolhas feitas para esses dois pontos: **MJPEG streaming** pro vídeo, e **AJAX** com **polling** pro estado.

---

## 2. Por que precisamos disso

Sem essa camada, o sistema seria "batch": o usuário enviaria o vídeo, esperaria minutos pelo processamento, depois baixaria o resultado já renderizado. Funciona, mas não é o que pedimos.

A interface promete:
- Vídeo **ao vivo**, com o efeito da etapa selecionada aplicado em tempo real.
- **Troca de etapa instantânea**, sem reiniciar o stream.
- **Contador que atualiza** conforme veículos cruzam a linha.

O MJPEG resolve o vídeo; o AJAX resolve a interatividade.

---

## 3. Como funciona

### 3.1 MJPEG Streaming — vídeo do Python pro navegador

**MJPEG** (Motion JPEG) é uma das técnicas mais antigas de streaming de vídeo na web. A ideia é simples: cada frame é codificado como uma imagem JPEG independente, e elas são enviadas em sequência por uma única conexão HTTP. O navegador exibe num `<img>` comum e troca o conteúdo a cada nova imagem que chega.

O truque pra que o navegador entenda "isso é uma sequência, não uma imagem só" é o tipo MIME:

```
Content-Type: multipart/x-mixed-replace; boundary=frame
```

A resposta vem formatada com separadores:

```
--frame
Content-Type: image/jpeg

<bytes do JPEG 1>
--frame
Content-Type: image/jpeg

<bytes do JPEG 2>
...
```

#### Implementação no Flask

```python
@app.route("/stream/<video_id>")
def stream(video_id):
    return Response(
        gerar_stream_opencv(video_id, caminho_video),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )

def gerar_stream_opencv(video_id, caminho_video):
    cap = cv2.VideoCapture(caminho_video)
    while True:
        ret, frame = cap.read()
        ...
        ok, buffer = cv2.imencode(".jpg", frame_display, [cv2.IMWRITE_JPEG_QUALITY, 80])
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
        )
```

`gerar_stream_opencv` é uma **função geradora** (note o `yield` em vez de `return`). O Flask consome esse generator e envia cada bloco assim que é produzido. Quando o navegador desconecta (usuário fecha a aba), o `yield` lança um `GeneratorExit`, o `finally` libera o `cv2.VideoCapture`, e o processamento para.

#### No HTML, simples assim:

```html
<img src="{{ url_for('stream', video_id=video_id) }}" alt="Stream">
```

O navegador é responsável por receber o multipart e atualizar a `<img>` conforme novos JPEGs chegam. **Zero JavaScript** envolvido na exibição do vídeo.

#### Por que JPEG e não outro formato?

- **Universalmente suportado.** Qualquer navegador exibe.
- **Compressão eficiente** pra imagens fotográficas (como frames de vídeo).
- **Sem dependência de codec.** PNG seria muito grande; WebP, H.264 etc precisariam de mais infra.

Qualidade `80` é um bom equilíbrio: arquivos pequenos, sem artefatos visíveis.

### 3.2 Controle de FPS — não acelerar nem travar

`cv2.VideoCapture` lê frames o mais rápido que conseguir — sem controle, o stream rodaria a centenas de FPS, esgotando CPU e fazendo o vídeo parecer "acelerado". A solução:

```python
fps = cap.get(cv2.CAP_PROP_FPS)
delay_alvo = 1.0 / fps    # ex: 0.04s pra 25 FPS

while True:
    inicio = time.time()
    # ... processa e envia frame
    transcorrido = time.time() - inicio
    atraso = delay_alvo - transcorrido
    if atraso > 0:
        time.sleep(atraso)
```

Isso mantém a taxa original do vídeo. Se o processamento demora mais que `delay_alvo`, o stream simplesmente fica abaixo do FPS nominal — mas isso é raro com vídeos em 960px e MOG2 em CPU.

### 3.3 AJAX — controlando o estado do stream sem recarregar

**Cenário:** o usuário clica em "Background Subtraction" no painel lateral. Queremos que o próximo frame do stream já mostre a máscara. Sem reiniciar o vídeo, sem recarregar a página.

**Estratégia:** o backend mantém um dicionário compartilhado `estado_videos[video_id]['etapa']`. O gerador de stream lê esse valor a cada iteração e renderiza a etapa correspondente. O navegador, ao clicar numa etapa, dispara um `fetch` HTTP que **escreve** nesse dicionário.

#### No JavaScript:

```javascript
fetch(`/api/etapa/${VIDEO_ID}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ etapa: 3 }),
});
```

#### No Flask:

```python
@app.route("/api/etapa/<video_id>", methods=["POST"])
def api_definir_etapa(video_id):
    etapa = int(request.get_json()["etapa"])
    estado_videos[video_id]["etapa"] = etapa
    return jsonify({"ok": True})
```

Sem WebSocket, sem servidor especial. O stream e a API rodam em threads diferentes do Flask (porque ligamos `threaded=True` no `app.run`), e o dicionário Python é compartilhado entre elas. A próxima iteração do generator lê o novo valor automaticamente.

### 3.4 Polling — lendo o contador periodicamente

O contador (número de veículos) precisa aparecer no painel lateral, atualizado conforme cresce. Há duas escolhas clássicas:

| Técnica | Como funciona | Quando usar |
|---------|---------------|-------------|
| **Polling** | Cliente pergunta "qual o contador agora?" a cada N ms. | Simples, sem infraestrutura. Ok pra atualizações poucas vezes por segundo. |
| **WebSocket** | Conexão bidirecional persistente; servidor empurra updates. | Latência sub-segundo, muitos eventos por segundo, jogos em tempo real. |

Pra um contador que muda a cada 1-2 segundos, **polling a 2 vezes por segundo é mais que suficiente** e dispensa qualquer biblioteca extra:

```javascript
setInterval(async () => {
    const resp = await fetch(`/api/contador/${VIDEO_ID}`);
    const data = await resp.json();
    contadorTotal.textContent = data.total;
    contadorDetalhe.textContent = `${data.por_minuto} por minuto`;
}, 500);
```

Polling tem desvantagens (tráfego mesmo quando não há mudança), mas pra escopo acadêmico é o caminho mais didático: cada peça (cliente que pergunta, servidor que responde) é compreensível isoladamente.

### 3.5 ROI normalizada — independente da resolução

> **A ROI agora é uma ÁREA (polígono), não uma linha.** O usuário clica em N pontos (≥ 3) e forma um polígono; o backend conta veículos que entram nessa área (ver `docs/03`, seção 3.6). O mecanismo de coordenadas abaixo é o mesmo, só que com uma lista de pontos em vez de dois.

Quando o usuário desenha a área no canvas, ele clica em coordenadas em pixels relativos ao **canvas exibido**. Mas o vídeo é processado no backend numa **resolução possivelmente diferente** (redimensionamos pra 960px). Se enviássemos `(x, y)` em pixels do canvas, a área apareceria em local errado depois.

**Solução:** trabalhar com coordenadas normalizadas `[0, 1]` desde o clique. No clique, dividimos pela dimensão **exibida** do canvas (via `getBoundingClientRect`), e guardamos a fração:

```javascript
const rect = canvas.getBoundingClientRect();
const x = (e.clientX - rect.left) / rect.width;   // já é 0..1
const y = (e.clientY - rect.top) / rect.height;
pontos.push({ x, y });
```

> **Cuidado com os dois tamanhos do canvas.** Um `<canvas>` tem o tamanho de *exibição* (CSS) e o do *bitmap* interno (`canvas.width/height`), onde o JS realmente desenha. A versão inicial dividia o clique pelo bitmap, mas lia o clique em pixels de tela — quando os dois divergiam, a normalização passava de `1.0`, o backend rejeitava (erro 400) e a ROI caía no fallback do meio do vídeo. Além disso o desenho saía invisível, fora do bitmap. A correção: (1) manter o bitmap sempre do tamanho exibido com um `ResizeObserver`, (2) normalizar sempre pelo `rect` exibido, e (3) ajustar a proporção do container à do vídeo no `loadedmetadata`, pra o `object-fit: contain` não criar barras pretas e o canvas cobrir exatamente os pixels do vídeo.

No backend, ao iniciar o stream, multiplicamos cada vértice pelas dimensões do frame processado:

```python
def _converter_poligono(roi_normalizada, largura, altura):
    # ... (fallback pra faixa central se não houver área válida) ...
    return [(int(x * largura), int(y * altura)) for (x, y) in roi_normalizada]
```

Resultado: a área aparece exatamente onde o usuário desenhou, mesmo se a tela tiver tamanho diferente da resolução de processamento.

**Botão "Alterar área" + atalho.** No modo OpenCV há um botão (e a tecla **A**) que volta pra tela de seleção. A contagem zera naturalmente: ao reabrir o modo, a `<img>` do stream refaz a requisição, o generator cria um `Contador` novo e o total volta a 0. A tela de seleção repovoa o polígono anterior (`roi_inicial` → `window.ROI_INICIAL`) pra o usuário ajustar em vez de redesenhar do zero.

### 3.6 Concorrência — thread do stream vs threads de API

Quando o Flask roda com `threaded=True`, cada requisição é tratada em uma thread Python. O stream e as chamadas de API rodam em paralelo. Como ambos acessam o mesmo `estado_videos`, há risco de **race condition**:

- Thread A está escrevendo `estado_videos[id]['etapa'] = 3`
- Thread B (stream) está lendo `estado_videos[id]['etapa']` simultaneamente

No Python (CPython), operações simples em dicionários são protegidas pelo **GIL** (Global Interpreter Lock), então leituras e escritas atômicas raramente corrompem. Mas pra operações compostas (criar uma nova entrada, modificar várias chaves de uma vez), usamos um `threading.Lock`:

```python
_lock_estado = threading.Lock()

def garantir_estado(video_id):
    with _lock_estado:
        if video_id not in estado_videos:
            estado_videos[video_id] = {...}
```

O `with` garante que duas threads não vão criar a entrada simultaneamente.

---

## 4. Como usamos

### Fluxo completo (de cima a baixo)

1. Usuário envia vídeo em `/` → POST `/upload` → arquivo salvo em `uploads/abc123_vid.mp4`, `estado_videos['abc123']['caminho']` definido.
2. Redirecionado pra `/configurar/abc123`. Vê o vídeo via `<video src="/video/abc123">`.
3. Clica em ≥ 3 pontos no canvas → JS normaliza e POST `/api/roi/abc123` com `{pontos: [{x:0.2,y:0.4},{x:0.8,y:0.4},{x:0.8,y:0.7},{x:0.2,y:0.7}]}`.
4. Clica em "OpenCV clássico" → navega pra `/processar/abc123/opencv`.
5. A página carrega com `<img src="/stream/abc123">` — o Flask começa a gerar JPEGs em loop, processando cada frame com o pipeline OpenCV.
6. O navegador exibe os JPEGs em sequência (vídeo ao vivo).
7. Em paralelo, o JS faz polling em `/api/contador/abc123` a cada 500ms — o contador no painel cresce.
8. Usuário clica em "Background Subtraction" → POST `/api/etapa/abc123` com `{etapa: 2}`. No próximo frame do stream, a imagem exibida é a máscara em vez do frame original.

### Lendo logs do Flask

Durante o dev, o terminal mostra cada requisição:

```
127.0.0.1 - - [27/May 23:50:12] "GET /stream/abc123 HTTP/1.1" 200 -
127.0.0.1 - - [27/May 23:50:14] "POST /api/etapa/abc123 HTTP/1.1" 200 -
127.0.0.1 - - [27/May 23:50:14] "GET /api/contador/abc123 HTTP/1.1" 200 -
```

A linha do stream fica "aberta" enquanto o navegador está nele — Flask só registra ao fechar.

---

## 5. Limitações e alternativas

### Limitações desta abordagem

- **Não recapagema múltiplos streams simultâneos** sem problemas: cada `<img>` no navegador abre uma conexão própria, multiplicando o trabalho do servidor.
- **Estado em memória** se perde a cada restart do servidor.
- **Polling gera tráfego desnecessário** quando o contador não muda.
- **Sem autenticação:** qualquer um com o `video_id` acessa o stream.

### Alternativas

| Técnica | Quando faria sentido |
|---------|----------------------|
| **WebSocket** (Flask-SocketIO) | Atualizações sub-segundo, ou múltiplos clientes recebendo eventos simultâneos. |
| **HLS / DASH** | Streams longos pra muitos espectadores. Requer codec H.264 e player no front. |
| **WebRTC** | Latência ultra-baixa (videoconferência). Complexo de setup. |
| **Server-Sent Events (SSE)** | Push de servidor pro cliente em texto. Mais simples que WebSocket. |
| **gRPC + protobuf** | Microserviços e comunicação binária estruturada. Overkill aqui. |

Pra um trabalho acadêmico com 1 usuário e foco didático, MJPEG + polling é a escolha certa.

---

## 6. Perguntas prováveis na apresentação

**P: Por que vocês não usam WebSocket?**
R: Porque pra essa escala (1 cliente, contador que muda a cada poucos segundos, vídeo a 25 FPS) o ganho de WebSocket sobre MJPEG+polling é negligível e o custo em complexidade é grande. WebSocket exigiria Flask-SocketIO no servidor, conexão bidirecional, handshakes, e um eventloop assíncrono. MJPEG cabe numa única `<img>` e polling em quatro linhas de JS.

**P: O vídeo "ao vivo" no navegador é um vídeo real ou uma sequência de imagens?**
R: Tecnicamente é uma sequência de imagens JPEG enviadas pela mesma conexão HTTP. O navegador exibe num `<img>` comum e troca o conteúdo a cada imagem nova que chega. Esse é o protocolo MJPEG (Motion JPEG). Como o servidor envia 25 imagens por segundo, o efeito é indistinguível de vídeo.

**P: Onde fica o "estado" da etapa selecionada?**
R: Num dicionário Python global no servidor: `estado_videos[video_id]['etapa']`. Quando o usuário clica numa etapa, JS faz POST `/api/etapa/<id>` que atualiza esse dicionário. O generator do stream lê esse valor a cada iteração e renderiza a etapa correspondente.

**P: O que acontece se eu abrir a mesma página em duas abas?**
R: Cada `<img>` abre uma conexão independente com `/stream/<id>`. Como ambas leem do mesmo `estado_videos`, vão mostrar a mesma etapa. Mas os pipelines OpenCV (`detector`, `tracker`, `contador`) são instanciados dentro de cada chamada de stream — então cada aba tem o seu próprio contador, que pode divergir. Isso é uma limitação assumida.

**P: O Flask aguenta isso? Não é só pra apps simples?**
R: Pro escopo do trabalho, sim. O servidor de desenvolvimento do Flask (Werkzeug) com `threaded=True` lida bem com 1-2 streams simultâneos. Em produção, usaríamos Gunicorn ou uWSGI atrás de Nginx — mas isso é fora do escopo.

**P: Por que normalizar a ROI em vez de mandar pixels?**
R: Porque o vídeo é exibido no navegador num tamanho diferente do que é processado no backend. O canvas do usuário pode ter 800px de largura, e o vídeo processado pode ter 960px. Coordenadas em pixels só fariam sentido pra uma resolução específica. Normalizando em `[0,1]`, o backend multiplica pela resolução real do processamento e a linha cai no lugar certo.

**P: O contador "por minuto" é a média histórica?**
R: Não. É uma **janela móvel de 60 segundos**: quantos cruzamentos aconteceram nos últimos 60s. Guardamos o timestamp de cada cruzamento numa lista e filtramos a cada consulta. Isso responde "qual o fluxo agora?", que é mais útil que a média desde o início.

**P: O `time.sleep` dentro do generator não trava o servidor?**
R: Não, porque o Flask com `threaded=True` rodando o stream numa thread separada da thread principal. O `sleep` só pausa aquela thread. Outras requisições (API, polling) continuam respondidas normalmente.

**P: Por que `use_reloader=False`?**
R: O reloader do Flask, quando ativo, abre uma **segunda instância** do processo (uma "pai" que reinicia, e uma "filha" que serve). Em produção isso é irrelevante, mas com nosso estado em memória global, duas instâncias significaria dois `estado_videos` separados — e a thread do stream poderia rodar na instância errada. Desligando o reloader garantimos uma única cópia.
