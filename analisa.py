#!/usr/bin/env python3
"""Analise VISUAL/cinematografica de um video com o Gemini.

Uso: analisa.py <video> <duracao_segundos> [meta.json] > analise.json

Nao e transcricao de fala. O foco e o que um cineasta / diretor de fotografia /
montador / produtor musical enxerga: plano, movimento de camera, luz, cor,
ritmo de corte, grafismo, trilha e como refazer aquilo.
"""
import base64
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request

MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
API = "https://generativelanguage.googleapis.com"
INLINE_LIMIT = 15 * 1024 * 1024

PROMPT = """Voce e um diretor de fotografia + montador + produtor musical
analisando um video. Responda SO com JSON valido, sem markdown, em pt-BR
(termos tecnicos podem ficar em ingles quando for o jargao usual).

NAO transcreva a fala. Se houver narracao, resuma em uma linha o que ela faz
(tom, funcao) e siga. O que importa e a LINGUAGEM AUDIOVISUAL.

Campos obrigatorios:
- resumo: 2 a 4 frases sobre o que o video e e como ele se parece.
- tipo: ex "reel de marca", "clipe musical", "vlog", "trailer", "ad", "b-roll".
- formato: {aspecto: "16:9"|"9:16"|"1:1"|outro, sensacao_de_resolucao, fps_aparente}
- fotografia: {paleta: [ate 6 cores em hex aproximado], temperatura_cor,
  contraste, exposicao, esquema_de_luz (ex "key dura lateral + rim"),
  fonte_de_luz, grain_textura, look (ex "teal&orange", "bleach bypass"),
  profundidade_de_campo, lente_aparente (ex "35mm", "anamorfico 2x")}
- camera: lista de blocos observados, cada um
  {t_inicio: "mm:ss", t_fim: "mm:ss", plano: "close|medio|geral|detalhe|plano-sequencia",
   angulo: "nivel|contra-plongee|plongee|birds-eye", movimento:
   "estatico|pan|tilt|dolly-in|dolly-out|travelling|handheld|steadicam|gimbal|
    zoom|crash-zoom|orbital|drone|whip-pan|snorricam", velocidade, nota}
  Cubra o video inteiro, nao so o comeco.
- composicao: {enquadramento, regras (ex "tercos", "simetria central"),
  headroom, uso_de_negativo, camadas_de_profundidade}
- montagem: {cortes_estimados: int, cortes_por_minuto: number,
  ritmo: "lento|medio|acelerado", tipos_de_transicao: [], match_cut: bool,
  jump_cut: bool, corte_no_beat: bool, uso_de_slowmo_speedramp}
- movimento_no_quadro: como sujeito/objetos se movem, blocking.
- audio: {tem_musica: bool, genero, subgenero, bpm_aprox: int, tonalidade_aprox,
  instrumentacao: [], mood, energia: "baixa|media|alta",
  estrutura_musical: "secoes com timecode, ex 'intro 00:00-00:04, build ate
    00:11, drop 00:11-00:22, outro'",
  sfx: [], mixagem (voz x musica x ambiencia), sincronia_com_a_imagem,
  prompt_musica: "prompt EM INGLES, 30 a 60 palavras, pronto pra colar em
    Suno/Udio/ElevenLabs Music, descrevendo genero, bpm, tonalidade,
    instrumentacao, mood, arco de energia e uso (trilha de reel etc).
    Autocontido, sem citar o video original nem artista real.",
  negativo_musica: "negative prompt curto em ingles (o que evitar na trilha)"}
- texto_e_grafismo: {tem_texto: bool, estilo_tipografico, familia_aproximada,
  animacao_do_texto, legendas_estilo, lower_thirds, motion_graphics: []}
- pos_producao: {efeitos: [], vfx, estabilizacao, lut_sugerida, sound_design}
- narrativa: {gancho_primeiros_3s, estrutura, arco, cta, ritmo_de_informacao}
- reproduzir: {dificuldade: "facil|media|dificil",
  equipamento_minimo: [], passos: [5 a 10 passos praticos para refazer],
  prompt_gerador_video: "prompt em ingles do trecho mais forte (o melhor da
  lista abaixo, repetido aqui por compatibilidade)",
  prompts_gerador_video: [
    NO MINIMO 5 e no maximo 10 itens — UM PROMPT POR CENA, cobrindo o video
    do inicio ao fim (nao so o comeco), cada um
    {cena: int (1,2,3...), t_inicio: "mm:ss", t_fim: "mm:ss",
     titulo: "rotulo curto em pt-BR da cena",
     prompt: "prompt EM INGLES, 40 a 80 palavras, pronto pra colar em
       Kling/Veo/Seedance. Deve conter, nesta ordem: sujeito e acao;
       enquadramento e angulo; movimento de camera e velocidade; lente/DOF;
       luz e hora do dia; paleta com as cores em hex; look/grade e textura
       (grain, halation); ambiente e cenario; duracao aproximada do plano.
       Autocontido: nao escreva 'mesma cena anterior' nem cite outras cenas.",
     negativo: "negative prompt curto em ingles (o que evitar)",
     duracao_s: number (duracao do plano em segundos)}
  ]}
  As cenas devem ser derivadas dos blocos de 'camera' / dos cortes reais.
  Se o video tiver menos de 5 cortes, quebre em 5 momentos distintos
  (abertura, desenvolvimento, pico, virada, fechamento).
- referencias_estilo: [ate 5 referencias de diretor/canal/filme/estetica]
- tags: 8 a 15 tags curtas em pt-BR para busca posterior.
- confianca: 0..1 quao seguro voce esta da analise (video curto/escuro baixa).

Se algum campo nao se aplicar, use null ou lista vazia. Nunca invente
timecode fora da duracao informada.
"""


