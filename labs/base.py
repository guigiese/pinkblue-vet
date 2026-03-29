"""
Interface base para conectores de laboratório.

Cada lab deve retornar um snapshot no formato:
{
    "record_id": {
        "label":  "ANIMAL - PROPRIETÁRIO",
        "data":   "2026-03-29",
        "itens": {
            "item_id": {"nome": str, "status": str}
        }
    }
}
"""

from abc import ABC, abstractmethod


class LabConnector(ABC):

    @property
    @abstractmethod
    def lab_id(self) -> str:
        """Identificador único do lab (ex: 'bitlab', 'nexio')."""

    @property
    @abstractmethod
    def lab_name(self) -> str:
        """Nome legível (ex: 'BioAnálises BitLab')."""

    @abstractmethod
    def snapshot(self) -> dict[str, dict]:
        """
        Faz login, busca todos os exames e retorna o snapshot atual.
        Deve encapsular login + coleta em uma chamada só.
        """
