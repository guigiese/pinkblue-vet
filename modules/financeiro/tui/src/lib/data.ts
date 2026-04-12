import * as fs from 'fs';
import * as path from 'path';
import {
  Colaborador,
  Evidence,
  ExtractedEntry,
  FolhaResult,
  Lancamento,
  PeriodoMeta,
} from '../types';

export function resolveDir(dir: string): string {
  return path.isAbsolute(dir) ? dir : path.resolve(process.cwd(), dir);
}

function readJSON<T>(filePath: string, fallback: T): T {
  if (!fs.existsSync(filePath)) return fallback;
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf-8')) as T;
  } catch {
    return fallback;
  }
}

export function readMeta(dir: string): PeriodoMeta | null {
  const p = path.join(resolveDir(dir), 'periodo.json');
  return readJSON<PeriodoMeta | null>(p, null);
}

export function readResult(dir: string): FolhaResult | null {
  const p = path.join(resolveDir(dir), 'saida', 'resultado.json');
  return readJSON<FolhaResult | null>(p, null);
}

export function readPool(dir: string): Evidence[] {
  const p = path.join(resolveDir(dir), 'pool', 'evidencias_indexadas.json');
  return readJSON<Evidence[]>(p, []);
}

export function readColaboradores(dir: string): Colaborador[] {
  const p = path.join(resolveDir(dir), 'colaboradores.json');
  return readJSON<Colaborador[]>(p, []);
}

export function readLancamentos(dir: string): Lancamento[] {
  const p = path.join(resolveDir(dir), 'lancamentos.json');
  return readJSON<Lancamento[]>(p, []);
}

export function writePool(dir: string, pool: Evidence[]): void {
  const p = path.join(resolveDir(dir), 'pool', 'evidencias_indexadas.json');
  fs.writeFileSync(p, JSON.stringify(pool, null, 2), 'utf-8');
}

export function appendLancamentos(dir: string, entries: Lancamento[]): void {
  const existing = readLancamentos(dir);
  const p = path.join(resolveDir(dir), 'lancamentos.json');
  fs.writeFileSync(p, JSON.stringify([...existing, ...entries], null, 2), 'utf-8');
}

export function acceptEvidenceEntries(
  dir: string,
  sha256: string,
  entries: ExtractedEntry[],
): void {
  const lancamentos: Lancamento[] = entries.map(
    ({ confidence: _c, notes: _n, ...rest }) => rest,
  );
  appendLancamentos(dir, lancamentos);

  const pool = readPool(dir);
  writePool(
    dir,
    pool.map((item) =>
      item.sha256 === sha256
        ? {
            ...item,
            status: 'processado',
            review_status: 'aceito',
            normalizado_em: new Date().toISOString(),
          }
        : item,
    ),
  );
}

export function rejectEvidence(dir: string, sha256: string): void {
  const pool = readPool(dir);
  writePool(
    dir,
    pool.map((item) =>
      item.sha256 === sha256
        ? { ...item, status: 'rejeitado', review_status: 'rejeitado' }
        : item,
    ),
  );
}

export function resultsExist(dir: string): boolean {
  return fs.existsSync(path.join(resolveDir(dir), 'saida', 'resultado.json'));
}

export function poolExists(dir: string): boolean {
  return fs.existsSync(path.join(resolveDir(dir), 'pool'));
}

export function absoluteFilePath(dir: string, relPath: string): string {
  return path.join(resolveDir(dir), relPath);
}

export function formatMoney(val: string | number): string {
  const n = typeof val === 'string' ? parseFloat(val) : val;
  return `R$ ${n.toLocaleString('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function modeName(mode: string): string {
  const map: Record<string, string> = {
    comissao_com_piso_diario: 'comissão+piso',
    comissao_percentual: 'comissão %',
    horista: 'horista',
    valor_importado: 'CLT/fixo',
  };
  return map[mode] || mode;
}
