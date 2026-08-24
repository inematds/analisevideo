# Falhas

Uma linha por falha real. Mais recente no topo.

| data | o que quebrou | menor correção | prompt \| infra |
|---|---|---|---|
| 2026-08-24 | Facebook recusava todo download (`Cannot parse data`, 503) — jobs 5152 a 5155 do bot, quatro links seguidos; o inemavox baixava os MESMOS links | passar `--cookies-from-browser firefox:<perfil>` (e `--impersonate chrome`) nos sites de sessão, como o inemavox já fazia | infra |
