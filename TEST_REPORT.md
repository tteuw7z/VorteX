# Testes e evidências

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
