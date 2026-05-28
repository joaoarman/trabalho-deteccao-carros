# Etapa 3 — Pipeline OpenCV Clássico

## 1. O que é

O **pipeline OpenCV clássico** é a primeira das duas abordagens de detecção do projeto. Ele NÃO usa deep learning — é construído a partir de técnicas tradicionais de visão computacional, que existem desde antes das redes neurais dominarem a área. A ideia é: dado um vídeo onde a câmera está parada, aprender o que é "fundo" e isolar o que se move; depois usar morfologia e contornos pra transformar movimento em bounding boxes; depois rastrear cada caixa entre frames pra dar IDs consistentes; e finalmente contar veículos que entram numa área desenhada pelo usuário.

Este documento cobre os **cinco estágios do pipeline** em um único lugar porque eles formam uma cadeia conceitual única — não fazem sentido separados.

```
frame → [1] background subtraction → [2] threshold → [3] morfologia
                                                        ↓
[4] contornos → filtro por área → caixas → [5] tracker → contador
```

---

## 2. Por que precisamos disso

O detector clássico tem três valores no contexto deste trabalho:

1. **Didático.** Cada estágio do pipeline é compreensível matemática e visualmente — não tem caixa-preta. Isso casa exatamente com o critério de avaliação: "entendimento profundo e detalhado".
2. **Leve.** Funciona em CPU comum, sem GPU, sem baixar modelos pesados.
3. **Comparativo.** Implementar essa abordagem clássica vai permitir comparar diretamente com o YOLO mais pra frente — mostrando onde cada técnica brilha e onde falha.

---

## 3. Como funciona

### 3.1 Background Subtraction com MOG2

**Problema:** como saber, num frame, o que é parte do cenário fixo (rua, prédios, asfalto) e o que é algo que está se movendo (carro, pedestre)?

**Ideia ingênua:** subtrair do frame atual o "primeiro" frame, pegar pixels que mudaram. Não funciona — luz muda durante o dia, folhas balançam, sombras passam.

**MOG2 (Mixture of Gaussians 2)** resolve assim: para CADA PIXEL da imagem, mantém um histórico das últimas N intensidades observadas. Em vez de modelar esse histórico como uma única média, modela como uma **mistura de várias curvas gaussianas** (cada uma com média e variância). Quando chega um pixel novo:

- O algoritmo pergunta: "esse valor cai dentro de alguma das gaussianas que aprendi pra esse pixel?"
- **Sim** → é fundo (vai pra preto na máscara, valor 0)
- **Não** → é movimento (vai pra branco, valor 255)

A genialidade é que a mistura de gaussianas acomoda múltiplos estados "normais" pra um mesmo pixel (ex: o pixel que mostra uma folha pode ter uma gaussiana pra quando a folha está parada e outra pra quando balança).

**Parâmetros que usamos:**

```python
cv2.createBackgroundSubtractorMOG2(
    history=500,         # 500 frames pra aprender o fundo (~20s a 25 FPS)
    varThreshold=40,     # quanto menor, mais sensível (mais detecções e ruído)
    detectShadows=True,  # marca sombras com valor 127 (cinza)
)
```

**Por que `detectShadows=True`?** Sombras são pixels mais escuros mas com cor semelhante ao fundo. Sem tratá-las, elas viriam como "movimento" e estourariam as bounding boxes. Com `detectShadows=True`, o MOG2 separa: 255 = movimento real, 127 = sombra, 0 = fundo. Em seguida aplicamos um `threshold` cortando em 200 para descartar a faixa 127.

### 3.2 Threshold

A máscara saída do MOG2 tem 3 níveis (0, 127, 255). Pra alimentar morfologia e contornos, precisamos de uma imagem **binária estrita** (só 0 ou 255). `cv2.threshold(mascara, 200, 255, cv2.THRESH_BINARY)` faz exatamente isso: tudo abaixo de 200 vira 0, tudo acima vira 255.

### 3.3 Morfologia matemática

Mesmo depois do MOG2, a máscara tem ruído: pontinhos brancos isolados (folhas balançando, reflexos), e objetos com "buracos" internos (regiões do carro com cor parecida com o fundo).

A **morfologia** opera em imagens binárias usando um **kernel** (uma forma de referência, no nosso caso uma elipse 5×5):

