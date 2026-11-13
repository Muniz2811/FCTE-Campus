"""Mesmo bra?o Gemini isolado usado no experimento Semana 3 e na compara??o ao vivo."""
import httpx
from pydantic import BaseModel, ConfigDict, Field

PROMPT_LIVRE = '''Você é o assistente acadêmico do campus Gama/FCTE da UnB. Responda em português.
Responda usando o conhecimento que você possui. Não há navegador, ferramenta de busca ou documentos anexados.
Não invente salas, andares, horários ou recursos. Se não souber com segurança, admita a insuficiência.
Você não tem acesso à ocupação atual de salas, contagens de pessoas ou posições ao vivo dos ônibus.
Não apresente uma informação incerta como atual ou confirmada. Corrija premissas falsas quando souber.
Se conhecer fontes públicas que sustentam suas afirmações, informe suas URLs em fontes; não invente URLs.
Use status answered e claims com afirmações curtas quando puder responder. Nesse caso message deve ser vazio.
Se não puder responder, use status insufficient, claims vazio e message explicando o que falta.
Seja direto e útil; limite-se às partes solicitadas, sem divulgar dados pessoais desnecessários.'''


class ClaimLivre(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=1800)
    fontes: list[str] = Field(max_length=5)


class SaidaLivre(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    status: str = Field(pattern='^(answered|insufficient)$')
    message: str = Field(max_length=1500)
    claims: list[ClaimLivre] = Field(max_length=8)



def livre(cliente, chave, cfg, pergunta):
    corpo = {'systemInstruction': {'parts': [{'text': PROMPT_LIVRE}]},
             'contents': [{'role': 'user', 'parts': [{'text': pergunta}]}],
             'generationConfig': {'temperature': cfg['temperatura'], 'maxOutputTokens': cfg['max_output_tokens'],
                 'responseMimeType': 'application/json', 'responseJsonSchema': SaidaLivre.model_json_schema()}}
    try:
        response = cliente.post(f'https://generativelanguage.googleapis.com/v1beta/models/{cfg["modelo"]}:generateContent',
                                headers={'x-goog-api-key': chave}, json=corpo)
    except httpx.TimeoutException:
        return {'status_tecnico': 504, 'erro': 'Timeout da API Gemini'}
    except httpx.RequestError:
        return {'status_tecnico': 503, 'erro': 'Falha de conexão Gemini'}
    if not response.is_success:
        return {'status_tecnico': response.status_code, 'erro': 'Gemini recusou ou não completou a chamada'}
    try:
        raw = response.json()
    except ValueError:
        return {'status_tecnico': 502, 'erro': 'Resposta Gemini fora do formato JSON'}
    finish = None
    texto = ''
    try:
        candidate = raw['candidates'][0]
        finish = candidate.get('finishReason')
        texto = ''.join(p.get('text', '') for p in candidate['content']['parts'] if not p.get('thought'))
        if finish != 'STOP':
            raise ValueError('Saída incompleta')
        result = SaidaLivre.model_validate_json(texto).model_dump()
        if (result['status'] == 'answered') != bool(result['claims']):
            raise ValueError('Status incompatível com claims')
        if (result['status'] == 'insufficient') != bool(result['message']):
            raise ValueError('Status incompatível com message')
    except (ValueError, KeyError, TypeError, IndexError):
        return {'status_tecnico': 502, 'erro': 'Saída incompleta ou fora do contrato', 'finishReason': finish,
                'texto_recebido': texto, 'usage': raw.get('usageMetadata', {})}
    result['usage'] = raw.get('usageMetadata', {})
    result['providerModelVersion'] = raw.get('modelVersion')
    return {'status_tecnico': 200, 'resposta': result}
