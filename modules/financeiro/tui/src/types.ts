export interface CalculationLine {
  categoria: string;
  descricao: string;
  valor: string;
  detalhes?: Record<string, string>;
}

export interface ColaboradorResult {
  id: string;
  nome: string;
  modo: string;
  bruto: string;
  descontos: string;
  liquido: string;
  proventos: CalculationLine[];
  descontos_detalhados: CalculationLine[];
  avisos: string[];
}

export interface FolhaResult {
  periodo: string;
  empresa: string;
  moeda: string;
  resumo: {
    colaboradores: number;
    bruto_total: string;
    descontos_total: string;
    liquido_total: string;
  };
  avisos: string[];
  colaboradores: ColaboradorResult[];
  fontes_brutas: unknown[];
}

export interface Evidence {
  sha256: string;
  relative_path: string;
  bucket: string;
  filename: string;
  extension: string;
  mime_type: string;
  size_bytes: number;
  profile: string;
  target_schema: string;
  prompt_objective: string;
  status: string;
  review_status: string;
  normalizado_em?: string | null;
}

export interface Colaborador {
  id: string;
  nome: string;
  modo: string;
  config: Record<string, unknown>;
}

export interface Lancamento {
  colaborador_id: string;
  categoria: string;
  valor?: number;
  quantidade?: number;
  data?: string;
  descricao: string;
  fonte: string;
}

export interface ExtractedEntry extends Lancamento {
  confidence: 'high' | 'medium' | 'low';
  notes?: string | null;
}

export interface PeriodoMeta {
  periodo: string;
  empresa: string;
  moeda: string;
}
