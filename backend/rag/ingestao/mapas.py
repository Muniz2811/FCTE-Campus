"""Converte o inventário das plantas em fontes textuais rastreáveis do RAG."""
import json
import math
import re
import sqlite3
import subprocess
from pathlib import Path

from rag.armazenamento.manifesto import gravar_json, hash_bytes
from rag.config import caminho_projeto
from rag.ingestao.catalogo import ler_catalogo, salvar_catalogo, validar_catalogo

PREDIOS = ('uac', 'ued')
CATEGORIAS = {'sala', 'laboratorio', 'banheiro', 'escada', 'elevador', 'rampa',
              'convivencia', 'servico'}
LIMITACOES = ('Inventário do mapa da equipe, derivado de plantas e correções locais; '
              'não é confirmação de uso atual em campo. Posições e proximidades são aproximadas. '
              'Não confirma acesso liberado, ocupação, funcionamento ou acessibilidade de uma rota.')


def _ler_planta(raiz: Path, item: dict):
    arquivo = raiz / item['geojson']
    dados = arquivo.read_bytes()
    origem = {'caminho': item['geojson'], 'sha256': hash_bytes(dados)}
    documento = json.loads(dados)
    # A edição salva prevalece sobre o GeoJSON, como no serviço da coleta.
    banco = raiz / 'data/plantas.sqlite3'
    if banco.is_file():
        with sqlite3.connect(banco.resolve().as_uri() + '?mode=ro', uri=True) as db:
            linha = db.execute('SELECT doc FROM plantas WHERE id = ?', (item['id'],)).fetchone()
        if linha:
            documento = json.loads(linha[0])
            origem = {'caminho': 'data/plantas.sqlite3#' + item['id'],
                      'versao': documento['properties'].get('versao'),
                      'sha256': hash_bytes(linha[0].encode('utf-8'))}
    return documento, origem


def _distancia(a, b):
    lon1, lat1 = a['coordenadas']
    lon2, lat2 = b['coordenadas']
    return 111_320 * math.hypot((lon2 - lon1) * math.cos(math.radians(lat1)), lat2 - lat1)


def _paragrafo(ambiente, ambientes, predio, andar):
    nome, aid = ambiente['nome'], ambiente['id']
    texto = f'{nome} (identificador no mapa: {aid}), {andar} da {predio}.'
    if ambiente['categoria'] == 'banheiro':
        texto += ' Categoria: banheiro / sanitário / WC.'
        # Proximidade geométrica é referência, nunca instrução de navegação.
        referencias = [a for a in ambientes if a['categoria'] in {'escada', 'elevador', 'sala', 'laboratorio'}
                       and a['id'] != aid]
        referencias.sort(key=lambda a: (_distancia(ambiente, a), a['id']))
        proximas = [f"{a['nome']} ({a['id']})" for a in referencias[:2] if _distancia(ambiente, a) <= 25]
        if proximas:
            texto += ' Referências próximas no desenho: ' + ', '.join(proximas) + '.'
    lon, lat = ambiente['coordenadas']
    return texto + f' Ponto aproximado: latitude {lat:.7f}, longitude {lon:.7f}.'


