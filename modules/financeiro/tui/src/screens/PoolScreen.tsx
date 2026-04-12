import React, { useCallback, useEffect, useState } from 'react';
import { Box, Text, useInput } from 'ink';
import Spinner from 'ink-spinner';
import TextInput from 'ink-text-input';
import SelectInput from 'ink-select-input';
import {
  absoluteFilePath,
  acceptEvidenceEntries,
  readColaboradores,
  readPool,
  rejectEvidence,
  writePool,
} from '../lib/data';
import { runIndexar } from '../lib/runner';
import { canNormalizeText, normalizeEvidence, NormalizationResult } from '../lib/normalizer';
import { Colaborador, Evidence, ExtractedEntry } from '../types';

type Mode = 'list' | 'indexing' | 'processing' | 'review' | 'editing';

const EARNING_CATS = [
  'valor_importado','horas_trabalhadas','producao_vet',
  'comissao_tosa','bonus_manual','credito_manual','reembolso',
];
const DISCOUNT_CATS = [
  'adiantamento','consumo_em_aberto','falha_veterinaria','desconto_manual',
];
const ALL_CATS = [...EARNING_CATS, ...DISCOUNT_CATS];

const EDIT_FIELDS = ['colaborador_id', 'categoria', 'valor', 'quantidade', 'data', 'descricao'] as const;
type EditField = typeof EDIT_FIELDS[number];
const SELECT_FIELDS = new Set<EditField>(['colaborador_id', 'categoria']);

function statusColor(s: string): string {
  if (s === 'aceito' || s === 'processado') return 'green';
  if (s === 'rejeitado') return 'red';
  return 'yellow';
}

function confidenceDots(c: 'high' | 'medium' | 'low'): string {
  if (c === 'high') return '●●●';
  if (c === 'medium') return '●●○';
  return '●○○';
}

function confidenceColor(c: 'high' | 'medium' | 'low'): string {
  if (c === 'high') return 'green';
  if (c === 'medium') return 'yellow';
  return 'red';
}

interface Props {
  dir: string;
  onBack: () => void;
}

