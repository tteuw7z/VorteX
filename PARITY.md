# Matriz de equivalência — após Fase 4.1

**Base da auditoria da Fase 1:** árvores Git não truncadas, 361 arquivos na referência e 12 no destino antes desta auditoria. Referência: 337 Markdown, 16 Python e 8 arquivos complementares. São 28 skills e 268 fichas de perfis, reunidas em 18 divisões, incluindo engenharia, pesquisa, design, testes, segurança defensiva, educação, criação, negócios e suporte. Fichas descrevem papéis e referências, sem representar instâncias em execução. O inventário é do código versionado. Outros produtos, mídia, históricos e arquivos de conta ficam fora da distribuição pública.

**Estados:** executável = código acionável; documentado = procedimento/conhecimento registrado; parcial = apenas parte do contrato; pendente = implementação ou validação faltante.

| Capacidade | Referência auditada | VorteX público 0.1.0 | Fase / aceite |
| --- | --- | --- | --- |
| Roteamento e CLI | Executável: rotas, cenários, perfis, planejamento, simulação e comandos técnicos | Executável para planejamento, inventário, conhecimento, contexto e aprendizagem; CLI técnico integrado, com seleção explícita para ZIP | 4 revisada / ampliar cobertura contextual na Fase 5 |
| Core de colaboração | Executável: dependências, aprovações, fallback, passagem de artefatos, evidência e cache em processo | Executável: DAG sequencial, aprovações por estágio, resultados com evidência, artefatos JSON e alternativas condicionais. Cache por execução e integração externa seguem em aberto | 4 integrada / DAG preserva resultados parciais e impede dependências de consumi-los |
| Agentes e skills | Executável para seleção limitada por cenário; catálogo e instruções documentados | Executável para seleção limitada, configuração de capacidades e 12 perfis originais sob demanda. Execução externa depende do host | 2 entregue / portar contratos em fases posteriores |
| Contexto | Executável: estimativa, máscaras reversíveis de observações e deduplicação | Executável: preservação do checkpoint, deduplicação de observações extensas, restauração em memória e estimativa explícita | 2 entregue / medir em Fase 5 |
| Aprendizagem | Documentada: revisão, origem e consolidação de conhecimento | Executável: SQLite opt-in, deduplicação lexical, evidência fornecida, consulta seletiva e remoção | 2 entregue / verificar portabilidade em Fase 5 |
| Engenharia, debug e QA | Triagem e seleção de procedimentos executáveis. Segurança defensiva documentada | Inventário de imports, manifestos e sintaxe, com escopo estático e evidências por arquivo | 3 entregue em escopo local / regressão dinâmica e integração na Fase 5 |
| Pesquisa e reconstrução autorizada (Craft Anything / REA) | Procedimentos documentados e ferramentas externas condicionais | Excertos com origem e SHA-256; Study → Build → Check com candidato original, checks estáticos e fonte complementar | 3 entregue em escopo local / pesquisa autônoma e execução verificadas separadamente |
| Design/UI, canvas e 3D | Critérios de acessibilidade, dependências e handoff documentados | Auditoria de contraste e prévia responsiva de tokens, verificada em Chromium; integração com Figma, canvas vivo e 3D pendentes | 4 revisada / relatório de contraste integrado à CLI e à DAG; Figma e 3D pendentes |
| Motion, animação, editor e voz | Timeline, storyboard, tipografia, narração autorizada e revisão | Editor real com cortes, escala Full HD, 60 CFR, fades, P&B e legenda. Efeitos avançados e geração de voz não validados | 3 parcial / integrar e expandir testes de efeitos |
| Media QA | FFprobe, metadados, orientação, áudio e SRT | Probe, cenas, lote e QA de cadência por timestamps/frame. H.264/AAC 1080p60 e OCR opcional de texto em quadros amostrados verificados | 4.1 parcial / eventos, objetos, ações e descrição semântica pendentes |
| Transcrição | Lote via faster-whisper, TXT/SRT/JSON e revisão | Reconhecimento local via whisper.cpp, TXT/JSON/SRT/ASS com revisão. Tempo de grafemas estimado. EN exercitado. PT e FR exercitados com fala sintética, com erros de idioma automático e de palavras registrados | 4.1 parcial / verificar condições reais e revisão humana |
| ZIP | Plugin com extração, substituição e fluxo de lote | Limites, verificação CRC, sem sobrescrita, lista de candidatos, extração e reempacotamento. 17 vídeos reais sintéticos passaram | 3 entregue no Linux / checar sistemas adicionais |
| Android/APK | Build condicionado ao SDK/Gradle, assinatura e relatório | Build real de fixture por SDK e Gradle, isolamento de projeto, verificação da assinatura, hash e checagem estrutural de ABI; APK sintético com objeto compartilhado ARM64 assinado e verificado. Instalação e execução física pendentes | 4.1 verificada a estrutura nativa em Linux |
| Automação e provedores | Permissões, handoffs, fallback e callbacks | DAG com manifesto, aprovações e operações locais permitidas; SDK, Gradle, FFmpeg e Whisper acionados. Conectores SaaS autenticados pendentes | 4 integrada no escopo local / verificar portabilidade entre assistentes na Fase 5 |
| CI e portabilidade | Workflow e suíte de referência aferida na Fase 1 | CI em CPython 3.15.2, FFmpeg e fixture Android auditada. Execução local com ferramentas nativas validada em Linux | 3 entregue no escopo testado / núcleo, CLI, ZIP e contratos locais também testados em macOS e Windows |

