# Testes e evidências

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
