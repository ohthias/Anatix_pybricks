"""
Testes no PC (CPython) do anatix.py, com o Pybricks simulado.

    python tests/test_anatix.py
"""
import io
import os
import sys
import types

# ---- Pybricks falso ----------------------------------------------------------
_fake_ms = [0]
_stdin_queue = []


class StopWatch:
    def time(self):
        return _fake_ms[0]


def wait(ms):
    _fake_ms[0] += ms


def read_input_byte():
    return _stdin_queue.pop(0) if _stdin_queue else None


pybricks = types.ModuleType("pybricks")
pybricks.version = ("primehub", "4.0.0", "teste")
tools = types.ModuleType("pybricks.tools")
tools.StopWatch = StopWatch
tools.wait = wait
tools.read_input_byte = read_input_byte
pybricks.tools = tools
sys.modules["pybricks"] = pybricks
sys.modules["pybricks.tools"] = tools

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "host"))
import anatix  # noqa: E402
from anatix_protocol import parse_line  # noqa: E402

anatix.ticks_us = lambda: _fake_ms[0] * 1000
anatix.ticks_diff = lambda a, b: a - b

out = io.StringIO()
anatix.stdout = out


def send(cmd):
    _stdin_queue.extend((cmd + "\n").encode())


def frames():
    lines = out.getvalue().splitlines()
    out.seek(0)
    out.truncate()
    parsed = [parse_line(l) for l in lines]
    for l, p in zip(lines, parsed):
        assert p is not None and p["kind"] != "invalid", "frame inválido: " + l
    return parsed


class Hub:
    class battery:
        @staticmethod
        def voltage():
            return 8123


falhas = 0


def check(cond, msg):
    global falhas
    if not cond:
        falhas += 1
        print("FALHOU:", msg)
    else:
        print("ok:", msg)


# ---- Testes -----------------------------------------------------------------
a = anatix.Anatix()
a.begin("Robo", Hub())
a.update()
a.value("x", 1)
check(out.getvalue() == "", "nada é enviado antes do PING")

send("ANX PING")
a.update()
f = frames()
check(f[0]["type"] == "H" and f[0]["fields"] == ["1", "Robo", "primehub", "250"], "hello após PING")
check(any(x["type"] == "V" and x["fields"][0] == "hub_bateria_v" and x["fields"][1] == "8.123" for x in f), "bateria automática")

a.value("dist", 12.5)
a.value("conta", 7)
a.value("ruim", float("nan"))
a.event("obstaculo", 33.9)
f = frames()
check([x["fields"] for x in f] == [["dist", "12.500"], ["conta", "7"], ["ruim", "nan"], ["obstaculo", "33"]], "valores e evento")

a.state("modo", "seguir")
a.state("modo", "seguir")
a.state("modo", "desviar")
f = frames()
check([x["fields"][1] for x in f] == ["seguir", "desviar"], "estado só envia quando muda")

_fake_ms[0] = 100
a.value("lento", 1, every=1000)
a.value("lento", 2, every=1000)
_fake_ms[0] = 1200
a.value("lento", 3, every=1000)
f = frames()
check([x["fields"][1] for x in f] == ["1", "3"], "limite de frequência (every)")

send("ANX PING")
_fake_ms[0] = 1300
a.update()
frames()
for _ in range(5):
    with a.scope("pid"):
        _fake_ms[0] += 2
    a.update()
_fake_ms[0] = 1600
a.update()
f = [x for x in frames() if x["type"] in "LT"]
t = [x for x in f if x["type"] == "T"]
check(len(t) == 1 and t[0]["fields"][:3] == ["pid", "5", "2000"], "seção cronometrada (T)")
check(any(x["type"] == "L" for x in f), "relatório de loop (L)")

a.log("ola, mundo\nlinha 2")
f = frames()
check(f[0]["fields"] == ["ola, mundo linha 2"], "log com vírgula e quebra de linha")

# limite de banda: muitos frames de uma vez -> descartes
a.set_bandwidth(400)
for i in range(200):
    a.value("spam", i)
enviados = len(frames())
check(enviados < 200, "limite de banda descarta (%d de 200 enviados)" % enviados)

send("ANX RATE 500")
send("ANX STOP")
a.update()
a.value("x", 1)
check(out.getvalue() == "", "STOP para de transmitir")

send("ANX PING")
a.update()
f = frames()
check(f[0]["fields"][3] == "500", "RATE altera o período")
check(any(x["type"] == "S" and x["fields"] == ["modo", "desviar"] for x in f) is False, "estado ainda não reenviado antes de state()")
a.state("modo", "desviar")
check(frames()[0]["fields"] == ["modo", "desviar"], "estado reenviado após reconectar")

_fake_ms[0] += 2500
a.update()
a.value("x", 1)
check(out.getvalue() == "", "timeout sem PING desliga")

linhas = []
a.set_line_handler(linhas.append)
send("parar")
a.update()
check(linhas == ["parar"], "linhas que não são do Anatix vão para o handler")

b = anatix.Anatix()
b.begin("X", enabled=False)
b.update()
b.value("x", 1)
with b.scope("y"):
    pass
check(out.getvalue() == "" and b.connected() is False, "enabled=False não envia nada")

c = anatix.Anatix()
c.begin("Livre", require_handshake=False)
c.value("x", 1)
f = frames()
check(f[0]["type"] == "H" and f[1]["type"] == "V", "require_handshake=False transmite direto")

# compatibilidade com o exemplo do PROTOCOLO.md da versão Arduino
check(parse_line("$ANX,V,1520,distancia_cm,23.400*23")["fields"] == ["distancia_cm", "23.400"], "checksum do exemplo oficial")
check(parse_line("$ANX,V,1520,distancia_cm,23.400*24")["kind"] == "invalid", "checksum errado é rejeitado")
check(parse_line("ola mundo")["kind"] == "console", "linha comum vira console")

print()
print("TODOS OK" if not falhas else "%d FALHA(S)" % falhas)
sys.exit(1 if falhas else 0)
