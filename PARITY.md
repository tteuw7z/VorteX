# Matriz de equivalência — baseline da Fase 1

**Base verificável:** árvores Git não truncadas, 361 arquivos na referência e 12 no destino antes desta auditoria. Referência: 337 Markdown, 16 Python e 8 arquivos complementares. São 28 skills e 268 fichas de perfis, reunidas em 18 divisões, incluindo engenharia, pesquisa, design, testes, segurança defensiva, educação, criação, negócios e suporte. Fichas descrevem papéis e referências, sem representar instâncias em execução. O inventário é do código versionado. Outros produtos, mídia, históricos e arquivos de conta ficam fora da distribuição pública.

**Estados:** executável = código acionável; documentado = procedimento/conhecimento registrado; parcial = apenas parte do contrato; pendente = implementação ou validação faltante.

| Capacidade | Referência auditada | VorteX público 0.1.0 | Fase / aceite |
| --- | --- | --- | --- |
| Roteamento e CLI | Executável: rotas, cenários, perfis, planejamento, simulação rotulada e comandos técnicos | Parcial: plan/inventory/version; regra determinística, até 3 skills e limite de papéis | 2 / manter contratos e testar empates, desconhecidos, PT/EN e validação |
| Core de colaboração | Executável: dependências válidas, aprovação, fallback, passagem de artefatos, evidência e cache em processo | Parcial: despacho de um adaptador aprovado, sem DAG | 2 / validar DAG, estados, erros, evidência, dependências e execução parcial |
| Agentes e skills | Executável para seleção limitada por cenário; catálogo e instruções documentados; execução externa depende do host | Parcial: oito descritores embutidos e papéis genéricos; nenhum executor externo de fábrica | 2 / catálogo indexado e carregamento seletivo; contrato com permissões do host |
| Contexto | Executável: estimativa consultiva, máscaras reversíveis de observações grandes e deduplicação | Pendente | 2 / ida e volta, limites, preservação de decisões e dados sensíveis |
| Aprendizagem | Documentada: revisão, origem e consolidação de conhecimento; persistência automática não comprovada | Parcial: plano educacional; memória de técnica pendente | 2 / registro explícito, origem, deduplicação e persistência |
| Engenharia/debug/QA e segurança defensiva | Executável para triagem e seleção de procedimentos; conhecimento documentado; sem execução generalizada de terceiros | Parcial: rotas de planejamento | 3 / diagnóstico defensivo reproduzível e evidência de regressão |
| Pesquisa e reconstrução autorizada (Craft Anything / REA) | Documentado: coleta, comparação e verificação; ferramentas externas condicionais | Parcial: plano de pesquisa | 3 / fontes rastreáveis, verificador e reconstrução original autorizada |
| Design/UI, canvas e 3D | Documentado: critérios visuais, acessibilidade, dependências e handoff | Parcial: plano de design | 3 / validar saída e revisão com fixture; integração real apenas se disponível |
| Motion, animação, editor e voz | Documentado: timeline, storyboard, tipografia, narração consentida, ritmo e revisão | Parcial: plano de mídia, sem render ou voz | 3 / timeline original e render verificável; voz autorizada e opcional |
| Media QA | Executável: FFprobe, orientação, dimensões, FPS médio, áudio e SRT; probe real testado | Pendente | 3 / fixture real, duração, áudio, timecodes e evidência de CFR separada |
| Transcrição | Executável com adaptador faster-whisper: lote, timestamps, TXT/SRT/JSON, hash e modelo opt-in; testes usam modelo simulado | Pendente | 3 / fala sintética, idioma, timecodes, textos e dependências reais |
| ZIP | Cobertura de inventário público aferida; extração/reempacotamento do plugin não aparece como executável na árvore de referência auditada | Executável em leitura: limites e validações básicas; sem extração/reempacotamento | 3 / validar caminhos, colisões, CRC, recursos, cópia e lote |
| Android/APK | Executável condicionado: wrapper/Gradle, lint, apksigner, hash, relatório e workflow; build debug e projeto Gradle externo | Parcial: plano Android sem build | 3 / build isolado, assinatura, hash e artefato; release e ARM64 verificadas separadamente |
| Automação e provedores | Documentado: permissões, handoffs e fallback; motor aceita callbacks fornecidos | Parcial: contrato genérico; conectores reais pendentes | 3 / um adaptador real por necessidade, autorização, idempotência e verificação |
| CI e portabilidade | Workflow Python 3.11 declarado e suíte executada localmente em 3.15.2 nesta auditoria | Executável: workflow 3.15.2 com execução pública bem-sucedida; compatibilidade entre hosts pendente | 2–6 / confirmar pacote e CI por plataforma, sem extrapolar sucesso |

## Consolidação

- Nenhum grupo de arquivos idênticos por SHA-256. Há sobreposição funcional entre regra de rota, triagem de workflow e escolha de perfis. Manter um catálogo de capacidades, um planejador e políticas de seleção reutilizáveis.
- Editor, voz e QA de mídia compartilham ativos e tempo em uma timeline única. Transcrição e legendas são etapas da mesma cadeia. Manter status distintos por etapa.
- Design, pesquisa e engenharia compartilham evidências e revisão. Usar um contrato de verificação em vez de um runtime por especialidade.
- Adaptadores e estados de aprovação devem passar por um único Core; perfis, ferramentas e serviços externos entram sob demanda.
