# Falhas

Uma linha por falha real. Mais recente no topo.

| data | o que quebrou | menor correção | prompt \| infra |
|---|---|---|---|
| 2026-08-24 | analise morria com 503 do Gemini (jobs 5156/5158/5159) mesmo havendo chave boa: o codigo insistia 6x (5,5 min) com a chave lotada e desistia, porque assumia que 5xx e congestao GLOBAL | 5xx esgotado vira troca de chave — medido: no mesmo minuto 2 chaves respondiam e 2 davam 503 | prompt |
| 2026-08-24 | Facebook recusava todo download (`Cannot parse data`, 503) — jobs 5152 a 5155 do bot, quatro links seguidos; o inemavox baixava os MESMOS links | passar `--cookies-from-browser firefox:<perfil>` (e `--impersonate chrome`) nos sites de sessão, como o inemavox já fazia | infra |
