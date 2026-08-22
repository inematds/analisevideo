# analisevideo

Análise **visual e cinematográfica** de vídeo com o Gemini, arquivada num banco
local pesquisável. Não é transcrição de fala: o que sai daqui é o que um diretor
de fotografia, um montador e um produtor musical enxergam no material.

Roda como skill do [OpenPCBot](https://github.com/inematds/openpcbotv2) sob o
comando `/analisevideo` — de propósito **não dispara por vibe** (link solto ou
"analisa esse vídeo" continuam indo pro inemaVOX).

## 📖 Guia de uso

Guia completo (landing + passo a passo): **https://inematds.github.io/analisevideo/guia/**

## Uso

```bash
S=~/projetos/analisevideo/analisevideo.sh

bash $S analisa <url|arquivo> [slug] [--keep-src] [--prompt "..."]
bash $S ver     <slug>       # relatório markdown
bash $S json    <slug>       # análise crua
bash $S prompts <slug>       # 1 prompt por cena (5–10), pronto pra Kling/Veo/Seedance
bash $S list    [N]          # últimas análises
bash $S search  "<termo>"    # busca no banco
bash $S stats                # o que mais aparece no banco
bash $S reindex              # reconstrói o índice a partir das pastas
```

Precisa de `yt-dlp`, `ffmpeg`/`ffprobe`, `jq`, `python3` e uma `GOOGLE_API_KEY`
(lida de `~/projetos/openpcbotv2/.env` ou `~/projetos/wifi/.env`).

## O que a análise cobre

- **Prompts por cena** — 5 a 10 prompts em inglês (+ negative prompt), um por
  cena com timecode, cobrindo o vídeo inteiro.
- **Fotografia** — paleta em hex, esquema de luz, temperatura, contraste, look,
  lente aparente, profundidade de campo, textura/grain.
- **Câmera bloco a bloco** com timecode — plano, ângulo, movimento (pan, dolly,
  gimbal, whip-pan, drone, orbital...), velocidade e nota.
- **Composição** — enquadramento, regras, camadas de profundidade.
- **Montagem** — cortes estimados, cortes por minuto, ritmo, transições, match
  cut, jump cut, corte no beat, slow-mo/speed ramp.
- **Trilha e som** — gênero, BPM aproximado, instrumentação, mood, SFX, mixagem
  e sincronia com a imagem.
- **Texto e grafismo** — tipografia, animação, legendas, motion graphics.
- **Pós** — efeitos, VFX, LUT sugerida, sound design.
- **Narrativa** — gancho dos 3 primeiros segundos, estrutura, arco, CTA.
- **Como refazer** — equipamento mínimo, passos práticos e um prompt pronto para
  Kling/Veo/Seedance reproduzindo o look e o movimento do trecho mais forte.

## Banco

Cada análise vira uma pasta em `~/projetos/output/analisevideo/<slug>/` com
`meta.json`, `analise.json` e `analise.md`. Uma linha por vídeo é acrescentada a
`index.jsonl` — é o que `list`, `search` e `stats` leem. O vídeo baixado é
apagado no fim (guarde com `--keep-src`).

## Detalhes

- Download em até 480p de propósito: cor, luz e movimento se leem bem e o upload
  fica rápido. Acima de 18 MB o arquivo é reencodado para 360p/12fps só para a
  análise.
- Link que o yt-dlp não pega (site logado): baixe por fora e passe o caminho.
- Vídeo longo (>15 min) fica caro e vago — prefira analisar um trecho.
- 429/500/503 do Gemini são reprocessados automaticamente (4 tentativas).

## Chaves do Gemini — três, e ele troca sozinho

O `analisa.py` tenta as chaves nesta ordem, parando na primeira que funcionar:

| variável | onde |
|---|---|
| `GOOGLE_API_KEY` | a de sempre |
| `GEMINI_API_KEY` | idem (deduplicada se for o mesmo valor) |
| `GEMINI_API_KEY_INEMACCBOT_TIME` | `projects/1056030032122` |
| `GEMINI_API_KEY_INEMACCBOT_PROMPTS` | `projects/1000152753819` |

Todas saem de `~/projetos/wifi/.env` (ou do `.env` local).

**O que faz trocar e o que faz esperar** — a distinção é o ponto:

- **429 (cota) e 403 (bloqueada)** → passa para a chave seguinte **na hora**. Ela
  está em outro projeto, com cota própria; esperar não resolveria nada.
- **500 / 502 / 503** → é o Gemini congestionado. A chave não tem culpa, e trocar
  não ajuda: espera (20s, 40s, 60s, 90s, 120s) e insiste na mesma.

O upload do arquivo grande também entra nessa conta: um 429 nele troca de chave
em vez de virar erro final — é justamente o caso em que o vídeo já foi baixado e
comprimido, e perder tudo ali seria caro.

Quando usa uma chave que não é a primeira, ele diz qual, no stderr. Se todas
falharem por cota, o erro lista **quais** falharam, em vez de um "deu erro".
