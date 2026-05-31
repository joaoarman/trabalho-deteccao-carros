# Etapa 2 — Interface Web (Flask)

## 1. O que é

Esta etapa cria a **casca visual** do sistema: as páginas HTML, o estilo (CSS), a interatividade básica do navegador (JavaScript) e o servidor Flask que entrega tudo isso pro browser. Nenhuma detecção real acontece ainda — todos os contadores e visualizações mostram dados placeholder. O objetivo é ter o "esqueleto" da UX pronto antes de plugar a lógica de visão computacional.

---

## 2. Por que precisamos disso

Construir a interface primeiro tem três motivos práticos:

1. **Define o contrato.** Cada tela exige certos dados (vídeo, ROI, modo, contador, etc.). Construir a interface deixa óbvio o que a parte de processamento precisa devolver. Sem isso, a gente acabaria escrevendo lógica que ninguém usa, ou faltando dados que ninguém previu.
2. **Permite demonstrar o fluxo cedo.** Já temos algo navegável pra mostrar pro grupo (e pro professor, se quisermos validar conceito antes da apresentação final).
3. **Separação clara de responsabilidades.** A interface é uma camada independente do processamento. Trocar OpenCV por outra biblioteca, mais pra frente, não exige redesenhar telas.

---

## 3. Como funciona

### O que é Flask

Flask é um **microframework** web em Python. "Micro" porque o núcleo é pequeno e não impõe estrutura — você decide. Em essência, Flask faz três coisas:

1. **Recebe requisições HTTP** do navegador (GET, POST, etc.).
2. **Despacha** cada requisição pra uma função Python que você registrou com um decorador `@app.route(...)`.
3. **Devolve a resposta** — geralmente HTML renderizado a partir de um template.

```python
@app.route("/")              # registra a URL "/"
def index():
    return render_template("index.html")   # devolve o HTML renderizado
```

### Templates Jinja2

O Flask vem com o **Jinja2**, motor de templates. Em vez de HTML estático, escrevemos arquivos `.html` com "marcações" que o Python preenche dinamicamente:

```html
<p>Vídeo: <strong>{{ nome_arquivo }}</strong></p>
```

A sintaxe é:

- `{{ ... }}` — expressão (imprime o valor)
- `{% ... %}` — bloco de controle (if, for, extends, block)
- `{# ... #}` — comentário (não vai pro HTML final)

#### Herança de templates

Usamos `base.html` como "molde". Cada página filha herda dele e preenche os "buracos":

```html
{% extends "base.html" %}
{% block conteudo %}
    <h1>Conteúdo da página</h1>
{% endblock %}
```

Isso evita repetir `<head>`, header, footer, links de CSS em cada página.

### `url_for` — gerando URLs corretamente

Em vez de escrever `<a href="/configurar/abc123">`, escrevemos:

```html
<a href="{{ url_for('configurar', video_id='abc123') }}">
```

A função `url_for` consulta as rotas registradas e monta a URL correta. Vantagem: se a rota mudar, o link continua funcionando.

### Arquivos estáticos (`static/`)

CSS, JS, imagens vão na pasta `static/`. O Flask serve esses arquivos automaticamente. No template, usamos:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
```

### Sessão (cookie assinado)

Como não temos banco de dados, usamos `session` do Flask pra guardar o nome do vídeo entre páginas. A sessão é um **cookie assinado**: o navegador armazena, mas o servidor assina criptograficamente, então o usuário não consegue forjar.

```python
session[f"video_{video_id}"] = nome_arquivo
```

A assinatura usa `app.secret_key`. Pra desenvolvimento basta uma string qualquer; em produção, viria de variável de ambiente.

### Fluxo de uma requisição

1. Usuário clica em "Enviar" → navegador dispara `POST /upload` com o arquivo no corpo.
2. Flask roteia pra função `upload()`.
3. A função salva o arquivo em `uploads/`, gera um `video_id`, salva na sessão.
4. Devolve `redirect(url_for("configurar", video_id=...))` → o navegador recebe `302` e faz `GET /configurar/<video_id>`.
5. Flask roteia pra `configurar()`, que renderiza `configurar.html` com os dados.

---

## 4. Como usamos

### Estrutura criada

```
trabalho-topicos/
├── app.py                                  # servidor Flask + rotas
├── templates/
│   ├── base.html                           # molde compartilhado
│   ├── index.html                          # upload
│   ├── configurar.html                     # ROI + escolha de modo
│   ├── processar_opencv.html               # modo OpenCV com etapas
│   ├── processar_yolo.html                 # modo YOLO
│   └── processar_comparativo.html          # lado a lado
└── static/
    ├── css/style.css                       # estilos
    └── js/app.js                            # interatividade
