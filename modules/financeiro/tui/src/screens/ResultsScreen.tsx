import React, { useEffect, useState } from 'react';
import { Box, Text, useInput } from 'ink';
import { readResult, formatMoney, modeName } from '../lib/data';
import { ColaboradorResult, FolhaResult } from '../types';

interface Props {
  dir: string;
  onBack: () => void;
  onRecalculate: () => void;
}

function pad(s: string, n: number): string {
  return s.length >= n ? s.slice(0, n) : s + ' '.repeat(n - s.length);
}

function rpad(s: string, n: number): string {
  return s.length >= n ? s.slice(0, n) : ' '.repeat(n - s.length) + s;
}

function DetailPanel({ emp }: { emp: ColaboradorResult }) {
  return (
    <Box flexDirection="column" padding={1}>
      <Text bold color="cyan">
        {emp.nome}
      </Text>
      <Text color="dim">  Modo: {modeName(emp.modo)}</Text>
      <Text>
        {'  '}Bruto: <Text color="green">{formatMoney(emp.bruto)}</Text>
        {'  '}Descontos: <Text color="red">{formatMoney(emp.descontos)}</Text>
        {'  '}Líquido: <Text bold color="white">{formatMoney(emp.liquido)}</Text>
      </Text>
      {emp.proventos.length > 0 && (
        <>
          <Text> </Text>
          <Text color="dim">  Proventos:</Text>
          {emp.proventos.map((p, i) => (
            <Text key={i} color="green">
              {'    • '}{p.descricao}: {formatMoney(p.valor)}
            </Text>
          ))}
        </>
      )}
      {emp.descontos_detalhados.length > 0 && (
        <>
          <Text color="dim">  Descontos:</Text>
          {emp.descontos_detalhados.map((d, i) => (
            <Text key={i} color="red">
              {'    • '}{d.descricao}: {formatMoney(d.valor)}
            </Text>
          ))}
        </>
      )}
      {emp.avisos.length > 0 && (
        <>
          <Text color="dim">  Avisos:</Text>
          {emp.avisos.map((a, i) => (
            <Text key={i} color="yellow">
              {'    ⚠ '}{a}
            </Text>
          ))}
        </>
      )}
    </Box>
  );
}

export default function ResultsScreen({ dir, onBack, onRecalculate }: Props) {
  const [result, setResult] = useState<FolhaResult | null>(null);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [showDetail, setShowDetail] = useState(false);

  useEffect(() => {
    setResult(readResult(dir));
  }, [dir]);

  useInput((_input, key) => {
    if (!result) {
      if (_input === 'q' || key.escape) onBack();
      if (_input === 'r') onRecalculate();
      return;
    }
    const len = result.colaboradores.length;
    if (showDetail) {
      if (key.escape || _input === 'q') setShowDetail(false);
      return;
    }
    if (key.upArrow) setSelectedIdx((i) => Math.max(0, i - 1));
    if (key.downArrow) setSelectedIdx((i) => Math.min(len - 1, i + 1));
    if (key.return) setShowDetail(true);
    if (_input === 'r') onRecalculate();
    if (_input === 'q' || key.escape) onBack();
  });

  if (!result) {
    return (
      <Box flexDirection="column" padding={1}>
        <Box borderStyle="round" borderColor="yellow" padding={1} flexDirection="column">
          <Text color="yellow"> Nenhum fechamento calculado ainda.</Text>
          <Text> </Text>
          <Text color="dim">  r calcular agora   q voltar</Text>
        </Box>
      </Box>
    );
  }

  const emp = result.colaboradores[selectedIdx];

  return (
    <Box flexDirection="column" padding={1}>
      <Box borderStyle="round" borderColor="cyan" flexDirection="column" padding={1} width={68}>
        <Text bold color="cyan"> Fechamento {result.periodo} · {result.empresa}</Text>
        <Text> </Text>
        <Box flexDirection="row" gap={3}>
          <Text>Bruto: <Text color="green" bold>{formatMoney(result.resumo.bruto_total)}</Text></Text>
          <Text>Descontos: <Text color="red">{formatMoney(result.resumo.descontos_total)}</Text></Text>
          <Text>Líquido: <Text color="white" bold>{formatMoney(result.resumo.liquido_total)}</Text></Text>
        </Box>
        <Text> </Text>

        {result.avisos.length > 0 && (
          <>
            {result.avisos.map((a, i) => (
              <Text key={i} color="yellow">  ⚠ {a}</Text>
            ))}
            <Text> </Text>
          </>
        )}

        {!showDetail && (
          <>
            <Text color="dim">
              {'  '}{pad('Nome', 22)}{pad('Modo', 15)}{rpad('Bruto', 11)}{rpad('Desc.', 9)}{rpad('Líquido', 10)}
            </Text>
            <Text color="dim">  {'─'.repeat(64)}</Text>
            {result.colaboradores.map((c, i) => (
              <Text key={c.id} color={i === selectedIdx ? 'cyan' : 'white'}>
                {i === selectedIdx ? ' ▶' : '  '}
                {' '}{pad(c.nome, 21)}
                {' '}{pad(modeName(c.modo), 14)}
                {rpad(formatMoney(c.bruto), 11)}
                {rpad(formatMoney(c.descontos), 9)}
                {rpad(formatMoney(c.liquido), 10)}
                {c.avisos.length > 0 ? <Text color="yellow"> ⚠</Text> : null}
              </Text>
            ))}
            <Text> </Text>
            <Text color="dim">  ↑↓ navegar  Enter detalhar  r recalcular  q voltar</Text>
          </>
        )}

        {showDetail && emp && (
          <>
            <DetailPanel emp={emp} />
            <Text> </Text>
            <Text color="dim">  Esc / q voltar à lista</Text>
          </>
        )}
      </Box>
    </Box>
  );
}
