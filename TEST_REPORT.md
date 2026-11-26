# Testes e evidências

## Fase 4.1

CPython 3.15.2 em Linux x86-64, com pacote instalado. **72 de 72 testes locais passaram** em 40,140 s. Foram habilitados FFmpeg 7.1.5, Tesseract 5.5.0, SDK Android 35, Build Tools 35.0.0, Gradle 8.9 e whisper.cpp 1.8.3. O [CI do commit técnico c910c32](https://github.com/tteuw7z/VorteX/actions/runs/45825375788) aprovou Linux, a fixture Android separada e as suítes de portabilidade em macOS e Windows. Na suíte Linux do runner passaram 69 testes, com 3 integrações opt-in cobertas localmente.

| Ensaio | Resultado observado |
| --- | --- |
| Revisão independente de Core/CLI | Foram reproduzidas quatro falhas no baseline. Regressões passam para alteração da lista externa de dependências, relatório escalar inválido, tarefa com 6.006 caracteres com emoji nas duas APIs locais e inventário JSON com stdout cp1252. |
| Fallback e roteamento | Relatório sem evidência entra no histórico e uma alternativa autorizada pode concluir a etapa. Oito casos PT/EN verificam seleção e limite de papéis. |
| GitHub Actions em três sistemas | O primeiro CI achou que o escritor de fixtures convertia a barra invertida no Windows. A fixture foi corrigida para gravar o nome literal. No CI técnico final os cinco módulos portáveis passaram nos dois runners adicionais. |
| Lote ZIP com OCR, ASR e render | Um MP4 íntegro com nome Unicode, fala sintética PT e texto visível, mais um arquivo corrompido. Lote devolveu código 1 e PARTIAL com 1 de 2 completos. Tesseract leu VORTEX TEST com timecodes. O JSON da transcrição gerou render H.264/AAC 1920×1080 com 180 quadros, 43 intervalos de legenda e cadência 60 fps confirmada por QA. SHA-256 do render: f080031441357289fcd22131d08d401f0287e420a5a9da17bb02243cbc57a7b8. |
| Áudio vazio | Whisper retornou [BLANK_AUDIO] para vídeo sintético com faixa silenciosa. Após a correção, o mesmo arquivo gerou speech_recognized=false e zero segmentos de fala. |
| Android ARM64 por SDK | Zig 0.17.1 compilou uma função original mínima em ELF64 AArch64 ET_DYN. AAPT2, zipalign e apksigner empacotaram, alinharam e assinaram com chave descartável. O VorteX confirmou ABI e esquemas v1/v2/v3. SHA-256: 511f0ffce319de34b115fc84a4325c8088ac629ba9b79450be74ee797cb99aea. |
| Android ARM64 por Gradle | AGP 8.7.3, Gradle 8.9 e Java 21. APKs debug e release com a biblioteca AArch64 passaram no verificador e registraram v1/v2. A primeira tentativa release offline terminou com saída 1. A repetição com repositórios habilitados passou. SHA-256 debug: 2427b05bdc07cd81e4cac2020f2d30b798aa41e0ea551e97f7a7058b64e9e5c3. Release: 5cccce1ab09c68066da94073ecb3eebf7842cc7e9e1e6ebd1d13569a77d7bafc. Foi usada assinatura de teste. |
| Latência do planejador | 12,72 µs por tarefa tanto em f0daf28 quanto na revisão, em sete séries alternadas de 7.000 pares PT/EN por versão na mesma máquina. O CI técnico mediu 16,66 µs por tarefa no seu runner. Sem telemetria de tokens dos provedores. |

### Reconhecimento multilíngue real com áudio de teste

EN foi exercitado na suíte com fala sintética via flite, inferência local e render. PT e FR foram sintetizados com eSpeak NG e processados por whisper.cpp em MP4. As contagens são edições de palavras após normalizar caixa e pontuação, divididas pelo total de palavras da referência. O resultado pode ultrapassar 100% quando há inserções.

| Modelo e configuração | PT, idioma reportado e erros | FR, idioma reportado e erros |
| --- | --- | --- |
| base, automático | la · 21/16 | ms · 14/14 |
| base, explícito | pt · 7/16 | fr · 15/14 |
| small, automático | es · 10/16 | ro · 13/14 |
| small, explícito | pt · 0/16 | fr · 5/14 |

Pesos base SHA-256 60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe. Pesos small SHA-256 1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b. A amostra PT com idioma explícito ainda recebeu sinalização de baixa confiança em dois trechos. A precisão geral, detecção automática e tempo acústico por grafema continuam sem aceite.

Nenhuma chamada autenticada foi realizada aos provedores de IA. Testes em aparelho e outros binários nativos fora de Linux permanecem pendentes. O relatório registra apenas fixtures originais, dados sintéticos e hashes públicos dos insumos de teste.

## Fase 5

[CI da implementação final](https://github.com/tteuw7z/VorteX/actions/runs/45819556837), CPython 3.15.2. A suíte executou em 1,845 s. Dos 63 testes descobertos, 60 passaram e 3 foram pulados (integrações locais opcionais de SDK, Gradle e ASR). O job Android separado compilou, assinou e verificou a fixture. A validação desta fase ocorreu no runner GitHub Actions.

| Ensaio | Evidência |
| --- | --- |
| ZIP + legendagem, PT e EN | Planejamento em processo Python e CLI em subprocesso entregou o mesmo JSON normalizado. Com limite 2, ambos selecionaram mídia e engenharia de arquivos. |
| Alternativa e colaboração | Falha inicial com artefato parcial, segunda tentativa com sucesso e etapa dependente executada. Histórico contém a evidência inicial. O dependente recebeu apenas o resultado final. |
| Aprovação e revisão defensiva | String usada como coleção de aprovações rejeitada, aprovação booleana inválida bloqueada, política de repetição inválida rejeitada e status desconhecido bloqueado. |
| Interrupção de lote | Injeção de KeyboardInterrupt antes da conclusão. Destino final ficou disponível para nova execução no mesmo caminho, que publicou manifesto com falha de mídia prevista. |
| Contratos de assistente | Fixtures Responses e Messages passaram pelo tradutor Python com identificador correlacionado e plano idêntico. Nome de ferramenta e campos inesperados foram rejeitados. Testes locais de protocolo; chamadas autenticadas permanecem pendentes. |
| Latência | Mediana de 15,19 µs por tarefa no runner, 5 séries de 1.000 pares PT/EN. O teste mede o planejamento em processo. As condições do runner variam; não há comparação controlada com o baseline nem métrica faturada de tokens. |

## Fase 4

CPython 3.15.2 em Linux. A suíte local descobriu 57 testes; 54 passaram e três integrações opt-in foram puladas (SDK, Gradle e reconhecimento com modelo local). Compilação de módulos e verificação de espaços no diff passaram. A fixture de APK é executada em job separado no [CI do commit técnico](https://github.com/tteuw7z/VorteX/actions/runs/45817987722).

| Ensaio | Resultado |
| --- | --- |
| Relatório de inspeção com erro sintático | CLI retorna 1 e REVIEW_REQUIRED. A DAG conserva o relatório com hash, bloqueia a etapa dependente e registra zero tentativas nela. |
| ZIP → lote → etapa dependente, com FFmpeg e FFprobe | Um MP4 válido e um arquivo corrompido. Lote PARTIAL, 1 de 2 completo. O resultado incluiu o caminho do manifesto e a evidência por vídeo. CLI retornou 1 e o dependente ficou bloqueado. |
| Linha do tempo | MP4 sintético com início em 5 s. A amostragem devolveu 0 e 0,5 s relativos e o mesmo digest da inspeção. O teste de render com legenda também passou. |
| Seleção e dependências | ZIP resolveu um perfil existente. Plano validou verificação Android, ZIP, lote e transcrição sem chamar os binários. Inspeção AST de 28 módulos encontrou apenas imports locais ou da biblioteca padrão. Manifesto declara zero dependências Python de execução. |

Os testes de Gradle e ASR reais desta operação estão registrados na Fase 3. Esta fase não mediu portabilidade entre assistentes, fidelidade multilíngue nem cobertura de conteúdo semântico.

## Fase 3

As verificações locais usaram CPython 3.15.2 em Linux x86-64. O pacote foi instalado a partir do código público. A suíte passou **54/54**, sem skips, com SDK Android, Gradle, FFmpeg e ASR habilitados. O pacote continua sem dependências Python de execução.

| Verificação | Resultado observado |
| --- | --- |
| ZIP e lote | O CLI extraiu e processou 17 clipes sintéticos H.264. Foram gerados 17 manifests de quadros. Um teste separado detectou um clipe inválido e preservou os resultados dos outros dois. A substituição de um membro preservou os outros 16, o CRC final e o hash da fonte. |
| Editor e QA | Um MP4 1920×1080 H.264/AAC teve 60 quadros em 1 s. O QA confirmou 60 fps e cadência por timestamps. Outro render passou por dois cortes. Teste de pixels confirmou a entrada da legenda no quadro 12, após a ausência no quadro 11. |
| ASR local | Whisper.cpp v1.8.3 e modelo tiny local reconheceram fala sintética em inglês. O teste confirmou a frase esperada, tempos de palavras e export TXT/JSON/SRT/ASS. O render usou o JSON exportado. Foram assinalados trechos de incerteza. Tempo acústico por grafema é estimado. |
| Android SDK | Plataforma 35 e Build Tools 35.0.0 produziram APK de recursos. `apksigner verify` validou v1, v2 e v3. |
| Android Gradle | Gradle 8.9, AGP 8.7.3 e Java 21 produziram APKs debug e release a partir de projeto sintético. O release usou uma chave descartável fornecida ao projeto. Os dois foram reinspecionados e passaram em `apksigner verify` com v1 e v2. A cópia de build preservou o checkout de entrada. |
| Design | Prévia de tokens renderizada no Chromium nas larguras 360, 768 e 1440 px. As amostras de contraste estavam visíveis, sem rolagem horizontal. O escopo cobre os pares declarados, não uma auditoria de acessibilidade de aplicações. |
| Pesquisa e engenharia | Testes com fontes e código originais verificaram citações exatas, hashes, lacunas, compilação estática, símbolos e distinção entre evidência primária e complementar. |
| Automação | Um manifesto real executou extração de ZIP e descoberta de candidatos com confirmação por etapa. O modo de plano e a ausência de aprovação mantiveram o destino intacto. Argumentos inválidos e operações fora do catálogo foram bloqueados antes de qualquer etapa. |

### SHA-256 dos artefatos sintéticos locais

| Arquivo | SHA-256 |
| --- | --- |
| APK de recursos SDK | `f80902762097b5279757829ccffa061a81f8ed13bc5af6ac93a757b2ecaec9ab` |
| Gradle debug | `9c8ee2aa1c351416bf93abf635724fd394476c6ece60350a58b11f62203671e1` |
| Gradle release | `766726a7b48320c492e50ab68bbc96582d695d852dbc7a8bab0ad46b4662bf72` |
| MP4 Full HD 60 CFR | `9aa011770dff0eba05726abcdc16f50418f86c5b7f5ae24db8dbd0226601e891` |

Os hashes identificam amostras verificadas nesta execução. A assinatura usa chaves de teste, e os APKs não contêm bibliotecas ARM64. Esta etapa não inclui execução em aparelho.

### Reproduzir

Com o pacote instalado, rode `python -m unittest discover -s tests -v`. Os testes de mídia precisam de FFmpeg e FFprobe no PATH. Para ativar os três testes opcionais de integração, configure `VORTEX_TEST_ANDROID_SDK` com a raiz do SDK (plataforma 35, Build Tools 35.0.0 e keytool disponível), `VORTEX_TEST_GRADLE=1` com Gradle 8.9 no PATH e `VORTEX_WHISPER_MODEL` com o arquivo local do modelo tiny e `whisper-cli` no PATH. O teste de Gradle cria o próprio projeto e requer acesso às dependências do AGP ou cache preparado. A amostra de ASR usa um FFmpeg com filtro flite.

### GitHub Actions

A [primeira execução](https://github.com/tteuw7z/VorteX/actions/runs/45775628134) passou nos testes Python. O job Android falhou na preparação porque o runner não tinha `sdkmanager`. O workflow passou a provisionar os dois pacotes fixados do SDK a partir da origem oficial e verificar seus hashes antes de executar os binários. Veja [execuções do CI](https://github.com/tteuw7z/VorteX/actions/workflows/ci.yml).

A [execução corrigida](https://github.com/tteuw7z/VorteX/actions/runs/45775863338) passou nas duas tarefas. A suíte do runner teve 51 casos aprovados e 3 opcionais omitidos. Os 54 foram executados localmente. O job Android compilou, assinou e verificou uma nova amostra. [APK sintético e relatório](https://github.com/tteuw7z/VorteX/actions/runs/45775863338/artifacts/15095504078). O SHA-256 do ZIP do CI é `318e0722dd8297911ed306fad23d92c6bee4dec72f976f524d602f2e7b4545f0`.

## Histórico

## Fase 2

Execução no Linux x86_64 com CPython 3.15.2, em ambiente virtual novo. O pacote foi construído e instalado a partir do código público, sem dependências de runtime.

| Verificação | Resultado observado |
| --- | --- |
| `python -m unittest discover -s tests -v` | 15/15 testes passaram, incluindo os quatro da base. |
| Core e integração local | DAG, ciclo, dependência ausente, aprovação, simulação, fallback condicionado, evidência obrigatória, proteção contra mutação dos artefatos e validação de JSON. Um workflow leu o inventário de um ZIP real de teste em uma etapa e verificou seu SHA-256 na seguinte. |
| Agentes, skills e CLI | Filtragem e deduplicação de papéis, perfis selecionados, configuração inválida rejeitada, CLI instalado com versão 0.1.0 e conhecimento restrito à seleção. |
| Contexto e aprendizagem | Restauração exata das observações, deduplicação em memória, SQLite reaberto com registros e proveniência, deduplicação com acentos/espaços e remoção de registro. |
| Sintaxe e revisão | `python -m compileall -q src tests` e `git diff --cached --check` passaram. |

O teste com ZIP mede operações de leitura e digest, a partir de uma fixture sintética. APK, render, ASR em CPython 3.15.2 e conexões externas seguem para a Fase 3.

## Fase 1

| Verificação | Resultado observado |
| --- | --- |
| Inventário Git | Árvores recursivas completas. Conteúdo recuperado e verificado byte a byte pelo hash de objeto Git, 361/361 na referência e 12/12 no baseline público. |
| VorkX de referência, CPython 3.15.2 | 50/50 testes unitários passaram. Incluem seleção de perfis, roteamento, colaboração, contexto, transcrição com modelo simulado e QA. |
| VorteX público, CPython 3.15.2 | Pacote construído e instalado em ambiente isolado. 4/4 testes passaram. CLI 0.1.0 respondeu a `plan "compile APK Android"` com `PLAN_ONLY`. |
| GitHub Actions público | [Execução verde no commit-base](https://github.com/tteuw7z/VorteX/actions/runs/45718345975). |
| Probe audiovisual real da referência | FFmpeg local gerou fixture sintética H.264/AAC 1080×1920. O QA leu áudio e FPS médio 60 e retornou `WARN / METADATA_ONLY`, pois FPS médio não prova CFR. |
| APK | A ajuda do CLI abriu. Gradle e apksigner ausentes nesta sessão. APK real não foi compilado. |
| ASR opcional em CPython 3.15.2 Linux x86_64 | Resolução somente com wheels falhou para faster-whisper devido à disponibilidade de dependências nativas com ABI cp315, em especial onnxruntime; versões antigas também atingiram lacuna de CTranslate2. Compilação de dependências a partir de fonte e alternativas não foram testadas nesta fase. |
| Privacidade | Comparação do pacote publicado com a árvore pública de base: somente os sete arquivos de continuidade novos, sem dados de commit, trechos de código ou ativos da fonte privada. |

Reprodução pública: em ambiente Python 3.15.2, instale o pacote local, rode `python -m unittest discover -s tests -v` e execute `vortex --version` e `vortex plan "compile APK Android"`. Os testes do projeto de referência rodam apenas em checkout autorizado. Esta fase não estabelece equivalência integral nem desempenho medido.

## Fase 6.1 — testes adicionados (a executar)

Casos bilíngues para dez novas capacidades, integridade de perfis, limite de agentes, configuração restrita e ausência de adaptador de execução; argumentos duplicados, limites inválidos e tarefas vazias nos contratos de host. Nenhum resultado do candidato é declarado aprovado antes de CI.

CI 45868049061, commit 06cb01b: 77 testes descobertos, 73 aprovados, 1 erro no caso PT `Experiência imersiva`, 3 ignorados. macOS, Windows e fixture Android aprovados. Corrigida a ausência do alias feminino; novos testes incluídos também no CI portátil. Revalidação pendente.

## Fase 6.2 — testes adicionados (a executar)

Testes de contagem real de chamadas, isolamento de artefatos, aprovação de cada estágio, reinicialização de cache por workflow, não reutilização de falhas e validação de opt-in. Não implica medição de tokens faturados.

## Validação Fase 6.2

CI 45868236196, a622fb4: 80 testes descobertos, 77 aprovados, 3 ignorados; todos os quatro jobs aprovados. Mediana do planejamento 30,27 µs/tarefa no job Linux. Fase 6.3 adiciona regressão de equivalência de pontuação e comparação pareada no mesmo runner; resultado pendente.

## Fase 6.4 — testes adicionados (a executar)

Ciclos locais de ferramenta nos dois protocolos, preservação de IDs e itens, uso por resposta, aprovação, credencial, limites, falhas, endpoints fixos e rejeição de redirects/JSON duplicado. Respostas injetadas e HTTPS mockado não comprovam transporte autenticado ao vivo.

## Validação Fase 6.4

CI 45868607929, 612afce: 89 testes descobertos, 86 aprovados, 3 ignorados; quatro jobs aprovados. Benchmark pareado: 14,6327 → 10,8773 µs/tarefa, planos comuns iguais. Oito testes de transporte/protocolo passaram, sem chamadas autenticadas.

## Fase 6.5 — testes adicionados

Render sintético a 60 fps com efeitos e áudio, comparação de pixels em quadros ativos/inativos, cadência, limites e rejeição de intervalos inválidos. Nenhum resultado do candidato declarado aprovado antes de CI.

## Validação Fase 6.5

CI 45868881805, 434bc0b: 93 testes descobertos, 90 aprovados, 3 ignorados; quatro jobs aprovados. Render a 60 fps, comparação de pixels em quadros ativos/inativos, limites e integridade de mídia passaram. Fase 6.6 acrescenta transientes de graves e flash automático; CI pendente.

## Validação Fase 6.6

CI 45869077696, 0da86f8: 95 testes descobertos, 92 aprovados, 3 ignorados; quatro jobs aprovados. Dois transientes sintéticos de 80 Hz detectados, dois flashes renderizados, remapeamento de cortes e cadência aprovados. Benchmark pareado: 15,5032 → 11,3740 µs/tarefa; planos comuns iguais. Nenhuma medição de tokens faturados ou corpus musical real.

## Revisão de segurança Fase 6.7

Snapshot 0da86f8: 57/57 arquivos rastreados de texto examinados para formatos comuns de chaves de OpenAI/Anthropic, GitHub, Google, AWS, Slack e chaves privadas PEM; 0 correspondências, 0 erros de leitura. Não equivale a auditoria de histórico, análise semântica de dados pessoais ou revisão de dependências externas. SHAs das quatro Actions extraídos dos logs do CI aprovado; revalidação após pinning pendente.

## Fase 6.8 — testes adicionados

Casos de bloqueio sem atestado, assinatura errada, evidência faltante, expiração, alteração de bytes, tipo incorreto, credenciais sem reprodução, symlink/Git, artefato não analisado, publicação exata e sem sobrescrita; Gradle sem aprovação, permissões POSIX e colisão de aprovação/JSON. CI pendente; sem garantia de segurança integral.

CI 45882300851 (3f3e9e9): 105 testes descobertos, 102 aprovados, 3 ignorados, quatro jobs aprovados. Fase 6.9 adiciona testes de troca do manifesto, não herança de credenciais, URL de script, nome contendo credencial e caminhos reservados; novo CI pendente.

Fase 6.10 adiciona teste de logs ausentes/adulterados, não inclusão de evidências na entrega e falha de rename sem diretório final. CI pendente; testes usam registros e chave sintéticos, não auditoria externa real.

CI 45882508405 (bb98add): 109 testes encontrados, 106 aprovados, 3 ignorados, quatro jobs aprovados. Fase 6.11 testa criação privada, não sobrescrita, publicação de mídia e extração ZIP sob umask permissivo. CI pendente.

## Recuperação 6.11 / candidato 6.12

CI 45882770153, 2aaecf2: 113 testes descobertos, 110 aprovados, 3 ignorados; quatro jobs aprovados. Novos testes de histórico com credencial sintética removida em commit posterior, clone shallow e bloqueio de credenciais em entrada/resposta remota aguardam CI. Nenhum resultado do scanner de histórico real declarado antes de execução.
