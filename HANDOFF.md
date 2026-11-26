# Handoff da Operação VORTEX

Fase 2 concluída em 26/11/2026. Ao receber **Continuar**, retome na Fase 3 (Sol 6.2 Max). Leia PROGRESS, PARITY, DECISIONS, TASKS e TEST_REPORT. Confira o HEAD atual e preserve alterações concorrentes. Use os resultados da Fase 1 sem refazer o inventário.

## Interfaces entregues

- `vortex.core.Engine` mantém `register` e `run` e acrescenta `run_workflow` para `Workflow` e `Stage`. Callbacks podem receber artefatos de dependência com `with_context=True`. O contrato de sucesso do workflow exige evidência e dados JSON.
- `SkillEngine` filtra o catálogo antes do ranking. `AgentEngine` seleciona papéis distintos e carrega perfis originais sob demanda. `knowledge` pode carregar aprendizagem somente das capacidades selecionadas.
- `ContextEngine` preserva o checkpoint e devolve uma visão reduzida reversível em memória. `LearningEngine` persiste explicitamente técnicas e proveniência via SQLite.
- `--config` é TOML explícito. `plan`, `inventory` e a versão 0.1.0 mantêm a interface anterior.

## Ordem sugerida da Fase 3

1. Usar o contrato do Engine com adaptadores técnicos. Estender o inventário ZIP para extração/reempacotamento seguro e testar com fixtures autorizadas.
2. Implementar Android em Python chamando ferramentas reais do SDK/Gradle. Criar fixture pública original, usar outputs isolados, verificar assinatura, ABI e digest. Gradle/apksigner estavam ausentes no ambiente da Fase 1. Separar build debug e assinatura de release.
3. Integrar probe e pipeline audiovisual com dados sintéticos. A tentativa binária de faster-whisper no Linux cp315 falhou na Fase 1. Verificar disponibilidade atual por plataforma ou validar um backend isolado com contrato claro. Testar fala, tempos, áudio e render real.
4. Implementar ferramentas de editor, design, pesquisa, engenharia defensiva e automação como adaptadores separados. Aplicar estudo, implementação original e verificação no fluxo Craft Anything/REA. Verificar licença, configuração e autorização de ferramentas externas.
5. Usar CI para casos reproduzíveis. Atualizar a matriz, testes e handoff antes de fechar a fase.

Exigir prova para execução real. Preservar as fronteiras de autorização e os dados privados. Mantêm-se pendentes a execução externa de agentes e a validação de ponta a ponta dos adaptadores técnicos.
