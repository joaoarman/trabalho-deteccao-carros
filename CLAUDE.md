# Trabalho de Tópicos Especiais em Computação — Contador de Veículos

> **Este arquivo é a fonte de verdade do projeto.** Ele é carregado automaticamente a cada nova interação com o Claude e deve ser atualizado sempre que decisões forem tomadas, etapas forem concluídas ou novos conceitos forem explicados. Leia-o por inteiro antes de começar qualquer tarefa.

---

## 1. Contexto Acadêmico

- **Cadeira:** Tópicos Especiais em Computação
- **Tema:** IA / Ciência de Dados
- **Enunciado:** *"Desenvolva um sistema, aplicativo, prova de conceito, MVP ou demo técnica que utilize uma ou mais das tecnologias vistas em aula (pode ser alguma não vista também, desde que relacionada a IA/Ciência de Dados)."*
- **Trabalho escolhido:** Sistema de contagem de veículos por minuto em vídeos (sugestão do professor, com OpenCV como tecnologia recomendada).
- **Critério de avaliação:** *"A avaliação do trabalho se dará pelos códigos enviados e pela apresentação, focando na complexidade do trabalho e no entendimento profundo e detalhado dos alunos em relação ao que foi produzido. A nota de cada integrante do grupo poderá diferir de acordo com o entendimento individual demonstrado na apresentação."*

**Implicação prática:** cada linha de código precisa poder ser defendida por qualquer integrante do grupo. Não basta funcionar — precisa ser entendido.

---

## 2. Filosofia de Desenvolvimento

Estas regras guiam **todas** as interações com o Claude no escopo deste projeto:

1. **Desenvolvimento incremental, parte por parte.** Nada de "faz tudo de uma vez". Cada etapa é construída, explicada e validada antes de seguir.
2. **Entendimento antes de código.** Quando uma biblioteca/método pronto for usado (ex: `cv2.createBackgroundSubtractorMOG2`), o algoritmo por trás precisa ser explicado — não basta saber "que função chamar".
3. **Comentários didáticos no código.** Cada bloco relevante leva comentário em português explicando o "porquê", não só o "o quê". Pensar nos comentários como roteiro de apresentação.
4. **Documentação viva.** Este `CLAUDE.md` e os arquivos de documentação do projeto são atualizados a cada etapa concluída. A documentação cresce junto com o código.
5. **Sem mágica oculta.** Evitar abstrações que escondam conceitos importantes (motivo de termos escolhido Flask em vez de Streamlit, por exemplo).
6. **Estrutura definida sob demanda.** Diretórios, módulos e arquivos são criados conforme a necessidade aparece — não pré-definimos uma estrutura completa. Isso evita confusão e mantém o domínio sobre cada peça.
7. **Etapas definidas sob demanda.** O fluxo de etapas é decidido pelo grupo conforme o projeto avança, não imposto por um roadmap fixo no início.

---

## 3. Visão Geral do Sistema

