# Contador de Veículos

Trabalho da cadeira de Tópicos Especiais em Computação. O sistema conta veículos que passam por uma área marcada em um vídeo, mostrando o total e a taxa por minuto.

## Como rodar

Precisa do Python 3.10 ou mais novo instalado.

Abra o terminal dentro da pasta do projeto e rode:

```bash
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

python app.py
```

No Windows, em vez de `source venv/bin/activate`, use:

```bash
venv\Scripts\activate
```

Depois é só abrir o navegador em http://127.0.0.1:5000

## Como usar

1. Suba um vídeo na página inicial (tem alguns de teste na pasta `samples/`).
2. Desenhe a área que vai contar os veículos por cima do vídeo.
3. Escolha o modo de processamento (OpenCV clássico ou YOLO).
4. Acompanhe o vídeo sendo processado e o contador na tela.

O modelo do YOLO já está na pasta `modelos/`, não precisa baixar nada.
