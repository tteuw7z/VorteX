# Tarefas da Operação VORTEX

## Fase 1 — auditoria concluída

- [x] Fixar snapshots das branches principais e verificar conteúdo por hash Git. 361 arquivos da referência e 12 públicos.
- [x] Inventariar código, perfis, skills, workflows, documentação, testes e distribuição.
- [x] Comparar comportamento observado, previsto e pendente por capacidade.
- [x] Revisar sobreposições, licenças declaradas e material que permanece privado.
- [x] Reexecutar as suítes no CPython 3.15.2, checar pacote público e dependência opcional.
- [x] Registrar matriz, decisões, testes e handoff neste commit.

## Fase 2 — estrutura concluída

- [x] Reaproveitar o CLI, o planejador e o contrato de adaptadores existentes.
- [x] Core Engine: DAG validada, resultados tipados, dependências, aprovações e evidência.
- [x] Skill/Agent Engines: registro de capacidades, perfis autorizados, seleção limitada e carregamento sob demanda.
- [x] Context Engine: estimativas sinalizadas, checkpoints e compactação reversível.
- [x] Learning Engine: registro local opt-in, evidência, deduplicação por capacidade e exclusão de dados.
- [x] Configuração, estratégia de dependências e testes unitários no Python alvo.

## Fase 3 — motores técnicos

- [x] Compilador APK com Android SDK e Gradle, assinatura verificada e evidência por hash.
- [x] Inspeção audiovisual, amostragem por cena e tempo, QA da cadência e editor com cortes, fades e legendas.
- [x] ASR local via `whisper-cli`, saída TXT/JSON/SRT/ASS e render real com fala sintética.
- [x] Inventário, extração segura, substituição e inspeção de 17 vídeos de um ZIP sintético.
- [x] Auditoria de contraste e prévia HTML, pesquisa local com proveniência e engenharia estática.
- [x] Study → Build → Check com evidência complementar separada.
- [x] Automação local por DAG, adaptadores de subprocesso, CLI integrado e GitHub Actions.


## Fase 4.1 — revisão antes da Fase 6

- [x] Conferir o baseline público f0daf28 e revisar as pendências registradas nas fases 4 e 5.
- [x] Corrigir snapshot da DAG, histórico de fallback, resultado inválido, Unicode e cenários bilíngues de roteamento.
- [x] Verificar ZIP, CLI, Core e adaptadores de protocolo em Linux, macOS e Windows.
- [x] Ler texto visível em mídia real sintética. Testar transcrição em EN/PT/FR, render e cadência. Registrar as falhas de detecção e reconhecimento.
- [x] Verificar tamanho, hash, assinatura e arquitetura de APK ARM64 sintético com SDK e Gradle.
- [x] Medir latência sobre as mesmas tarefas na base e no código revisado.

## Próximas etapas

- [x] Fase 4. Revisar arquitetura e dependências, integrar resultados de CLI/DAG e rotas técnicas, unificar origem temporal e reconciliar a matriz.
- [x] Fase 5. Refinar roteamento e fallback, publicar lotes atomicamente, medir latência e testar regressões e contratos locais de dois formatos de assistente.
- [ ] Validar em contas autorizadas os dois ciclos de chamada remota e registrar uso real fornecido pelos serviços.
- [ ] Fase 6. Auditar arquitetura, segurança, privacidade e licenças. Validar builds e mídia finais e preparar release.
- [ ] Registrar separadamente as capacidades ainda parciais, incluindo interpretação semântica de cenas, render de efeitos avançados, provedores externos, testes Android em aparelho e casos de ASR multilingue.

## Fase 6 — checkpoint 6.1

- [x] Confirmar baseline e acesso de leitura à referência privada.
- [x] Implementar dez rotas de planejamento originais e perfis correspondentes, sem publicar arquivos privados.
- [x] Rejeitar argumentos JSON duplicados e validar limites de chamadas de planejamento.
- [ ] Verificar CI do candidato e reconciliar capacidades restantes em detalhe.
- [ ] Implementar e medir lacunas técnicas ainda abertas; manter validações externas separadas.

- [x] Implementar cache opt-in, limitado à execução e a adaptadores puros sem contexto.
- [ ] Validar cache, medir ganho em tarefas equivalentes e auditar demais componentes.

