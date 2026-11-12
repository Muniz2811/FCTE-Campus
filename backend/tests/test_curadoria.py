from rag.ingestao.extracao import extrair_html
from rag.config import carregar_config
from rag.ingestao.catalogo import COLUNAS, validar_catalogo


def test_limpeza_preserva_conteudo_e_exclui_somente_blocos_configurados():
    regras = {'conteudo': 'main', 'remover': [], 'titulos_extras': [],
              'excluir_paragrafos_regex': ['Restaurante'], 'excluir_secoes': ['Instalar app']}
    resultado = extrair_html(b'<main><h2>Campus</h2><p>Quadra</p><p>Restaurante</p><h2>Instalar app</h2><p>Baixe agora</p></main>', regras, 1)
    assert resultado['secoes'] == [{'caminho': ['Campus'], 'paragrafos': ['Quadra']}]


def test_aprovacao_sem_download_nao_e_confundida_com_fonte_indexavel():
    fonte = {c: '' for c in COLUNAS}
    fonte.update(source_id='EX-001', titulo='Fonte de exemplo', tipo='pagina_web', url='https://exemplo.invalid',
                 campus='Gama', abrangencia='Gama', validade='desconhecida', status='aprovado',
                 revisor='Revisor de exemplo', data_revisao='2026-11-11', indexavel='false',
                 motivo='Original indisponível para extração')
    assert validar_catalogo([fonte], carregar_config()['catalogo']) == []
