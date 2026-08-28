#!/usr/bin/env bash
# analisevideo — analise VISUAL/cinematografica de video (Gemini) + banco local.
#
#   analisevideo.sh analisa <url|path> [slug] [--keep-src] [--prompt "..."]
#   analisevideo.sh ver     <slug>            # relatorio markdown
#   analisevideo.sh json    <slug>            # analise crua
#   analisevideo.sh list    [N]               # ultimas analises
#   analisevideo.sh search  "<termo>"         # busca no banco
#   analisevideo.sh stats
#   analisevideo.sh reindex
#
# Nao transcreve fala: quem transcreve e a skill inemavox.
set -uo pipefail

# O ~/.local/bin ENTRA NO PATH. O serviço do bot roda pelo systemd --user, que
# não o herda — então `yt-dlp` (instalado com pip --user) existia no terminal e
# sumia no bot, que falhava com "yt-dlp nao instalado" numa máquina onde ele
# está instalado. Mesma classe do `claude` 2.1.63 vs 2.1.250 do musicavideo.
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) PATH="$HOME/.local/bin:$PATH"; export PATH ;;
esac

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BANCO="${ANALISEVIDEO_BANCO:-$HOME/projetos/output/analisevideo}"
INDEX="$BANCO/index.jsonl"
MAX_H="${ANALISEVIDEO_MAX_H:-480}"   # 480p basta pra ler luz/camera e mantem o upload leve
mkdir -p "$BANCO"

die() { echo "[analisevideo] erro: $*" >&2; exit 1; }

# Sites que EXIGEM sessão: cookies do navegador, como o inemavox já fazia.
#
# O Facebook recusa o yt-dlp cru com "Cannot parse data" — medido em 2026-08-24
# nos jobs 5152 a 5155, quatro links seguidos. Não é versão velha nem falta de
# `--impersonate` (testei os dois: mesma recusa); é sessão mesmo. Com os cookies
# do Firefox o mesmo link lista 20 formatos na hora.
#
# O `--impersonate chrome` vai junto porque não custa e o inemavox o usa no
# Facebook — sozinho ele não resolve, mas some com uma classe de bloqueio por
# TLS que aparece em outros sites.
#
# Perfil: o do inemavox (`cookies.sqlite` presente), com `snap` primeiro, que é
# onde o Firefox desta máquina mora. Sem perfil, seguimos SEM cookies — numa
# VPS não há navegador, e falhar por isso seria pior que tentar.
perfil_firefox() {
  [ -n "${ANALISEVIDEO_FIREFOX_PROFILE:-}" ] && { echo "$ANALISEVIDEO_FIREFOX_PROFILE"; return; }
  local p
  for p in "$HOME/snap/firefox/common/.mozilla/firefox"/*/ "$HOME/.mozilla/firefox"/*/; do
    [ -f "$p/cookies.sqlite" ] && { echo "${p%/}"; return; }
  done
}

