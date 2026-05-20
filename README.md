# NotificAI

Sistema de apoio à notificação compulsória de violências e agravos à saúde em prontuários eletrônicos, desenvolvido para o **Núcleo de Vigilância Epidemiológica (NUVE)** do Hospital das Clínicas da FMUSP.

> TCC do MBA em Data Science e Analytics — USP/ESALQ
> Rafael Marques Geraldo · 2024

Este repositório contém:

- **Monografia revisada**: `[TCC Revisado] - Rafael Marques Geraldo (1).docx`
- **Código-fonte de referência** — pipeline lexical descrito na metodologia do TCC, refatorado para uso reprodutível fora do Google Colab.

O código institucional completo (integração BERT/Streamlit, léxico fechado de 1.500 termos, painéis com workflow e exportação SINAN) vive em [`rafamarquesg/Projetos/NotificAI_Sistema`](https://github.com/rafamarquesg/Projetos/tree/main/NotificAI_Sistema). Este repositório mantém a versão limpa, modular e auditável que acompanha o TCC.

---

## Resultados publicados (TCC)

| Métrica | Valor |
|---|---|
| Sensibilidade explícita | 84,9% (IC 95% 78,4–89,8%, Wilson score) |
| Sensibilidade expandida (com score contextual) | 100% |
| Precisão entre detectados (validação humana) | 100% |
| Tempo médio de processamento | 3,7 s/prontuário |
| Redução vs. revisão manual (13 min) | 99,5% |
| Amostra | 152 pacientes únicos / 170 documentos |

---

## Arquitetura

Pipeline de sete etapas conforme Materiais e Métodos da monografia:

```
PDF ─► extractor ─► metadata ─► identifier ─► analyzer ─► scoring ─► exporter ─► CSV/JSON
       (cascata)    (datas,     (HIPAA       (regex +    (severidade)
                     autor,      Safe Harbor) negação +
                     serviço)                 padrões)
```

| Módulo | Responsabilidade |
|---|---|
| `config.py` | `ProcessingConfig`, enums (`SeverityLevel`, `DocumentType`, `QualityLevel`), limiares e bônus de padrões críticos |
| `lexicon.py` | `ExpandedViolenceLexicon` — 8 categorias semânticas (Tabela 1 do TCC) com pesos diferenciados (2,8 a 1,5); 529 termos públicos cobrindo todas as categorias, incluindo violência sexual; padrões críticos (armas, ameaças de morte, gravidez, crianças presentes, controle psicológico, abuso econômico) |
| `extractor.py` | `EnhancedTextExtractor` — cascata **PDFPlumber → PyMuPDF → Tesseract OCR** com extração por página (`PageInfo`) para permitir localização das detecções |
| `classifier.py` | `DocumentClassifier` — Evolução Médica / Anotações de Enfermagem / Multiprofissional / Outros |
| `metadata.py` | `DocumentMetadataExtractor` — extração de data do documento (com validação de range médico 1980–2030), autor, serviço |
| `identifier.py` | `EnhancedPatientIdentifier` — RGHC (íntegro), CPF (3+***+3), nome (íntegro para contexto clínico), data de nascimento, pseudônimo `PAC_XXXX` via SHA-256 com salt |
| `analyzer.py` | `EnhancedViolenceAnalyzer` — matching regex pré-compilado, contexto ±150 chars, detecção de negação (janela ~80 chars), fator de intensidade contextual, deduplicação de sobreposições, localização página/linha de cada detecção, detecção dos 10 padrões críticos descritos no TCC |
| `scoring.py` | Classificação de severidade **CRÍTICO ≥10 / ALTO ≥6 / MODERADO ≥3 / BAIXO ≥1 / MÍNIMO**, com **ajuste de 30%** dos limiares quando padrões críticos (armas, ameaças de morte, sexual, gravidez) estão presentes |
| `sensitivity.py` | Cálculo Wilson score de IC95% — composição **explícita + expandida** (reproduz 129/152 = 84,9% IC95% 78,3–89,7%) |
| `keyword_extraction.py` | Agregação para a **Tabela 2** do TCC — frequência absoluta e relativa por categoria, top-K |
| `pipeline.py` | `TriagePipeline` — orquestra as 7 etapas, retorna `CaseReport` com tudo |
| `exporter.py` | Gera os quatro artefatos descritos na metodologia |
| `main.py` | CLI |

---

## Uso

```bash
pip install -r requirements.txt
python main.py /caminho/para/pdfs --out ./saida
```

Para reproduzir o cálculo de sensibilidade do TCC (assumindo que todos os PDFs da pasta são casos positivos confirmados):

```bash
python main.py /caminho/para/pdfs --out ./saida --positivos 152
```

### Artefatos gerados em `--out`

| Arquivo | Descrição |
|---|---|
| `resumo_executivo.csv` | Uma linha por documento, com identificação, metadados, scores, severidade, padrões críticos detectados |
| `deteccoes_consolidadas.csv` | Uma linha por documento; coluna `termos_detectados` no formato `"termo (pág.X-linhaY-DD/MM/AAAA)"` |
| `analise_completa.json` | Estrutura completa com todas as detecções, contextos, sentenças, padrões |
| `relatorio_estatistico.txt` | Sumário agregado: distribuição por severidade, tipo de documento, padrões |
| `tabela2_palavras_chave.csv` | Reproduz a Tabela 2 do TCC |

---

## Anonimização (HIPAA Safe Harbor)

Política exatamente como descrita na seção 3.4 da metodologia:

| Campo | Tratamento |
|---|---|
| RGHC | **Íntegro** (chave institucional para auditoria do NUVE) |
| CPF | Parcial: `123***456` |
| Nome | Íntegro (preservado para contexto clínico, uso restrito) |
| Data de nascimento | Íntegra |
| Pseudônimo | `PAC_XXXXXXXXXXXX` (SHA-256 com salt institucional) |

Pode ser totalmente desativada via `--no-anonymize` (uso interno apenas).

---

## Léxico

A versão pública contém **529 termos** distribuídos pelas 8 categorias da Tabela 1, suficientes para reproduzir o pipeline e cobrir todos os padrões críticos descritos no TCC:

| Categoria | Peso | Termos |
|---|---|---|
| Termos médicos formais | 2,8 | 118 |
| Violência infantil | 2,7 | 16 |
| Terminologia legal/policial | 2,5 | 74 |
| Violência doméstica / Maria da Penha | 2,3 | 84 |
| Contextos de enfermagem | 2,0 | 70 |
| Abuso psicológico | 1,9 | 24 |
| Linguagem coloquial | 1,8 | 95 |
| Variações ortográficas | 1,5 | 48 |

Curadoria removeu três falsos positivos identificados durante validação: `pau` (confusão com "São Paulo"), `machado` (sobrenome comum) e `DEAM` (sigla de delegacia, não-violência por si só).

A versão institucional completa contém 1.500 termos (inclui jargões internos do HC-FMUSP) e pode ser disponibilizada mediante solicitação formal ao NUVE.

---

## Padrões críticos detectados (Análise contextual)

10 padrões com bônus de score conforme metodologia:

| Padrão | Bônus |
|---|---|
| Violência sexual | +4,0 |
| Violência na gravidez | +3,5 |
| Armas envolvidas | +3,0 |
| Ameaças de morte | +3,0 |
| Crianças presentes | +2,5 |
| Violência crônica | +2,0 |
| Controle psicológico | +2,0 |
| Escalada da violência | +1,5 |
| Múltiplas lesões | +1,5 |
| Abuso econômico | +1,0 |

Quando qualquer dos quatro padrões mais graves (armas, ameaças de morte, sexual, gravidez) é detectado, todos os limiares de severidade caem em 30%.

---

## Reprodutibilidade

O cálculo de sensibilidade Wilson score implementado em `sensitivity.py` reproduz exatamente o resultado publicado no TCC:

```python
>>> from sensitivity import composite_sensitivity, format_pct
>>> s = composite_sensitivity(detected_explicit=129, total_positive=152, contextual_high_risk=23)
>>> format_pct(s['explicita'].sensitivity), format_pct(s['explicita'].ci_lower), format_pct(s['explicita'].ci_upper)
('84.9%', '78.3%', '89.7%')   # TCC reporta 78,4%–89,8% (diferença ≤0,1pp por arredondamento)
>>> format_pct(s['expandida'].sensitivity)
'100.0%'
```

---

## Limitações reconhecidas (TCC)

- Validação apenas com **casos positivos confirmados** (viés de verificação parcial — impede cálculo de especificidade e VPN)
- Validação por **avaliador único** (sem Kappa de Cohen)
- Léxico sem lematização (variações morfológicas demandam entradas múltiplas)
- Coorte de 2024 de um único centro (HC-FMUSP)

Próximos passos descritos no TCC: inclusão de coorte balanceada, validação inter-avaliadores, externalização do léxico em JSON/YAML, integração de stemming RSLP.

---

## Referências

- BOSSUYT, P. M. et al. **STARD 2015**: An Updated List of Essential Items for Reporting Diagnostic Accuracy Studies. *BMJ*, 2015.
- WILSON, E. B. Probable inference, the law of succession, and statistical inference. *JASA*, 1927.
- Ministério da Saúde. **Portaria MS/GM nº 1.271/2014** — Notificação compulsória.
- KUSHIDA, C. A. et al. Strategies for de-identification of clinical data. *Med Care*, 2012 (HIPAA Safe Harbor).

---

## Licença

Uso acadêmico. Para uso institucional ou comercial, consultar o autor (rafael.m.geraldo@alumni.usp.br).