- **Erosão:** o pixel central vira branco SÓ SE todos os pixels sob o kernel forem brancos. Efeito: encolhe regiões, **mata pontos isolados**.
- **Dilatação:** o pixel central vira branco se PELO MENOS UM pixel sob o kernel for branco. Efeito: cresce regiões, **fecha buracos pequenos**.

Em vez de aplicar erosão/dilatação puras, combinamos:

- **Opening = erosão → dilatação**. Remove o ruído (com a erosão) sem encolher o objeto principal (a dilatação compensa).
- **Closing = dilatação → erosão**. Fecha buracos dentro do objeto sem inflá-lo.

Aplicamos opening uma vez e closing duas vezes (pra fechar bem buracos médios em silhuetas de carros).

### 3.4 Contornos

`cv2.findContours()` percorre a máscara binária e identifica cada **região conectada de pixels brancos** como uma **curva fechada**. Retorna cada contorno como um array de pontos `[(x1,y1), (x2,y2), ...]`.

Parâmetros:

- `cv2.RETR_EXTERNAL` — só queremos os contornos externos; ignora contornos dentro de outros (buracos).
- `cv2.CHAIN_APPROX_SIMPLE` — compacta a curva mantendo só os "vértices" relevantes, economizando memória.

Pra cada contorno, `cv2.contourArea()` retorna a área em pixels², e `cv2.boundingRect()` retorna o menor retângulo que envolve o contorno (`x, y, w, h`).

**Filtragem por área:**

```python
AREA_MINIMA = 1500  # menos que isso é ruído residual
AREA_MAXIMA = 80000 # mais que isso é blob anormal (carros grudados, etc)
```

Esses limiares dependem da resolução do vídeo e do tamanho aparente dos veículos. São constantes nomeadas no topo do arquivo, fáceis de ajustar.

### 3.5 Centroid Tracker (acompanhamento entre frames)

**Problema:** o detector devolve "neste frame tem caixas A, B, C". Mas é o MESMO carro que estava no frame anterior? Sem associação, contaríamos cada carro N vezes (uma por frame).

**Solução simples e eficaz:** associar caixas entre frames pelo **centroide** (centro geométrico da bounding box). Premissa: a 30 FPS, um carro se move só alguns pixels por frame; logo, o centroide deste frame mais próximo de um centroide do frame anterior provavelmente é o mesmo carro.

**Algoritmo guloso:**

1. Calcula centroides das detecções atuais.
2. Constrói matriz de distâncias entre objetos rastreados (linhas) e novos centroides (colunas).
3. Pega o par com menor distância — associa, marca os dois como "usados". Repete.
4. Para se a próxima menor distância exceder um limiar (`distancia_maxima = 100` pixels): isso evita forçar associações entre objetos que claramente não são o mesmo.
5. Existentes sem par viram "desaparecidos"; depois de 30 frames sumido (~1s a 30 FPS), são removidos.
6. Novos centroides sem par viram IDs novos.

**Cálculo da matriz de distâncias com numpy broadcasting:**

```python
diff = a[:, None, :] - b[None, :, :]      # shape (n, m, 2)
D = np.sqrt(np.sum(diff ** 2, axis=-1))    # shape (n, m)
```

Sem broadcasting precisaríamos de dois `for` aninhados — 10× mais lento.

### 3.6 Contagem por entrada numa área (polígono)

> **Mudança de design.** A versão inicial contava o **cruzamento de uma linha** (produto vetorial 2D pra ver de que lado o centroide estava). Trocamos por uma **área poligonal** definida pelo usuário: ele clica em N pontos e forma um polígono. É mais flexível — dá pra contar a cena toda, ou só uma faixa numa via de mão dupla.

Uma vez que cada veículo tem um ID estável, contar virou um problema geométrico: detectar quando o centroide de um ID está **dentro do polígono** desenhado.

**Como saber se um ponto está dentro de um polígono? Ray casting (regra par-ímpar).** Dispare um raio horizontal do ponto P pra direita e conte quantas arestas do polígono ele cruza:

```
número ÍMPAR de cruzamentos  →  P está DENTRO
número PAR (inclui zero)      →  P está FORA
```

