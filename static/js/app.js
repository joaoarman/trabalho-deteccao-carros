function inicializarUpload() {
    const areaUpload = document.getElementById("area-upload");
    const campoVideo = document.getElementById("campo-video");
    const nomeArquivo = document.getElementById("nome-arquivo-selecionado");
    const botaoEnviar = document.getElementById("botao-enviar");

    if (!areaUpload || !campoVideo) return;

    campoVideo.addEventListener("change", () => {
        if (campoVideo.files.length > 0) {
            mostrarNomeArquivo(campoVideo.files[0]);
        }
    });

    // Drag and drop
    ["dragenter", "dragover"].forEach((evento) => {
        areaUpload.addEventListener(evento, (e) => {
            e.preventDefault();
            areaUpload.classList.add("arrastando");
        });
    });
    ["dragleave", "drop"].forEach((evento) => {
        areaUpload.addEventListener(evento, (e) => {
            e.preventDefault();
            areaUpload.classList.remove("arrastando");
        });
    });
    areaUpload.addEventListener("drop", (e) => {
        const arquivos = e.dataTransfer.files;
        if (arquivos.length > 0) {
            campoVideo.files = arquivos;
            mostrarNomeArquivo(arquivos[0]);
        }
    });

    function mostrarNomeArquivo(arquivo) {
        const tamanhoMB = (arquivo.size / (1024 * 1024)).toFixed(1);
        nomeArquivo.textContent = `Selecionado: ${arquivo.name} (${tamanhoMB} MB)`;
        nomeArquivo.classList.add("visivel");
        botaoEnviar.disabled = false;
    }
}

/* ----------------------------------------------------------------------------
   O usuário clica em quantos pontos quiser pra formar um polígono. A partir de
   3 pontos a área já é válida e é salva no backend. Um veículo só é contado
   quando o centroide dele entra nessa área - assim dá pra contar a cena toda
   ou só uma faixa.

   DOIS TAMANHOS DO CANVAS
   ------------------------------------------
   Um <canvas> tem o tamanho de EXIBIÇÃO (CSS: width/height 100%) e o do BITMAP
   interno (canvas.width/height), onde o JS realmente desenha. Se divergem, o
   desenho sai deslocado/invisível e a normalização estoura 0..1. Por isso:
     - guardamos os pontos SEMPRE como frações 0..1 (relativas ao tamanho exibido);
     - mantemos o bitmap sincronizado com o tamanho exibido (ResizeObserver);
     - na hora de desenhar, multiplicamos a fração pela dimensão atual do bitmap.
   O backend multiplica pela resolução real do frame na hora de aplicar.
   ---------------------------------------------------------------------------- */
