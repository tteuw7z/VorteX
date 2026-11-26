# Handoff da Operação VORTEX

Fase 4 concluída em 26/11/2026. Ao receber **Continuar**, retome a Fase 5 com Astra 6.2 High. Leia PROGRESS, PARITY, TEST_REPORT, DECISIONS, TASKS e CHANGELOG no HEAD atual. A implementação desta revisão está no commit 3d749ef75741ed6aae03f69eab67135b319513ab.

## Contratos a preservar

- A tarefa passa pelo catálogo de skills, pela seleção limitada de perfis e pelo carregamento seletivo de contexto. A aprendizagem continua local e explícita. A CLI e o manifesto usam os mesmos parsers técnicos.
- A CLI retorna 1 em falha, bloqueio ou revisão de resultado técnico. A DAG mantém relatório e evidência inclusive para um lote parcial. Dependentes exigem sucesso. A simulação continua sem efeitos.
- Os relatórios de quadros indicam a origem da faixa primária e seu instante no arquivo. Editor, ASR e amostragem compartilham essa referência. O reconhecimento continua opcional via modelo local.
- A publicação de arquivos mantém garantias próprias de cada motor. Android, ASR e FFmpeg dependem do host. Pesquisa verifica excertos, engenharia verifica contratos estáticos, e design verifica os pares de contraste declarados.

## Aceite da Fase 5

1. Avaliar o roteamento com tarefas compostas em português e inglês, limites de agentes e perfis selecionados. Testar duas integrações de host disponíveis e registrar exatamente quais foram executadas.
2. Exercitar falha recuperável, fallback autorizado e passagem de artefatos entre agentes. Verificar perda de evidência em múltiplas tentativas e comportamento diante de estados novos. Medir custo e latência em conjuntos reproduzíveis; contar tokens apenas com métrica real.
3. Revisar interrupção e recuperação de lotes, acesso a caminhos e exposição de evidências. Rodar integração e regressão em CPython 3.15.2.
4. Preservar na matriz as lacunas de ASR multilíngue, descrição visual, mídia avançada, Android nativo/em aparelho e serviços autenticados. A Fase 6 exige aceite e evidência próprios para cada capacidade.