### Fluxo completo do usuário

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Interface web abre na tela inicial                           │
│ 2. Usuário faz upload de um vídeo (.mp4, .avi, etc)             │
│ 3. Vídeo é exibido e o usuário SELECIONA uma área (ROI)         │
│    — região onde a contagem será feita (ex: linha de cruzamento │
│      ou polígono sobre uma pista)                               │
│ 4. Usuário escolhe o modo de processamento:                     │
│     a) OpenCV puro (clássico)                                   │
│     b) YOLO (deep learning)                                     │
│     c) Comparativo lado a lado                                  │
│ 5. Vídeo é processado e reproduzido em tempo real com           │
│    anotações + contador atualizado (carros totais + por minuto) │
└─────────────────────────────────────────────────────────────────┘
```

### Modo OpenCV puro — visualização passo a passo

Quando o usuário escolhe o modo clássico, ele deve poder **navegar entre as etapas do pipeline** (via setas ou submenus) e ver o vídeo se transformando em tempo real conforme a etapa selecionada:

| Etapa | O que mostra |
|-------|--------------|
| 1. Frame original | Vídeo cru, sem processamento |
| 2. Background Subtraction | Máscara mostrando apenas o que se move |
| 3. Morfologia (erosão + dilatação) | Máscara limpa, sem ruído |
| 4. Contornos detectados | Bounding boxes desenhadas sobre o vídeo original |
| 5. Tracking + Contagem | Visualização final com IDs e contador |

O vídeo segue rodando, mas o **efeito visual aplicado se adapta** à etapa que o usuário está visualizando. Isso é o coração didático da apresentação.

### Modo YOLO

Vídeo + bounding boxes do YOLO + tracking + contador. Pode ter um submenu mostrando as detecções com `confidence score` e a classe detectada (car/truck/bus/motorcycle).

### Modo Comparativo

Dois players lado a lado, mesmo vídeo, mesmo ROI, processamentos diferentes. Contadores independentes pra mostrar diferenças de desempenho.

---

## 4. Decisões Técnicas (já fechadas)

| Tópico | Escolha | Por quê |
|--------|---------|---------|
| Linguagem | **Python 3.10+** | Padrão de visão computacional, sugerido pelo professor |
| Detecção | **Ambas: OpenCV clássico + YOLO** | Permite comparar abordagens e enriquece a apresentação |
| Tracking | **Centroid Tracker implementado do zero** | Algoritmo simples e altamente didático |
| Interface | **Flask + HTML/CSS/JS puros** | Sem mágica, controle total, fácil de explicar |
| Ambiente | **Local (notebooks dos integrantes)** | Estabilidade na apresentação, sem dependência de internet |
| Modelo YOLO | **Pré-treinado em COCO** (variante via `NOME_MODELO` em `detector_yolo.py`) | Detecta car/truck/bus/motorcycle sem precisar treinar |
| Treinamento próprio | **Não vamos treinar** | YOLO já vem pronto; explicaremos por quê na apresentação |

---

## 5. Stack e Dependências

```
# Visão computacional e processamento de vídeo
opencv-python              # leitura de vídeo, processamento de imagem, desenhos
numpy                      # operações com arrays (base de tudo em CV)

# Deep learning (modo YOLO)
ultralytics                # YOLO pronto pra uso
torch + torchvision        # backend do ultralytics

# Interface web
flask                      # servidor e roteamento
werkzeug                   # uploads seguros (vem com Flask)