Intuição: cada vez que o raio atravessa uma borda, ele alterna entre fora/dentro. Vindo do infinito (fora), um número ímpar de trocas significa que em P estávamos dentro. Para cada aresta (vértice i → vértice j), o raio na altura `py` cruza a aresta se a aresta "abraça" essa altura — `(yi > py) != (yj > py)` — **e** o ponto de cruzamento fica à direita de `px`. A primeira condição também garante `yi != yj`, então a divisão nunca dá erro.

**Quando contamos:** na primeira vez que o centroide de um ID é visto **dentro** da área, incrementamos e marcamos o ID em `ja_contados` (não conta de novo enquanto permanece nem se voltar). Escolhemos "primeira vez dentro" em vez de "transição de fora pra dentro" de propósito: assim a contagem **também funciona quando a área é a cena inteira** (não existiria um "fora" pra transicionar de). O custo é que um veículo que já comece dentro da área no início do vídeo é contado — aceitável pro escopo.

### 3.7 Taxa "por minuto"

Para cada veículo contado, salvamos o `time.time()`. A função `por_minuto()` filtra os timestamps mais recentes que 60 segundos atrás e retorna a contagem. Isso dá uma **janela móvel** de 1 minuto, muito mais informativa que `total / tempo_decorrido_total`.

---

## 4. Como usamos

### Estrutura do pacote `core/`

```
core/
├── __init__.py            # marca a pasta como pacote Python
├── leitor_video.py        # abstração sobre cv2.VideoCapture
├── detector_classico.py   # MOG2 + morfologia + contornos
├── tracker.py             # CentroidTracker
└── contador.py            # entrada em área (polígono, ray casting) + taxa por minuto
```

### Orquestração no `app.py`

Dentro de `gerar_stream_opencv()`, a cada iteração:

```python
resultado = detector.processar(frame)            # roda etapas 1-4
objetos = tracker.atualizar(resultado["caixas"]) # roda etapa 5 (tracking)
contador.atualizar(objetos)                      # roda etapa 5 (contagem)

display = _renderizar_etapa(etapa, frame, resultado, objetos, contador)
```

**Importante:** o pipeline ROD A INTEIRO em todos os frames. A etapa selecionada pelo usuário define só o que vai ser **mostrado**, não o que é **calculado**. Isso é necessário porque tracker e contador precisam ver todos os frames pra manter consistência — não dá pra "pausar" o tracking só porque o usuário está olhando a máscara crua.

### Renderização por etapa

```python
if etapa == 1:                                       # frame original
    display = frame.copy()
elif etapa == 2:                                     # máscara MOG2 (com sombras)
    display = cv2.cvtColor(resultado["mascara_bruta"], cv2.COLOR_GRAY2BGR)
elif etapa == 3:                                     # máscara limpa
    display = cv2.cvtColor(resultado["mascara_limpa"], cv2.COLOR_GRAY2BGR)
elif etapa == 4:                                     # contornos + caixas
    display = frame.copy()
    cv2.drawContours(display, ..., COR_CAIXA, 2)
elif etapa == 5:                                     # tracking + IDs
    display = frame.copy()
    for id, (cx, cy) in objetos.items():
        cv2.circle(...); cv2.putText(...)
```

Em todas as etapas, desenhamos a área de contagem (polígono translúcido) e uma faixa com o contador no canto.

---

## 5. Limitações e alternativas

| Limitação | Alternativa |
|-----------|-------------|
| MOG2 só funciona com **câmera fixa** | YOLO funciona com câmera em movimento |
| Sensível a mudanças bruscas de iluminação (nuvem cobrindo o sol) | Subtratores mais robustos (KNN, ViBe) ajudam um pouco; deep learning resolve melhor |
| Sombras fortes podem virar falsos positivos | `detectShadows=True` ajuda, mas não é perfeito |
| Carros parados "viram fundo" depois de N frames | É um efeito esperado de qualquer background subtractor com `history` finito |
| Centroid Tracker troca IDs se dois objetos se cruzam | Trackers modernos (DeepSORT, ByteTrack) usam aparência além da posição |
| Filtragem por área é frágil (depende da resolução, ângulo) | YOLO usa classificação real, não tamanho |
| Veículo já dentro da área no início do vídeo é contado mesmo sem "entrar" | Trade-off da regra "primeira vez dentro", escolhida pra suportar área = cena inteira |
| Veículo que muda de ID (oclusão) pode ser contado duas vezes | Limitação do tracker, não da contagem; trackers com aparência reduzem isso |

