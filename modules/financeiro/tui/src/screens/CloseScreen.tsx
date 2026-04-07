import React, { useEffect, useState } from 'react';
import { Box, Text, useInput } from 'ink';
import Spinner from 'ink-spinner';
import { runFechar } from '../lib/runner';

interface Props {
  dir: string;
  onBack: () => void;
  onViewResults: () => void;
}

export default function CloseScreen({ dir, onBack, onViewResults }: Props) {
  const [status, setStatus] = useState<'running' | 'done' | 'error'>('running');
  const [output, setOutput] = useState('');

  useEffect(() => {
    runFechar(dir).then(({ success, output: out }) => {
      setOutput(out);
      setStatus(success ? 'done' : 'error');
    });
  }, [dir]);

  useInput((_input, key) => {
    if (status === 'running') return;
    if (_input === 'v') onViewResults();
    if (_input === 'q' || key.escape) onBack();
  });

  return (
    <Box flexDirection="column" padding={1}>
      <Box
        borderStyle="round"
        borderColor={status === 'error' ? 'red' : status === 'done' ? 'green' : 'cyan'}
        flexDirection="column"
        padding={1}
        width={66}
      >
        <Text bold color="cyan"> Fechar Folha</Text>
        <Text> </Text>

        {status === 'running' && (
          <Box>
            <Text color="green">
              <Spinner type="dots" />
            </Text>
            <Text>  Calculando fechamento…</Text>
          </Box>
        )}

        {status !== 'running' && (
          <>
            <Text
              bold
              color={status === 'done' ? 'green' : 'red'}
            >
              {status === 'done' ? ' Fechamento concluído' : ' Erro no fechamento'}
            </Text>
            <Text> </Text>
            <Box borderStyle="single" borderColor="dim" padding={1} flexDirection="column">
              {output.split('\n').map((line, i) => (
                <Text key={i} color={line.startsWith('-') ? 'yellow' : 'white'}>
                  {line}
                </Text>
              ))}
            </Box>
            <Text> </Text>
            <Text color="dim">
              {status === 'done'
                ? '  v ver resultados   q voltar'
                : '  q voltar'}
            </Text>
          </>
        )}
      </Box>
    </Box>
  );
}
