# Etapa 1 — Setup do Ambiente

## 1. O que é

Setup é a preparação do ambiente antes de escrever uma única linha de código de aplicação. Para este projeto, consiste em:

- Criar um **ambiente virtual** Python (`venv`)
- Declarar as **dependências** num arquivo (`requirements.txt`)
- Configurar o **`.gitignore`** pra evitar versionar lixo
- Escrever um **`README.md`** que explica como rodar o projeto

Nenhum desses arquivos contém lógica do contador — eles existem pra garantir que qualquer pessoa que clone o repositório consiga rodar o projeto da mesma forma.

---

## 2. Por que precisamos disso

### Ambiente virtual

O Python instalado no sistema operacional é compartilhado por todos os projetos da máquina. Se um projeto precisar do `opencv-python==4.5` e outro do `opencv-python==4.9`, vai dar conflito. O `venv` resolve isso criando uma "caixa" isolada: o projeto tem o seu próprio Python e suas próprias bibliotecas, sem afetar o sistema.

### `requirements.txt`

É a **receita** do ambiente. Sem ele, instalar manualmente cada dependência é trabalhoso e propenso a erros. Com ele, um único comando (`pip install -r requirements.txt`) reproduz o ambiente.

### `.gitignore`

Diz pro git **o que NÃO versionar**. Coisas que entram nessa lista:

- O próprio ambiente virtual (`venv/`) — cada pessoa cria o seu
- Caches do Python (`__pycache__/`) — gerados automaticamente
- Vídeos enviados pelo usuário (`uploads/`) — são grandes e não fazem parte do código
- Vídeos gerados pelo sistema (`outputs/`) — idem
- Modelos do YOLO (`.pt`) — pesos pré-treinados que podem chegar a dezenas de MB; são baixados sob demanda pela `ultralytics`
- Arquivos do sistema operacional (`.DS_Store`, `Thumbs.db`) e de editores (`.vscode/`, `.idea/`)

---

## 3. Como funciona

### O que o `venv` faz por dentro

Quando você roda `python -m venv venv`, o Python:

1. Cria a pasta `venv/`
2. Copia (ou faz link simbólico) do executável do Python pra dentro dela
3. Cria uma pasta `site-packages` vazia, onde as bibliotecas serão instaladas
4. Gera scripts de **ativação** (`bin/activate` no Linux/macOS, `Scripts\activate` no Windows)

Quando você "ativa" o venv (ex: `source venv/bin/activate`), esses scripts modificam temporariamente a variável de ambiente `PATH` do terminal. Resultado: ao digitar `python` ou `pip`, o sistema pega os executáveis de dentro do `venv/` em vez dos do sistema. Qualquer `pip install` agora instala dentro do `venv/`, sem poluir o Python global.

Ao rodar `deactivate`, o `PATH` volta ao normal.

### Operadores de versão no `requirements.txt`

```text
opencv-python>=4.8.0
```

- `==1.2.3` → exatamente essa versão (rígido, ótimo pra reprodutibilidade absoluta).
- `>=1.2.0` → essa versão ou qualquer superior (permite atualizações).
- `~=1.2` → "compatível com 1.2", aceita 1.2.x mas não 1.3.

Optamos por `>=` porque:

- Permite que o `pip` resolva conflitos com dependências transitivas (em especial `torch`, instalado pela `ultralytics`, cuja versão correta varia por sistema operacional e por presença/ausência de GPU).
- Patches de segurança e correções menores são absorvidos automaticamente.

### Como o `pip install -r` decide o que baixar

O `pip`:

1. Lê o arquivo linha por linha.
2. Pra cada pacote, consulta o repositório oficial (PyPI) e resolve a melhor versão que satisfaz **todos** os requisitos simultaneamente (do projeto e das dependências entre si).
3. Baixa e instala cada pacote dentro de `venv/lib/.../site-packages/`.

