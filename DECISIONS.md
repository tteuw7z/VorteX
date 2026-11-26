# Decisões arquiteturais

1. **Baseline:** preservar o pacote público atual, usar a biblioteca padrão no núcleo e estender contratos gradualmente. CPython 3.15.2 é a versão estável verificada para esta auditoria ([Python.org](https://www.python.org/downloads/release/python-3152/)).
2. **Implementação original:** autorar lógica própria em Python. Gradle/SDK, FFmpeg e motores externos ficam atrás de adaptadores explícitos quando necessários. A configuração de empacotamento e CI continua declarativa.
3. **Licenciamento:** o repositório público registra Apache-2.0. A árvore privada analisada não contém licença geral. Usar sua funcionalidade como especificação e escrever fonte pública original. O upstream do catálogo confirma [MIT no commit referenciado](https://github.com/msitarzewski/agency-agents/blob/8ae6164602c95ca78828b148b9052460ee426885/LICENSE), com aviso de autoria e licença a manter se houver importação autorizada; nesta fase foram publicadas apenas categorias e contagens. Para cada artefato futuro verificar autoria, versão, termos e avisos.
4. **Dependências:** faster-whisper tem [MIT](https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE); dependências transitivas e pesos precisam de análise própria. FFmpeg tem [termos que variam com sua compilação](https://ffmpeg.org/legal.html). Confirmar licenças e disponibilidade do backend/SDK escolhido antes de distribuir binários. O core público não tem dependências de runtime no baseline; setuptools é de build.
5. **Privacidade:** código, conteúdo e histórico privados, dados pessoais, credenciais, gravações, APKs, referências de trabalho e ativos sem autorização permanecem fora do Git público. A publicação contém apenas sínteses de capacidades, números de cobertura, decisões e resultados sanitizados.
6. **Execução verificável:** planejamento, simulação, bloqueio e execução têm estados distintos. Preservar papéis apenas indicativos até um adaptador real produzir evidência. Testes com doubles provam contrato, não integração externa.

## Fase 2

7. **Um registro de capacidades.** O planner e as opções de configuração usam o mesmo catálogo. Os 12 perfis genéricos foram escritos para o VorteX em linguagem própria. Os prompts referenciados pelo catálogo privado permanecem de fora.
8. **Execução estruturada.** DAG sequencial determinística, com dependências e aprovação explícita por estágio. O host registra adaptadores e escolhe se a etapa tolera tentativa alternativa após chamada. O despacho legado preserva seu contrato anterior.
9. **Dados locais.** A compactação só reduz texto que o chamador colocou nas observações. A restauração depende da visão em memória. O SQLite só persiste técnicas por instrução explícita. A deduplicação é lexical por capacidade, com evidência preservada por fonte. O tokenizador real e a validação externa das fontes ficam para fases posteriores.
10. **Empacotamento.** A lógica da Fase 2 usa apenas a biblioteca padrão. Setuptools permanece dependência de build e a versão do pacote segue em 0.1.0 até a etapa de release.

## Fase 3

11. **SDK e Gradle.** A lógica do compilador é Python e chama o SDK instalado. A fixture de SDK é de recursos e usa chave temporária. O adaptador Gradle compila uma cópia de projeto autocontido. A assinatura do projeto governa o build release. Variáveis adicionais exigem o nome explícito e os valores não entram no relatório.
12. **ASR desacoplado.** Um processo local `whisper-cli` lê WAV produzido por FFmpeg e retorna tempos. O backend v1.8.3 e o modelo tiny foram verificados na integração. Os grafemas usam a biblioteca padrão do CPython 3.15, com timing estimado. As versões e pesos são externos ao pacote. [Whisper.cpp](https://github.com/ggml-org/whisper.cpp) · [Modelos](https://huggingface.co/ggerganov/whisper.cpp)
13. **Entradas locais e evidência.** ZIP, mídia, pesquisa e engenharia operam em arquivos locais explícitos. Arquivos são dados. Conteúdo de projeto só é executado quando o operador seleciona a compilação Gradle de um projeto confiável. O workflow genérico aceita somente operações locais permitidas e não executa comandos de shell.
14. **Reconstrução original.** A sequência Study → Build → Check valida evidências, compilação estática e contrato do candidato. Material complementar pode esclarecer lacunas da fonte primária. `READY_FOR_RUNTIME_TEST` preserva a necessidade de testar comportamento.
15. **Licenças e verificações.** Nenhum código ou binário de Android SDK, Gradle, FFmpeg, Whisper ou modelos é incorporado ao pacote. A disponibilidade continua dependente do ambiente. O preview aplica os limiares de contraste aos pares declarados. [Android SDK](https://developer.android.com/tools/apksigner) · [FFmpeg](https://ffmpeg.org/legal.html) · [WCAG 2.2](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)

## Fase 4

16. A CLI e a automação interpretam o estado de cada relatório pela mesma função. O Core exige evidência para transportar artefatos, inclusive em resultados bloqueados. Somente sucesso libera dependentes. O relatório de domínio conserva estados como PARTIAL e REVIEW_REQUIRED.
17. O catálogo de skills identifica ZIP e reutiliza o perfil de engenharia. O manifesto admite verificação de APK, mídia em lote e transcrição por adaptadores locais. O build Gradle continua com entrada direta e projeto confiável.
18. A origem da faixa primária vem dos metadados do mesmo arquivo para render, ASR e quadros. O cálculo de SHA-256 de arquivos é único. ZIP exige publicação atômica exclusiva; Android primeiro verifica assinaturas e produz relatório; mídia publica conjuntos de derivados. Essas garantias específicas orientam cada rotina.

## Fase 5

19. Com orçamento insuficiente para todos os papéis, o planejador prioriza um responsável por capacidade selecionada. Quando todos cabem, preserva a ordem anterior.
20. Cada resultado de etapa pode registrar tentativas anteriores com evidências e artefatos. Dependentes recebem somente os artefatos do resultado final bem-sucedido. O chamador precisa declarar explicitamente uma alternativa e indicar se a repetição é segura.
21. O lote prepara todas as saídas em diretório temporário no mesmo sistema de arquivos. Reutiliza a publicação exclusiva do ZIP depois de fechar o manifesto. Saídas parciais são publicadas quando o manifesto consegue identificar os vídeos com falha.
22. Os adaptadores de assistente traduzem chamadas de planejamento em memória. Transporte, credenciais e contagem de tokens ficam com o host. [OpenAI Responses](https://developers.openai.com/api/docs/guides/function-calling) · [Anthropic Messages](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)

## Fase 4.1

23. O grafo mantém cópias imutáveis das dependências e alternativas. Resultados inválidos entram no histórico ao usar uma alternativa marcada como segura. A automação exige objeto ou lista JSON.
24. O limite dos adaptadores é definido em caracteres da tarefa. O envelope Responses admite a expansão dos escapes JSON. A CLI usa escapes JSON para tornar previsível a saída em codificações legadas.
25. O OCR é ativado por idioma e lê somente quadros amostrados. Usa Tesseract e dados já instalados no host. O relatório separa texto visível de reconhecimento de fala. O modelo Whisper conserva sinalização de revisão e não trata o marcador [BLANK_AUDIO] como fala.
26. MacOS e Windows executam regressões de Core, ZIP, CLI, DAG e envelopes. No Windows, a fixture de ZIP grava o nome literal para testar a mesma entrada do Linux. O motor Android continua dependente de SDK e host compatíveis.
27. A verificação ARM64 confirma cabeçalho ELF e assinatura do pacote. O aceite da execução nativa requer um aparelho ou emulador ARM64 e uma aplicação de teste que invoque a biblioteca. Tesseract, SDK, compiladores, Whisper e pesos permanecem externos ao pacote. [Tesseract](https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE) · [Android ABIs](https://developer.android.com/ndk/guides/abis)

## Fase 6 — expansão inicial

Usar descritores próprios, genéricos e compactos em vez de copiar fichas privadas. Distinguir cobertura de planejamento de execução real. Rejeitar chaves duplicadas em JSON recebido pelo planejador e aplicar validação explícita de limites antes de planejar.

## Fase 6.2 — cache restrito

Cache não persistente, desabilitado por padrão; apenas adaptadores puros sem contexto podem optar. Cada estágio continua sujeito a aprovação e dependências. Apenas sucesso validado em JSON entra no cache, com cópias independentes e limite de 128 entradas por execução. Não reutilizar resultados de operações externas ou arquivos mutáveis. `cache_hit` identifica reutilização.
