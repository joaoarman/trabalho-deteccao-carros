# Etapa 5 — YOLOv8 e o Modo Comparativo

## 1. O que é

Esta etapa adiciona a **segunda abordagem de detecção** do projeto — o **YOLOv8**, um modelo de *deep learning* — e o **modo comparativo**, que roda as duas abordagens (clássica e YOLO) lado a lado, sobre o mesmo vídeo e a mesma área de contagem.

Agora o sistema tem três modos:

| Modo | Detector | Onde está |
|------|----------|-----------|
| OpenCV clássico | Subtração de fundo + morfologia + contornos | `core/detector_classico.py` |
| YOLO | Rede neural pré-treinada (YOLOv8n) | `core/detector_yolo.py` |
| Comparativo | Os dois ao mesmo tempo | dois streams na mesma página |

O **tracker** (`CentroidTracker`) e o **contador** (`Contador`, por área) são exatamente os mesmos nos três modos. O que muda é só **quem produz as caixas**.

---

## 2. Por que precisamos disso

1. **Comparação é o coração da apresentação.** Mostrar a mesma cena processada de duas formas torna visível o que cada técnica faz bem e mal: o clássico é leve mas sensível a sombra/iluminação e só vê *movimento*; o YOLO entende *o que* é cada objeto, mas custa mais caro.
2. **Reaproveitamento.** Como YOLO e clássico devolvem o mesmo formato de saída (lista de caixas `(x, y, w, h)`), o resto do pipeline não muda. Isso prova, na prática, o valor de uma boa interface entre módulos.
3. **Deep learning sem treinar.** Usamos um modelo pré-treinado em COCO. Conseguimos detecção de qualidade sem GPU nem dataset próprio — e sabemos explicar por que isso é suficiente.

---

## 3. Como funciona o YOLO

### 3.1 A ideia — "You Only Look Once"

Detectores antigos varriam a imagem com uma janela deslizante, classificando cada recorte (lento). O YOLO faz **uma única passada** pela rede: divide a imagem numa grade e, para cada célula, prevê de uma vez caixas candidatas, a confiança de haver objeto e a probabilidade de cada classe. Por ser uma passada só, roda rápido o bastante para vídeo.

### 3.2 COCO e as classes de veículo

O `yolov8n.pt` já vem treinado no **COCO** (80 classes do dia a dia). Não treinamos nada — apenas filtramos as classes de veículo (os IDs são fixos no COCO):

```
2 = car      3 = motorcycle      5 = bus      7 = truck
```

### 3.3 NMS (Non-Max Suppression)

A rede tende a prever várias caixas sobrepostas para o mesmo objeto. O NMS mantém a de maior confiança e descarta as que se sobrepõem demais (IoU alto). O ultralytics aplica NMS internamente — não precisamos implementar.

### 3.4 Por que o "nano" (yolov8n)?

A família YOLOv8 vem em tamanhos `n < s < m < l < x`. O `n` é o menor e mais rápido — roda em CPU comum, ideal para a apresentação. Tem menos precisão que os maiores, mas é suficiente para contar carros. Esse trade-off precisão × velocidade é, em si, um ótimo assunto de prova.

### 3.5 Como usamos (código comentado)

`DetectorYOLO.processar(frame)` roda a inferência e converte a saída pro formato do nosso pipeline:

```python
resultados = self.modelo.predict(
    frame,
    conf=self.confianca_minima,          # descarta detecções fracas
    classes=list(CLASSES_VEICULOS.keys()),  # só car/moto/bus/truck
    verbose=False,
)
for box in resultados[0].boxes:
    x1, y1, x2, y2 = box.xyxy[0].tolist()      # canto-a-canto
    x, y, w, h = int(x1), int(y1), int(x2-x1), int(y2-y1)  # vira (x,y,w,h)
    ...
```

O modelo é carregado **uma única vez** (lazy + lock), compartilhado entre streams, pra não pagar o custo de carregamento toda hora.

---

## 4. Arquitetura — um gerador, dois detectores