# O MESMO video ja baixado antes? Reusa a pasta em vez de baixar de novo.
#
# O slug vem do TITULO, e o Facebook devolve "Facebook" para todo link: cada
# tentativa criava `facebook-2`, `-3`, `-4`... e baixava os 41 MB outra vez.
# Em 2026-08-24 o MESMO clipe foi baixado QUATRO vezes (facebook-4 a -7), 141 MB
# de rede e disco por um erro de cota que nao tinha nada a ver com o download.
#
# A URL e a identidade. Se houver pasta com esta url e o arquivo ainda no disco,
# ela e reusada — o download e a compressao (o passo caro) sao pulados.
pasta_com_a_url() {
  local url="$1" m arq
  for m in "$BANCO"/*/meta.json; do
    [ -f "$m" ] || continue
    [ "$(jq -r '.url // ""' "$m" 2>/dev/null)" = "$url" ] || continue
    arq="$(jq -r '.arquivo // ""' "$m" 2>/dev/null)"
    [ -n "$arq" ] && [ -f "$arq" ] && { dirname "$m"; return; }
  done
}

# As flags de download para ESTA url. Ecoa nada quando não há o que acrescentar.
flags_do_site() {
  local url="$1" perfil
  case "$url" in
    *facebook.com*|*fb.com*|*fb.watch*|*instagram.com*|*tiktok.com*|*youtube.com*|*youtu.be*)
      perfil="$(perfil_firefox)"
      if [ -n "$perfil" ]; then
        printf '%s\n' "--cookies-from-browser" "firefox:$perfil"
      else
        echo "[analisevideo] aviso: site que costuma exigir login e nenhum perfil do Firefox nesta maquina" >&2
      fi
      case "$url" in
        *facebook.com*|*fb.com*|*fb.watch*|*instagram.com*)
          printf '%s\n' "--impersonate" "chrome" ;;
      esac
      ;;
  esac
}


# Exporta TODAS as chaves do Gemini que existirem, nao so a primeira.
#
# O analisa.py tenta uma a uma: cota estourada (429) ou chave bloqueada (403)
# faz ele passar para a proxima, que esta em outro PROJETO e por isso tem cota
# propria. Carregar so uma aqui anularia essa rede — foi por isso que a lista
# saiu do shell e virou responsabilidade do Python.
CHAVES_GEMINI="GOOGLE_API_KEY GEMINI_API_KEY GEMINI_API_KEY_INEMACCBOT_TIME GEMINI_API_KEY_INEMACCBOT_PROMPTS"
# A chave da RESERVA (OpenRouter). Sem ela o analisa.py so avisa e falha como
# antes — a reserva e opcional de proposito: ela existe para o dia em que as
# quatro chaves do Gemini recusam com o video ja baixado e comprimido.
CHAVES_RESERVA="OPENROUTER_API_KEY"

load_key() {
  local achou=0 nome v f
  for nome in $CHAVES_GEMINI $CHAVES_RESERVA; do
    [ -n "$(eval echo "\${$nome:-}")" ] && { case " $CHAVES_GEMINI " in *" $nome "*) achou=1 ;; esac; continue; }
    for f in "$ROOT/.env" "$HOME/projetos/wifi/.env"; do
      [ -f "$f" ] || continue
      v="$(grep -m1 "^$nome=" "$f" | cut -d= -f2- | tr -d '"'"'"' \r')"
      # A RESERVA nao conta como "achou": ela e rede, nao motor. Sem Gemini
      # nenhum o `analisa.py` ainda roda (vai direto para a reserva), mas quem
      # perdeu as quatro chaves precisa saber disso, e nao descobrir por um
      # tempo de analise tres vezes maior.
      [ -n "$v" ] && { export "$nome=$v"; case " $CHAVES_GEMINI " in *" $nome "*) achou=1 ;; esac; break; }
    done
  done
  [ "$achou" = 1 ] || echo "[analisevideo] aviso: nenhuma chave do Gemini (.env do repo ou do wifi) — vai direto para a reserva" >&2
}

slugify() {
  echo "$1" | iconv -f utf8 -t ascii//TRANSLIT 2>/dev/null || echo "$1"
}

mk_slug() {
  local base; base="$(slugify "$1" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]\+/-/g; s/^-//; s/-$//')"
  base="$(echo "$base" | cut -c1-48)"
  [ -z "$base" ] && base="video"
  local s="$base" i=2
  while [ -d "$BANCO/$s" ]; do s="$base-$i"; i=$((i+1)); done
  echo "$s"
}

cmd="${1:-help}"; shift || true

case "$cmd" in

analisa|prep)
  SRC="${1:-}"; [ -n "$SRC" ] || die "uso: analisa <url|path> [slug]"
  shift
  SLUG=""; KEEP=0; EXTRA=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --keep-src) KEEP=1; shift ;;
      --prompt) EXTRA="$2"; shift 2 ;;
      -*) shift ;;
      *) [ -z "$SLUG" ] && SLUG="$1"; shift ;;
    esac
  done
  load_key

  TITULO=""; URL=""; UPLOADER=""; DATA=""
  if [[ "$SRC" =~ ^https?:// ]]; then
    URL="$SRC"
    command -v yt-dlp >/dev/null || die "yt-dlp nao instalado"
    mapfile -t FLAGS < <(flags_do_site "$URL")
    TITULO="$(yt-dlp --no-warnings "${FLAGS[@]}" --print '%(title)s' --skip-download "$URL" 2>/dev/null | head -1)"
    UPLOADER="$(yt-dlp --no-warnings "${FLAGS[@]}" --print '%(uploader)s' --skip-download "$URL" 2>/dev/null | head -1)"
    DATA="$(yt-dlp --no-warnings "${FLAGS[@]}" --print '%(upload_date)s' --skip-download "$URL" 2>/dev/null | head -1)"
    REUSO="$(pasta_com_a_url "$URL")"
    if [ -n "$REUSO" ] && [ -z "$SLUG" ]; then
      DIR="$REUSO"; SLUG="$(basename "$DIR")"
      FILE="$(jq -r '.arquivo' "$DIR/meta.json")"
      echo "[analisevideo] este video ja estava baixado em $SLUG — reusando (sem baixar de novo)" >&2
    else
    [ -z "$SLUG" ] && SLUG="$(mk_slug "${TITULO:-video}")"
    DIR="$BANCO/$SLUG"; mkdir -p "$DIR"
    echo "[analisevideo] baixando (<=${MAX_H}p)..." >&2
    yt-dlp --no-warnings --no-playlist "${FLAGS[@]}" \
      -f "bv*[height<=$MAX_H]+ba/b[height<=$MAX_H]/b" \
      --merge-output-format mp4 -o "$DIR/fonte.%(ext)s" "$URL" >&2 \
      || die "download falhou (yt-dlp). Se for site logado, confira a sessao no Firefox (ou baixe manual e passe o path)."
    FILE="$(ls -1 "$DIR"/fonte.* 2>/dev/null | head -1)"
    fi
  else
    [ -f "$SRC" ] || die "arquivo nao existe: $SRC"
    TITULO="$(basename "$SRC")"
    [ -z "$SLUG" ] && SLUG="$(mk_slug "${TITULO%.*}")"
    DIR="$BANCO/$SLUG"; mkdir -p "$DIR"
    FILE="$DIR/fonte.${SRC##*.}"
    cp -f "$SRC" "$FILE"
  fi
  [ -f "${FILE:-}" ] || die "nao achei o arquivo baixado"

  DUR="$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$FILE" 2>/dev/null | cut -d. -f1)"
  [ -z "$DUR" ] && DUR=0
  RES="$(ffprobe -v quiet -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of csv=p=0:s=x "$FILE" 2>/dev/null | head -1)"
  BYTES="$(stat -c%s "$FILE")"

  # >18MB tende a estourar tempo/limite: reencoda menor antes de mandar.
  ENVIA="$FILE"
  if [ "$BYTES" -gt 18874368 ]; then
    echo "[analisevideo] arquivo grande (${BYTES}B), comprimindo pra analise..." >&2
    ENVIA="$DIR/analise-src.mp4"
    if [ -s "$ENVIA" ]; then
      echo "[analisevideo] versao comprimida ja existe — reusando" >&2
    else
    ffmpeg -y -v error -i "$FILE" -vf "scale=-2:360" -r 12 -c:v libx264 -crf 30 -preset veryfast \
      -c:a aac -b:a 64k "$ENVIA" </dev/null >&2 || ENVIA="$FILE"
    fi
  fi

  # titulo vem de fora (aspas, acentos, barras): so por argv, nunca interpolado.
  python3 - "$DIR/meta.json" "$SLUG" "$TITULO" "$URL" "$UPLOADER" "$DATA" "$DUR" "$RES" "$BYTES" "$FILE" <<'PY'
import json, sys
_, dest, slug, titulo, url, canal, data, dur, res, bytes_, arq = sys.argv
json.dump({
  "slug": slug, "titulo": titulo, "url": url, "canal": canal,
  "data_publicacao": data, "duracao_s": int(dur or 0), "resolucao": res,
  "bytes": int(bytes_ or 0), "arquivo": arq,
}, open(dest, "w"), ensure_ascii=False, indent=2)
PY

  echo "[analisevideo] analisando com Gemini (${DUR}s)..." >&2
  export ANALISEVIDEO_EXTRA="$EXTRA"
  if ! python3 "$HERE/analisa.py" "$ENVIA" "$DUR" "$DIR/meta.json" > "$DIR/analise.json"; then
    cat "$DIR/analise.json" >&2
    die "analise falhou"
  fi
  python3 "$HERE/relatorio.py" "$DIR/analise.json" "$SLUG" > "$DIR/analise.md" || die "relatorio falhou"

  # banco pesquisavel: uma linha por analise
  python3 - "$DIR/analise.json" "$DIR/meta.json" "$INDEX" <<'PY'
import json, sys, datetime
a = json.load(open(sys.argv[1])); m = json.load(open(sys.argv[2]))
au = a.get("audio") or {}; f = a.get("fotografia") or {}; mo = a.get("montagem") or {}
row = {
  "slug": m.get("slug"), "titulo": m.get("titulo"), "url": m.get("url"),
  "canal": m.get("canal"), "duracao_s": m.get("duracao_s"),
  "quando": datetime.datetime.now().isoformat(timespec="seconds"),
  "tipo": a.get("tipo"), "resumo": a.get("resumo"),
  "look": f.get("look"), "paleta": f.get("paleta"),
  "movimentos": sorted({c.get("movimento") for c in (a.get("camera") or []) if c.get("movimento")}),
  "ritmo": mo.get("ritmo"), "cortes_por_minuto": mo.get("cortes_por_minuto"),
  "musica": au.get("genero"), "bpm": au.get("bpm_aprox"), "mood": au.get("mood"),
  "tags": a.get("tags"), "referencias": a.get("referencias_estilo"),
}
with open(sys.argv[3], "a") as fh:
    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
PY

  if [ "$KEEP" != 1 ]; then
    [ "$ENVIA" != "$FILE" ] && rm -f "$ENVIA"
    rm -f "$FILE"
    # o meta nao pode apontar pra um arquivo que acabou de ser apagado
    tmp="$(mktemp)"; jq '.arquivo = null' "$DIR/meta.json" > "$tmp" && mv "$tmp" "$DIR/meta.json"
  fi
  echo "[analisevideo] pronto: $SLUG"
  echo "$DIR/analise.md"
  ;;

ver)
  S="${1:?ver <slug>}"; cat "$BANCO/$S/analise.md" ;;

json)
  S="${1:?json <slug>}"; cat "$BANCO/$S/analise.json" ;;

prompts)
  S="${1:?prompts <slug>}"
  A="$BANCO/$S/analise.json"; [ -f "$A" ] || die "sem analise: $S"
  python3 - "$A" <<'PY2'
import json, sys
a = json.load(open(sys.argv[1]))
r = a.get("reproduzir") or {}
cenas = r.get("prompts_gerador_video") or []
if not cenas:
    p = r.get("prompt_gerador_video")
    print(p or "(sem prompts nesta analise — rode 'analisa' de novo)")
    raise SystemExit(0)
for i, c in enumerate(cenas, 1):
    d = f" ~{c['duracao_s']}s" if c.get("duracao_s") else ""
    print(f"--- Cena {c.get('cena', i)} [{c.get('t_inicio','?')}-{c.get('t_fim','?')}]{d} "
          f"{c.get('titulo','')}".rstrip())
    print(c.get("prompt", "").strip())
    if c.get("negativo"):
        print(f"negative: {c['negativo']}")
    print()
PY2
  ;;

list)
  N="${1:-15}"
  [ -f "$INDEX" ] || { echo "banco vazio ($BANCO)"; exit 0; }
  tail -n "$N" "$INDEX" | jq -r '"\(.quando[0:16])  \(.slug)  [\(.tipo // "-")]  \(.titulo // "")"'
  ;;

search)
  Q="${1:?search \"<termo>\"}"
  [ -f "$INDEX" ] || { echo "banco vazio"; exit 0; }
  jq -c --arg q "$(echo "$Q" | tr '[:upper:]' '[:lower:]')" \
    'select((tostring | ascii_downcase) | contains($q))' "$INDEX" \
    | jq -r '"\(.slug)  [\(.tipo // "-")] \(.titulo // "")\n   \(.resumo // "" | .[0:160])\n   tags: \(.tags // [] | join(", "))"'
  ;;

stats)
  [ -f "$INDEX" ] || { echo "banco vazio ($BANCO)"; exit 0; }
  echo "banco: $BANCO"
  echo "analises: $(wc -l < "$INDEX")"
  echo "-- tipos:";       jq -r '.tipo // "-"' "$INDEX" | sort | uniq -c | sort -rn | head
  echo "-- movimentos:";  jq -r '.movimentos[]?' "$INDEX" | sort | uniq -c | sort -rn | head
  echo "-- tags:";        jq -r '.tags[]?' "$INDEX" | sort | uniq -c | sort -rn | head -15
  ;;

reindex)
  : > "$INDEX"
  for d in "$BANCO"/*/; do
    [ -f "$d/analise.json" ] && [ -f "$d/meta.json" ] || continue
    python3 - "$d/analise.json" "$d/meta.json" "$INDEX" <<'PY'
import json, sys, datetime, os
a = json.load(open(sys.argv[1])); m = json.load(open(sys.argv[2]))
au = a.get("audio") or {}; f = a.get("fotografia") or {}; mo = a.get("montagem") or {}
row = {"slug": m.get("slug"), "titulo": m.get("titulo"), "url": m.get("url"),
  "canal": m.get("canal"), "duracao_s": m.get("duracao_s"),
  "quando": datetime.datetime.fromtimestamp(os.path.getmtime(sys.argv[1])).isoformat(timespec="seconds"),
  "tipo": a.get("tipo"), "resumo": a.get("resumo"), "look": f.get("look"),
  "paleta": f.get("paleta"),
  "movimentos": sorted({c.get("movimento") for c in (a.get("camera") or []) if c.get("movimento")}),
  "ritmo": mo.get("ritmo"), "cortes_por_minuto": mo.get("cortes_por_minuto"),
  "musica": au.get("genero"), "bpm": au.get("bpm_aprox"), "mood": au.get("mood"),
  "tags": a.get("tags"), "referencias": a.get("referencias_estilo")}
open(sys.argv[3], "a").write(json.dumps(row, ensure_ascii=False) + "\n")
PY
  done
  echo "reindexado: $(wc -l < "$INDEX") analises"
  ;;

*)
  sed -n '2,20p' "$0" | sed 's/^# \?//'
  ;;
esac
