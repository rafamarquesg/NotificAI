# NotificAI

Sistema de apoio à notificação compulsória de violências e agravos à saúde em prontuários eletrônicos, desenvolvido para o **Núcleo de Vigilância Epidemiológica (NUVE)** do Hospital das Clínicas da FMUSP.

> TCC do MBA em Data Science e Analytics — USP/ESALQ

---

## Resultados

| Métrica | Valor |
|---|---|
| Sensibilidade | 84,9% (IC 95%: 79,2–90,6%) |
| Tempo de processamento | ~3,7 s/prontuário |
| Redução de tempo vs. revisão manual | 99,5% |

---

## Funcionalidades

- **Detecção lexical** de termos de violência com suporte a negação, contexto e deduplicação
- **Classificação automática** em 7 tipos SINAN: Física, Sexual, Psicológica, Autoprovocada, Negligência, Trabalho Infantil, Tráfico de Pessoas
- **NER clínico** via BioBERTpt (`pucpr/clinicalnerpt-disease`, `clinicalnerpt-medical`)
- **Embeddings BERT** com BioBERTpt (`pucpr/biobertpt-clin`) e BERTimbau (`neuralmind/bert-base-portuguese-cased`)
- **Exportação SINAN** — CSV e Excel no layout da Ficha de Notificação de Violência (SINAN NET v2019)
- **Dashboard Streamlit** com dois painéis:
  - **Painel Público** — métricas agregadas e anônimas
  - **Painel Seguro** — dados sensíveis com autenticação, fila de prioridade e timeline de reincidência
- **Monitoramento de pasta** — integração futura com diretório de prontuários da TI (watchdog)
- **Workflow de casos** — pendente → em análise → notificado → arquivado
- **Aprendizado ativo** — feedback de classificação para treino futuro com dados rotulados

---

## Arquitetura

```
NotificAI/
├── detector.py          ← Detecção lexical (regex + negação + contexto)
├── lexicon.py           ← Léxico hierárquico (8 categorias, pesos)
├── features.py          ← Extração de ~35 características + embeddings BERT
├── classifier.py        ← Classificador (regras → ML quando houver dados)
├── notification_types.py← Enum de tipos SINAN
├── pipeline.py          ← Orquestrador: texto → análise completa
├── embedder.py          ← BertEmbedder (BioBERTpt / BERTimbau)
├── ner.py               ← ClinicalNER (pucpr/clinicalnerpt-*)
├── complete.py          ← Pré-processamento de PDF e texto
├── models.py            ← Modelos de dados (dataclasses)
├── utils.py             ← Utilitários (hash, limpeza)
├── requirements.txt     ← Dependências base
├── pytest.ini
├── test_detector.py
├── test_ml.py
└── frontend/
    ├── app.py                       ← Ponto de entrada: streamlit run frontend/app.py
    ├── requirements_frontend.txt
    ├── .streamlit/config.toml
    ├── core/
    │   ├── database.py              ← SQLite: schema, queries, workflow
    │   ├── anonymizer.py            ← Pseudonimização + extração de IDs
    │   ├── processor.py             ← PDF → análise → banco
    │   ├── watcher.py               ← Watchdog para monitoramento de pasta
    │   └── export.py                ← CSV/Excel no layout SINAN
    ├── components/
    │   ├── charts.py                ← Gráficos Plotly
    │   ├── upload_widget.py         ← Upload e config de pasta
    │   ├── priority_queue.py        ← Fila de casos por score
    │   ├── timeline_viewer.py       ← Timeline de reincidência
    │   └── record_viewer.py         ← Card de detalhe com feedback
    └── panels/
        ├── painel_publico.py        ← Dashboard anônimo
        └── painel_seguro.py         ← Dashboard autenticado (dados sensíveis)
```

### Três níveis de operação

| Nível | Requisitos | Descrição |
|---|---|---|
| 1 — Lexical | Nenhum (só Python stdlib + scikit-learn) | Regras + ~35 características |
| 2 — + NER clínico | `transformers` | Entidades UMLS (doenças, achados) |
| 3 — + BERT | `transformers` + `torch` | Mean-pooling BioBERTpt (~803 dims) |

---

## Instalação