## Revisão da Fase 5

| Capacidade | Evidência de integração | Limite para aceite final |
| --- | --- | --- |
| Roteamento e colaboração | Planejamento bilíngue de mídia + ZIP via Python e CLI; o orçamento limitado prioriza um responsável por capacidade. A DAG preserva evidência das alternativas e encaminha ao dependente os artefatos da tentativa bem-sucedida. | Corpus sintético reduzido; falta medir precisão em solicitações reais. |
| Automação e segurança | Aprovação por rótulo exato, estado técnico desconhecido bloqueado e publicação exclusiva de lote completo ou parcial com manifesto. Interrupção tratada permite repetir o destino. | Queda abrupta pode deixar diretório temporário órfão. Sistemas adicionais precisam de teste. |
| Integração com assistentes | Contratos locais para planejamento em OpenAI Responses e Anthropic Messages; as duas respostas carregam o mesmo plano e identificadores de chamada correspondentes. | Transporte, autenticação e chamadas ao vivo pendentes. |
| Desempenho e custo | Medição reproduzível de latência do planejador bilíngue no CI. | Sem telemetria de tokens faturados. |


## Revisão da Fase 4.1

| Pendência auditada | Evidência atual | Condição que resta |
| --- | --- | --- |
| Permissões, fallback e artefatos | Dependências e alternativas congeladas no grafo. Resultado inválido bloqueia dependentes ou aciona a alternativa aprovada com histórico. Lote lê a mesma árvore de extração que publica no relatório. | Cache de execução segue pendente. Evidência ligada a arquivo mutável requer identificação de conteúdo antes de reutilizar resultados. |
| Roteamento e custo | Oito tarefas PT/EN com perfis limitados e cenário de resposta direta. Medição local pareada com o baseline em duas tarefas sem regressão observada na mediana. | Precisão num corpus representativo e tokens retornados pelos provedores. |
| Portabilidade e permissões de host | Mesmos módulos locais e envelopes de assistente exercitados nos três sistemas. A CLI devolve JSON até em saída cp1252. | Binários de mídia e SDK validados em Linux. Serviços ao vivo exigem conta autorizada, credencial e modelo habilitado. |
| Transcrição e descrição | OCR retorna texto visível com timecodes. A cadeia ZIP → ASR → legendas → render → QA foi executada. A matriz de desempenho é sintética e confirma erros automáticos de idioma. | Descrição semântica, precisão da fala real, sincronização acústica por grafema, 3D, voz e aprendizagem autônoma com vídeo seguem abertos. |
| Android e distribuição | Biblioteca ELF AArch64 compilada e embutida em APK assinado, validado por AAPT2 e apksigner. Gradle também produziu APK com ARM64. | Instalação e execução da biblioteca em aparelho, binários de produção e distribuição. |
| Interrupção e privacidade | Lote preparado em diretório temporário privado antes de publicar. A regressão de interrupção tratada passou. O pacote preserva zero dependências Python de execução. | Morte abrupta pode deixar temporários órfãos. Integrações autenticadas, como Figma, dependem de escopo e conta autorizados. |

