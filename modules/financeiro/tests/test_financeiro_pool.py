import tempfile
import unittest
from pathlib import Path

from modules.financeiro.pool import index_evidence_pool, init_competency_workspace


class FinanceiroPoolTests(unittest.TestCase):
    def test_index_evidence_pool_builds_profiles_and_queue(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            period_dir = Path(tmp_dir) / "2026-04"
            init_competency_workspace(period_dir, period="2026-04", company="PinkBlue Vet", force=True)

            (period_dir / "pool" / "inbox" / "contabilidade" / "folha.pdf").write_bytes(b"%PDF-1.7")
            (period_dir / "pool" / "inbox" / "simplesvet" / "base-comissoes.xlsx").write_bytes(b"xlsx")
            (period_dir / "pool" / "inbox" / "whatsapp" / "batidas.txt").write_text(
                "Pedro: 08:00 12:00 13:30 18:10",
                encoding="utf-8",
            )
            (period_dir / "pool" / "inbox" / "imagens" / "ponto.jpg").write_bytes(b"fake-jpeg")

            summary = index_evidence_pool(period_dir)

            self.assertEqual(summary["indexed"], 4)
            self.assertEqual(summary["profiles"]["folha_contabilidade_pdf"], 1)
            self.assertEqual(summary["profiles"]["comissao_itemizada"], 1)
            self.assertEqual(summary["profiles"]["whatsapp_texto"], 1)
            self.assertEqual(summary["profiles"]["imagem_ocr"], 1)

            queue_path = period_dir / "pool" / "fila_normalizacao.json"
            self.assertTrue(queue_path.exists())


if __name__ == "__main__":
    unittest.main()