function inicializarSelecaoROI() {
    const canvas = document.getElementById("canvas-roi");
    const botaoLimpar = document.getElementById("botao-limpar-roi");
    const botaoDesfazer = document.getElementById("botao-desfazer-roi");
    const statusRoi = document.getElementById("status-roi");
    const video = document.getElementById("video-preview");
    const area = document.getElementById("area-roi");

    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    // Pontos guardados como frações 0..1 (ex: {x: 0.3, y: 0.5}). N pontos.
    let pontos = [];

    // Repovoa o polígono salvo antes (fluxo "Alterar área"). ROI_INICIAL vem do
    // backend como lista de pares [x, y]; convertemos pra {x, y}.
    if (Array.isArray(window.ROI_INICIAL)) {
        pontos = window.ROI_INICIAL.map(([x, y]) => ({ x, y }));
    }

    // Mantém o bitmap do canvas do mesmo tamanho em que ele é exibido.
    // Sem isso, o desenho sai deslocado/invisível. Redesenha em seguida porque
    // mexer em canvas.width/height limpa o conteúdo.
    function sincronizarTamanhoCanvas() {
        const rect = canvas.getBoundingClientRect();
        const largura = Math.round(rect.width);
        const altura = Math.round(rect.height);
        if (
            largura > 0 &&
            altura > 0 &&
            (canvas.width !== largura || canvas.height !== altura)
        ) {
            canvas.width = largura;
            canvas.height = altura;
        }
        redesenhar();
    }

    // ResizeObserver avisa sempre que o canvas muda de tamanho na tela - cobre
    // o carregamento inicial, redimensionar a janela e o ajuste de proporção
    // abaixo, tudo num único caminho. Mais confiável que escutar 'resize'.
    if (window.ResizeObserver) {
        new ResizeObserver(sincronizarTamanhoCanvas).observe(canvas);
    } else {
        window.addEventListener("resize", sincronizarTamanhoCanvas);
    }
    sincronizarTamanhoCanvas();

    // Ajusta a proporção do container à do vídeo assim que ela é conhecida.
    // Com o container na mesma proporção do vídeo, o `object-fit: contain` não
    // gera barras pretas, e o canvas passa a cobrir EXATAMENTE os pixels do
    // vídeo - a área desenhada cai no mesmo lugar que o backend vai usar.
    if (video && area) {
        video.addEventListener("loadedmetadata", () => {
            if (video.videoWidth && video.videoHeight) {
                area.style.aspectRatio = `${video.videoWidth} / ${video.videoHeight}`;
            }
        });
    }

    canvas.addEventListener("click", (e) => {
        const rect = canvas.getBoundingClientRect();
        // Converte o clique (pixels de tela) direto pra fração 0..1.
        const x = (e.clientX - rect.left) / rect.width;
        const y = (e.clientY - rect.top) / rect.height;
        pontos.push({ x, y });
        redesenhar();
        // A partir de 3 pontos a área é válida - salva a cada novo ponto.
        if (pontos.length >= 3 && !window.EH_DEMO) {
            salvarROI();
        } else {
            atualizarStatus();
        }
    });

    botaoLimpar.addEventListener("click", () => {
        pontos = [];
        redesenhar();
        atualizarStatus();
    });

    if (botaoDesfazer) {
        botaoDesfazer.addEventListener("click", desfazerUltimoPonto);
    }
    // Atalho: Backspace desfaz o último ponto (natural ao desenhar polígono).
    document.addEventListener("keydown", (e) => {
        if (e.key === "Backspace") {
            e.preventDefault();
            desfazerUltimoPonto();
        }
    });

    function desfazerUltimoPonto() {
        if (pontos.length === 0) return;
        pontos.pop();
        redesenhar();
        if (pontos.length >= 3 && !window.EH_DEMO) salvarROI();
        else atualizarStatus();
    }

    function redesenhar() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        // Frações 0..1 → pixels do bitmap atual.
        const emPixels = pontos.map((p) => ({
            px: p.x * canvas.width,
            py: p.y * canvas.height,
        }));

        // Preenchimento translúcido da área (só com polígono fechado, >= 3 pontos)
        if (emPixels.length >= 3) {
            ctx.beginPath();
            ctx.moveTo(emPixels[0].px, emPixels[0].py);
            emPixels.slice(1).forEach((p) => ctx.lineTo(p.px, p.py));
            ctx.closePath();
            ctx.fillStyle = "rgba(37, 99, 235, 0.2)";
            ctx.fill();
        }

        // Arestas entre os pontos (linha aberta com 2 pontos, fechada com 3+)
        if (emPixels.length >= 2) {
            ctx.beginPath();
            ctx.moveTo(emPixels[0].px, emPixels[0].py);
            emPixels.slice(1).forEach((p) => ctx.lineTo(p.px, p.py));
            if (emPixels.length >= 3) ctx.closePath();
            ctx.strokeStyle = "#2563eb";
            ctx.lineWidth = 3;
            ctx.stroke();
        }

        // Vértices por cima
        emPixels.forEach((p) => {
            ctx.beginPath();
            ctx.arc(p.px, p.py, 6, 0, Math.PI * 2);
            ctx.fillStyle = "#2563eb";
            ctx.fill();
            ctx.strokeStyle = "white";
            ctx.lineWidth = 2;
            ctx.stroke();
        });
    }

    function atualizarStatus(texto, definida) {
        if (!statusRoi) return;
        if (texto === undefined) {
            // Texto automático conforme o nº de pontos
            if (pontos.length === 0) texto = "Nenhuma área desenhada";
            else if (pontos.length < 3)
                texto = `${pontos.length} ponto(s) - faltam ${3 - pontos.length} pra fechar`;
            else texto = `Área com ${pontos.length} pontos`;
            definida = pontos.length >= 3;
        }
        statusRoi.textContent = texto;
        statusRoi.classList.toggle("definida", !!definida);
    }

    async function salvarROI() {
        // Os pontos já estão normalizados (0..1) - é só mandar.
        try {
            const resp = await fetch(`/api/roi/${window.VIDEO_ID}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ pontos }),
            });
            const data = await resp.json();
            if (data.ok) {
                atualizarStatus(`Área salva ✓ (${pontos.length} pontos)`, true);
            } else {
                console.error("Backend recusou a ROI:", data.erro);
                atualizarStatus();
            }
        } catch (err) {
            console.error("Erro ao salvar ROI:", err);
        }
    }

    // Estado inicial (reflete um polígono pré-carregado, se houver)
    atualizarStatus();
}

/* ----------------------------------------------------------------------------
   "Navegação ao vivo": ao clicar numa etapa, dispara fetch pro backend.
   O servidor lê esse estado a cada frame do stream e ajusta o display.
   ---------------------------------------------------------------------------- */
function inicializarPipelineOpenCV() {
    const itensEtapa = document.querySelectorAll(".etapa-item");
    const descricaoTitulo = document.getElementById("descricao-etapa-titulo");
    const descricaoTexto = document.getElementById("descricao-etapa-texto");
    const botaoAnterior = document.getElementById("etapa-anterior");
    const botaoProxima = document.getElementById("etapa-proxima");
    const contadorTotal = document.getElementById("contador-total");
    const contadorDetalhe = document.getElementById("contador-detalhe");
    const botaoAlterarArea = document.getElementById("botao-alterar-area");

    if (itensEtapa.length === 0) return;

    // "Alterar área": volta pra tela de seleção. Ao reabrir o modo OpenCV, um
    // novo stream é iniciado e um Contador novo é criado - ou seja, a contagem
    // zera naturalmente. O href do botão já aponta pra /configurar/<id>; aqui
    // só replicamos isso num atalho de teclado ("A").
    function irParaSelecaoArea() {
        if (botaoAlterarArea && botaoAlterarArea.href) {
            window.location.href = botaoAlterarArea.href;
        }
    }

    let etapaAtiva = 1;

    function selecionarEtapa(numero) {
        if (numero < 1) numero = 1;
        if (numero > itensEtapa.length) numero = itensEtapa.length;
        etapaAtiva = numero;

        itensEtapa.forEach((item) => {
            const n = parseInt(item.dataset.etapa, 10);
            if (n === numero) {
                item.classList.add("ativa");
                if (descricaoTitulo)
                    descricaoTitulo.textContent = `${n}. ${item.dataset.titulo}`;
                if (descricaoTexto)
                    descricaoTexto.textContent = item.dataset.descricao;
            } else {
                item.classList.remove("ativa");
            }
        });

        if (botaoAnterior) botaoAnterior.disabled = numero === 1;
        if (botaoProxima) botaoProxima.disabled = numero === itensEtapa.length;

        // Comunica ao backend
        if (!window.EH_DEMO) {
            fetch(`/api/etapa/${window.VIDEO_ID}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ etapa: numero }),
            }).catch((err) => console.error("Erro ao mudar etapa:", err));
        }
    }

    itensEtapa.forEach((item) => {
        item.addEventListener("click", () => {
            selecionarEtapa(parseInt(item.dataset.etapa, 10));
        });
    });

    botaoAnterior.addEventListener("click", () =>
        selecionarEtapa(etapaAtiva - 1),
    );
    botaoProxima.addEventListener("click", () =>
        selecionarEtapa(etapaAtiva + 1),
    );

    // Atalhos de teclado (←, → navegam etapas; "A" volta pra seleção da área)
    document.addEventListener("keydown", (e) => {
        if (e.key === "ArrowLeft") selecionarEtapa(etapaAtiva - 1);
        else if (e.key === "ArrowRight") selecionarEtapa(etapaAtiva + 1);
        else if (e.key === "a" || e.key === "A") irParaSelecaoArea();
    });

    selecionarEtapa(1);

    // ----- Polling do contador -----
    // setInterval chama a função a cada N ms. Aqui buscamos o contador
    // duas vezes por segundo. Não é "tempo real" estrito, mas é mais que
    // suficiente - e bem mais simples que WebSockets.
    if (!window.EH_DEMO) {
        async function atualizarContador() {
            try {
                const resp = await fetch(
                    `/api/contador/${window.VIDEO_ID}/opencv`,
                );
                const data = await resp.json();
                if (contadorTotal) contadorTotal.textContent = data.total;
                if (contadorDetalhe)
                    contadorDetalhe.textContent = `${data.por_minuto} por minuto`;
            } catch (err) {
                // Silencioso - se o servidor reiniciou ou rede caiu, só ignora
            }
        }
        setInterval(atualizarContador, 500);
        atualizarContador(); // executa uma vez imediatamente
    }
}

