"""
notification/sinan_bridge.py
============================
PLACEHOLDER — Integração futura com o SINAN (Sistema de Informação de
Agravos de Notificação) e e-SUS / RNDS (Rede Nacional de Dados em Saúde).

=== ETAPA D DO FLUXO HitL ===

Este módulo é disparado SOMENTE após a Etapa B (validação pelo técnico).
Nunca é executado automaticamente sem aprovação humana explícita.

Fluxo previsto:
  1. Técnico aprova ReviewTask com `trigger_sinan=True`
  2. FeedbackStore._dispatch_sinan() chama SinanBridge.submit()
  3. SinanBridge mapeia os dados para a Ficha de Notificação Individual (FNI)
  4. Envia via API REST do e-SUS ou exporta XML/CSV para importação manual

Referências de integração:
  - API e-SUS: https://integracao.esus.ufsc.br/
  - RNDS (FHIR R4): https://rnds.saude.gov.br/
  - Ficha de Notificação SINAN: Layout definido pelo DATASUS
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class SinanNotificationPayload:
    """
    Estrutura da Ficha de Notificação Individual do SINAN.
    Campos obrigatórios conforme Portaria GM/MS nº 264/2020.
    """
    # Identificação do caso
    agravo_cid10: str = ""          # Ex: "X85" (agressão por substância)
    municipio_notificacao: str = ""
    unidade_saude: str = ""
    data_notificacao: str = ""

    # Dados do paciente (preenchidos pelo NER)
    nome_paciente: Optional[str] = None
    data_nascimento: Optional[str] = None
    sexo: Optional[str] = None
    cpf: Optional[str] = None
    raca_cor: Optional[str] = None
    escolaridade: Optional[str] = None
    municipio_residencia: Optional[str] = None

    # Dados do agravo
    data_ocorrencia: Optional[str] = None
    tipo_violencia: Optional[str] = None       # Campo 36 da FNI
    meio_agressao: Optional[str] = None        # Campo 37 da FNI
    local_ocorrencia: Optional[str] = None
    autor_violencia: Optional[str] = None

    # Campos de encaminhamento
    encaminhamento_delegacia: bool = False
    encaminhamento_conselho_tutelar: bool = False
    encaminhamento_rede_saude: bool = False

    # Metadados internos
    task_id: str = ""
    source_analysis_id: str = ""
    raw_evidence: str = ""  # Trecho de evidência (não vai ao SINAN, só para auditoria interna)

    extra_fields: Dict[str, Any] = field(default_factory=dict)


class SinanBridge:
    """
    Bridge de integração com o SINAN.

    ESTADO ATUAL: Modo simulação — loga a tentativa de envio.
    ATIVAR: Implementar `_send_to_api()` com as credenciais do serviço e-SUS.
    """

    # TODO: Mover para variáveis de ambiente
    _API_ENDPOINT = "https://integracao.esus.ufsc.br/notificacao"  # placeholder
    _API_TOKEN = ""  # Configurar via env var SINAN_API_TOKEN

    def submit(self, decision: Any) -> dict:
        """
        Constrói o payload da notificação e envia ao SINAN.
        Recebe ValidationDecision do módulo hitl.

        Returns:
            dict com {"status": "simulated"|"sent"|"error", "payload": {...}}
        """
        try:
            payload = self._build_payload(decision)
            result = self._send_to_api(payload)
            logger.info(f"SINAN: Notificação disparada para task={decision.task_id}: {result}")
            return result
        except Exception as exc:
            logger.error(f"SINAN: Falha no envio para task={decision.task_id}: {exc}")
            return {"status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Privados
    # ------------------------------------------------------------------

    @staticmethod
    def _build_payload(decision: Any) -> SinanNotificationPayload:
        """
        Mapeia ValidationDecision → SinanNotificationPayload.
        TODO: Preencher campos com dados do PatientEntities e AnalysisResult.
        """
        return SinanNotificationPayload(
            agravo_cid10=SinanBridge._map_agravo_to_cid10(decision),
            task_id=decision.task_id,
            tipo_violencia=decision.agravo_confirmed.value if decision.agravo_confirmed else "",
        )

    @staticmethod
    def _map_agravo_to_cid10(decision: Any) -> str:
        """
        Mapeamento AgravoType → CID-10.
        Referência: Tabela de codificação SINAN/DATASUS.
        """
        from hitl.models import AgravoType
        mapping = {
            AgravoType.VIOLENCIA_DOMESTICA: "Z63.3",
            AgravoType.VIOLENCIA_SEXUAL: "X85",
            AgravoType.VIOLENCIA_AUTOPROVOCADA: "X71",
            AgravoType.MAUS_TRATOS_CRIANCA: "T74.1",
            AgravoType.MAUS_TRATOS_IDOSO: "T74.1",
            AgravoType.FEMINICIDIO: "X99",
            AgravoType.NEGLIGENCIA: "T74.0",
            AgravoType.OUTRO: "Y09",
        }
        if not decision.agravo_confirmed:
            return "Y09"  # Violência por meios não especificados
        return mapping.get(decision.agravo_confirmed, "Y09")

    def _send_to_api(self, payload: SinanNotificationPayload) -> dict:
        """
        Envia a notificação ao endpoint do SINAN/e-SUS.

        MODO ATUAL: Simulação (dry-run).
        ATIVAR: Descomentar o bloco `requests.post(...)` e configurar credenciais.
        """
        payload_dict = payload.__dict__.copy()
        payload_dict.pop("raw_evidence", None)  # Não enviar dados brutos ao SINAN

        # ================================================================
        # INTEGRAÇÃO REAL — descomentar quando credenciais estiverem prontas
        # ================================================================
        # import requests
        # headers = {
        #     "Authorization": f"Bearer {self._API_TOKEN}",
        #     "Content-Type": "application/json",
        # }
        # response = requests.post(
        #     self._API_ENDPOINT,
        #     json=payload_dict,
        #     headers=headers,
        #     timeout=30,
        # )
        # response.raise_for_status()
        # return {"status": "sent", "sinan_protocol": response.json().get("protocol")}
        # ================================================================

        # Simulação: loga o payload e retorna sucesso
        logger.info(
            f"[SINAN SIMULADO] Payload que seria enviado:\n"
            + "\n".join(f"  {k}: {v}" for k, v in payload_dict.items() if v)
        )
        return {
            "status": "simulated",
            "message": "Integração SINAN em modo de simulação. Configure _API_TOKEN para ativar.",
            "payload_preview": payload_dict,
        }
