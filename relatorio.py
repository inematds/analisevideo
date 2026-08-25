#!/usr/bin/env python3
"""analise.json -> relatorio markdown legivel no Telegram.

Uso: relatorio.py <analise.json> <slug> > analise.md
"""
import json
import sys


def g(d, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
        if d is None:
            return default
    return d


def lista(v):
    if not v:
        return "-"
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v)


def main() -> int:
    a = json.load(open(sys.argv[1]))
    slug = sys.argv[2] if len(sys.argv) > 2 else ""
    if a.get("erro"):
        print(f"Falhou: {a['erro']}")
        return 1

    o = []
    fonte = a.get("_fonte") or {}
    o.append(f"# analisevideo — {fonte.get('titulo') or slug}")
    if fonte.get("url"):
        o.append(f"Fonte: {fonte['url']}")
    o.append(f"Duracao: {a.get('_duracao_s', 0):.0f}s · tipo: {a.get('tipo', '-')} "
             f"· confianca: {a.get('confianca', '-')}")
    o.append("")
    o.append(a.get("resumo", ""))

    f = a.get("fotografia") or {}
    o.append("\n## Fotografia")
    o.append(f"- Paleta: {lista(f.get('paleta'))}")
    o.append(f"- Luz: {f.get('esquema_de_luz', '-')} ({f.get('fonte_de_luz', '-')})")
    o.append(f"- Cor: {f.get('temperatura_cor', '-')} · contraste {f.get('contraste', '-')} "
             f"· look {f.get('look', '-')}")
    o.append(f"- Lente/DOF: {f.get('lente_aparente', '-')} · {f.get('profundidade_de_campo', '-')}")
    o.append(f"- Textura: {f.get('grain_textura', '-')}")

    o.append("\n## Camera (bloco a bloco)")
    for c in (a.get("camera") or [])[:40]:
        o.append(f"- {c.get('t_inicio', '?')}–{c.get('t_fim', '?')} · {c.get('plano', '-')} · "
                 f"{c.get('movimento', '-')} ({c.get('velocidade', '-')}) · "
                 f"{c.get('angulo', '-')} — {c.get('nota', '')}")

    m = a.get("montagem") or {}
    o.append("\n## Montagem")
    o.append(f"- {m.get('cortes_estimados', '-')} cortes · {m.get('cortes_por_minuto', '-')}/min "
             f"· ritmo {m.get('ritmo', '-')}")
    o.append(f"- Transicoes: {lista(m.get('tipos_de_transicao'))}")
    o.append(f"- match cut: {m.get('match_cut')} · jump cut: {m.get('jump_cut')} "
             f"· corte no beat: {m.get('corte_no_beat')}")
    o.append(f"- Velocidade: {m.get('uso_de_slowmo_speedramp', '-')}")

    au = a.get("audio") or {}
    o.append("\n## Trilha e som")
    o.append(f"- Musica: {au.get('tem_musica')} · {au.get('genero', '-')}/{au.get('subgenero', '-')} "
             f"· ~{au.get('bpm_aprox', '-')} bpm · {au.get('tonalidade_aprox', '-')}")
    o.append(f"- Instrumentacao: {lista(au.get('instrumentacao'))}")
    o.append(f"- Mood/energia: {au.get('mood', '-')} · {au.get('energia', '-')}")
    o.append(f"- SFX: {lista(au.get('sfx'))}")
    o.append(f"- Estrutura: {au.get('estrutura_musical', '-')}")
    o.append(f"- Mixagem: {au.get('mixagem', '-')} · sincronia: {au.get('sincronia_com_a_imagem', '-')}")
    if au.get("prompt_musica"):
        o.append("\n**Prompt de musica (Suno/Udio):**")
        o.append(f"```\n{au['prompt_musica']}\n```")
        if au.get("negativo_musica"):
            o.append(f"Negativo: `{au['negativo_musica']}`")

    t = a.get("texto_e_grafismo") or {}
    o.append("\n## Texto e grafismo")
    o.append(f"- Tipografia: {t.get('estilo_tipografico', '-')} ({t.get('familia_aproximada', '-')})")
    o.append(f"- Animacao: {t.get('animacao_do_texto', '-')} · legendas: {t.get('legendas_estilo', '-')}")
    o.append(f"- Motion graphics: {lista(t.get('motion_graphics'))}")

    p = a.get("pos_producao") or {}
    o.append("\n## Pos")
    o.append(f"- Efeitos: {lista(p.get('efeitos'))} · VFX: {p.get('vfx', '-')}")
    o.append(f"- LUT sugerida: {p.get('lut_sugerida', '-')} · sound design: {p.get('sound_design', '-')}")

    n = a.get("narrativa") or {}
    o.append("\n## Narrativa")
    o.append(f"- Gancho (3s): {n.get('gancho_primeiros_3s', '-')}")
    o.append(f"- Estrutura: {n.get('estrutura', '-')} · arco: {n.get('arco', '-')}")
    o.append(f"- CTA: {n.get('cta', '-')}")

    # REFAZER SEMELHANTE: os dois prompts que importam, juntos e no topo do
    # bloco de reproducao.
    #
    # O `prompt_musica` ja era pedido no PROMPT e vinha preenchido no JSON —
    # so nunca aparecia no relatorio, que e o que a pessoa le. Ele ficava
    # enterrado em `audio`, e quem quisesse refazer a musica tinha que abrir o
    # `.json` para achar. Pedido do dono em 2026-08-24.
    au_p = (a.get("audio") or {}).get("prompt_musica")
    r = a.get("reproduzir") or {}
    clipe_p = r.get("prompt_gerador_video")
    if au_p or clipe_p:
        o.append("\n## Refazer semelhante")
        if au_p:
            o.append("\n**Música** (Suno/Udio — cole como está):")
            o.append(f"> {au_p}")
            neg = (a.get("audio") or {}).get("negativo_musica")
            if neg:
                o.append(f"\nNegativo: `{neg}`")
        if clipe_p:
            o.append("\n**Clipe** (o trecho mais forte, para gerador de vídeo):")
            o.append(f"> {clipe_p}")
        # A LINHA PRONTA para o bot: quem quer refazer nao quer montar comando,
        # quer colar. O `--estilo` fica de fora de proposito — o estilo esta
        # descrito dentro do proprio prompt, e um id de catalogo brigaria com ele.
        if au_p:
            uma_linha = " ".join(str(au_p).split())
            o.append("\n**No bot, de uma vez:**")
            o.append(f"```\nmusicavideo: {uma_linha}\n```")

    o.append(f"\n## Como refazer (dificuldade: {r.get('dificuldade', '-')})")
    o.append(f"- Equipamento: {lista(r.get('equipamento_minimo'))}")
    for i, passo in enumerate(r.get("passos") or [], 1):
        o.append(f"{i}. {passo}")
    cenas = r.get("prompts_gerador_video") or []
    if cenas:
        o.append(f"\n## Prompts p/ gerador de video ({len(cenas)} cenas)")
        for i, c in enumerate(cenas, 1):
            n = c.get("cena", i)
            janela = f"{c.get('t_inicio', '?')}–{c.get('t_fim', '?')}"
            dur = c.get("duracao_s")
            cab = f"\n### Cena {n} · {janela}"
            if dur:
                cab += f" · ~{dur}s"
            if c.get("titulo"):
                cab += f" — {c['titulo']}"
            o.append(cab)
            o.append(f"> {c.get('prompt', '-')}")
            if c.get("negativo"):
                o.append(f"\nNegativo: `{c['negativo']}`")
    elif r.get("prompt_gerador_video"):
        o.append("\nPrompt p/ gerador de video:")
        o.append(f"> {r['prompt_gerador_video']}")

    o.append(f"\nReferencias: {lista(a.get('referencias_estilo'))}")
    o.append(f"Tags: {lista(a.get('tags'))}")
    print("\n".join(o))
    return 0


if __name__ == "__main__":
    sys.exit(main())