/* ----------------------------------------------------------------------------
   O vídeo em si chega pela <img> do stream (multipart, sem JS). Aqui só
   buscamos, por polling, o contador e a lista de detecções do frame atual
   (classe + confiança) pra preencher o painel lateral.
   ---------------------------------------------------------------------------- */
function inicializarYOLO() {
    if (window.EH_DEMO) return;

    const contadorTotal = document.getElementById("contador-total");
    const contadorDetalhe = document.getElementById("contador-detalhe");
    const listaDeteccoes = document.getElementById("lista-deteccoes");

    async function atualizar() {
        try {
            // Duas chamadas independentes - disparamos em paralelo.
            const [respContador, respDeteccoes] = await Promise.all([
                fetch(`/api/contador/${window.VIDEO_ID}/yolo`),
                fetch(`/api/deteccoes/${window.VIDEO_ID}`),
            ]);
            const contador = await respContador.json();
            const deteccoes = await respDeteccoes.json();

            if (contadorTotal) contadorTotal.textContent = contador.total;
            if (contadorDetalhe)
                contadorDetalhe.textContent = `${contador.por_minuto} por minuto`;

            renderizarDeteccoes(deteccoes.deteccoes || []);
        } catch (err) {
            // Silencioso - ignora falha pontual de rede
        }
    }

    function renderizarDeteccoes(itens) {
        if (!listaDeteccoes) return;
        if (itens.length === 0) {
            listaDeteccoes.innerHTML =
                '<p class="deteccoes-vazio">Nenhum veículo no frame atual.</p>';
            return;
        }
        // Monta um item por detecção. Reconstruímos o HTML inteiro a cada poll
        // (a lista é curta, no máximo 10 itens - simples e barato).
        listaDeteccoes.innerHTML = itens
            .map(
                (d) => `
            <div class="deteccao-item">
                <span class="deteccao-classe">${d.classe}</span>
                <span class="deteccao-confianca">${d.confianca.toFixed(2)}</span>
            </div>
        `,
            )
            .join("");
    }

    setInterval(atualizar, 500);
    atualizar();
}

