import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = resolve(root, process.argv[2] ?? 'data/imports/campus/evidencias.json');
const raw = await readFile(source);
const data = JSON.parse(raw.toString('utf8'));
if (!Array.isArray(data.points) || !data.points.length) throw new Error('Exportação sem pontos');
const ids = new Set();
const classify = point => {
  if (['building_entry', 'campus_access'].includes(point.kind)) return 'entrance';
  if (point.kind === 'building_reference_point') return 'building';
  if (point.kind === 'parking') return 'parking';
  if (['outdoor_area', 'sports_area'].includes(point.kind)) return 'outdoor';
  if (/lab/i.test(point.name)) return 'laboratory';
  return 'service';
};
const places = data.points.map(point => {
  if (typeof point.id !== 'string' || !point.id || typeof point.name !== 'string' || !point.name.trim()) throw new Error('Ponto sem identificação');
  if (ids.has(point.id)) throw new Error(`ID duplicado: ${point.id}`);
  ids.add(point.id);
  const [longitude, latitude] = point.coordinates ?? [];
  // Esta importação é do campus Gama: também detecta eixos trocados, ambos válidos globalmente.
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude) ||
    latitude < -16.1 || latitude > -15.8 || longitude < -48.2 || longitude > -47.8) {
    throw new Error(`Coordenada fora do campus Gama: ${point.id}`);
  }
  return {
    id: point.id, name: point.name, category: classify(point),
    coordinate: { latitude, longitude }, description: point.description ?? '',
    sourceId: 'MAP-001', sourceLabel: 'Mapeamento da equipe · KML',
    eligibleForPilot: point.eligible === true,
    buildingId: point.building_id ?? null, candidateBuildingId: point.candidate_building_id ?? null,
  };
});
const output = resolve(root, 'src/campus/infrastructure/campus.json');
await mkdir(dirname(output), { recursive: true });
await writeFile(output, `${JSON.stringify({
  source: { id: 'MAP-001', label: 'Mapeamento da equipe · KML',
    exportDate: data.exported_at, sha256: createHash('sha256').update(raw).digest('hex'),
    origin: 'data/imports/campus/evidencias.json',
    limitations: 'Pontos de referência, sem contorno, verificação de acesso atual ou rotas.' },
  places,
}, null, 2)}\n`, 'utf8');
console.log(`${places.length} locais importados. Snapshot público independente da pasta de origem.`);