def importar_mapas(raiz: Path, config: dict, data: str) -> dict:
    raiz = raiz.resolve()
    indice = json.loads((raiz / 'config/plantas/predios.json').read_text(encoding='utf-8'))
    itens = {p['id']: p for p in indice['predios']}
    commit = subprocess.run(['git', '-C', str(raiz), 'rev-parse', 'HEAD'],
                            capture_output=True, text=True, check=True).stdout.strip()
    fontes = ler_catalogo(caminho_projeto(config['caminhos']['catalogo']))
    novas, documentos, contagens = [], [], {}
    for pid in PREDIOS:
        item = itens[pid]
        doc, origem = _ler_planta(raiz, item)
        props = doc['properties']
        if 'estimad' in props.get('aviso', '').lower() or 'Inferido:' in props.get('observacao', ''):
            raise ValueError(f'{pid}: planta estimada exige curadoria específica antes da importação')
        andares = item.get('andares') or props['andares']
        for andar in andares:
            ambientes = []
            for feature in doc['features']:
                p = feature.get('properties') or {}
                if (p.get('tipo') != 'ambiente' or p.get('andar') != andar['nivel']
                        or p.get('categoria') not in CATEGORIAS or not p.get('nomeado')
                        or not p.get('id') or not p.get('nome')
                        or re.search(r'^(Sala sem nome|Área aberta)', p['nome'], re.I)):
                    continue
                ponto = p.get('rotulo')
                if not ponto or len(ponto) != 2 or not (-180 <= ponto[0] <= 180 and -90 <= ponto[1] <= 90):
                    raise ValueError(f'{pid}/{p["id"]}: ponto de referência inválido')
                ambientes.append({k: p[k] for k in ('id', 'nome', 'categoria', 'andar')}
                                 | {'coordenadas': ponto})
            ambientes.sort(key=lambda a: (a['categoria'], a['id']))
            if not ambientes or len({a['id'] for a in ambientes}) != len(ambientes):
                raise ValueError(f'{pid}/{andar["nivel"]}: inventário vazio ou com IDs duplicados')
            sid = f'MAP-{pid.upper()}-{andar["nivel"]}'
            titulo = f'Mapeamento interno da {item["nome"]} — {andar["nome"]}'
            snapshot = {'source_id': sid, 'predio_id': pid, 'predio': item['nome'],
                        'titulo_predio': item.get('titulo', ''), 'andar': andar,
                        'origem': origem | {'commit_coleta': commit},
                        'limitacoes': LIMITACOES, 'ambientes': ambientes}
            dados = (json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
            sha = hash_bytes(dados)
            versao = f'{data}-{sha[:8]}'
            url = ('https://github.com/Muniz2811/FCTE-Campus/blob/main/'
                   f'backend/data/imports/mapas/{sid}.json')
            fonte = {k: '' for k in fontes[0]}
            fonte.update(source_id=sid, titulo=titulo, tipo='ficha', url=url, campus='Gama',
                         abrangencia='Gama', descricao='Ambientes nomeados do mapa interno existente',
                         data_coleta=data, data_revisao=data, validade='desconhecida',
                         revisor='Equipe G09 (mapa existente; importação autorizada por Pedro)',
                         status='aprovado', motivo='Autorização para usar o mapeamento existente no RAG; sem nova vistoria em campo.',
                         sha256=sha, versao=versao, limitacoes=LIMITACOES,
                         condicoes_uso='Mapeamento próprio da equipe; preservar origem e limitações.', indexavel='true')
            secoes = []
            for categoria in sorted({a['categoria'] for a in ambientes}):
                nome = 'Banheiros e sanitários' if categoria == 'banheiro' else categoria.capitalize()
                secoes.append({'caminho': [titulo, nome],
                               'paragrafos': [_paragrafo(a, ambientes, item['nome'], andar['nome'])
                                              for a in ambientes if a['categoria'] == categoria]})
            extraido = {'source_id': sid, 'versao': versao, 'sha256_original': sha,
                        'url': url, 'secoes': secoes}
            novas.append(fonte)
            documentos.append((sid, dados, extraido))
            contagens[sid] = {'ambientes': len(ambientes),
                             'banheiros': sum(a['categoria'] == 'banheiro' for a in ambientes)}
    ids = {f['source_id'] for f in novas}
    atualizadas = [f for f in fontes if f['source_id'] not in ids] + novas
    problemas = validar_catalogo(atualizadas, config['catalogo'])
    if problemas:
        raise ValueError('\n'.join(map(str, problemas)))
    for sid, dados, extraido in documentos:
        pasta = caminho_projeto('data/imports/mapas')
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / f'{sid}.json').write_bytes(dados)
        # Original também no lugar esperado pelo pipeline de curadoria.
        original = caminho_projeto(config['caminhos']['originais']) / sid
        original.mkdir(parents=True, exist_ok=True)
        (original / f'{extraido["versao"]}.json').write_bytes(dados)
        gravar_json(caminho_projeto(config['caminhos']['extraido']) / f'{sid}__{extraido["versao"]}.json', extraido)
    salvar_catalogo(caminho_projeto(config['caminhos']['catalogo']), atualizadas)
    return {'fontes_importadas': len(novas), 'plantas': contagens,
            'publicado_no_supabase': False, 'origem_commit': commit}
