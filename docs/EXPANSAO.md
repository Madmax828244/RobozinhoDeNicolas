# Plano de expansão

## Situação atual (medida, não estimada)

Execute `python3 -m nicolas commands` para ver os números do seu bot. Nesta versão:

| Tipo | Quantidade |
|---|---|
| Comandos reais (cada um com função própria) | 155 |
| Aliases simples | 96 |
| Atalhos de conversão de unidades gerados por tabela (`.km-mi`, `.c-f`...) | 220 |
| **Nomes invocáveis no total** | **471** |

A meta de **10.000 comandos úteis ainda não foi atingida**, e o projeto não afirma isso em nenhum lugar.

## Princípios

1. **Utilidade antes de volume.** Só entra comando que faz algo diferente. Trocar o nome da mesma função não conta.
2. **Todo comando novo precisa de teste.** O teste `test_every_command_executes_without_internal_error` executa cada comando
   registrado; o registro rejeita nomes duplicados e exemplos que não resolvem.
3. **Dados em tabelas, lógica em um lugar.** Como as conversões de unidades: uma função + uma tabela geram centenas de atalhos.

## Etapas

| Etapa | Entrega | Ordem de grandeza |
|---|---|---|
| 1. Conteúdo em pacotes de dados | Carregar quiz, charadas, piadas, frases e curiosidades de `data/packs/*.json` (hoje ficam em `nicolas/data.py`). Milhares de itens sem mexer em código. | conteúdo, não comandos |
| 2. Mais conversões e tabelas | Moedas fixas de referência (sem cotação ao vivo), culinária (xícara/colher), energia, ângulos, números romanos, bases numéricas. Atalhos `a-b` gerados por tabela. | +300 a 800 atalhos |
| 3. Categorias de jogos | Forca, memória, anagrama, batalha naval em duplas, bingo, "verdade ou desafio", trivia por tema (cada tema vira um comando). | +40 comandos |
| 4. Ferramentas de texto e dev | Regex tester, diff de textos, contador de sílabas, cifras clássicas, gerador de CPF/CNPJ **de teste** (válidos só no formato), cron explainer, calculadora de datas. | +60 comandos |
| 5. Personalização por grupo | Comandos próprios criados por admins (`.addcmd nome resposta`), respostas automáticas, apelidos de comandos (aliases por grupo). | ilimitado por grupo |
| 6. Integrações com chave de API | Notícias, cotações ao vivo, tradução em lote, busca de imagens — sempre opcionais e com aviso de "não configurado". | +30 comandos |
| 7. Sistema de plugins externos | Pasta `plugins_extra/` carregada em tempo de execução, cada plugin independente, com verificação de duplicados na carga. | comunidade |

## Como chegar perto de 10.000 nomes sem enganar

* Comandos de **conteúdo personalizado criados por grupos** (etapa 5) e **atalhos gerados por tabela** (etapa 2) são a
  única forma realista de passar de milhares. Eles são contados **separadamente** de comandos reais em `.info` e `.menu`
  (como já é feito hoje com "aliases" e "atalhos").
* O número de comandos reais crescerá devagar (dezenas por etapa) e cada um continuará coberto por teste.

## Critérios de qualidade para aceitar um comando novo

- [ ] Função própria, descrição curta em português e `example` válido.
- [ ] Valida todos os parâmetros e nunca executa código/expressões arbitrárias recebidas.
- [ ] Respeita permissões (`min_role`) e `group_only` quando necessário.
- [ ] Sem rede, falha com mensagem clara (nada de erro interno).
- [ ] Sem dados privados desnecessários; sem segredos em respostas ou logs.
- [ ] Passa em `python3 -m nicolas test`.
