import { spawn } from 'child_process';

function runAsync(
  args: string[],
): Promise<{ success: boolean; output: string }> {
  return new Promise((resolve) => {
    const proc = spawn('python', args, {
      cwd: process.cwd(),
      shell: true,
    });
    let output = '';
    proc.stdout?.on('data', (d: Buffer) => {
      output += d.toString();
    });
    proc.stderr?.on('data', (d: Buffer) => {
      output += d.toString();
    });
    proc.on('close', (code) => {
      resolve({ success: code === 0, output: output.trim() });
    });
    proc.on('error', (err) => {
      resolve({ success: false, output: `Erro ao iniciar Python: ${err.message}` });
    });
  });
}

export function runFechar(dir: string): Promise<{ success: boolean; output: string }> {
  return runAsync(['-m', 'modules.financeiro', 'fechar', dir]);
}

export function runIndexar(dir: string): Promise<{ success: boolean; output: string }> {
  return runAsync(['-m', 'modules.financeiro', 'indexar-pool', dir]);
}
