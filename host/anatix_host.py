#!/usr/bin/env python3
"""
Anatix — cliente de terminal para hubs Pybricks (Bluetooth ou cabo USB)

Conecta no hub, mantém o handshake (ANX PING), mostra a telemetria ao vivo
e, se quiser, grava tudo em CSV. Também pode enviar e iniciar o programa.

Instalação:
    pip install pybricksdev

Exemplos:
    python anatix_host.py --ble                         # primeiro hub Pybricks
    python anatix_host.py --ble "Pybricks Hub" --csv corrida.csv
    python anatix_host.py --usb --programa meu_robo.py

Com --programa, o anatix.py precisa estar na mesma pasta do programa.
Sem --programa, inicie o programa pelo botão do hub depois de conectar.
"""
import argparse
import asyncio
import csv
import os
import sys
import time
from collections import deque

from anatix_protocol import parse_line

PING_S = 0.5
BANDWIDTH = {"ble": 4000, "usb": 16000}


class Painel:
    def __init__(self, csv_path):
        self.hello = None
        self.values = {}
        self.states = {}
        self.sections = {}
        self.loop = None
        self.events = deque(maxlen=8)
        self.console = deque(maxlen=8)
        self.invalid = 0
        self.frames = 0
        self._csv_file = None
        self._csv = None
        if csv_path:
            self._csv_file = open(csv_path, "w", newline="", encoding="utf-8")
            self._csv = csv.writer(self._csv_file)
            self._csv.writerow(["pc_s", "robo_ms", "tipo", "nome", "valor"])

    def close(self):
        if self._csv_file:
            self._csv_file.close()

    def feed(self, line):
        f = parse_line(line)
        if f["kind"] == "console":
            if f["text"].strip():
                self.console.append(f["text"])
            return None
        if f["kind"] == "invalid":
            self.invalid += 1
            return None
        self.frames += 1
        t, ms, fl = f["type"], f["ms"], f["fields"]
        row = None
        if t == "H" and len(fl) >= 4:
            self.hello = {"versao": fl[0], "robo": fl[1], "placa": fl[2], "periodo": fl[3]}
            self.sections.clear()
        elif t == "V" and len(fl) >= 2:
            self.values[fl[0]] = fl[1]
            row = (fl[0], fl[1])
        elif t == "E" and len(fl) >= 2:
            self.events.append("%8.2fs  %s (%s)" % (ms / 1000, fl[0], fl[1]))
            row = (fl[0], fl[1])
        elif t == "S" and len(fl) >= 2:
            self.states[fl[0]] = fl[1]
            row = (fl[0], fl[1])
        elif t == "T" and len(fl) >= 4:
            self.sections[fl[0]] = fl[1:4]
        elif t == "L" and len(fl) >= 5:
            self.loop = fl[:5]
            row = ("loop_hz", fl[0])
        elif t == "M" and fl:
            self.console.append("[robô] " + fl[0])
            row = ("log", fl[0])
        if row and self._csv:
            self._csv.writerow(["%.3f" % time.time(), ms, t, row[0], row[1]])
        return t

    def render(self, transporte, conectado):
        out = ["\x1b[2J\x1b[H"]
        h = self.hello
        titulo = "%s (%s)" % (h["robo"], h["placa"]) if h else "aguardando o programa do robô..."
        out.append("ANATIX · %s · %s · %s\n" % (transporte.upper(), titulo,
                                              "conectado" if conectado else "sem telemetria"))
        out.append("frames: %d   inválidos: %d\n\n" % (self.frames, self.invalid))
        if self.loop:
            hz, avg, mx, ram, drops = self.loop
            ram_txt = "-" if ram == "-1" else "%s B" % ram
            out.append("LOOP  %s Hz   média %.2f ms   pior %.2f ms   RAM livre %s   descartes %s\n\n"
                       % (hz, int(avg) / 1000, int(mx) / 1000, ram_txt, drops))
        if self.values:
            out.append("MÉTRICAS\n")
            for k in sorted(self.values):
                out.append("  %-24s %s\n" % (k, self.values[k]))
            out.append("\n")
        if self.states:
            out.append("ESTADOS\n")
            for k, v in sorted(self.states.items()):
                out.append("  %-24s %s\n" % (k, v))
            out.append("\n")
        if self.sections:
            out.append("TEMPOS            execuções    média (ms)    pior (ms)\n")
            for k, (n, avg, mx) in sorted(self.sections.items()):
                out.append("  %-16s %9s %13.2f %12.2f\n" % (k, n, int(avg) / 1000, int(mx) / 1000))
            out.append("\n")
        if self.events:
            out.append("EVENTOS\n" + "".join("  %s\n" % e for e in self.events) + "\n")
        if self.console:
            out.append("CONSOLE\n" + "".join("  %s\n" % c for c in self.console))
        sys.stdout.write("".join(out))
        sys.stdout.flush()