```

### Rotas

| Método | URL | Função | O que faz |
|--------|-----|--------|-----------|
| GET | `/` | `index` | Mostra o formulário de upload |
| POST | `/upload` | `upload` | Recebe o arquivo, valida, salva, redireciona |
| GET | `/configurar/<video_id>` | `configurar` | Tela de seleção de ROI + escolha de modo |
| GET | `/processar/<video_id>/<modo>` | `processar` | Tela de processamento, varia por modo |

### Como rodar

```bash
source venv/bin/activate         # ou venv\Scripts\activate no Windows
pip install -r requirements.txt
python app.py
```

Abrir [http://localhost:5000](http://localhost:5000). O Flask reinicia automaticamente quando `app.py` é salvo (porque rodamos com `debug=True`).

### Interatividade no navegador (app.js)

Três funções, uma por tipo de tela:

- `inicializarUpload()` — drag-and-drop, mostra nome do arquivo escolhido, habilita o botão de envio
- `inicializarSelecaoROI()` — usuário clica em dois pontos do canvas, JS desenha uma linha (mock; o backend ainda não recebe esses pontos)
- `inicializarPipelineOpenCV()` — troca a etapa ativa (1 a 5) ao clicar nos itens da lista, com setas e atalhos ← / →

---

## 5. Limitações e alternativas

### Limitações da implementação atual

- **Nenhum processamento real.** Contadores são `0`, vídeos são placeholders, ROI não é enviada.
- **Sessão em cookie.** Se o usuário limpar cookies, o `video_id` se perde. Em produção, usaríamos banco ou armazenamento server-side.
- **Sem autenticação.** Qualquer um que abrir a URL acessa qualquer vídeo. Pro escopo acadêmico não é problema.
- **Servidor de desenvolvimento.** `app.run(debug=True)` é só pra dev. Em produção, usaríamos Gunicorn ou similar.

### Alternativas que descartamos

| Tecnologia | Por que não escolhemos |
|------------|------------------------|
| Streamlit | Mágica demais — esconde o que é HTTP, request, template. Atrapalha o aprendizado. |
| FastAPI | Mais moderno, mas focado em APIs JSON. Pra renderizar HTML, Flask é mais direto. |
| Django | Muito grande pra um MVP. Vem com ORM, admin, autenticação — coisas que não usamos. |
| React/Vue + API | Separação front/back valeria a pena num projeto maior. Aqui dobraria a complexidade sem ganho. |
| Bootstrap/Tailwind | Frameworks de CSS escondem como o CSS funciona. Preferimos CSS puro com variáveis. |

---

## 6. Perguntas prováveis na apresentação

**P: Por que Flask e não Streamlit, já que Streamlit faz upload e vídeo player com 3 linhas?**
R: Justamente porque o Streamlit faz isso "do nada". Não conseguiríamos explicar o que acontece por baixo. Com Flask, escrevemos cada rota, cada template, cada estilo — e dominamos. O critério do trabalho é entendimento profundo, não economia de linhas.

**P: O que é o Jinja2 e por que vocês usaram herança de templates?**
R: Jinja2 é o motor de templates do Flask. Permite misturar HTML com expressões Python. Herança evita repetir `<head>`, header e footer em cada página — qualquer mudança no layout global é feita em um lugar só (`base.html`).

**P: Como vocês passam dados entre páginas sem banco de dados?**
R: Pela sessão do Flask, que é um **cookie assinado**. O servidor escreve dados ali (`session["video_xyz"] = "nome.mp4"`) e o navegador devolve esse cookie em cada requisição. A assinatura impede o usuário de alterar valores.

**P: Por que vocês usam `url_for()` em vez de escrever URLs direto?**
R: Porque desacopla os links das rotas. Se mudarmos a URL `/configurar/<video_id>` pra `/setup/<video_id>`, todos os `url_for("configurar", ...)` continuam funcionando — só precisamos mexer no nome da rota num lugar.

**P: O que é o `secure_filename` que vocês importaram do werkzeug?**
R: Uma função que sanitiza o nome do arquivo enviado pelo usuário. Sem ela, alguém poderia fazer upload com nome `../../../etc/passwd` e nosso código sobrescreveria arquivos do sistema. Ela também remove acentos e caracteres especiais que podem dar problema em diferentes sistemas operacionais.

**P: Por que o canvas é desenhado por cima do vídeo em vez de no próprio vídeo?**
R: Porque o `<video>` é uma tag opaca — não dá pra desenhar dentro dela diretamente. A técnica padrão é sobrepor um `<canvas>` na mesma posição, com `position: absolute`. O canvas captura os cliques e desenha as marcações. Quando integrarmos o processamento real, vamos pintar os bounding boxes nesse mesmo canvas.

**P: Por que tem três templates separados pra processamento em vez de um só com if/else?**
R: Os três modos têm layouts e elementos bem diferentes (OpenCV tem lista de etapas; YOLO tem lista de detecções; Comparativo tem dois players). Forçar tudo num template só com `{% if modo == "opencv" %}` ficaria ilegível. Separar deixa cada arquivo focado.

**P: O `debug=True` é seguro?**
R: Só pra desenvolvimento local. Em produção mostraria stack traces sensíveis pro usuário e permitiria executar código remotamente via console interativo. Sempre desligado em produção.
