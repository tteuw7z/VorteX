# Changelog


## 2026-11-26 — Operação VORTEX, Fase 4.1

- A DAG preserva as dependências validadas e registra a tentativa inválida antes de usar um fallback autorizado. Retornos técnicos sem relatório falham.
- A CLI mantém JSON legível por máquinas em terminais com codificação legada. Responses e Messages aceitam tarefas Unicode com o mesmo limite de caracteres.
- A inspeção de mídia lê texto visível em quadros amostrados via Tesseract opcional. Lotes ZIP inspecionam a árvore extraída. O reconhecimento diferencia o marcador de áudio vazio da fala transcrita.
- A verificação de APK valida a classe, máquina e tipo de objeto ELF. O CI executa regressões do núcleo, ZIP e portabilidade em macOS e Windows.

## 2026-11-26 — Operação VORTEX, Fase 5

- Roteamento composto português/inglês e melhor distribuição de especialistas com orçamento limitado.
- Histórico de tentativas no Core, validação de aprovações e bloqueio de estados desconhecidos.
- Publicação atômica do lote, contratos de planejamento para dois hosts e medição de latência no CI.

## 2026-11-26 — Operação VORTEX, Fase 4

- CLI e automação compartilham a classificação dos resultados. Relatórios parciais ou bloqueados conservam evidência para revisão.
- A seleção de capacidades reconhece ZIP. O manifesto aceita verificação de APK, lote de vídeos e transcrição local.
- A amostragem de quadros usa a origem da faixa primária que orienta o editor e a transcrição. Android e mídia compartilham o cálculo do digest de arquivo.

## 2026-11-26 — Operação VORTEX, Fase 3

- Compilador APK e verificação de assinatura e arquitetura com Android SDK e Gradle.
- Extração e reempacotamento ZIP, lote de mídia, QA por quadro, ASR local e editor.
- Auditoria de design, pesquisa por evidência, engenharia estática, reconstrução e automação.
- CI com fixture Android sintética, relatórios, matriz e handoff.

## 2026-11-26 — Operação VORTEX, Fase 2

- Núcleo de workflows validados, contratos de resultados, aprovações e evidência.
- Seleção de skills e papéis, perfis originais, contexto reversível, aprendizagem local e configuração TOML.
- Mantidos CLI e inventário compatíveis. Acrescentados `knowledge`, `context` e `learn`.

## 2026-11-26 — Operação VORTEX, Fase 1

- Inventário e matriz de equivalência dos snapshots privado e público.
- Decisões de licença, Python e dependências, evidências e handoff.
- Mantida a versão do pacote 0.1.0. Esta etapa acrescenta os registros da auditoria.

## Fase 6.1 — candidato em desenvolvimento

- Dez novas capacidades de planejamento e dez perfis originais, com roteamento PT/EN.
- Validação de entradas duplicadas e limites nos contratos de planejamento.
- Testes de seleção, restrições de configuração e ausência de execução implícita.
- CI pendente; sem alteração na versão pública.