Se houver conflito impossível de resolver, o `pip` aborta e mostra qual pacote causou o problema.

---

## 4. Como usamos

### Comandos do dia a dia

```bash
# Criar o ambiente (uma única vez)
python -m venv venv

# Ativar (sempre que abrir um terminal novo)
source venv/bin/activate           # macOS/Linux
venv\Scripts\activate.bat          # Windows (cmd)

# Atualizar o pip (boa prática logo após criar o venv)
pip install --upgrade pip

# Instalar tudo do requirements
pip install -r requirements.txt

# Conferir o que está instalado no venv atual
pip list

# Sair do venv ao terminar
deactivate
```

### Conteúdo dos arquivos criados

- **`requirements.txt`** — lista as 5 bibliotecas principais do projeto (`opencv-python`, `numpy`, `ultralytics`, `flask`, `pillow`) com versões mínimas e comentários explicando cada uma.
- **`.gitignore`** — exclui ambiente virtual, caches, modelos `.pt`, vídeos de upload/saída e arquivos de sistema operacional.
- **`README.md`** — instruções passo a passo de setup, com comandos separados por sistema operacional.

---

## 5. Limitações e alternativas

- **`venv` vs `conda`**: o `conda` resolve dependências binárias melhor (especialmente CUDA, BLAS). Pra projetos puros de Python rodando em CPU, `venv` é mais leve e suficiente.
- **`pip` vs `poetry` / `uv` / `pipenv`**: ferramentas mais modernas trazem lockfile (versão exata garantida) e melhor resolução de dependências. Pra escopo acadêmico, `pip + requirements.txt` é o padrão e funciona sem instalar nada extra.
- **Versão fixa (`==`) vs mínima (`>=`)**: pra reprodutibilidade absoluta de uma demo, `==` seria mais seguro. Optamos por `>=` pela compatibilidade com diferentes sistemas operacionais e configurações de GPU.
- **Docker**: garantiria ambiente idêntico em qualquer máquina, mas adiciona complexidade desnecessária pro escopo do trabalho.

---

## 6. Perguntas prováveis na apresentação

**P: Por que não instalar as bibliotecas direto no Python do sistema?**
R: Conflitos de versão entre projetos seriam inevitáveis. Se um projeto precisar de `opencv-python 4.5` e outro de `4.9`, um vai quebrar o outro. O `venv` isola.

**P: Por que vocês usaram versões mínimas (`>=`) em vez de versões fixas (`==`)?**
R: Porque o `ultralytics` instala o `torch` como dependência, e a versão correta do `torch` varia entre Linux, Windows, macOS e entre máquinas com e sem GPU. Deixar uma faixa de versões permite que o `pip` resolva esse quebra-cabeça automaticamente.

**P: O que tem dentro do `.gitignore`?**
R: Tudo que é (a) grande, (b) gerado automaticamente ou (c) específico da máquina. Especificamente: `venv/`, `__pycache__/`, `uploads/`, `outputs/`, `*.pt`, `.DS_Store`, configs de editores.

**P: O que é o `__pycache__`?**
R: Pasta onde o Python guarda os arquivos `.pyc` (bytecode compilado) pra acelerar a próxima execução do programa. É regenerado automaticamente, não precisa versionar.

**P: O `requirements.txt` lista 5 pacotes, mas o `pip install` baixou dezenas. Por quê?**
R: As bibliotecas principais têm dependências próprias (dependências transitivas). Por exemplo, o `ultralytics` puxa `torch`, `torchvision`, `matplotlib`, `pyyaml`, etc. O `pip` baixa toda a árvore automaticamente.

**P: O que muda entre `source venv/bin/activate` (Linux/Mac) e `venv\Scripts\activate.bat` (Windows)?**
R: A lógica é a mesma — modificar o `PATH` do terminal pra apontar pro Python do `venv/`. A diferença é só o shell: bash usa `source`, cmd usa `.bat`. O efeito é idêntico.
