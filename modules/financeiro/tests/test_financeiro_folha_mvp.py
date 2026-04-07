import json
import tempfile
import unittest
from pathlib import Path

from modules.financeiro.folha import calculate_period, init_period_directory, write_outputs


class FolhaMvpTests(unittest.TestCase):
    def test_calculate_period_supports_multiple_payment_modes(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            period_dir = Path(tmp_dir) / "2026-04"
            init_period_directory(period_dir, period="2026-04", company="PinkBlue Vet", force=True)

            (period_dir / "colaboradores.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "clt",
                            "nome": "CLT",
                            "modo": "valor_importado",
                        },
                        {
                            "id": "free",
                            "nome": "Free",
                            "modo": "horista",
                            "config": {"valor_hora": 25},
                        },
                        {
                            "id": "vet",
                            "nome": "Vet",
                            "modo": "comissao_com_piso_diario",
                            "config": {
                                "percentual_comissao": 0.1,
                                "piso_diario": 150,
                                "base_categories": ["producao_vet"],
                            },
                        },
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )

            (period_dir / "lancamentos.json").write_text(
                json.dumps(
                    [
                        {
                            "colaborador_id": "clt",
                            "categoria": "valor_importado",
                            "valor": 1000,
                        },
                        {
                            "colaborador_id": "clt",
                            "categoria": "adiantamento",
                            "valor": 100,
                        },
                        {
                            "colaborador_id": "free",
                            "categoria": "horas_trabalhadas",
                            "quantidade": 8,
                        },
                        {
                            "colaborador_id": "free",
                            "categoria": "bonus_manual",
                            "valor": 50,
                        },
                        {
                            "colaborador_id": "vet",
                            "categoria": "producao_vet",
                            "data": "2026-04-01",
                            "valor": 1000,
                        },
                        {
                            "colaborador_id": "vet",
                            "categoria": "producao_vet",
                            "data": "2026-04-02",
                            "valor": 3000,
                        },
                        {
                            "colaborador_id": "vet",
                            "categoria": "consumo_em_aberto",
                            "valor": 50,
                        },
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = calculate_period(period_dir)

            self.assertEqual(result["resumo"]["bruto_total"], "1700.00")
            self.assertEqual(result["resumo"]["descontos_total"], "150.00")
            self.assertEqual(result["resumo"]["liquido_total"], "1550.00")

            employee_map = {item["id"]: item for item in result["colaboradores"]}
            self.assertEqual(employee_map["clt"]["liquido"], "900.00")
            self.assertEqual(employee_map["free"]["liquido"], "250.00")
            self.assertEqual(employee_map["vet"]["liquido"], "400.00")

            output_dir = write_outputs(period_dir, result)
            self.assertTrue((output_dir / "resultado.json").exists())
            self.assertTrue((output_dir / "resultado.csv").exists())
            self.assertTrue((output_dir / "resultado.md").exists())
            self.assertTrue((output_dir / "memoria_calculo.csv").exists())

    def test_daily_floor_applies_only_to_responsible_vet_from_scale(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            period_dir = Path(tmp_dir) / "2026-04"
            init_period_directory(period_dir, period="2026-04", company="PinkBlue Vet", force=True)

            (period_dir / "colaboradores.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "vet_responsavel",
                            "nome": "Vet Responsavel",
                            "modo": "comissao_com_piso_diario",
                            "config": {
                                "percentual_comissao": 0.1,
                                "piso_diario": 150,
                                "base_categories": ["producao_vet"],
                            },
                        },
                        {
                            "id": "vet_apoio",
                            "nome": "Vet Apoio",
                            "modo": "comissao_com_piso_diario",
                            "config": {
                                "percentual_comissao": 0.1,
                                "piso_diario": 150,
                                "base_categories": ["producao_vet"],
                            },
                        },
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )

            (period_dir / "lancamentos.json").write_text(
                json.dumps(
                    [
                        {
                            "colaborador_id": "vet_responsavel",
                            "categoria": "producao_vet",
                            "data": "2026-04-01",
                            "valor": 500,
                        },
                        {
                            "colaborador_id": "vet_apoio",
                            "categoria": "producao_vet",
                            "data": "2026-04-01",
                            "valor": 1000,
                        },
                        {
                            "colaborador_id": "vet_apoio",
                            "categoria": "producao_vet",
                            "data": "2026-04-02",
                            "valor": 3000,
                        },
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )

            (period_dir / "escalas.json").write_text(
                json.dumps(
                    [
                        {
                            "data": "2026-04-01",
                            "colaborador_id": "vet_responsavel",
                            "tipo": "responsavel",
                            "piso_minimo": 150,
                        },
                        {
                            "data": "2026-04-02",
                            "colaborador_id": "vet_apoio",
                            "tipo": "responsavel",
                            "piso_minimo": 150,
                        },
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = calculate_period(period_dir)
            employee_map = {item["id"]: item for item in result["colaboradores"]}

            self.assertEqual(employee_map["vet_responsavel"]["bruto"], "150.00")
            self.assertEqual(employee_map["vet_apoio"]["bruto"], "400.00")

            responsavel_line = employee_map["vet_responsavel"]["proventos"][0]
            apoio_first_day = employee_map["vet_apoio"]["proventos"][0]
            apoio_second_day = employee_map["vet_apoio"]["proventos"][1]

            self.assertEqual(responsavel_line["detalhes"]["pagamento_por"], "piso")
            self.assertEqual(responsavel_line["detalhes"]["situacao_escala"], "responsavel")
            self.assertEqual(apoio_first_day["detalhes"]["piso_elegivel"], "0.00")
            self.assertEqual(apoio_first_day["detalhes"]["situacao_escala"], "sem_piso")
            self.assertEqual(apoio_second_day["detalhes"]["pagamento_por"], "comissao")
            self.assertEqual(apoio_second_day["detalhes"]["situacao_escala"], "responsavel")


if __name__ == "__main__":
    unittest.main()
