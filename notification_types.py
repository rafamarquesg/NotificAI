"""
Tipos de notificação compulsória de violência conforme o sistema SINAN/NUVE.

Referência: Ficha de Notificação Individual — Violência Interpessoal/Autoprovocada
(SINAN — Sistema de Informação de Agravos de Notificação, Ministério da Saúde).
"""

from enum import Enum


class NotificationType(Enum):
    """
    Classifica o tipo principal de violência para fins de notificação compulsória.

    Quando dados rotulados estiverem disponíveis, o ML aprenderá a distinguir
    automaticamente as características textuais associadas a cada tipo.
    """

    VIOLENCIA_FISICA = "Violência Física"
    """Agressões corporais, lesões, espancamentos, uso de objetos ou armas."""

    VIOLENCIA_SEXUAL = "Violência Sexual"
    """Estupro, abuso sexual, assédio, exploração sexual."""

    VIOLENCIA_PSICOLOGICA = "Violência Psicológica/Moral"
    """Humilhação, gaslighting, controle coercitivo, ameaças psicológicas."""

    VIOLENCIA_AUTOPROVOCADA = "Violência Autoprovocada"
    """Tentativa de suicídio, automutilação, autolesão."""

    NEGLIGENCIA = "Negligência/Abandono"
    """Falta de cuidados básicos, desnutrição, abandono de incapaz."""

    TRABALHO_INFANTIL = "Trabalho Infantil"
    """Exploração de trabalho de menores de idade."""

    TRAFICO_PESSOAS = "Tráfico de Pessoas"
    """Tráfico para fins de exploração sexual, trabalho forçado, etc."""

    OUTROS = "Outros/Não Classificado"
    """Violência não enquadrável nas categorias acima ou texto insuficiente."""
