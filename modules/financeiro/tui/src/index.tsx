import React from 'react';
import { render } from 'ink';
import * as path from 'path';
import App from './app';

const args = process.argv.slice(2);
let competenciaDir = args[0];

if (!competenciaDir) {
  competenciaDir = 'runtime-data/financeiro/competencias/2026-04';
} else if (!path.isAbsolute(competenciaDir) && /^\d{4}-\d{2}$/.test(competenciaDir)) {
  // accept bare period like "2026-04"
  competenciaDir = `runtime-data/financeiro/competencias/${competenciaDir}`;
}

render(<App dir={competenciaDir} />);