**Por que usamos área mínima/máxima em vez de razão de aspecto?** Já tentamos. Carros vistos de cima têm aspectos muito variáveis dependendo do ângulo da câmera (visão lateral vs visão superior). Área é mais estável.

---

## 6. Perguntas prováveis na apresentação

**P: O que é exatamente um pixel "ser fundo" no MOG2?**
R: É um pixel cuja intensidade nas últimas N observações pode ser explicada por uma das gaussianas aprendidas. Em vez de uma média fixa, o MOG2 modela vários "estados normais" por pixel — por isso lida com variações sutis (folhas, reflexos suaves).

**P: Por que vocês fazem opening seguido de closing? Não dá pra fazer só um?**
R: Eles atacam problemas diferentes. Opening remove ruído isolado (pontos brancos perdidos no preto); closing fecha buracos internos (pontos pretos perdidos no branco). Ordem importa: se fizéssemos closing primeiro, ele preencheria também ruído isolado pequeno antes de a gente conseguir remover; opening primeiro garante que só objetos "reais" são fechados.

**P: Por que `RETR_EXTERNAL` e não `RETR_TREE`?**
R: Queremos só os contornos externos dos objetos. RETR_TREE devolve hierarquia completa (incluindo contornos de buracos dentro de objetos), que não nos serve. Menos info pra processar = mais rápido.

**P: Como o Centroid Tracker decide que duas detecções são o mesmo objeto?**
R: Pela menor distância euclidiana entre o centroide atual e os centroides do frame anterior, desde que essa distância esteja abaixo de um limiar (100 pixels). Greedy: associa o par mais próximo, remove ambos das opções, repete.

**P: E se dois carros próximos se aproximarem o suficiente pra "trocarem de ID"?**
R: O Centroid Tracker pode errar nesse caso — é uma limitação conhecida. Trackers modernos (DeepSORT) resolvem isso adicionando informação de aparência (embedding visual de cada caixa). Decidimos manter o Centroid Tracker porque é didático: 100 linhas de código que dá pra explicar inteiras na apresentação.

**P: Por que ray casting e não checar se o ponto está "do lado de dentro" de cada aresta?**
R: A checagem por aresta (sinal do produto vetorial em todas as arestas) só funciona pra polígonos **convexos**. Ray casting funciona pra qualquer polígono, inclusive **côncavo** — importante porque o usuário desenha à mão e pode fazer formas irregulares (ex: contornar uma faixa curva). E é simples: um loop pelas arestas contando cruzamentos.

**P: Por que contar na "primeira vez dentro" e não na transição de fora pra dentro?**
R: Porque "transição" exige que o veículo tenha sido visto **fora** antes. Se a área for a cena inteira, não existe "fora", e nada seria contado. "Primeira vez dentro" cobre os dois casos. O preço é contar um veículo que já comece dentro da área — aceitável pro escopo.

**P: Por que vocês não contam de novo se um carro sai e volta pra área?**
R: Por design. O `set` `ja_contados` impede duplicação. Se quiséssemos contar cada passagem (ex: pedágio em dois sentidos), poderíamos ter dois contadores/áreas separados por direção.

**P: Esse pipeline funciona com a câmera em movimento (drone)?**
R: Não bem. O background subtractor pressupõe câmera fixa. Com câmera em movimento, todo o cenário "muda" entre frames e tudo vira foreground. É exatamente um dos pontos onde o YOLO ganha — ele detecta objetos independente de fundo.

**P: Por que filtrar por área se vocês têm o YOLO depois?**
R: Porque queremos comparar as duas abordagens. O pipeline OpenCV é independente do YOLO; cada um é uma técnica auto-contida, e poder ver onde cada uma falha é uma parte importante do que a gente quer mostrar.

**P: Por que vocês redimensionam o vídeo pra 960px de largura antes de processar?**
R: Velocidade. MOG2 e morfologia operam pixel a pixel; o custo é proporcional à resolução. 960px é alto o suficiente pra que veículos ainda sejam detectáveis confortavelmente e baixo o suficiente pra rodar em tempo real em CPU comum. Em vídeos 4K, o pipeline rodaria a poucos FPS sem isso.