# Auxiliares
pillow                     # manipulação de imagens auxiliar
```

Tudo será fixado em um `requirements.txt` na raiz quando chegarmos na etapa de setup.

---

## 6. Convenções e Padrões

### Código

- Comentários em **português**, didáticos, explicando o "porquê".
- Funções com docstring curta (1–3 linhas) explicando entrada e saída.
- Nomes de variáveis em português quando ajudar no entendimento (`mascara_movimento` é melhor que `motion_mask` pra alunos brasileiros lendo o código pela primeira vez).
- Constantes mágicas (limiares de área, taxa de aprendizado do background, etc) ficam em constantes nomeadas no topo do arquivo, com comentário justificando o valor.

### Documentação por etapa

Cada etapa concluída deve gerar um arquivo `.md` de documentação correspondente (nome e local a serem definidos quando a etapa for executada). Esse arquivo deve conter:

1. **O que é** (conceito em linguagem simples)
2. **Por que precisamos disso** (papel no pipeline)
3. **Como funciona o algoritmo** (matemática/lógica, sem enrolação)
4. **Como usamos** (trecho de código comentado)
5. **Limitações e alternativas** (importante pra apresentação)
6. **Perguntas prováveis na apresentação** (com respostas)

### Commits (se usar git)

- Um commit por etapa concluída (ex: `feat: etapa X - background subtraction`).
- Mensagens em português.

---

## 7. Glossário Técnico

*(Vai sendo expandido conforme as etapas avançam.)*

- **Frame**: uma imagem individual de um vídeo. Vídeo = sequência de frames a uma taxa (FPS).
- **FPS (Frames Per Second)**: quantos frames são exibidos por segundo. Crítico pra calcular "veículos por minuto".
- **ROI (Region of Interest)**: região da imagem onde queremos focar o processamento. No nosso projeto é um **polígono** (área fechada com N pontos) desenhado pelo usuário; um veículo é contado ao entrar nessa área.
- **Polígono**: figura fechada definida por uma sequência de vértices. Pode ser convexo ou côncavo.
- **Point-in-polygon / Ray casting**: algoritmo que decide se um ponto está dentro de um polígono disparando um raio e contando cruzamentos com as arestas (ímpar = dentro, par = fora). Funciona com polígonos côncavos, ao contrário do teste por sinal em cada aresta.
- **Background Subtraction**: técnica que "aprende" o fundo estático de uma cena e isola o que se move.
- **Morfologia matemática**: operações em imagens binárias (erosão, dilatação) que limpam ruído.
- **Contorno**: curva fechada que delimita uma região conectada na imagem.
- **Bounding box**: retângulo que envolve um objeto detectado.
- **Tracking**: acompanhar o mesmo objeto entre frames consecutivos.
- **Centroid**: centro geométrico de uma bounding box.
- **YOLO (You Only Look Once)**: família de modelos de deep learning que detecta objetos em uma única passada pela rede.
- **COCO**: dataset público com 80 classes de objetos, incluindo car/truck/bus/motorcycle. Base do YOLO pré-treinado.
- **IoU (Intersection over Union)**: métrica que mede sobreposição entre bounding boxes (usada em tracking e NMS).
- **NMS (Non-Max Suppression)**: técnica para descartar detecções redundantes do YOLO.
- **venv**: ambiente virtual Python. Caixa isolada com o próprio interpretador e suas próprias bibliotecas, evitando conflitos entre projetos da mesma máquina.
- **pip**: gerenciador de pacotes do Python. Lê o `requirements.txt`, baixa pacotes do PyPI e instala dentro do venv ativo.
- **PyPI (Python Package Index)**: repositório oficial onde o `pip` busca os pacotes.
- **Dependência transitiva**: pacote instalado automaticamente porque outro pacote depende dele (ex: `torch` é puxado pelo `ultralytics`).
- **.gitignore**: arquivo que diz pro git quais caminhos não devem ser versionados.
- **Flask**: microframework web em Python. Recebe requisições HTTP e despacha cada uma pra uma função registrada via `@app.route`.
- **Rota**: par "URL → função Python" registrado no Flask. Ex: `GET /configurar/<id>` chama `configurar(id)`.
- **Template (Jinja2)**: arquivo HTML com marcações `{{ }}` e `{% %}` que o Flask preenche com dados do Python antes de enviar pro navegador.
- **Herança de templates**: técnica do Jinja em que um arquivo base define blocos vazios e templates filhos os preenchem (`{% extends %}` + `{% block %}`).
- **Sessão**: cookie assinado pelo servidor onde o Flask guarda dados entre requisições sem precisar de banco de dados.
- **`url_for`**: função do Flask que gera a URL correta pra uma rota a partir do nome dela, evitando hardcoding de caminhos.
- **`secure_filename`**: função do werkzeug que sanitiza nomes de arquivos enviados pelo usuário (remove `../`, acentos, etc).
- **Canvas (HTML)**: elemento `<canvas>` onde JavaScript desenha gráficos pixel a pixel. Usamos pra desenhar a ROI por cima do vídeo. Tem dois tamanhos que precisam casar: o de exibição (CSS) e o do bitmap interno (`canvas.width/height`), onde o desenho realmente acontece.
- **ResizeObserver**: API do navegador que avisa o JS sempre que um elemento muda de tamanho na tela. Usamos pra manter o bitmap do canvas sincronizado com o tamanho exibido.
- **object-fit: contain**: regra CSS que encaixa a mídia dentro do espaço mantendo a proporção, criando barras pretas se as proporções não baterem. Ajustamos a proporção do container à do vídeo pra evitar essas barras.
- **MOG2 (Mixture of Gaussians 2)**: algoritmo de background subtraction que modela cada pixel como uma mistura de gaussianas, identificando o que é fundo e o que é movimento.
- **Kernel (morfologia)**: pequena matriz/forma usada como referência em operações morfológicas (erosão, dilatação).
- **Opening / Closing**: combinações de erosão e dilatação. Opening remove ruído; closing fecha buracos.
- **Threshold (`cv2.threshold`)**: operação que binariza uma imagem em escala de cinza — abaixo do limiar vira 0, acima vira 255.
- **`findContours`**: função do OpenCV que identifica curvas fechadas em uma imagem binária.
- **`boundingRect`**: menor retângulo (alinhado aos eixos) que envolve um contorno.
- **Produto vetorial 2D**: técnica para descobrir de que lado de uma linha um ponto está. Sinal positivo/negativo indica o lado.
- **Generator (Python)**: função que usa `yield` em vez de `return`. Produz valores sob demanda; ideal pra streaming.
- **MJPEG (Motion JPEG)**: técnica de streaming onde cada frame é enviado como uma imagem JPEG independente via `multipart/x-mixed-replace`.
- **AJAX (`fetch`)**: chamada HTTP do navegador pro servidor sem recarregar a página. Usamos pra mudar a etapa e ler o contador.
- **Polling**: técnica em que o cliente faz requisições periódicas pra obter atualizações do servidor.
- **GIL (Global Interpreter Lock)**: lock do CPython que serializa execução de bytecode entre threads. Garante atomicidade básica de operações em dict, mas não cobre operações compostas.
- **`threading.Lock`**: mecanismo de sincronização entre threads. Usado pra proteger escritas compostas no estado global.
- **ultralytics**: biblioteca que empacota o YOLO com API simples (`YOLO(...).predict(...)`). Aplica NMS internamente.
- **Inferência**: passar uma entrada (frame) pela rede já treinada pra obter a saída (detecções). Diferente de treino, que ajusta os pesos.
- **Confiança (confidence score)**: probabilidade que o modelo atribui a uma detecção. Filtramos abaixo de 0.4.
- **`NOME_MODELO`**: constante em `detector_yolo.py` que define qual arquivo `.pt` carregar (ex.: `yolov8n.pt`). Trocar a variante altera precisão × velocidade sem mudar o resto do pipeline.
- **Lazy loading**: carregar um recurso caro (o modelo) só na primeira vez que é preciso, e reaproveitar depois. Feito com double-checked locking em `detector_yolo.py`.
- **Carregamento único + lock (double-checked locking)**: padrão pra garantir que o modelo seja carregado uma só vez mesmo com vários streams começando juntos.

---

## 8. Histórico de Decisões

| Data | Decisão | Justificativa |
|------|---------|---------------|
| 2026-05-27 | Adotar ambas as abordagens de detecção | Mais conteúdo de apresentação, permite comparação |
| 2026-05-27 | Flask em vez de Streamlit | Controle total, sem mágica oculta, mais didático |
| 2026-05-27 | YOLO pré-treinado, sem treino próprio | Já cobre as classes que precisamos; treinar seria overkill |
| 2026-05-27 | Centroid Tracker implementado do zero | Algoritmo simples ideal para entender tracking |
| 2026-05-27 | Visualização passo a passo no modo OpenCV | Coração didático da apresentação |
| 2026-05-27 | Estrutura de diretórios e etapas definidas sob demanda | Evitar confusão e aumentar domínio sobre cada peça do projeto |
| 2026-05-27 | Versões mínimas (`>=`) no requirements.txt, sem fixar | Permite ao pip resolver conflitos com torch entre SOs/GPU |
| 2026-05-27 | Etapa 1 concluída: setup do ambiente | Criados `requirements.txt`, `.gitignore`, `README.md`, `docs/01_setup_ambiente.md` |
| 2026-05-27 | Etapa 2 concluída: interface Flask (sem backend funcional) | Criados `app.py`, 6 templates, `style.css`, `app.js`, `docs/02_interface_flask.md` |
| 2026-05-27 | CSS puro (sem Bootstrap/Tailwind) e JS vanilla (sem React/Vue) | Coerente com filosofia de "sem mágica oculta" |
| 2026-05-31 | Removido modo demo (`video_id="demo"`) | Fluxo exige upload real; simplifica rotas, templates e JS |
| 2026-05-27 | Etapa 3 concluída: pipeline OpenCV clássico funcional | Criados `core/leitor_video.py`, `core/detector_classico.py`, `core/tracker.py`, `core/contador.py`, `docs/03_pipeline_opencv.md` |
| 2026-05-27 | Etapa 4 concluída: streaming MJPEG + API JSON funcional | Reescrita do `app.py` com rotas de stream/API; templates atualizados com vídeo real e polling do contador; `docs/04_streaming_tempo_real.md` |
| 2026-05-27 | MJPEG + polling escolhidos sobre WebSocket | Mais didático, menos infraestrutura, suficiente pro escopo |
| 2026-05-27 | Estado global em memória (`estado_videos`) com `threading.Lock` | Sem banco de dados; lock protege escritas compostas |
| 2026-05-27 | Largura máxima de processamento: 960px | Equilíbrio entre tempo real e qualidade da detecção |
| 2026-05-27 | YOLO e modo comparativo ainda não implementados | Modo OpenCV priorizado por ser o coração didático do trabalho |
| 2026-05-27 | Correção da seleção de ROI no canvas | Linha não aparecia ao desenhar e caía no "default" do meio no processamento. Causa: divergência entre tamanho de exibição (CSS) e bitmap do canvas — a normalização estourava 0..1 e o backend rejeitava (erro 400). Solução em `app.js`: coords normalizadas desde o clique, `ResizeObserver` sincronizando o bitmap e ajuste da proporção do container ao vídeo no `loadedmetadata` (elimina barras pretas do `object-fit: contain`) |
| 2026-05-27 | ROI passou de LINHA para ÁREA (polígono de N pontos) | Mais flexível: permite contar a cena toda ou só uma faixa em via de mão dupla. Contagem reescrita com point-in-polygon (ray casting) em `contador.py`; contagem na "primeira vez dentro" da área (não em transição) pra suportar área = cena inteira |
| 2026-05-27 | Botão + atalho "Alterar área e zerar" no modo OpenCV | Antes era preciso voltar/recarregar. Botão linka pra `/configurar/<id>` (atalho tecla A); o `Contador` é recriado no novo stream, zerando a contagem. `configurar` repovoa o polígono salvo (`roi_inicial`) |
| 2026-05-27 | Etapa 5 concluída: YOLO + modo comparativo | Criado `core/detector_yolo.py` (YOLO pré-treinado em COCO, classes de veículo, NMS via ultralytics); `app.py` refatorado com `_gerar_stream` genérico parametrizado por modo, contadores por modo no estado, rotas `/stream/<id>/<modo>`, `/api/contador/<id>/<modo>`, `/api/deteccoes/<id>`; templates YOLO e comparativo funcionais; `docs/05_yolo_e_comparativo.md` |
| 2026-05-27 | YOLO e clássico devolvem o mesmo formato de saída `(x,y,w,h)` | Permite reusar o mesmo tracker e contador nos três modos; só o detector e a renderização mudam |
| 2026-05-27 | Um único `_gerar_stream` parametrizado por modo (sem duplicar) | OpenCV e YOLO compartilham o fluxo de stream; só detector + renderização diferem |
| 2026-05-27 | Modelo YOLO guardado localmente em `modelos/` | Garante funcionamento offline na apresentação (ultralytics baixaria só na 1ª vez com internet) |
| 2026-05-31 | Referências unificadas como "YOLO" (não YOLOv8/nano) | Variante do modelo é parametrizável via `NOME_MODELO`; docs e UI não amarram a um tamanho específico |
| 2026-05-27 | Comparativo: dois streams independentes + etapa OpenCV forçada em 5 | Cada lado tem seu contador; lado clássico mostra o resultado final (tracking) em vez do frame cru |

---

## 9. Como o Claude deve operar neste projeto

Ao receber um novo pedido nesta pasta:

1. **Ler este arquivo por completo.**
2. Identificar em que ponto do desenvolvimento estamos (com base nas decisões já registradas e no que existe na pasta).
3. Explicar o conceito **antes** de codar.
4. Codar com comentários didáticos.
5. Criar/atualizar o arquivo de documentação da etapa correspondente.
6. Atualizar este `CLAUDE.md` (registrar decisões novas no histórico, adicionar termos novos ao glossário).
7. Resumir ao final o que foi feito e qual a próxima etapa sugerida — **sem impor**, apenas sugerindo, já que o grupo decide o caminho.

**Princípio guia:** se ao final da etapa qualquer integrante do grupo não conseguir explicar o que foi feito, o trabalho não está pronto — independentemente de funcionar.