## Consolidação

- Nenhum grupo de arquivos idênticos por SHA-256. Há sobreposição funcional entre regra de rota, triagem de workflow e escolha de perfis. Manter um catálogo de capacidades, um planejador e políticas de seleção reutilizáveis.
- Editor, voz e QA de mídia compartilham ativos e tempo em uma timeline única. Transcrição e legendas são etapas da mesma cadeia. Manter status distintos por etapa.
- Design, pesquisa e engenharia compartilham evidências e revisão. Usar um contrato de verificação em vez de um runtime por especialidade.
- Adaptadores e estados de aprovação devem passar por um único Core; perfis, ferramentas e serviços externos entram sob demanda.

## Fase 6 — ampliação inicial

19 capacidades de planejamento, 22 perfis originais. Finanças, informações de saúde, marketing, vendas, produto, projetos, jogos, GIS, experiências espaciais e suporte ganham rotas bilíngues limitadas. São descritores e perfis de planejamento; não equivalem a execução de ferramentas especializadas ou a cobertura integral das fichas da referência. Testes do candidato ainda aguardam CI. A paridade integral permanece aberta.

Fase 6.2: cache em processo agora implementado para adaptadores puros explicitamente habilitados, limitado a 128 resultados bem-sucedidos por workflow. Não reutiliza falhas, arquivos mutáveis ou operações externas por padrão. Validação e ganho medido ainda pendentes.

Fase 6.3: catálogo e cache passaram no CI 45868236196 (77 aprovados, 3 ignorados). Otimização por índice invertido implementada; ganho exige comparação pareada no CI. Nenhuma telemetria de tokens reais foi coletada.

Fase 6.4: transporte de OpenAI Responses/Anthropic Messages e coleta de uso por resposta implementados no código. Somente testes locais de protocolo e fronteira HTTPS previstos neste commit. Zero chamadas autenticadas; integração real e economia faturada permanecem não comprovadas.

Fase 6.3/6.4: CI aprovou o índice e contratos locais HTTPS; mediana pareada de 14,63 para 10,88 µs/tarefa com planos iguais. Fase 6.5 adiciona efeitos explícitos de flash, shake rotacional, blur e contraste, ainda pendentes de validação. Sincronização automática musical, transições avançadas e descrição semântica continuam abertas.

Fase 6.5: efeitos explícitos aprovados em render sintético e comparação de pixels (CI 45868881805). Fase 6.6 implementa onsets locais de 35–160 Hz e remapeamento de flash para cortes; ainda exige CI e validação musical real. Não equivale a reconhecimento semântico ou classificação perfeita de batidas.

Fase 6.6: detecção de graves e flash automático passaram em áudio sintético real e render a 60 fps (CI 45869077696). Fase 6.7 reconfirmou inventário privado e verificou padrões comuns de credenciais em 57 arquivos públicos do candidato; nenhum match. Isso não comprova privacidade integral nem substitui revisão de histórico/licenças. Paridade e validações externas seguem abertas.

Fase 6.8: segurança de entrega ganha gate executável local, scanner heurístico e atestado autenticado independente. Não há verificador implantado ou integração obrigatória de todos os hosts. Controles de Gradle, aprendizagem e automação reforçados. CI pendente; cobertura e auditoria integral ainda abertas.
