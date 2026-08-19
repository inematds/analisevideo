---
name: analisevideo
description: SO POR COMANDO EXPLICITO `/analisevideo`. Nao dispare por vibe, por link de video nem por pedido em linguagem natural — analise falada de video continua sendo do vox (`analyze`). Faz analise VISUAL/cinematografica com Gemini (camera, plano, luz, paleta, montagem, trilha, grafismo, como refazer) e arquiva num banco pesquisavel.
---

# analisevideo — o que um cineasta ve no video

**Gatilho unico: o comando `/analisevideo`.** Sem comando, nao rode esta skill —
"analisa esse video" solto vai pro vox (`analyze`), de proposito.

`bash /home/nmaldaner/projetos/openpcbotv2/skills/analisevideo/analisevideo.sh <subcmd>`

Nao transcreve fala. Quem transcreve e a skill **inemavox**. Se o usuario quiser
a fala, mande pro vox; se quiser entender *como o video foi feito*, e aqui.

## Comandos

```bash
S=/home/nmaldaner/projetos/openpcbotv2/skills/analisevideo/analisevideo.sh

bash $S analisa <url|path> [slug] [--keep-src]   # baixa (yt-dlp), analisa, grava no banco
bash $S ver     <slug>        # relatorio markdown (o que mandar no Telegram)
bash $S json    <slug>        # analise crua
bash $S list    [N]           # ultimas analises
bash $S search  "<termo>"     # busca no banco (tag, look, movimento, genero, titulo)
bash $S stats                 # o que mais aparece no banco
bash $S reindex               # reconstroi o index a partir das pastas
```

## O que sai

Banco em `~/projetos/output/analisevideo/<slug>/`:
`meta.json` (titulo, canal, duracao, resolucao), `analise.json` (estruturado),
`analise.md` (relatorio). Index geral em `~/projetos/output/analisevideo/index.jsonl`
— uma linha por video, e o que `list`/`search`/`stats` leem.

Campos da analise: fotografia (paleta hex, luz, look, lente, DOF, grain),
camera bloco a bloco com timecode (plano, angulo, movimento, velocidade),
composicao, montagem (cortes/min, ritmo, transicoes, corte no beat),
audio (genero, bpm, instrumentacao, mood, sfx, mixagem), texto e grafismo,
pos-producao, narrativa (gancho de 3s, arco, CTA), `reproduzir` (passos +
prompt pronto pra Kling/Veo/Seedance) e tags.

## Fluxo no bot

1. Briefing de 1 linha ("analisando o visual desse video, te aviso").
2. `analisa <url>` — tarefa longa (download + upload + Gemini): usar
   `scripts/notify.sh` nos checkpoints (baixou / analisando / pronto).
3. Mandar o resumo curto no corpo da mensagem + `[SEND_FILE:<.../analise.md>]`.
4. Se o usuario perguntar de video antigo ("aquele do drone", "o que tinha
   trilha synthwave"), e `search`, nao reanalisar.

## Detalhes que importam

- Download em ate 480p de proposito: cor/luz/camera se leem bem e o upload
  fica rapido. Fonte com mais de 18MB e reencodada pra 360p/12fps so pra
  analise. O `fonte.mp4` e apagado no fim — `--keep-src` guarda.
- Link que o yt-dlp nao pega (site logado): baixe por fora e passe o caminho.
- Video longo (>15min) fica caro e vago; prefira analisar um trecho cortado.
- `GOOGLE_API_KEY` vem do `.env` do openpcbotv2 (fallback `~/projetos/wifi/.env`).
- Nao mistura com a skill `musica`: link + palavra de musica = clonar, nao analisar.
