import * as fs from 'fs';
import * as path from 'path';
import { Colaborador, ExtractedEntry } from '../types';

const TEXT_EXTENSIONS = new Set(['.txt', '.csv', '.json', '.md', '.tsv', '.xlsx', '.xls']);

export function canNormalizeText(evidence: { extension: string }): boolean {
  return TEXT_EXTENSIONS.has(evidence.extension.toLowerCase());
}

export interface NormalizationResult {
  entries: ExtractedEntry[];
  warnings: string[];
  needsHumanReview: boolean;
}

export async function normalizeEvidence(
  absoluteFilePath: string,
  profile: string,
  promptObjective: string,
  colaboradores: Colaborador[],
): Promise<NormalizationResult> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    throw new Error(
      'Variável ANTHROPIC_API_KEY não configurada.\n' +
      'Configure com: set ANTHROPIC_API_KEY=sk-ant-... (Windows)\n' +
      'ou export ANTHROPIC_API_KEY=sk-ant-... (Linux/Mac)',
    );
  }

  const ext = path.extname(absoluteFilePath).toLowerCase();
  if (!TEXT_EXTENSIONS.has(ext)) {
    throw new Error(
      `Arquivo binário (${ext}) — processamento por OCR não disponível nesta versão.\n` +
      'Adicione os lançamentos manualmente via lancamentos.json.',
    );
  }

  let content: string;
  try {
    content = fs.readFileSync(absoluteFilePath, 'utf-8');
  } catch {
    throw new Error('Não foi possível ler o arquivo. Verifique se está acessível.');
  }

  const filename = path.basename(absoluteFilePath);
  const colaboradoresList = colaboradores
    .map((c) => `  - id: "${c.id}", nome: "${c.nome}", modo: "${c.modo}"`)
    .join('\n');

  // Dynamic import to avoid CJS/ESM issues at module load time
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const Anthropic = require('@anthropic-ai/sdk').default ?? require('@anthropic-ai/sdk');
  const client = new Anthropic({ apiKey });

  const response = await client.messages.create({
    model: 'claude-haiku-4-5-20251001',
    max_tokens: 2000,
    system:
      'Você é um extrator especializado em dados de folha de pagamento para clínicas veterinárias brasileiras. Responda APENAS com JSON válido, sem markdown nem texto extra.',
    messages: [
      {
        role: 'user',
        content: `Perfil: ${profile}
Objetivo: ${promptObjective}
Arquivo: ${filename}

Colaboradores cadastrados:
${colaboradoresList}

Categorias de proventos: valor_importado, horas_trabalhadas, comissao_tosa, producao_vet, bonus_manual, credito_manual, reembolso
Categorias de descontos: adiantamento, consumo_em_aberto, falha_veterinaria, desconto_manual

Conteúdo do arquivo:
${content.slice(0, 6000)}

Retorne SOMENTE este JSON:
{
  "entries": [
    {
      "colaborador_id": "id_aqui",
      "categoria": "categoria_aqui",
      "valor": 0.0,
      "quantidade": null,
      "data": "YYYY-MM-DD",
      "descricao": "descricao_aqui",
      "fonte": "${filename}",
      "confidence": "high",
      "notes": null
    }
  ],
  "warnings": [],
  "needs_human_review": false
}`,
      },
    ],
  });

  const text =
    response.content[0].type === 'text' ? (response.content[0].text as string).trim() : '{}';

  let parsed: {
    entries?: ExtractedEntry[];
    warnings?: string[];
    needs_human_review?: boolean;
  };

  try {
    parsed = JSON.parse(text);
  } catch {
    const match = text.match(/\{[\s\S]*\}/);
    if (!match) throw new Error('IA retornou resposta inválida. Tente novamente.');
    parsed = JSON.parse(match[0]);
  }

  return {
    entries: (parsed.entries ?? []).map((e: ExtractedEntry) => ({
      ...e,
      valor: e.valor != null ? parseFloat(String(e.valor)) : undefined,
      quantidade: e.quantidade != null ? parseFloat(String(e.quantidade)) : undefined,
    })),
    warnings: parsed.warnings ?? [],
    needsHumanReview: parsed.needs_human_review ?? true,
  };
}