def upload(key: str, path: str, mime: str) -> str:
    size = os.path.getsize(path)
    req = urllib.request.Request(
        f"{API}/upload/v1beta/files?key={key}",
        data=json.dumps({"file": {"display_name": os.path.basename(path)}}).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(size),
            "X-Goog-Upload-Header-Content-Type": mime,
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        up = r.headers.get("x-goog-upload-url")
    if not up:
        raise RuntimeError("Gemini nao devolveu URL de upload")

    put = urllib.request.Request(
        up,
        data=open(path, "rb").read(),
        method="POST",
        headers={
            "Content-Length": str(size),
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
        },
    )
    with urllib.request.urlopen(put, timeout=900) as r:
        info = json.load(r)["file"]

    name, uri, state = info["name"], info["uri"], info.get("state")
    # video sobe como PROCESSING; usar antes de ACTIVE devolve 400.
    for _ in range(120):
        if state == "ACTIVE":
            break
        if state == "FAILED":
            raise RuntimeError("Gemini falhou ao processar o arquivo")
        time.sleep(3)
        with urllib.request.urlopen(f"{API}/v1beta/{name}?key={key}", timeout=30) as r:
            state = json.load(r).get("state")
    if state != "ACTIVE":
        raise RuntimeError("arquivo nao ficou ACTIVE no Gemini")
    return uri


# ORDEM das chaves. A primeira é a de sempre; as outras existem porque estão em
# PROJETOS diferentes — cota estourada num projeto não estoura no outro.
NOMES_CHAVE = ("GOOGLE_API_KEY", "GEMINI_API_KEY",
               "GEMINI_API_KEY_INEMACCBOT_TIME", "GEMINI_API_KEY_INEMACCBOT_PROMPTS")

# 429 = cota; 403 = chave bloqueada/restrita. Nos dois casos OUTRA chave resolve,
# e esperar não resolve nada — é aqui que a redundância vale.
TROCA_DE_CHAVE = (429, 403)
# 5xx é o Gemini congestionado: a chave não tem culpa e trocar não ajuda. Espera.
ESPERA_E_TENTA = (500, 502, 503)


def chaves_disponiveis() -> list:
    """As chaves na ordem, sem repetir valor.

    Deduplica pelo VALOR, não pelo nome: `GOOGLE_API_KEY` e `GEMINI_API_KEY`
    costumam apontar para a mesma chave, e tentar duas vezes a mesma coisa
    depois de um 429 é só perder tempo.
    """
    saida, vistos = [], set()
    for nome in NOMES_CHAVE:
        v = (os.environ.get(nome) or "").strip()
        if v and v not in vistos:
            vistos.add(v)
            saida.append((nome, v))
    return saida


class CotaOuBloqueio(Exception):
    """A chave nao serve AGORA (cota ou bloqueio). Trocar de chave resolve."""

    def __init__(self, codigo: int):
        super().__init__(f"HTTP {codigo}")
        self.codigo = codigo


def tentar_com(key: str, path: str, mime: str, size: int, ctx: str, esperas) -> str:
    """Upload (se preciso) + geracao, com UMA chave.

    O upload entra aqui dentro de proposito: o arquivo enviado pertence ao
    PROJETO da chave, entao trocar de chave obriga a subir de novo — reaproveitar
    o `file_uri` da chave anterior daria 403 na geracao.
    """
    if size <= INLINE_LIMIT:
        part = {"inline_data": {"mime_type": mime,
                                "data": base64.b64encode(open(path, "rb").read()).decode()}}
    else:
        # O upload tambem recusa por cota/bloqueio — e é ele que gasta o tempo
        # do arquivo grande. Sem converter aqui, um 429 no upload viraria erro
        # final em vez de troca de chave.
        try:
            uri = upload(key, path, mime)
        except urllib.error.HTTPError as e:
            if e.code in TROCA_DE_CHAVE:
                raise CotaOuBloqueio(e.code) from e
            raise
        part = {"file_data": {"mime_type": mime, "file_uri": uri}}
    body = {
        "contents": [{"parts": [{"text": PROMPT + "\n\n" + ctx}, part]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3,
                             "maxOutputTokens": 16384},
    }
    for tentativa in range(len(esperas) + 1):
        req = urllib.request.Request(
            f"{API}/v1beta/models/{MODEL}:generateContent?key={key}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                return json.load(r)["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            if e.code in TROCA_DE_CHAVE:
                raise CotaOuBloqueio(e.code) from e
            if e.code in ESPERA_E_TENTA and tentativa < len(esperas):
                espera = esperas[tentativa]
                print(f"[analisevideo] Gemini {e.code} — esperando {espera}s "
                      f"(tentativa {tentativa + 1}/{len(esperas) + 1})",
                      file=sys.stderr, flush=True)
                time.sleep(espera)
                continue
            raise
    raise RuntimeError("Gemini nao respondeu depois de todas as esperas")


def main() -> int:
    path = sys.argv[1]
    dur = float(sys.argv[2] or 0)
    meta = {}
    if len(sys.argv) > 3 and os.path.exists(sys.argv[3]):
        meta = json.load(open(sys.argv[3]))

    chaves = chaves_disponiveis()
    if not chaves:
        print(json.dumps({"erro": "nenhuma chave do Gemini encontrada "
                                  "(GOOGLE_API_KEY, GEMINI_API_KEY, GEMINI_API_KEY_*)"}))
        return 1

    mime = mimetypes.guess_type(path)[0] or "video/mp4"
    size = os.path.getsize(path)

    ctx = f"Duracao do video: {dur:.0f}s. Titulo: {meta.get('titulo') or os.path.basename(path)}."
    extra = os.environ.get("ANALISEVIDEO_EXTRA", "").strip()
    if extra:
        ctx += "\nPedido especifico do usuario (responda tambem em 'pedido_extra'): " + extra

    # 5xx do Gemini sao rotina em horario de pico: tenta de novo, com a MESMA
    # chave. A espera era 5s, 10s, 15s — 30 segundos no total, que devolve o
    # pedido para dentro da MESMA congestao. Em 2026-08-22 uma analise morreu
    # assim (job 4775, 503) depois de ja ter baixado 22 MB e comprimido o video:
    # o trabalho caro estava feito e o que faltava era esperar.
    ESPERAS = (20, 40, 60, 90, 120)

    raw = None
    usada = None
    falhas = []
    for nome, key in chaves:
        try:
            raw = tentar_com(key, path, mime, size, ctx, ESPERAS)
            usada = nome
            break
        except CotaOuBloqueio as e:
            # NAO espera: a proxima chave esta em outro projeto, e a cota de la
            # nao foi tocada. Esperar aqui seria pagar o tempo sem necessidade.
            falhas.append(f"{nome}: HTTP {e.codigo}")
            print(f"[analisevideo] {nome} recusou (HTTP {e.codigo}) — "
                  f"tentando a proxima chave", file=sys.stderr, flush=True)
            continue
    if raw is None:
        print(json.dumps({"erro": "todas as chaves do Gemini falharam por cota ou "
                                  "bloqueio — " + "; ".join(falhas)}, ensure_ascii=False))
        return 1
    if usada != chaves[0][0]:
        print(f"[analisevideo] analise feita com {usada}", file=sys.stderr, flush=True)

    out = json.loads(raw)
    out["_fonte"] = meta
    out["_modelo"] = MODEL
    out["_duracao_s"] = dur
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # devolve erro em JSON pro shell nao virar lixo
        print(json.dumps({"erro": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        sys.exit(1)