- [x] Validar catálogo e cache em CI (a622fb4).
- [x] Implementar índice invertido e benchmark pareado para tarefas comuns.
- [ ] Validar otimização e registrar medição.

- [x] Implementar transporte HTTPS e ciclo limitado de planejamento com aprovação explícita.
- [ ] Validar contratos e fronteiras HTTPS em CI; executar validação autenticada somente com autorização e credenciais adequadas.

- [x] Validar índice e transporte em CI, sem alegar chamadas autenticadas.
- [x] Implementar flash, shake rotacional, blur e contraste por intervalos explícitos de saída.
- [ ] Validar renderização dos efeitos, detecção de graves e demais lacunas.

- [x] Validar efeitos reais por pixels e cadência em CI.
- [x] Implementar detecção heurística de graves e flash automático por cortes.
- [ ] Validar detecção e render em CI e corpus musical real autorizado.

- [x] Validar transientes sintéticos e flash automático em CI.
- [x] Recontar inventário privado por árvore Git não truncada e examinar padrões de credenciais no snapshot candidato.
- [x] Fixar referências das Actions em commits observados no CI aprovado.
- [ ] Revalidar workflow fixado, auditar histórico e licenças de distribuição e concluir reconciliação granular.

- [x] Implementar política de entrega fail-closed e verificação de atestado associado ao hash dos bytes.
- [x] Exigir aprovação de confiança Gradle, isolar permissões de aprendizagem POSIX e impedir colisões de aprovação/JSON duplicado.
- [ ] Validar CI, integrar verificador independente e obrigar gate nos hosts; concluir auditoria de histórico, dependências e demais superfícies.

- [x] Validar gate e proteções internas em CI 45882300851.
- [x] Vincular aprovações ao digest do manifesto e minimizar ambiente de ferramentas.
- [x] Reforçar caminhos portáveis e scanner HTML.
- [ ] Revalidar 6.9, implantar verificador independente e integrar gate a todos os caminhos de entrega.

- [x] Exigir logs reais vinculados a cada atestado e publicação em staging privado.
- [ ] Validar política v2 em CI e implementar verificador independente/integrações reais.

- [x] Definir permissões privadas em arquivos e diretórios de saída dos módulos principais.
- [ ] Validar CI da revisão de privacidade e configurar ACLs Windows em ambiente real.

- [x] Recuperar checkpoint 6.11 e confirmar CI sem repetir implementação.
- [x] Adicionar scanner de histórico alcançável e bloqueio de credenciais conhecidas em tráfego remoto.
- [ ] Validar 6.12 e revisar evidências de histórico; implantar verificador e gate obrigatório nos hosts.

- [x] Add automatic economical preflight, dedicated code review profile and exact file coverage requirement.
- [ ] Validate CI and integrate independent stage execution and real provider usage comparison.

- [x] Validar 6.13 em CI e implementar expansão automática, contrato AGENTS.md e separação da telemetria.
- [ ] Validar 6.14, medir desempenho e qualidade em tarefas reais equivalentes e integrar execução obrigatória nos hosts.

- [x] Implementar coordenador ordenado para integração de hosts com callbacks confiáveis.
- [ ] Validar CI e integrar adapters reais independentes, isolamento e publicação obrigatória nos hosts.

- [x] Implementar ativação explícita, saudação, menu estruturado e textual, preflight para pedidos diretos e contrato de skill portátil.
- [ ] Validar CI e integrar menus nativos, localização e bindings confiáveis em sessões reais dos hosts.

- [x] Validate phase 6.17 Spector pipeline and policy 4 (CI 45906687959).
- [x] Validate phase 6.18–6.21 trusted checks, repair loop, compatibility and database/API gates (CI 45907237193).
- [ ] Deploy independent reviewer, execution isolation and universal host enforcement; verify live provider token savings, complete source coverage and broader parity.

- [x] Build Motion UI, reusable controls, vector accents, planning profiles and headless browser checks (phase 6.28, CI 45909540313).
- [ ] Verify on physical phone, Safari/Firefox, assistive technology and trusted chat host; independently authorize delivery before production use.
