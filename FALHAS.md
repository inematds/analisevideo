# Falhas

Uma linha por falha real. Mais recente no topo.

| data | o que quebrou | menor correção | prompt \| infra |
|---|---|---|---|
| 2026-09-08 | a reserva do OpenRouter respondia 402 em todo vídeo: a API exige **US$ 1,00 disponíveis na chave** para pedido com vídeo, e a chave (teto de US$ 5) tinha US$ 0,72 — a conta tinha US$ 6,98. Texto passava, vídeo não; o `analisa.py` descarta o corpo do 402 e a mensagem ("requires at least $1.00 in balance for video") nunca chegou ao log | subir ou remover o teto da chave em openrouter.ai/settings/keys; e mostrar o corpo do erro HTTP no log | infra |
| 2026-08-28 | job 6331: `erro: yt-dlp nao instalado` numa máquina onde ele ESTÁ instalado — o `yt-dlp` do pip mora em `~/.local/bin`, e o serviço do bot roda pelo `systemd --user`, que não herda esse diretório no PATH. Mesma classe do `claude` 2.1.63 do musicavideo no mesmo dia | o script põe `~/.local/bin` no PATH no topo (só se ainda não estiver); o fecho da classe é `Environment=PATH=` na unit do bot | infra |
| 2026-08-26 | a reserva `stealth/ox-alpha` sumiu do OpenRouter — modelo em avaliacao, como o proprio codigo previa; toda analise ia para um modelo inexistente porque a reserva estava NA FRENTE do Gemini | trocar o slug para `google/gemini-3.7-flash` e devolver o Gemini direto para a frente (`ANALISEVIDEO_MOTOR` default `gemini`), com aviso no stderr sempre que a reserva paga rodar | infra |
| 2026-08-24 | analise do Facebook morreu com 41 MB ja baixados e comprimidos: as TRES chaves do Gemini em 429 (cota do dia) — sem correcao possivel no codigo, e o trabalho caro ja estava feito | reserva `stealth/ox-alpha` (OpenRouter) atras da cascata de chaves — provado em producao no mesmo video | infra |
| 2026-08-24 | analise morria com 503 do Gemini (jobs 5156/5158/5159) mesmo havendo chave boa: o codigo insistia 6x (5,5 min) com a chave lotada e desistia, porque assumia que 5xx e congestao GLOBAL | 5xx esgotado vira troca de chave — medido: no mesmo minuto 2 chaves respondiam e 2 davam 503 | prompt |
| 2026-08-24 | Facebook recusava todo download (`Cannot parse data`, 503) — jobs 5152 a 5155 do bot, quatro links seguidos; o inemavox baixava os MESMOS links | passar `--cookies-from-browser firefox:<perfil>` (e `--impersonate chrome`) nos sites de sessão, como o inemavox já fazia | infra |
