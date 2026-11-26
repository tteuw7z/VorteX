# Matriz de equivalência — após Fase 5

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
| Media QA | FFprobe, metadados, orientação, áudio e SRT | Probe, cenas, lote e QA de cadência por timestamps/frame. H.264/AAC 1080p60 verificado | 3 entregue no escopo testado / interpretação visual semântica pendente |
| Transcrição | Lote via faster-whisper, TXT/SRT/JSON e revisão | Reconhecimento local via whisper.cpp, TXT/JSON/SRT/ASS com revisão. Tempo de grafemas estimado. Execução real em inglês verificada | 3 entregue no escopo testado / outros idiomas e fala real requerem avaliação |
| ZIP | Plugin com extração, substituição e fluxo de lote | Limites, verificação CRC, sem sobrescrita, lista de candidatos, extração e reempacotamento. 17 vídeos reais sintéticos passaram | 3 entregue no Linux / checar sistemas adicionais |
| Android/APK | Build condicionado ao SDK/Gradle, assinatura e relatório | Build real de fixture por SDK e Gradle, isolamento de projeto, verificação da assinatura, hash e checagem estrutural de ABI; sem ensaio em aparelho | 3 entregue no escopo sintético / builds com app e ABI nativos na avaliação final |
| Automação e provedores | Permissões, handoffs, fallback e callbacks | DAG com manifesto, aprovações e operações locais permitidas; SDK, Gradle, FFmpeg e Whisper acionados. Conectores SaaS autenticados pendentes | 4 integrada no escopo local / verificar portabilidade entre assistentes na Fase 5 |
| CI e portabilidade | Workflow e suíte de referência aferida na Fase 1 | CI em CPython 3.15.2, FFmpeg e fixture Android auditada. Execução local com ferramentas nativas validada em Linux | 3 entregue no escopo testado / revisar portabilidade nas Fases 4 e 5 |

## Revisão da Fase 5

| Capacidade | Evidência de integração | Limite para aceite final |
| --- | --- | --- |
| Roteamento e colaboração | Planejamento bilíngue de mídia + ZIP via Python e CLI; o orçamento limitado prioriza um responsável por capacidade. A DAG preserva evidência das alternativas e encaminha ao dependente os artefatos da tentativa bem-sucedida. | Corpus sintético reduzido; falta medir precisão em solicitações reais. |
| Automação e segurança | Aprovação por rótulo exato, estado técnico desconhecido bloqueado e publicação exclusiva de lote completo ou parcial com manifesto. Interrupção tratada permite repetir o destino. | Queda abrupta pode deixar diretório temporário órfão. Sistemas adicionais precisam de teste. |
| Integração com assistentes | Contratos locais para planejamento em OpenAI Responses e Anthropic Messages; as duas respostas carregam o mesmo plano e identificadores de chamada correspondentes. | Transporte, autenticação e chamadas ao vivo pendentes. |
| Desempenho e custo | Medição reproduzível de latência do planejador bilíngue no CI. | Sem telemetria de tokens faturados. |

## Consolidação

- Nenhum grupo de arquivos idênticos por SHA-256. Há sobreposição funcional entre regra de rota, triagem de workflow e escolha de perfis. Manter um catálogo de capacidades, um planejador e políticas de seleção reutilizáveis.
- Editor, voz e QA de mídia compartilham ativos e tempo em uma timeline única. Transcrição e legendas são etapas da mesma cadeia. Manter status distintos por etapa.
- Design, pesquisa e engenharia compartilham evidências e revisão. Usar um contrato de verificação em vez de um runtime por especialidade.
- Adaptadores e estados de aprovação devem passar por um único Core; perfis, ferramentas e serviços externos entram sob demanda.
