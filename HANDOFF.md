# Handoff da Operação VORTEX

Fase 1 concluída em 26/11/2026. Ao receber **Continuar**, retome na Fase 2 (Sol 6.2 High). Leia PROGRESS, PARITY, DECISIONS, TASKS e TEST_REPORT. Confira o HEAD atual e preserve mudanças concorrentes. O código publicamente disponível já oferece planejamento e inspeção de ZIP. Preserve as interfaces públicas existentes ou documente migração deliberada.

Ordem sugerida: configuração tipada e contratos de resultado → Core com DAG e verificação → seleção de agentes e skills por capacidade → contexto seletivo e reversível → aprendizado com proveniência e persistência local explícita → CLI/testes e atualização dos sete arquivos de continuidade. Valide cada incremento no Python 3.15.2. Use contratos pequenos, implementação original e fixtures sintéticas.

Ao integrar, exija prova para execução real. Mantenha seleção e execução como operações distintas. Permissões de ferramentas e efeitos externos devem passar pelo adaptador. O seletor de perfis é catálogo consultável e seus perfis devem ser inéditos ou ter origem e licença verificadas. Execute os testes antes do próximo handoff e registre bloqueios em vez de declará-los resolvidos.

Limites já verificados: o resolvedor de wheels em Linux CPython 3.15.2 não resolveu faster-whisper. Preserve o core sem dependências opcionais e trate ASR como adaptador até verificar uma alternativa. Gradle/apksigner ausentes no ambiente auditado. O compilador Android de referência espera projeto Gradle externo e gera debug. Um APK de release ARM64 exige critérios próprios e chaves fornecidas em ambiente autorizado.
