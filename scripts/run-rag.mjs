import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const backend = resolve(root, 'backend');
const python = process.env.RAG_PYTHON || resolve(backend,
  process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
const commands = {
  servir: ['scripts/servir.py'],
  preparar: ['scripts/preparar_modelos.py'],
  indexar: ['scripts/05_indexar.py'],
  conferir: ['scripts/06_conferir.py'],
  migrar: ['scripts/07_migrar_supabase.py'],
  perguntar: ['scripts/perguntar.py'],
  testar: ['-m', 'pytest', '-q'],
};
const command = commands[process.argv[2]];
if (!command) {
  console.error('Comando RAG desconhecido. Use os scripts npm documentados no README.');
  process.exit(1);
}
if (!process.env.RAG_PYTHON && !existsSync(python)) {
  console.error('Crie backend/.venv e instale backend/requirements.txt, conforme o README.');
  process.exit(1);
}
const args = process.argv.slice(3);
const envIndex = args.indexOf('--env-file');
if (envIndex !== -1) {
  if (!args[envIndex + 1] || args[envIndex + 1].startsWith('--')) {
    console.error('Informe um caminho depois de --env-file.');
    process.exit(1);
  }
  // O usuário fornece o caminho a partir do terminal, antes de entrar no backend.
  args[envIndex + 1] = resolve(process.cwd(), args[envIndex + 1]);
}
const env = { ...process.env, PYTHONIOENCODING: 'utf-8' };
if (process.argv[2] === 'testar' && !args.some(arg => arg.startsWith('--basetemp'))) {
  // Isola temporários de execuções feitas por usuários diferentes no Windows.
  const cache = resolve(root, '.cache', 'pytest');
  mkdirSync(cache, { recursive: true });
  env.PYTEST_DEBUG_TEMPROOT = mkdtempSync(resolve(cache, 'run-'));
}
const child = spawn(python, [...command, ...args], {
  cwd: backend, stdio: 'inherit', shell: false,
  env,
});
child.on('error', error => {
  console.error(`Não foi possível iniciar o Python do RAG: ${error.message}`);
  process.exitCode = 1;
});
child.on('exit', code => { process.exitCode = code ?? 1; });
