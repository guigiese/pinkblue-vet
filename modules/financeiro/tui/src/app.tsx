import React, { useState } from 'react';
import { Box } from 'ink';
import HomeScreen from './screens/HomeScreen';
import ResultsScreen from './screens/ResultsScreen';
import PoolScreen from './screens/PoolScreen';
import CloseScreen from './screens/CloseScreen';
import HelpScreen from './screens/HelpScreen';

type Screen = 'home' | 'results' | 'pool' | 'close' | 'help';

interface Props {
  dir: string;
}

export default function App({ dir }: Props) {
  const [screen, setScreen] = useState<Screen>('home');

  return (
    <Box flexDirection="column">
      {screen === 'home' && (
        <HomeScreen dir={dir} onNavigate={(s) => setScreen(s as Screen)} />
      )}
      {screen === 'results' && (
        <ResultsScreen
          dir={dir}
          onBack={() => setScreen('home')}
          onRecalculate={() => setScreen('close')}
        />
      )}
      {screen === 'pool' && (
        <PoolScreen dir={dir} onBack={() => setScreen('home')} />
      )}
      {screen === 'close' && (
        <CloseScreen
          dir={dir}
          onBack={() => setScreen('home')}
          onViewResults={() => setScreen('results')}
        />
      )}
      {screen === 'help' && <HelpScreen onBack={() => setScreen('home')} />}
    </Box>
  );
}
