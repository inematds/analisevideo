"""Rotação de chave do Gemini: cota/bloqueio troca de chave, congestão espera.

Roda sem rede: o `urlopen` é trocado por um dublê que devolve os códigos que a
gente quer provar.
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analisa  # noqa: E402


def _erro(codigo):
    return urllib.error.HTTPError("u", codigo, "x", {}, None)


def _resposta(texto="{}"):
    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(
                {"candidates": [{"content": {"parts": [{"text": texto}]}}]}).encode()

    return R()


def _resposta_or(texto="{}"):
    """A MESMA casca, no formato do OpenRouter: `choices[].message.content`."""
    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": texto}}]}).encode()

    return R()


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    monkeypatch.setattr(analisa.time, "sleep", lambda *_: None)


@pytest.fixture
def video(tmp_path):
    """Um arquivo pequeno de verdade: o caminho inline lê o disco."""
    p = tmp_path / "v.mp4"
    p.write_bytes(b"\x00" * 64)
    return str(p)


def test_chaves_deduplicam_pelo_valor(monkeypatch):
    """GOOGLE_API_KEY e GEMINI_API_KEY costumam ser a MESMA chave — tentar duas
    vezes a mesma coisa depois de um 429 é só perder tempo."""
    monkeypatch.setenv("GOOGLE_API_KEY", "aaa")
    monkeypatch.setenv("GEMINI_API_KEY", "aaa")
    monkeypatch.setenv("GEMINI_API_KEY_INEMACCBOT_TIME", "bbb")
    monkeypatch.delenv("GEMINI_API_KEY_INEMACCBOT_PROMPTS", raising=False)
    assert analisa.chaves_disponiveis() == [("GOOGLE_API_KEY", "aaa"),
                                            ("GEMINI_API_KEY_INEMACCBOT_TIME", "bbb")]


def test_chaves_respeitam_a_ordem(monkeypatch):
    for n in analisa.NOMES_CHAVE:
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY_INEMACCBOT_PROMPTS", "z")
    monkeypatch.setenv("GOOGLE_API_KEY", "a")
    assert [n for n, _ in analisa.chaves_disponiveis()] == [
        "GOOGLE_API_KEY", "GEMINI_API_KEY_INEMACCBOT_PROMPTS"]


@pytest.mark.parametrize("codigo", [429, 403])
def test_cota_e_bloqueio_pedem_OUTRA_chave(monkeypatch, codigo, video):
    """429 (cota) e 403 (bloqueada) não melhoram com espera — melhoram com
    outra chave, que está em outro projeto."""
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(_erro(codigo)))
    with pytest.raises(analisa.CotaOuBloqueio) as e:
        analisa.tentar_com("k", video, "video/mp4", 10, "ctx", (1, 2))
    assert e.value.codigo == codigo


def test_congestao_espera_e_NAO_troca(monkeypatch, video):
    """503 é o Gemini lotado: a chave não tem culpa e trocar não ajuda."""
    chamadas = []

    def fake(*a, **k):
        chamadas.append(1)
        if len(chamadas) < 3:
            raise _erro(503)
        return _resposta('{"ok":1}')

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert analisa.tentar_com("k", video, "video/mp4", 10, "ctx", (1, 2, 3)) == '{"ok":1}'
    assert len(chamadas) == 3          # esperou e insistiu na MESMA chave


def test_congestao_que_NAO_passa_vira_troca_de_chave(monkeypatch, video):
    """503 esgotado troca de chave — porque o 503 do Gemini e POR PROJETO.

    Medido em 2026-08-24: no mesmo minuto, GOOGLE_API_KEY e GEMINI_API_KEY
    responderam e as duas GEMINI_API_KEY_INEMACCBOT_* devolveram 503. O codigo
    insistia 6 vezes com a chave lotada (5,5 min) e desistia com duas chaves
    boas na lista, nunca tentadas — foi assim que os jobs 5156/5158/5159
    morreram com o video ja baixado e comprimido.

    A espera continua vindo primeiro (`test_congestao_espera_e_NAO_troca`): a
    congestao costuma passar, e trocar de chave na primeira tentativa jogaria
    fora o upload feito para o projeto daquela chave.
    """
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(_erro(503)))
    with pytest.raises(analisa.CotaOuBloqueio):
        analisa.tentar_com("k", video, "video/mp4", 10, "ctx", (1,))


def test_upload_com_cota_estourada_tambem_troca(monkeypatch, video):
    """O upload é o passo caro do arquivo grande. Sem converter o 429 dele,
    a troca de chave nunca aconteceria no caso que mais importa."""
    monkeypatch.setattr(analisa, "upload",
                        lambda *a, **k: (_ for _ in ()).throw(_erro(429)))
    with pytest.raises(analisa.CotaOuBloqueio):
        analisa.tentar_com("k", video, "video/mp4",
                           analisa.INLINE_LIMIT + 1, "ctx", (1,))


def test_main_TROCA_de_chave_e_conclui(monkeypatch, video, capsys):
    """O caminho inteiro: a 1ª chave estoura a cota, a 2ª entrega a análise.

    É este o teste que prova o pedido — ter três chaves não vale nada se o
    programa não passar para a seguinte sozinho.
    """
    for n in analisa.NOMES_CHAVE:
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "estourada")
    monkeypatch.setenv("GEMINI_API_KEY_INEMACCBOT_TIME", "boa")

    usadas = []

    def fake(req, *a, **k):
        chave = req.full_url.rsplit("key=", 1)[-1]
        usadas.append(chave)
        if chave == "estourada":
            raise _erro(429)
        return _resposta('{"resumo": "ok"}')

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setattr(sys, "argv", ["analisa.py", video, "12"])
    assert analisa.main() == 0
    assert usadas == ["estourada", "boa"]           # tentou uma, passou pra outra
    saida = capsys.readouterr()
    assert json.loads(saida.out)["resumo"] == "ok"
    assert "GEMINI_API_KEY_INEMACCBOT_TIME" in saida.err   # diz qual usou


def test_main_com_TODAS_estouradas_explica(monkeypatch, video, capsys):
    for n in analisa.NOMES_CHAVE:
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "a")
    monkeypatch.setenv("GEMINI_API_KEY_INEMACCBOT_PROMPTS", "b")
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(_erro(429)))
    monkeypatch.setattr(sys, "argv", ["analisa.py", video, "12"])
    assert analisa.main() == 1
    erro = json.loads(capsys.readouterr().out)["erro"]
    assert "cota" in erro and "GOOGLE_API_KEY" in erro   # diz QUAIS falharam


def test_main_sem_chave_nenhuma(monkeypatch, video, capsys):
    for n in analisa.NOMES_CHAVE:
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setattr(sys, "argv", ["analisa.py", video, "12"])
    assert analisa.main() == 1
    assert "nenhuma chave" in json.loads(capsys.readouterr().out)["erro"]


# ---------------------------------------------------------------- reserva
# O que se perde quando o Gemini recusa TODAS as chaves nao e uma chamada de
# API: e o download e a compressao ja feitos. Em 2026-08-24 um clipe de 41 MB do
# Facebook levou minutos para chegar na analise e morreu com tres chaves em 429.

def test_reserva_entra_quando_o_gemini_inteiro_recusa(monkeypatch, video, capsys):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setattr(analisa, "chaves_disponiveis", lambda: [("GOOGLE_API_KEY", "k")])
    monkeypatch.setattr(analisa, "tentar_com",
                        lambda *a, **k: (_ for _ in ()).throw(analisa.CotaOuBloqueio(429)))
    monkeypatch.setattr(analisa, "tentar_openrouter",
                        lambda *a, **k: '{"resumo":"veio da reserva"}')
    monkeypatch.setattr(sys, "argv", ["analisa.py", video, "10"])
    assert analisa.main() == 0
    saida = json.loads(capsys.readouterr().out)
    assert saida["resumo"] == "veio da reserva"
    # O modelo REGISTRADO tem que ser o que analisou — senao o banco diz Gemini
    # para uma analise que o Gemini nao fez.
    assert saida["_modelo"] == analisa.OPENROUTER_MODELO


def test_sem_reserva_configurada_falha_como_antes(monkeypatch, video, capsys):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(analisa, "chaves_disponiveis", lambda: [("GOOGLE_API_KEY", "k")])
    monkeypatch.setattr(analisa, "tentar_com",
                        lambda *a, **k: (_ for _ in ()).throw(analisa.CotaOuBloqueio(429)))
    monkeypatch.setattr(sys, "argv", ["analisa.py", video, "10"])
    assert analisa.main() == 1
    assert "429" in capsys.readouterr().out


def test_reserva_espera_no_429_do_pool_compartilhado(monkeypatch, video):
    """O 429 da reserva nao e cota nossa: e `rate-limited upstream`, um pool
    compartilhado que passa sozinho. Desistir nele seria desistir cedo demais."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setattr(analisa.time, "sleep", lambda *_: None)
    chamadas = []

    def fake(*a, **k):
        chamadas.append(1)
        if len(chamadas) < 3:
            raise _erro(429)
        return _resposta_or('{"ok":1}')

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert analisa.tentar_openrouter(video, "video/mp4", "ctx", (1, 2, 3)) == '{"ok":1}'
    assert len(chamadas) == 3