export default function PoolScreen({ dir, onBack }: Props) {
  const [mode, setMode] = useState<Mode>('list');
  const [items, setItems] = useState<Evidence[]>([]);
  const [colaboradores, setColaboradores] = useState<Colaborador[]>([]);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [statusMsg, setStatusMsg] = useState('');
  const [error, setError] = useState('');
  const [warnings, setWarnings] = useState<string[]>([]);

  // review state
  const [entries, setEntries] = useState<ExtractedEntry[]>([]);
  const [reviewIdx, setReviewIdx] = useState(0);
  const [currentSha, setCurrentSha] = useState('');

  // editing state
  const [editIdx, setEditIdx] = useState(0); // which entry being edited
  const [editFieldIdx, setEditFieldIdx] = useState(0); // which field
  const [editValues, setEditValues] = useState<Record<string, string>>({});
  const [activeInput, setActiveInput] = useState(false);

  const reload = useCallback(() => {
    setItems(readPool(dir));
    setColaboradores(readColaboradores(dir));
  }, [dir]);

  useEffect(() => {
    reload();
  }, [reload]);

  const currentItem = items[selectedIdx];

  // ── key handler ─────────────────────────────────────────────────────────
  useInput((input, key) => {
    if (activeInput) return;

    if (mode === 'list') {
      if (key.upArrow) setSelectedIdx((i) => Math.max(0, i - 1));
      if (key.downArrow) setSelectedIdx((i) => Math.min(items.length - 1, i + 1));
      if (key.escape || input === 'q') onBack();
      if (input === 'i') handleIndex();
      if (input === 'p' && currentItem) handleProcess(currentItem);
      if (input === 'a' && currentItem) handleAcceptDirect(currentItem);
      if (input === 'x' && currentItem) {
        rejectEvidence(dir, currentItem.sha256);
        reload();
        setStatusMsg(`Rejeitado: ${currentItem.filename}`);
      }
    }

    if (mode === 'review') {
      if (key.upArrow) setReviewIdx((i) => Math.max(0, i - 1));
      if (key.downArrow) setReviewIdx((i) => Math.min(entries.length - 1, i + 1));
      if (input === 'e') startEdit(reviewIdx);
      if (input === 'a') acceptAll();
      if (input === 'x') {
        rejectEvidence(dir, currentSha);
        reload();
        setMode('list');
      }
      if (key.escape || input === 'q') setMode('list');
    }

    if (mode === 'editing') {
      if (key.upArrow) setEditFieldIdx((i) => Math.max(0, i - 1));
      if (key.downArrow) setEditFieldIdx((i) => Math.min(EDIT_FIELDS.length - 1, i + 1));
      if (key.return) setActiveInput(true);
      if (input === 's') saveEdit();
      if (key.escape) setMode('review');
    }
  });

  // ── handlers ────────────────────────────────────────────────────────────
  function handleIndex() {
    setMode('indexing');
    setStatusMsg('');
    setError('');
    runIndexar(dir).then(({ success, output }) => {
      if (success) {
        reload();
        setStatusMsg(output.split('\n')[0] || 'Pool indexado.');
      } else {
        setError(output);
      }
      setMode('list');
    });
  }

  function handleProcess(item: Evidence) {
    setError('');
    setStatusMsg('');
    if (!canNormalizeText(item)) {
      setError(
        `${item.filename} — arquivo binário. Não é possível processar via IA nesta versão.\nAdicione os lançamentos manualmente.`,
      );
      return;
    }
    setCurrentSha(item.sha256);
    setMode('processing');
    const absPath = absoluteFilePath(dir, item.relative_path);
    normalizeEvidence(absPath, item.profile, item.prompt_objective, colaboradores)
      .then((result: NormalizationResult) => {
        setEntries(result.entries);
        setWarnings(result.warnings);
        setReviewIdx(0);
        setMode('review');
      })
      .catch((err: Error) => {
        setError(err.message);
        setMode('list');
      });
  }

  function handleAcceptDirect(item: Evidence) {
    const pool = readPool(dir);
    writePool(
      dir,
      pool.map((e) =>
        e.sha256 === item.sha256
          ? { ...e, status: 'processado', review_status: 'aceito', normalizado_em: new Date().toISOString() }
          : e,
      ),
    );
    reload();
    setStatusMsg(`Aceito sem extração: ${item.filename}`);
  }

  function startEdit(entryIdx: number) {
    const e = entries[entryIdx];
    setEditIdx(entryIdx);
    setEditValues({
      colaborador_id: e.colaborador_id ?? '',
      categoria: e.categoria ?? '',
      valor: e.valor != null ? String(e.valor) : '',
      quantidade: e.quantidade != null ? String(e.quantidade) : '',
      data: e.data ?? '',
      descricao: e.descricao ?? '',
    });
    setEditFieldIdx(0);
    setActiveInput(false);
    setMode('editing');
  }

  function saveEdit() {
    const updated = entries.map((e, i) => {
      if (i !== editIdx) return e;
      return {
        ...e,
        colaborador_id: editValues['colaborador_id'],
        categoria: editValues['categoria'],
        valor: editValues['valor'] ? parseFloat(editValues['valor']) : undefined,
        quantidade: editValues['quantidade'] ? parseFloat(editValues['quantidade']) : undefined,
        data: editValues['data'] || undefined,
        descricao: editValues['descricao'],
      };
    });
    setEntries(updated);
    setMode('review');
  }

  function acceptAll() {
    acceptEvidenceEntries(dir, currentSha, entries);
    reload();
    setStatusMsg(`${entries.length} lançamento(s) adicionados a lancamentos.json`);
    setMode('list');
  }

  // ── renders ──────────────────────────────────────────────────────────────
  function renderList() {
    const pending = items.filter((e) => e.review_status === 'pendente').length;
    return (
      <>
        <Text bold color="cyan"> Pool de Evidências</Text>
        <Text color="dim">
          {' '}{items.length} arquivos · <Text color="yellow">{pending} pendentes</Text>
        </Text>
        <Text> </Text>

        {error && <Text color="red">  ✗ {error}</Text>}
        {!error && statusMsg && <Text color="green">  ✓ {statusMsg}</Text>}
        {(error || statusMsg) && <Text> </Text>}

        {items.length === 0 && (
          <Text color="dim">  Nenhuma evidência indexada. Coloque arquivos em pool/inbox/ e pressione i.</Text>
        )}
        {items.map((item, i) => {
          const needsReview = ['ponto_bruto', 'imagem_ocr', 'whatsapp_texto'].includes(item.profile);
          const selected = i === selectedIdx;
          return (
            <Box key={item.sha256} flexDirection="column">
              <Text color={selected ? 'cyan' : 'white'}>
                {selected ? ' ▶ ' : '   '}
                <Text bold={selected}>{item.filename}</Text>
              </Text>
              <Text>
                {'     '}
                <Text color="dim">{item.bucket} · {item.profile}</Text>
                {' · '}
                <Text color={statusColor(item.review_status)}>{item.review_status}</Text>
                {needsReview && item.review_status === 'pendente' && (
                  <Text color="yellow"> ⚠ revisão humana</Text>
                )}
              </Text>
            </Box>
          );
        })}
        <Text> </Text>
        <Text color="dim">  ↑↓ navegar  p processar IA  a aceitar  x rejeitar  i indexar  q voltar</Text>
      </>
    );
  }

  function renderIndexing() {
    return (
      <Box>
        <Text color="green"><Spinner type="dots" /></Text>
        <Text>  Indexando pool…</Text>
      </Box>
    );
  }

  function renderProcessing() {
    return (
      <Box>
        <Text color="green"><Spinner type="dots" /></Text>
        <Text>  Processando com IA… {items[selectedIdx]?.filename}</Text>
      </Box>
    );
  }

  function renderReview() {
    const entry = entries[reviewIdx];
    if (!entry) return null;
    const col = colaboradores.find((c) => c.id === entry.colaborador_id);
    return (
      <>
        <Text bold color="cyan"> Revisar extração</Text>
        <Text color="dim">  {reviewIdx + 1}/{entries.length} · {items.find(i => i.sha256 === currentSha)?.filename}</Text>
        {warnings.length > 0 && (
          <>
            <Text> </Text>
            {warnings.map((w, i) => <Text key={i} color="yellow">  ⚠ {w}</Text>)}
          </>
        )}
        <Text> </Text>
        <Box borderStyle="single" borderColor="dim" padding={1} flexDirection="column">
          <Text>
            <Text color="dim">colaborador:  </Text>
            <Text color="cyan">{col ? col.nome : entry.colaborador_id}</Text>
            <Text color="dim"> ({entry.colaborador_id})</Text>
          </Text>
          <Text>
            <Text color="dim">categoria:    </Text>
            <Text>{entry.categoria}</Text>
          </Text>
          {entry.valor != null && (
            <Text>
              <Text color="dim">valor:        </Text>
              <Text color="green">R$ {entry.valor.toFixed(2)}</Text>
            </Text>
          )}
          {entry.quantidade != null && (
            <Text>
              <Text color="dim">quantidade:   </Text>
              <Text>{entry.quantidade}</Text>
            </Text>
          )}
          {entry.data && (
            <Text>
              <Text color="dim">data:         </Text>
              <Text>{entry.data}</Text>
            </Text>
          )}
          <Text>
            <Text color="dim">descrição:    </Text>
            <Text>{entry.descricao}</Text>
          </Text>
          <Text>
            <Text color="dim">confidence:   </Text>
            <Text color={confidenceColor(entry.confidence)}>{confidenceDots(entry.confidence)} {entry.confidence}</Text>
          </Text>
          {entry.notes && (
            <Text>
              <Text color="dim">nota IA:      </Text>
              <Text color="yellow">{entry.notes}</Text>
            </Text>
          )}
        </Box>
        <Text> </Text>
        {entries.map((_, i) => (
          <Text key={i} color={i === reviewIdx ? 'cyan' : 'dim'}>{i === reviewIdx ? ' ▶ ' : '   '}entrada {i + 1}</Text>
        ))}
        <Text> </Text>
        <Text color="dim">  ↑↓ navegar  e editar  a aceitar todos e salvar  x rejeitar  q voltar</Text>
      </>
    );
  }

  function renderEditing() {
    const entry = entries[editIdx];
    if (!entry) return null;
    const fieldName = EDIT_FIELDS[editFieldIdx];
    const isSelect = SELECT_FIELDS.has(fieldName);

    return (
      <>
        <Text bold color="cyan"> Editar entrada {editIdx + 1}/{entries.length}</Text>
        <Text> </Text>
        {EDIT_FIELDS.map((field, fi) => {
          const isCurrent = fi === editFieldIdx;
          const val = editValues[field] || '—';
          return (
            <Box key={field}>
              <Text color={isCurrent ? 'cyan' : 'dim'}>
                {isCurrent ? ' ▶ ' : '   '}
                {(field + ':').padEnd(14)}
              </Text>
              {isCurrent && activeInput ? (
                isSelect ? null : (
                  <TextInput
                    value={editValues[field] ?? ''}
                    onChange={(v) => setEditValues((prev) => ({ ...prev, [field]: v }))}
                    onSubmit={() => setActiveInput(false)}
                    focus
                  />
                )
              ) : (
                <Text color={isCurrent ? 'white' : 'dim'}>{val}</Text>
              )}
            </Box>
          );
        })}

        {activeInput && isSelect && (
          <Box flexDirection="column" marginTop={1} marginLeft={3}>
            {fieldName === 'colaborador_id' && (
              <SelectInput
                items={colaboradores.map((c) => ({
                  label: `${c.nome} (${c.id})`,
                  value: c.id,
                }))}
                onSelect={(item) => {
                  setEditValues((prev) => ({ ...prev, colaborador_id: item.value }));
                  setActiveInput(false);
                }}
              />
            )}
            {fieldName === 'categoria' && (
              <SelectInput
                items={ALL_CATS.map((cat) => ({
                  label: cat,
                  value: cat,
                }))}
                onSelect={(item) => {
                  setEditValues((prev) => ({ ...prev, categoria: item.value }));
                  setActiveInput(false);
                }}
              />
            )}
          </Box>
        )}

        <Text> </Text>
        <Text color="dim">  ↑↓ campo  Enter editar  s salvar entrada  Esc voltar</Text>
      </>
    );
  }

  return (
    <Box flexDirection="column" padding={1}>
      <Box
        borderStyle="round"
        borderColor="cyan"
        flexDirection="column"
        padding={1}
        width={68}
      >
        {mode === 'list' && renderList()}
        {mode === 'indexing' && renderIndexing()}
        {mode === 'processing' && renderProcessing()}
        {mode === 'review' && renderReview()}
        {mode === 'editing' && renderEditing()}
      </Box>
    </Box>
  );
}
