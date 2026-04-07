from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

TWO_PLACES = Decimal("0.01")

MODE_ALIASES = {
    "clt": "valor_importado",
    "fixo_importado": "valor_importado",
    "valor_importado": "valor_importado",
    "horista": "horista",
    "free_hora": "horista",
    "free_por_hora": "horista",
    "comissao_percentual": "comissao_percentual",
    "comissao_simples": "comissao_percentual",
    "comissao_com_piso_diario": "comissao_com_piso_diario",
    "veterinario_comissao_piso": "comissao_com_piso_diario",
}

ADDITIONAL_EARNING_CATEGORIES = {
    "bonus_manual",
    "credito_manual",
    "reembolso",
}

DISCOUNT_CATEGORIES = {
    "adiantamento",
    "consumo_em_aberto",
    "falha_veterinaria",
    "desconto_manual",
}


@dataclass
class CalculationLine:
    categoria: str
    descricao: str
    valor: Decimal
    detalhes: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "categoria": self.categoria,
            "descricao": self.descricao,
            "valor": format_money(self.valor),
        }
        if self.detalhes:
            payload["detalhes"] = self.detalhes
        return payload


def to_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def money(value: Any) -> Decimal:
    return to_decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def format_money(value: Decimal) -> str:
    return f"{money(value):.2f}"


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(f"Arquivo obrigatorio ausente: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )


def init_period_directory(directory: Path, period: str, company: str, force: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)

    templates = {
        "periodo.json": {
            "periodo": period,
            "empresa": company,
            "moeda": "BRL",
            "observacoes": [
                "Use este diretorio como consolidado manual do periodo.",
                "Arquivos brutos podem ser listados em fontes_brutas.json.",
            ],
        },
        "colaboradores.json": [
            {
                "id": "exemplo_colaborador",
                "nome": "Nome do colaborador",
                "modo": "valor_importado",
                "config": {
                    "observacoes": "Troque o modo para horista, comissao_percentual ou comissao_com_piso_diario conforme necessario."
                },
            }
        ],
        "lancamentos.json": [
            {
                "colaborador_id": "exemplo_colaborador",
                "categoria": "valor_importado",
                "valor": 0,
                "descricao": "Substitua pelos lancamentos reais do periodo.",
                "fonte": "manual",
            }
        ],
        "escalas.json": [],
        "fontes_brutas.json": [
            {
                "origem": "planilha_atual",
                "arquivo": "substituir-caminho-ou-nome",
                "status": "pendente",
                "observacoes": "Liste aqui PDFs, prints, planilhas, textos de WhatsApp e exportacoes usadas no fechamento.",
            }
        ],
    }

    for filename, payload in templates.items():
        target = directory / filename
        if target.exists() and not force:
            continue
        write_json(target, payload)

    return directory


def calculate_period(period_dir: Path) -> dict[str, Any]:
    metadata = read_json(period_dir / "periodo.json")
    employees = read_json(period_dir / "colaboradores.json")
    entries = read_json(period_dir / "lancamentos.json")
    shift_entries = read_json(period_dir / "escalas.json", default=[])
    raw_sources = read_json(period_dir / "fontes_brutas.json", default=[])

    entries_by_employee: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        employee_id = entry.get("colaborador_id")
        if not employee_id:
            continue
        entries_by_employee[employee_id].append(entry)

    employee_results: list[dict[str, Any]] = []
    global_warnings: list[str] = []
    gross_total = Decimal("0")
    discount_total = Decimal("0")
    net_total = Decimal("0")

    for employee in employees:
        employee_result = _calculate_employee(
            employee,
            entries_by_employee.get(employee["id"], []),
            shift_entries=shift_entries,
        )
        employee_results.append(employee_result)
        gross_total += money(employee_result["bruto"])
        discount_total += money(employee_result["descontos"])
        net_total += money(employee_result["liquido"])
        for warning in employee_result["avisos"]:
            global_warnings.append(f"{employee_result['nome']}: {warning}")

    referenced_ids = {employee["id"] for employee in employees}
    for employee_id in entries_by_employee:
        if employee_id not in referenced_ids:
            global_warnings.append(
                f"Lancamentos encontrados para colaborador nao cadastrado: {employee_id}"
            )

    result = {
        "periodo": metadata.get("periodo"),
        "empresa": metadata.get("empresa"),
        "moeda": metadata.get("moeda", "BRL"),
        "fontes_brutas": raw_sources,
        "quantidade_fontes_brutas": len(raw_sources),
        "resumo": {
            "colaboradores": len(employee_results),
            "bruto_total": format_money(gross_total),
            "descontos_total": format_money(discount_total),
            "liquido_total": format_money(net_total),
        },
        "avisos": global_warnings,
        "colaboradores": employee_results,
    }
    return result


def _calculate_employee(
    employee: dict[str, Any],
    entries: list[dict[str, Any]],
    shift_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    mode_name = employee.get("modo", "valor_importado")
    mode = MODE_ALIASES.get(mode_name, mode_name)
    config = employee.get("config", {})
    warnings: list[str] = []
    earning_lines: list[CalculationLine] = []
    discount_lines: list[CalculationLine] = []

    if not entries:
        warnings.append("sem lancamentos no periodo")

    if mode == "valor_importado":
        earning_lines.extend(_calculate_imported_total(entries, config))
    elif mode == "horista":
        lines, mode_warnings = _calculate_hourly_total(entries, config)
        earning_lines.extend(lines)
        warnings.extend(mode_warnings)
    elif mode == "comissao_percentual":
        lines, mode_warnings = _calculate_commission_total(entries, config)
        earning_lines.extend(lines)
        warnings.extend(mode_warnings)
    elif mode == "comissao_com_piso_diario":
        lines, mode_warnings = _calculate_commission_with_daily_floor(
            employee,
            entries,
            config,
            shift_entries or [],
        )
        earning_lines.extend(lines)
        warnings.extend(mode_warnings)
    else:
        warnings.append(f"modo nao suportado: {mode_name}")

    for entry in entries:
        category = entry.get("categoria")
        value = money(entry.get("valor", 0))
        description = entry.get("descricao", category or "lancamento")

        if category in ADDITIONAL_EARNING_CATEGORIES:
            earning_lines.append(CalculationLine(category, description, value))
        if category in DISCOUNT_CATEGORIES:
            discount_lines.append(CalculationLine(category, description, value))

    gross = sum((line.valor for line in earning_lines), Decimal("0"))
    discounts = sum((line.valor for line in discount_lines), Decimal("0"))
    net = gross - discounts

    if gross == Decimal("0"):
        warnings.append("bruto zerado")

    return {
        "id": employee["id"],
        "nome": employee.get("nome", employee["id"]),
        "modo": mode_name,
        "bruto": format_money(gross),
        "descontos": format_money(discounts),
        "liquido": format_money(net),
        "proventos": [line.as_dict() for line in earning_lines],
        "descontos_detalhados": [line.as_dict() for line in discount_lines],
        "avisos": warnings,
    }


def _calculate_imported_total(entries: list[dict[str, Any]], config: dict[str, Any]) -> list[CalculationLine]:
    categories = config.get("earning_categories", ["valor_importado"])
    lines: list[CalculationLine] = []
    for entry in entries:
        if entry.get("categoria") in categories:
            lines.append(
                CalculationLine(
                    entry["categoria"],
                    entry.get("descricao", "Valor importado"),
                    money(entry.get("valor", 0)),
                )
            )
    return lines


def _calculate_hourly_total(
    entries: list[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[list[CalculationLine], list[str]]:
    categories = config.get("earning_categories", ["horas_trabalhadas"])
    default_rate = config.get("valor_hora")
    warnings: list[str] = []
    lines: list[CalculationLine] = []

    for entry in entries:
        if entry.get("categoria") not in categories:
            continue
        quantity = to_decimal(entry.get("quantidade", 0))
        rate_value = entry.get("valor_unitario", default_rate)
        if rate_value is None:
            warnings.append(
                f"lancamento '{entry.get('descricao', entry.get('categoria'))}' sem valor_hora"
            )
            continue
        rate = to_decimal(rate_value)
        total = money(quantity * rate)
        description = entry.get("descricao", "Horas trabalhadas")
        lines.append(
            CalculationLine(
                entry.get("categoria", "horas_trabalhadas"),
                f"{description} ({quantity}h x {format_money(rate)})",
                total,
            )
        )

    return lines, warnings


def _calculate_commission_total(
    entries: list[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[list[CalculationLine], list[str]]:
    categories = config.get("base_categories", ["base_comissao"])
    commission_percent = config.get("percentual_comissao")
    warnings: list[str] = []
    lines: list[CalculationLine] = []

    if commission_percent is None:
        return [], ["percentual_comissao ausente"]

    rate = to_decimal(commission_percent)
    for entry in entries:
        if entry.get("categoria") not in categories:
            continue
        base_value = money(entry.get("valor", 0))
        commission_value = money(base_value * rate)
        description = entry.get("descricao", "Base de comissao")
        lines.append(
            CalculationLine(
                "comissao_calculada",
                f"{description} ({format_money(base_value)} x {format_money(rate)})",
                commission_value,
            )
        )

    return lines, warnings


def _calculate_commission_with_daily_floor(
    employee: dict[str, Any],
    entries: list[dict[str, Any]],
    config: dict[str, Any],
    shift_entries: list[dict[str, Any]],
) -> tuple[list[CalculationLine], list[str]]:
    categories = set(config.get("base_categories", ["base_comissao_diaria"]))
    commission_percent = config.get("percentual_comissao")
    daily_floor = config.get("piso_diario")
    warnings: list[str] = []

    if commission_percent is None:
        return [], ["percentual_comissao ausente"]
    if daily_floor is None:
        return [], ["piso_diario ausente"]

    rate = to_decimal(commission_percent)
    floor_amount = money(daily_floor)
    grouped: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    floor_by_date, floor_warnings = _build_daily_floor_map(employee, shift_entries, floor_amount)
    warnings.extend(floor_warnings)
    use_shift_floor = bool(shift_entries)

    if not use_shift_floor:
        warnings.append("sem escalas.json; piso diario aplicado no modo legado para todas as datas")

    for entry in entries:
        if entry.get("categoria") not in categories:
            continue
        date = entry.get("data")
        if not date:
            warnings.append(
                f"lancamento '{entry.get('descricao', entry.get('categoria'))}' sem data para piso diario"
            )
            continue
        grouped[date] += money(entry.get("valor", 0))

    lines: list[CalculationLine] = []
    for date in sorted(grouped):
        base_value = grouped[date]
        commission_value = money(base_value * rate)
        eligible_floor = floor_by_date.get(date, Decimal("0")) if use_shift_floor else floor_amount
        payable = max(commission_value, eligible_floor)
        basis = "comissao" if commission_value >= eligible_floor else "piso"
        situation = "responsavel" if eligible_floor > Decimal("0") else "sem_piso"
        lines.append(
            CalculationLine(
                "comissao_com_piso_diario",
                (
                    f"{date}: base {format_money(base_value)}, comissao {format_money(commission_value)}, "
                    f"piso elegivel {format_money(eligible_floor)}, pagamento por {basis}"
                ),
                payable,
                detalhes={
                    "data": date,
                    "base_calculo": format_money(base_value),
                    "percentual_comissao": format_money(rate),
                    "comissao_calculada": format_money(commission_value),
                    "piso_elegivel": format_money(eligible_floor),
                    "pagamento_por": basis,
                    "situacao_escala": situation,
                },
            )
        )

    return lines, warnings


def _build_daily_floor_map(
    employee: dict[str, Any],
    shift_entries: list[dict[str, Any]],
    default_floor: Decimal,
) -> tuple[dict[str, Decimal], list[str]]:
    employee_id = employee.get("id")
    warnings: list[str] = []
    floor_by_date: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for shift in shift_entries:
        assigned_employee_id = (
            shift.get("colaborador_id")
            or shift.get("responsavel_id")
            or shift.get("veterinario_id")
        )
        if assigned_employee_id != employee_id:
            continue

        if shift.get("aplica_piso") is False:
            continue

        shift_type = shift.get("tipo", "responsavel")
        if shift_type not in {"responsavel", "plantonista_responsavel"}:
            continue

        date = shift.get("data") or shift.get("date")
        if not date:
            warnings.append(
                f"escala sem data para colaborador {employee.get('nome', employee_id)}"
            )
            continue

        floor_value = shift.get("piso_minimo", default_floor)
        floor_by_date[date] += money(floor_value)

    return floor_by_date, warnings


def write_outputs(period_dir: Path, result: dict[str, Any]) -> Path:
    output_dir = period_dir / "saida"
    output_dir.mkdir(parents=True, exist_ok=True)

    write_json(output_dir / "resultado.json", result)
    (output_dir / "resultado.md").write_text(_render_markdown(result), encoding="utf-8")
    _write_csv(output_dir / "resultado.csv", result)
    _write_calculation_memory_csv(output_dir / "memoria_calculo.csv", result)
    return output_dir


def _write_csv(path: Path, result: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["id", "nome", "modo", "bruto", "descontos", "liquido", "avisos"],
        )
        writer.writeheader()
        for employee in result["colaboradores"]:
            writer.writerow(
                {
                    "id": employee["id"],
                    "nome": employee["nome"],
                    "modo": employee["modo"],
                    "bruto": employee["bruto"],
                    "descontos": employee["descontos"],
                    "liquido": employee["liquido"],
                    "avisos": " | ".join(employee["avisos"]),
                }
            )


def _write_calculation_memory_csv(path: Path, result: dict[str, Any]) -> None:
    fieldnames = [
        "colaborador_id",
        "nome",
        "natureza",
        "categoria",
        "descricao",
        "valor",
        "data",
        "base_calculo",
        "percentual_comissao",
        "comissao_calculada",
        "piso_elegivel",
        "pagamento_por",
        "situacao_escala",
        "detalhes_json",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for employee in result["colaboradores"]:
            _write_memory_rows(writer, employee, "provento", employee["proventos"])
            _write_memory_rows(writer, employee, "desconto", employee["descontos_detalhados"])


def _write_memory_rows(
    writer: csv.DictWriter,
    employee: dict[str, Any],
    natureza: str,
    lines: list[dict[str, Any]],
) -> None:
    for line in lines:
        details = line.get("detalhes", {})
        writer.writerow(
            {
                "colaborador_id": employee["id"],
                "nome": employee["nome"],
                "natureza": natureza,
                "categoria": line["categoria"],
                "descricao": line["descricao"],
                "valor": line["valor"],
                "data": details.get("data", ""),
                "base_calculo": details.get("base_calculo", ""),
                "percentual_comissao": details.get("percentual_comissao", ""),
                "comissao_calculada": details.get("comissao_calculada", ""),
                "piso_elegivel": details.get("piso_elegivel", ""),
                "pagamento_por": details.get("pagamento_por", ""),
                "situacao_escala": details.get("situacao_escala", ""),
                "detalhes_json": json.dumps(details, ensure_ascii=True, sort_keys=True),
            }
        )


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# Fechamento da folha - {result['periodo']}",
        "",
        f"Empresa: {result['empresa']}",
        f"Moeda: {result['moeda']}",
        "",
        "## Resumo",
        "",
        f"- Colaboradores: {result['resumo']['colaboradores']}",
        f"- Bruto total: {result['resumo']['bruto_total']}",
        f"- Descontos total: {result['resumo']['descontos_total']}",
        f"- Liquido total: {result['resumo']['liquido_total']}",
        "",
    ]

    if result["avisos"]:
        lines.extend(["## Avisos globais", ""])
        for warning in result["avisos"]:
            lines.append(f"- {warning}")
        lines.append("")

    lines.extend(["## Colaboradores", ""])
    for employee in result["colaboradores"]:
        lines.extend(
            [
                f"### {employee['nome']} ({employee['modo']})",
                "",
                f"- Bruto: {employee['bruto']}",
                f"- Descontos: {employee['descontos']}",
                f"- Liquido: {employee['liquido']}",
            ]
        )
        if employee["proventos"]:
            lines.append("- Proventos:")
            for earning in employee["proventos"]:
                lines.append(
                    f"  - {earning['descricao']}: {earning['valor']} [{earning['categoria']}]"
                )
        if employee["descontos_detalhados"]:
            lines.append("- Descontos detalhados:")
            for discount in employee["descontos_detalhados"]:
                lines.append(
                    f"  - {discount['descricao']}: {discount['valor']} [{discount['categoria']}]"
                )
        if employee["avisos"]:
            lines.append("- Avisos:")
            for warning in employee["avisos"]:
                lines.append(f"  - {warning}")
        lines.append("")

    if result["fontes_brutas"]:
        lines.extend(["## Fontes brutas", ""])
        for source in result["fontes_brutas"]:
            origin = source.get("origem", "fonte")
            filename = source.get("arquivo", "sem arquivo")
            status = source.get("status", "sem status")
            lines.append(f"- {origin}: {filename} ({status})")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