### 1. Clonar e instalar dependências base

```bash
git clone https://github.com/rafamarquesg/NotificAI.git
cd NotificAI
pip install -r requirements.txt
```

### 2. Dependências opcionais (BERT / NER clínico)

```bash
# CPU
pip install torch transformers

# GPU (CUDA 11.8)
pip install torch --index-url https://download.pytorch.org/whl/cu118
pip install transformers
```

### 3. Frontend Streamlit

```bash
pip install -r frontend/requirements_frontend.txt
streamlit run frontend/app.py
```

---

## Uso rápido

### Análise de texto

```python
from pipeline import AnalysisPipeline

pipeline = AnalysisPipeline()
result = pipeline.analyze_text(
    "Paciente relata que o companheiro a agrediu com socos no rosto. "
    "Apresenta hematoma periorbital bilateral."
)
print(pipeline.summary(result))
# Tipo de notificação : Violência Física
# Confiança           : 78.3%
# Pontuação total     : 9.40
# Modo                : RULES
# Termos detectados   : 4 (0 negados)
# Tempo               : 12.1 ms
```

### Classificação com BERT (quando disponível)

```python
from embedder import BertEmbedder
from features import FeatureExtractor
from pipeline import AnalysisPipeline

embedder = BertEmbedder("pucpr/biobertpt-clin")
extractor = FeatureExtractor(embedder=embedder)
pipeline = AnalysisPipeline(extractor=extractor)

result = pipeline.analyze_text(texto)
```

### Treinar com dados rotulados

```python
from notification_types import NotificationType

labels = [NotificationType.VIOLENCIA_FISICA, NotificationType.VIOLENCIA_SEXUAL, ...]
pipeline.classifier.fit(textos, labels)
pipeline.classifier.save("modelo_nuve.pkl")

# Inferência posterior
pipeline = AnalysisPipeline(model_path="modelo_nuve.pkl")
```

---

## Modelos clínicos utilizados

| Modelo | Uso |
|---|---|
| `pucpr/biobertpt-clin` | Embeddings (treinado em 2M prontuários BR) |
| `pucpr/biobertpt-all` | Embeddings alternativos (clínico + biomédico) |
| `neuralmind/bert-base-portuguese-cased` | BERTimbau — fallback PT-BR geral |
| `pucpr/clinicalnerpt-disease` | NER: doenças e lesões (UMLS) |
| `pucpr/clinicalnerpt-medical` | NER: 13 tipos de entidades clínicas |

---

## Testes

```bash
pytest                        # 67 testes (roda sem GPU)
pytest -m "not slow"          # pula testes de BERT (requerem download de modelo)
```

---

## Exportação SINAN

O módulo `frontend/core/export.py` gera arquivos no layout da **Ficha de Notificação Individual de Violência Interpessoal/Autoprovocada** (SINAN NET v2019), incluindo:

- Código CID-10 sugerido por tipo
- Tipo de violência conforme tabela SINAN (campo 41)
- Hash anonimizado do paciente (sem PII)
- Export CSV (UTF-8 BOM — compatível com Excel) e XLSX com duas abas

---

## Privacidade e segurança

- Dados de identificação (nome, RGHC, CPF) ficam exclusivamente na tabela `patients` do SQLite local
- O Painel Público nunca acessa a tabela `patients`
- O Painel Seguro exige autenticação por senha (hash SHA-256, configurável via variável de ambiente `NOTIFICAI_ADMIN_HASH`)
- Todos os acessos a dados sensíveis são registrados em `access_log`

---

## Referências

- MORAES, E. M. et al. **BioBERTpt** — A Portuguese Neural Language Model for Clinical NER. *ACL Clinical NLP Workshop*, 2020.
- SOUZA, F.; NOGUEIRA, R.; LOTUFO, R. **BERTimbau**: Pretrained BERT Models for Brazilian Portuguese. *BRACIS*, 2020.
- Ministério da Saúde. **SINAN NET** — Ficha de Notificação/Investigação de Violência Doméstica, Sexual e/ou outras Violências, v2019.

---

## Licença

Uso acadêmico e institucional — NUVE/HC-FMUSP. Para outros usos, consulte o autor.