Os modos OpenCV e YOLO compartilham quase todo o fluxo de stream (abrir vídeo, redimensionar, rastrear, contar, codificar JPEG, respeitar o FPS). Para não duplicar isso, há **um único** `_gerar_stream(video_id, caminho, modo)` no `app.py`, parametrizado pelo modo. Só duas coisas dependem do modo:

```
detector = DetectorYOLO()  se modo == 'yolo'  senão  DetectorClassico()
...
if modo == 'yolo':  frame_display = _renderizar_yolo(...)
else:               frame_display = _renderizar_etapa(etapa, ...)
```

### 4.1 Estado por modo

Como o comparativo roda os dois ao mesmo tempo, o estado guarda **um contador por modo**:

```python
estado_videos[id]['contadores'] = { 'opencv': Contador, 'yolo': Contador }
```

E a API expõe `GET /api/contador/<id>/<modo>`. A tela do YOLO também consome `GET /api/deteccoes/<id>` (classe + confiança do último frame) para a lista lateral.

### 4.2 Rotas novas / alteradas

| Método | Rota | Função |
|--------|------|--------|
| GET | `/stream/<id>/<modo>` | Stream MJPEG do modo (`opencv` ou `yolo`) |
| GET | `/api/contador/<id>/<modo>` | Contador do modo |
| GET | `/api/deteccoes/<id>` | Detecções YOLO do frame atual |

> **Atenção:** o `/stream/<id>` antigo (sem modo) deixou de existir; agora o modo é obrigatório na URL.

### 4.3 O comparativo

A página tem duas `<img>`, uma apontando pra `/stream/<id>/opencv` e outra pra `/stream/<id>/yolo`. São **dois streams independentes**, cada um na sua thread, cada um escrevendo no seu contador. O JS faz polling dos dois contadores e, ao abrir a página, força a etapa do OpenCV pra 5 (tracking + contagem) — assim o lado clássico já mostra o resultado final, não o frame cru.

---

## 5. Limitações e alternativas

| Limitação | Comentário |
|-----------|------------|
| YOLOv8n em CPU pode rodar abaixo do FPS do vídeo | Esperado. O stream simplesmente roda no ritmo possível; modelos maiores ou GPU acelerariam |
| O comparativo roda **dois** pipelines ao mesmo tempo | Dobra o custo de CPU; em máquina fraca os dois lados ficam mais lentos |
| Precisão do `n` é menor que `s/m/l/x` | Trade-off consciente por velocidade |
| Contagem depende do tracker (centroid) | Mesma limitação dos outros modos: troca de ID em oclusão pode duplicar |
| O modelo precisa estar em `modelos/yolov8n.pt` | Já baixado; sem internet o ultralytics não conseguiria buscar na 1ª vez |

---

## 6. Perguntas prováveis na apresentação

**P: Vocês treinaram o YOLO?**
R: Não. Usamos o `yolov8n` pré-treinado em COCO, que já inclui car, truck, bus e motorcycle. Treinar exigiria dataset rotulado, GPU e tempo — e não melhoraria nada pro nosso objetivo, já que as classes que precisamos já vêm prontas.

**P: Por que o YOLO conta diferente do OpenCV no comparativo?**
R: São técnicas diferentes. O clássico só vê *movimento*: um carro parado some, sombras viram falsos positivos, carros colados grudam num só blob. O YOLO vê *objetos*: detecta carro parado e separa carros próximos, mas pode falhar com oclusão e custa mais caro. O comparativo deixa essas diferenças visíveis.

**P: O que é a confiança que aparece em cada caixa?**
R: É a probabilidade que a rede atribui àquela detecção. Filtramos abaixo de 0.4 pra cortar falsos positivos. Quanto maior, mais "certo" o modelo está.

**P: Por que reaproveitar o mesmo tracker e contador?**
R: Porque o problema "associar caixas entre frames" e "contar quem entra na área" é o mesmo independentemente de quem detectou. Manter a saída dos dois detectores no mesmo formato `(x,y,w,h)` deixou isso de graça.

**P: O modelo roda na nuvem?**
R: Não. Roda 100% local, a partir do arquivo `modelos/yolov8n.pt`. Por isso baixamos o modelo antes — pra apresentação não depender de internet.