async def conectar(args):
    from pybricksdev.connections.pybricks import PybricksHubBLE, PybricksHubUSB

    if args.usb:
        from usb.core import find as find_usb
        from pybricksdev.usb import (
            LEGO_USB_VID,
            MINDSTORMS_INVENTOR_USB_PID,
            SPIKE_ESSENTIAL_USB_PID,
            SPIKE_PRIME_USB_PID,
        )

        def eh_pybricks(dev):
            try:
                return (
                    dev.idVendor == LEGO_USB_VID
                    and dev.idProduct in (SPIKE_PRIME_USB_PID, SPIKE_ESSENTIAL_USB_PID,
                                          MINDSTORMS_INVENTOR_USB_PID)
                    and (dev.product or "").endswith("Pybricks")
                )
            except Exception:
                return False

        dev = find_usb(custom_match=eh_pybricks)
        if dev is None:
            sys.exit("Hub Pybricks não encontrado no USB. O firmware precisa ter USB habilitado.")
        hub = PybricksHubUSB(dev)
    else:
        from pybricksdev.ble import find_device

        nome = args.ble if isinstance(args.ble, str) else None
        print("Procurando %s por Bluetooth..." % (nome or "hub Pybricks"))
        hub = PybricksHubBLE(await find_device(nome))

    await hub.connect()
    return hub


async def main(args):
    from pybricksdev.ble.pybricks import StatusFlag

    transporte = "usb" if args.usb else "ble"
    hub = await conectar(args)
    painel = Painel(args.csv)

    # Recebe as linhas do stdout do hub numa fila (sem imprimir direto).
    hub.print_output = False
    hub._enable_line_handler = True

    if args.programa:
        print("Enviando e iniciando %s..." % args.programa)
        await hub.run(args.programa, wait=False, print_output=False, line_handler=True)

    estado = {"telemetria": False, "ultimo_frame": 0.0}

    def rodando():
        return bool(hub.status_observable.value & StatusFlag.USER_PROGRAM_RUNNING)

    async def pinger():
        while True:
            if rodando():
                try:
                    await hub.write_line("ANX PING")
                except Exception:
                    pass
            await asyncio.sleep(PING_S)

    async def leitor():
        while True:
            linha = await hub.read_line()
            tipo = painel.feed(linha)
            if tipo:
                estado["ultimo_frame"] = time.monotonic()
            if tipo == "H":
                await hub.write_line("ANX BW %d" % (args.banda or BANDWIDTH[transporte]))
                if args.rate:
                    await hub.write_line("ANX RATE %d" % args.rate)

    async def tela():
        while True:
            ativo = time.monotonic() - estado["ultimo_frame"] < 2.5
            painel.render(transporte, ativo)
            await asyncio.sleep(0.5)

    tarefas = [asyncio.ensure_future(t()) for t in (pinger, leitor, tela)]
    try:
        await hub.race_disconnect(asyncio.gather(*tarefas))
    except Exception as e:
        print("\nConexão encerrada: %s" % e)
    finally:
        for t in tarefas:
            t.cancel()
        try:
            if rodando():
                await hub.write_line("ANX STOP")
            await hub.disconnect()
        except Exception:
            pass
        painel.close()
        if args.csv:
            print("CSV salvo em %s" % os.path.abspath(args.csv))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Telemetria Anatix para hubs Pybricks")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--ble", nargs="?", const=True, metavar="NOME",
                   help="conectar por Bluetooth (opcional: nome do hub)")
    g.add_argument("--usb", action="store_true", help="conectar pelo cabo USB")
    p.add_argument("--programa", help="arquivo .py para enviar e iniciar no hub")
    p.add_argument("--csv", help="grava métricas, eventos e estados em CSV")
    p.add_argument("--rate", type=int, help="período dos relatórios L/T em ms (20 a 10000)")
    p.add_argument("--banda", type=int, help="banda máxima da telemetria em bytes/s")
    try:
        asyncio.run(main(p.parse_args()))
    except KeyboardInterrupt:
        pass
