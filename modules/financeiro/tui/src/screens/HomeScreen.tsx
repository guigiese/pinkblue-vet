import React, { useEffect, useState } from 'react';
import { Box, Text, useApp } from 'ink';
import SelectInput from 'ink-select-input';
import {
  readColaboradores,
  readLancamentos,
  readMeta,
  readPool,
  resultsExist,
  poolExists,
} from '../lib/data';

type Screen = 'home' | 'results' | 'pool' | 'close' | 'help';

interface Props {
  dir: string;
  onNavigate: (screen: Screen) => void;
}

interface Stats {
  periodo: string;
  empresa: string;
  colaboradores: number;
  lancamentos: number;
  poolItems: number;
  poolPending: number;
  hasResults: boolean;
  hasPool: boolean;
}

export default function HomeScreen({ dir, onNavigate }: Props) {
  const { exit } = useApp();
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    const meta = readMeta(dir);
    const colaboradores = readColaboradores(dir);
    const lancamentos = readLancamentos(dir);
    const pool = readPool(dir);
    const pending = pool.filter((e) => e.review_status === 'pendente');
    setStats({
      periodo: meta?.periodo ?? '—',
      empresa: meta?.empresa ?? '—',
      colaboradores: colaboradores.length,
      lancamentos: lancamentos.length,
      poolItems: pool.length,
      poolPending: pending.length,
      hasResults: resultsExist(dir),
      hasPool: poolExists(dir),
    });
  }, [dir]);

  const items = [
    {
      label: stats?.hasResults
        ? `Ver resultados do fechamento  (${stats.colaboradores} colaboradores)`
        : 'Ver resultados do fechamento  (ainda não calculado)',
      value: 'results' as Screen,
    },
    {
      label: stats?.hasPool
        ? `Pool de evidências  (${stats?.poolItems ?? 0} arq · ${stats?.poolPending ?? 0} pendentes)`
        : 'Pool de evidências  (não inicializado)',
      value: 'pool' as Screen,
    },
    {
      label: `Fechar folha  ${stats?.hasResults ? '(recalcular)' : '(calcular agora)'}`,
      value: 'close' as Screen,
    },
    { label: 'Ajuda e atalhos', value: 'help' as Screen },
    { label: 'Sair', value: 'quit' as Screen },
  ];

  function handleSelect(item: { value: string }) {
    if (item.value === 'quit') {
      exit();
      return;
    }
    onNavigate(item.value as Screen);
  }

  return (
    <Box flexDirection="column" padding={1}>
      <Box
        borderStyle="round"
        borderColor="cyan"
        flexDirection="column"
        padding={1}
        width={62}
      >
        <Text bold color="cyan">
          {' '}PinkBlue Vet · Folha de Pagamento
        </Text>
        <Text> </Text>
        <Box flexDirection="row" gap={4}>
          <Text color="dim">
            Competência: <Text color="white">{stats?.periodo ?? '…'}</Text>
          </Text>
          <Text color="dim">
            Empresa: <Text color="white">{stats?.empresa ?? '…'}</Text>
          </Text>
        </Box>
        <Box flexDirection="row" gap={4} marginTop={0}>
          <Text color="dim">
            Colaboradores: <Text color="white">{stats?.colaboradores ?? '…'}</Text>
          </Text>
          <Text color="dim">
            Lançamentos: <Text color="white">{stats?.lancamentos ?? '…'}</Text>
          </Text>
        </Box>
        <Text> </Text>
        <SelectInput items={items} onSelect={handleSelect} />
        <Text> </Text>
        <Text color="dim" dimColor>  ↑↓ navegar  Enter selecionar</Text>
      </Box>
    </Box>
  );
}
