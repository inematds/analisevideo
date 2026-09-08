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


## Sites que exigem sessão (Facebook, Instagram, TikTok, YouTube)

O `yt-dlp` cru é recusado pelo Facebook com `Cannot parse data` — não é versão
velha nem falta de `--impersonate` (os dois foram testados em 2026-08-24 e
falharam igual). É **sessão**: com os cookies do Firefox o mesmo link lista os
formatos e baixa em 7 segundos.

O script acha o perfil sozinho (o primeiro com `cookies.sqlite`, procurando no
`snap` primeiro) e só acrescenta as flags nesses domínios. Para forçar outro
perfil:

    export ANALISEVIDEO_FIREFOX_PROFILE=~/snap/firefox/common/.mozilla/firefox/xxxx.default

**Sem Firefox na máquina** (VPS), o download segue sem cookies e avisa no stderr
— para os sites públicos continua funcionando.


## Ordem dos motores (2026-08-26: o Gemini direto vai na frente)

    GOOGLE_API_KEY → GEMINI_API_KEY → …_TIME → …_PROMPTS  →  z-ai/glm-5.3-flash

Em 2026-08-25 a reserva tinha ido para a frente porque o `stealth/ox-alpha` era
**grátis** e as três chaves do Gemini estouravam a cota diária com ~9 análises.
Esse modelo **sumiu do OpenRouter** — era o risco anotado desde o começo. A
reserva de hoje é paga, então ela volta para trás: gastar crédito com cota do
Gemini de sobra não faz sentido. Ela entra quando a cota do dia acaba.

Para inverter (a reserva na frente), **sem tocar em código**:

    export ANALISEVIDEO_MOTOR=reserva

## Reserva: quando o motor da frente recusa

O passo caro do `analisa` não é a chamada de API — é o **download e a
compressão** que vêm antes. Um clipe de 41 MB do Facebook leva minutos para
chegar até ali. Em 2026-08-24, três chaves distintas do Gemini responderam 429
no mesmo minuto e esse trabalho todo foi jogado fora.

Por isso existe a reserva. A ordem é:

    GOOGLE_API_KEY → GEMINI_API_KEY → …_TIME → …_PROMPTS → z-ai/glm-5.3-flash

O `z-ai/glm-5.3-flash` (OpenRouter, `OPENROUTER_API_KEY` no `wifi/.env`) aceita
vídeo e devolve o MESMO JSON — o prompt não muda em nada. Entrou em 2026-09-08 no
lugar do `google/gemini-3.7-flash`: custa ~10x menos (US$ 0,075/M de entrada
contra 0,75) e, sendo outro provedor, não divide a cota nem a congestão com o
Gemini da frente.

**Vídeo no OpenRouter exige US$ 1,00 disponíveis NA CHAVE** — não na conta. Uma
chave com teto (`limit` em openrouter.ai/settings/keys) abaixo disso responde
`402 … requires at least $1.00 in balance for video` para qualquer vídeo, mesmo
um clipe de 20 s, enquanto texto passa. Foi assim que a reserva ficou muda de
2026-08 até 2026-09-08. O `analisa` agora imprime o corpo do erro.

Ele fica ATRÁS de propósito: **é pago**. Sempre que ele responde, o `analisa`
avisa no stderr (`ATENCAO: ... reserva paga`) — motor pago não roda calado.
Para trocar o modelo da reserva, `OPENROUTER_VIDEO_MODEL`.

`_modelo` no JSON registra QUEM analisou: sem isso o banco diria Gemini para uma
análise que o Gemini não fez.

Sem `OPENROUTER_API_KEY`, tudo funciona como antes — a reserva é opcional.


## Reprocessar sem baixar de novo

O slug vem do TÍTULO, e o Facebook devolve "Facebook" para todo link — então
cada tentativa criava `facebook-2`, `-3`, `-4`… e baixava tudo outra vez. Em
2026-08-24 o MESMO clipe foi baixado **quatro vezes** (141 MB de rede e disco)
por um erro de cota que não tinha nada a ver com o download.

Agora a **URL é a identidade**: se já houver uma pasta com aquela url e o
arquivo ainda no disco, ela é reusada — download e compressão são pulados. E a
versão comprimida (`analise-src.mp4`), se existir, também é reaproveitada.

Duas consequências práticas:

- **Repetir `analisa <url>` depois de um erro é barato** — vai direto para a
  análise. É o caminho para reprocessar o que falhou por cota.
- **`--keep-src` passa a valer a pena** em vídeo que você pode querer reanalisar
  (com `--prompt` diferente, por exemplo). Sem ele, o arquivo é apagado no fim e
  a próxima análise baixa de novo.

Passar um `slug` explícito desliga o reuso: ali você está dizendo qual pasta
quer, e adivinhar outra seria pior.
