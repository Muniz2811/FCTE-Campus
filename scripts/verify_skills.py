"""Confere integridade e recursos essenciais das skills instaladas, sem rede."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
if os.name == 'nt':
    ROOT = Path('\\\\?\\' + str(ROOT))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = json.loads((ROOT/'tooling/skills.lock.json').read_text(encoding='utf-8'))
    errors = []
    names = set()
    skills = 0
    files = 0
    for source in manifest['sources']:
        errors.extend(str(error) for error in source.get('errors', []))
        for skill in source['installed']:
            skills += 1
            folder = (ROOT/skill['path']).resolve()
            if not folder.is_relative_to((ROOT/'.agents/skills').resolve()):
                errors.append(f"Destino fora das skills: {skill['path']}")
                continue
            text = (folder/'SKILL.md').read_text(encoding='utf-8')
            found = re.search(r'^name:\s*[\"\']?([a-z0-9-]+)', text, re.MULTILINE)
            if not text.startswith('---') or not found:
                errors.append(f"Metadados ausentes: {skill['name']}")
            elif found[1] in names:
                errors.append(f"Nome de skill duplicado: {found[1]}")
            else:
                names.add(found[1])
            for relative, expected in skill['files'].items():
                path = (folder/relative).resolve()
                if not path.is_relative_to(folder) or not path.is_file():
                    errors.append(f"Arquivo ausente/inválido: {skill['name']}/{relative}")
                elif digest(path) != expected:
                    errors.append(f"Hash divergente: {skill['name']}/{relative}")
                files += 1
    essential = [
        'stageshow/references/motion.md', 'stageshow/scripts/film.mjs',
        'impeccable/reference/new-work.md', 'impeccable/reference/craft-floor.md',
        'ui-ux-pro-max/scripts/search.py', 'ui-ux-pro-max/data/styles.csv',
        'shared/methodology.md', 'legacy-modernizer/references/strangler-fig-pattern.md',
        'improve-codebase-architecture/HTML-REPORT.md',
    ]
    for relative in essential:
        if not (ROOT/'.agents/skills'/relative).is_file():
            errors.append(f'Recurso essencial ausente: {relative}')
    print(f'{skills} skills; {files} arquivos conferidos; {len(errors)} pendências.')
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
