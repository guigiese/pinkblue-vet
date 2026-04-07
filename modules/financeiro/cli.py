from __future__ import annotations

import argparse
from pathlib import Path

from .folha import calculate_period, init_period_directory, write_outputs
from .pool import index_evidence_pool, init_competency_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m modules.financeiro",
        description="MVP local para fechamento mensal da folha.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init-periodo",
        help="Cria a estrutura minima de um fechamento mensal.",
    )
    init_parser.add_argument("directory", help="Diretorio do periodo a ser criado.")
    init_parser.add_argument("period", help="Periodo no formato YYYY-MM.")
    init_parser.add_argument(
        "--empresa",
        default="PinkBlue Vet",
        help="Nome da empresa para gravar no periodo.",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Sobrescreve templates existentes no diretorio alvo.",
    )

    init_workspace_parser = subparsers.add_parser(
        "init-competencia",
        help="Cria a estrutura completa de uma competencia com chaos pool.",
    )
    init_workspace_parser.add_argument("directory", help="Diretorio da competencia.")
    init_workspace_parser.add_argument("period", help="Periodo no formato YYYY-MM.")
    init_workspace_parser.add_argument(
        "--empresa",
        default="PinkBlue Vet",
        help="Nome da empresa para gravar no periodo.",
    )
    init_workspace_parser.add_argument(
        "--force",
        action="store_true",
        help="Sobrescreve templates existentes no diretorio alvo.",
    )

    close_parser = subparsers.add_parser(
        "fechar",
        help="Processa um periodo e gera saidas revisaveis.",
    )
    close_parser.add_argument("directory", help="Diretorio do periodo a ser processado.")

    index_parser = subparsers.add_parser(
        "indexar-pool",
        help="Indexa evidencias do chaos pool e monta a fila de normalizacao.",
    )
    index_parser.add_argument("directory", help="Diretorio do periodo a ser indexado.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init-periodo":
        period_dir = init_period_directory(
            Path(args.directory),
            period=args.period,
            company=args.empresa,
            force=args.force,
        )
        print(f"Periodo inicializado em: {period_dir}")
        return 0

    if args.command == "init-competencia":
        period_dir = init_competency_workspace(
            Path(args.directory),
            period=args.period,
            company=args.empresa,
            force=args.force,
        )
        print(f"Competencia inicializada em: {period_dir}")
        return 0

    if args.command == "fechar":
        period_dir = Path(args.directory)
        result = calculate_period(period_dir)
        output_dir = write_outputs(period_dir, result)
        print(f"Fechamento processado em: {output_dir}")
        print(f"Liquido total: {result['resumo']['liquido_total']}")
        if result["avisos"]:
            print("Avisos encontrados:")
            for warning in result["avisos"]:
                print(f"- {warning}")
        return 0

    if args.command == "indexar-pool":
        period_dir = Path(args.directory)
        summary = index_evidence_pool(period_dir)
        print(f"Evidencias indexadas: {summary['indexed']}")
        print(f"Itens na fila de normalizacao: {summary['queue_items']}")
        for profile, count in sorted(summary["profiles"].items()):
            print(f"- {profile}: {count}")
        return 0

    parser.error("Comando invalido.")
    return 2
