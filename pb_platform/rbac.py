from __future__ import annotations

from typing import NamedTuple


class PermDef(NamedTuple):
    module: str
    perm_id: str
    label: str
    implies: list[str]


class PermissionRegistry:
    def __init__(self) -> None:
        self._perms: dict[str, PermDef] = {}

    def register(self, module: str, perm_id: str, label: str, implies: list[str] | None = None) -> None:
        self._perms[perm_id] = PermDef(module=module, perm_id=perm_id, label=label, implies=implies or [])

    def all_perms(self) -> list[PermDef]:
        return list(self._perms.values())

    def implied_by(self, perm_id: str) -> list[str]:
        return self._perms[perm_id].implies if perm_id in self._perms else []


registry = PermissionRegistry()

# Platform
registry.register("platform", "platform_access", "Acesso à plataforma")
registry.register("platform", "manage_users", "Gerenciar usuários")
registry.register("platform", "ops_tools", "Ferramentas de operações")

# Lab Monitor
registry.register("labmonitor", "labmonitor_access", "Acesso ao Lab Monitor")
registry.register("labmonitor", "manage_labmonitor", "Gerenciar Lab Monitor",
                  implies=["labmonitor_access", "manage_labmonitor_labs", "manage_labmonitor_settings"])
registry.register("labmonitor", "manage_labmonitor_labs", "Gerenciar conectores/labs")
registry.register("labmonitor", "manage_labmonitor_settings", "Gerenciar configs/notifiers/thresholds")

# Plantão
registry.register("plantao", "plantao_access", "Acesso ao Plantão")
registry.register("plantao", "manage_plantao", "Gerenciar Plantão",
                  implies=["plantao_access", "plantao_gerir_escalas", "plantao_aprovar_candidaturas",
                           "plantao_aprovar_cadastros", "plantao_ver_relatorios"])
registry.register("plantao", "plantao_gerir_escalas", "Gerir escalas")
registry.register("plantao", "plantao_aprovar_candidaturas", "Aprovar candidaturas")
registry.register("plantao", "plantao_aprovar_cadastros", "Aprovar cadastros")
registry.register("plantao", "plantao_ver_relatorios", "Ver relatórios")