/* ----------------------------------------------------------------------------
   Cada lado tem a sua <img> de stream (opencv e yolo). Aqui só fazemos o
   polling dos dois contadores. Também forçamos a etapa do OpenCV pra 5
   (tracking + contagem), pra o lado clássico já mostrar o resultado final em
   vez do frame cru.
   ---------------------------------------------------------------------------- */
function inicializarComparativo() {
    if (window.EH_DEMO) return;

    // Garante que o lado OpenCV mostre a etapa final (tracking + contagem).
    fetch(`/api/etapa/${window.VIDEO_ID}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ etapa: 5 }),
    }).catch(() => {});

    // Para cada modo, liga o polling do seu contador aos elementos do seu lado.
    function ligarContador(modo) {
        const total = document.getElementById(`contador-total-${modo}`);
        const detalhe = document.getElementById(`contador-detalhe-${modo}`);
        return async () => {
            try {
                const resp = await fetch(
                    `/api/contador/${window.VIDEO_ID}/${modo}`,
                );
                const data = await resp.json();
                if (total) total.textContent = data.total;
                if (detalhe)
                    detalhe.textContent = `${data.por_minuto} por minuto`;
            } catch (err) {
                /* silencioso */
            }
        };
    }

    const atualizarOpencv = ligarContador("opencv");
    const atualizarYolo = ligarContador("yolo");

    setInterval(() => {
        atualizarOpencv();
        atualizarYolo();
    }, 500);
    atualizarOpencv();
    atualizarYolo();
}
