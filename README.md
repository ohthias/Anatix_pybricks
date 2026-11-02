# Anatix para Pybricks

**Telemetria em tempo real para robôs LEGO.** Coloque algumas linhas no programa do Pybricks, conecte por
**Bluetooth** ou **cabo USB** e veja sensores, giro, estados das missões e tempos de execução enquanto o robô
roda na mesa.

É a versão em Python do [Anatix para Arduino](https://github.com/ohthias/Anatix_C), feita para a **FLL** e para
qualquer robô com [Pybricks](https://pybricks.com). As duas versões falam o mesmo protocolo e são analisadas no
mesmo lugar: o **LabTest do [RoboStage](https://robostage.com.br/anatix)**.

```python
from pybricks.hubs import PrimeHub
from anatix import anx

hub = PrimeHub()
anx.begin("MeuRobo", hub)

while True:
    anx.update()
    anx.value("heading", hub.imu.heading())
```

---

- [Por que usar](#por-que-usar)
- [Compatibilidade](#compatibilidade)
- [Começo rápido](#começo-rápido)
- [Exemplos](#exemplos)
- [Referência da API](#referência-da-api)
- [Onde ver os dados](#onde-ver-os-dados)
- [Desempenho e limites](#desempenho-e-limites)
- [Problemas comuns](#problemas-comuns)
- [Protocolo](#protocolo)
- [Para quem vem do Arduino](#para-quem-vem-do-arduino)
- [Estrutura e testes](#estrutura-e-testes)

## Por que usar

Quando uma missão falha, quase sempre falta saber **o que o robô estava medindo e decidindo naquele instante**.
O Anatix responde isso com dados:

| Pergunta | Chamada |
|---|---|
| Quanto o giroscópio marcava antes de errar o giro? | `anx.value("heading", ...)` |
| Em que missão o robô estava quando travou? | `anx.state("missao", "m03")` |
| Quanto tempo cada missão leva na rodada de 2:30? | `with anx.scope("m03"):` |
| Quando ele terminou a missão ou perdeu a linha? | `anx.event("missao_concluida")` |
| O loop está lento? A bateria está caindo? | automático (loops/s, tempo de loop, RAM, bateria) |

E sem atrapalhar o robô:

- **Sem conexão, sem custo.** Nada é transmitido até o computador pedir (`ANX PING`). Se a conexão cair, a
  telemetria desliga sozinha em 2 s.
- **Nunca trava o loop.** Há um limite de banda; o que passar dele é descartado e contado, nunca enfileirado.
- **Some no torneio.** `anx.begin(..., enabled=False)` troca todas as chamadas por funções vazias.
- **Funciona em programas sem loop**, como as missões da FLL, com `anx.keep_alive()` e `multitask()`.

## Compatibilidade

| Hub | Bluetooth | Cabo USB |
|---|:---:|:---:|
| SPIKE Prime | ✅ | ✅ ¹ |
| SPIKE Essential | ✅ | ✅ ¹ |
| MINDSTORMS Robot Inventor | ✅ | ✅ ¹ |
| Technic Hub, City Hub, Move Hub | ✅ | — |

- Firmware **Pybricks 3.3 ou mais novo** (o Anatix usa `read_input_byte` e `multitask`).
- ¹ O USB precisa de um firmware Pybricks com USB habilitado. Na versão 4.0 estável ele foi desligado
  temporariamente; está nas versões beta. O Bluetooth funciona em todos os casos.
- No computador: **Chrome ou Edge** (Web Bluetooth e WebUSB não existem no Firefox nem no Safari), ou
  Python 3.10+ para o cliente de terminal.

## Começo rápido

**1. Instale o firmware Pybricks** no hub, se ainda não tiver: [code.pybricks.com](https://code.pybricks.com) →
⚙️ → *Install Pybricks Firmware*.

**2. Adicione a biblioteca ao projeto.** No Pybricks Code, crie um arquivo chamado **`anatix`** e cole nele o
conteúdo de [`anatix.py`](anatix.py). Ele fica ao lado do seu programa, como qualquer outro arquivo do projeto.

**3. Marque o seu código:**

```python
from pybricks.hubs import PrimeHub
from anatix import anx

hub = PrimeHub()
anx.begin("MeuRobo", hub)       # com o hub, a bateria é enviada sozinha

while True:
    anx.update()                # obrigatório, 1x por volta do loop
    anx.value("heading", hub.imu.heading())
```

**4. Envie o programa e feche a conexão do Pybricks Code.** O hub aceita um aplicativo por vez.

**5. Conecte e analise.** No RoboStage, abra **LabTest → Anatix**, crie um laboratório **LEGO com Pybricks**,
clique em **Bluetooth** (ou **Cabo USB**) e depois em **Iniciar programa**. Cada execução do programa vira uma
sessão gravada, com gráficos, mapas e tabelas.

> Sem conta no RoboStage? Use o painel local [`host/anatix_web.html`](#painel-local-no-navegador) ou o
> [cliente de terminal](#cliente-de-terminal-python).

## Exemplos

Os três estão em [`examples/`](examples) e rodam em um SPIKE Prime (ajuste as portas do seu robô).

### Missões da FLL (sem loop)

Programas de FLL costumam ser uma sequência de movimentos. Como `robo.straight(500)` bloqueia, ninguém chamaria
`anx.update()`. A solução é rodar `anx.keep_alive()` **em paralelo**, com a multitarefa do Pybricks:

```python
from pybricks.tools import multitask, run_task, wait
from anatix import anx

anx.begin("Robo-FLL", hub)

async def missoes():
    anx.state("missao", "m01")
    with anx.scope("m01"):                  # tempo da missão inteira
        await robo.straight(500)
        await robo.turn(90)
    anx.event("missao_concluida", 1)

    anx.state("missao", "m02")
    with anx.scope("m02"):
        await braco.run_angle(500, 180)

async def sensores():                       # telemetria contínua, opcional
    while True:
        anx.value("heading", hub.imu.heading())
        anx.value("distancia_mm", robo.distance())
        await wait(100)

async def principal():
    await multitask(missoes(), sensores(), anx.keep_alive(), race=True)

run_task(principal())
```

Arquivo completo: [`examples/missoes_fll.py`](examples/missoes_fll.py).

### Seguidor de linha com PID

O mesmo exemplo da versão Arduino, com dois sensores de cor, ultrassônico e `DriveBase`:
[`examples/seguidor_de_linha.py`](examples/seguidor_de_linha.py).

```python
while True:
    anx.update()

    with anx.scope("leitura_cor"):
        esq, dir = sensor_esq.reflection(), sensor_dir.reflection()

    with anx.scope("pid"):
        erro = esq - dir
        correcao = KP * erro + KD * (erro - erro_anterior)
        erro_anterior = erro

    anx.value("pid_erro", erro)
    anx.value("pid_correcao", correcao)
    anx.value("motor_esq_graus_s", motor_esq.speed(), every=100)
    robo.drive(VELOCIDADE_BASE, correcao)
```

### Básico

IMU, botões, estado, tempo de um bloco e log: [`examples/basico.py`](examples/basico.py).

## Referência da API

Tudo passa pelo objeto global `anx`, importado com `from anatix import anx`.

### Ciclo de vida

| Chamada | O que faz |
|---|---|
| `anx.begin(nome, hub=None, require_handshake=True, enabled=True)` | Inicia o Anatix. `hub` habilita a métrica automática `hub_bateria_v`. `require_handshake=False` transmite sempre (útil no terminal do Pybricks Code). `enabled=False` desliga tudo. |
| `anx.update()` | Lê comandos do computador, mede o loop e envia os relatórios. Chame **uma vez por volta do loop**. |
| `await anx.keep_alive(period_ms=20)` | Coroutine que chama `update()` periodicamente. Use com `multitask()` em programas sem loop. |
| `anx.connected()` | `True` enquanto o computador estiver ouvindo. |

### Dados

| Chamada | O que envia |
|---|---|
| `anx.value(nome, v)` | Um número (int ou float; `nan` e `inf` são aceitos). Vira gráfico. |
| `anx.value(nome, v, every=ms)` | Idem, no máximo 1 envio a cada `ms`. Use em métricas que não precisam de todas as amostras. |
| `anx.event(nome)` / `anx.event(nome, n)` | Um evento pontual na linha do tempo, com um inteiro opcional. |
| `anx.state(maquina, estado)` | O estado atual de uma máquina de estados. **Só envia quando muda** (e reenvia ao reconectar). |
| `with anx.scope(nome):` | Cronometra o bloco. O computador recebe execuções, tempo médio e pior tempo. |
| `anx.section_begin(nome)` / `anx.section_end(nome)` | Idem, manual, para trechos que não cabem em um bloco. |
| `anx.log(texto)` | Mensagem de texto livre (pode ter vírgulas). |

### Ajustes

| Chamada | Padrão | O que faz |
|---|---|---|
| `anx.set_report_period(ms)` | 250 | Período dos relatórios de loop e tempos. |
| `anx.set_bandwidth(bytes_por_s)` | 4000 | Banda máxima da telemetria. O RoboStage ajusta sozinho (Bluetooth 4000, USB 16000). |
| `anx.set_battery_period(ms)` | 1000 | Período da métrica `hub_bateria_v` (0 desliga). |
| `anx.set_line_handler(funcao)` | — | Recebe as linhas do stdin que não são do Anatix, para quem também lê comandos pelo terminal. |

As constantes no topo de [`anatix.py`](anatix.py) (`ANATIX_TIMEOUT_MS`, `ANATIX_MAX_CHANNELS`, `ANATIX_RX_BUFFER`…)
podem ser editadas para casos especiais.

### Enviado automaticamente

A cada 250 ms, sem nenhuma linha a mais: **loops por segundo**, tempo médio e pior tempo do loop, **RAM livre**
(se o firmware tiver `gc`) e quantos frames foram **descartados**. Com o `hub` no `begin()`, também a **tensão da
bateria** (`hub_bateria_v`) a cada 1 s.

### Regras

- Nomes sem vírgulas e sem quebras de linha (`"pid_erro"`, não `"pid, erro"`).
- Uma seção não pode ser aninhada nela mesma.
- Até 32 canais (métricas com `every`, estados e seções). Métricas sem `every` não ocupam canal.

## Onde ver os dados

### RoboStage · LabTest (recomendado)

O caminho mais completo: conexão por Bluetooth ou USB direto no navegador, sessões gravadas por execução do
programa, gráficos, mapa XY, mapa de calor, tabelas e exportação.

- Guia da versão Pybricks: [robostage.com.br/fll/anatix](https://robostage.com.br/fll/anatix)
- As duas versões do Anatix: [robostage.com.br/anatix](https://robostage.com.br/anatix)

### Painel local no navegador

[`host/anatix_web.html`](host/anatix_web.html) é um arquivo único, sem instalação e sem conta. Abra no Chrome ou
Edge do computador. Se o navegador bloquear o arquivo local, sirva a pasta:

```bash
cd host
python -m http.server 8000      # e abra http://localhost:8000/anatix_web.html
```

1. Clique em **Bluetooth** ou **Cabo USB** e escolha o hub.
2. Inicie o programa pelo botão do hub ou em **▶ Iniciar**. O painel manda `ANX PING` sozinho.
3. Clique nas métricas para pô-las no gráfico. **CSV** baixa tudo o que chegou.

### Cliente de terminal (Python)

```bash
pip install pybricksdev
python host/anatix_host.py --ble                          # primeiro hub Pybricks
python host/anatix_host.py --ble "Meu Hub" --csv corrida.csv
python host/anatix_host.py --usb --programa meu_robo.py   # envia, inicia e mostra
```

| Opção | O que faz |
|---|---|
| `--ble [NOME]` / `--usb` | Meio de conexão (com `--ble`, o nome do hub é opcional). |
| `--programa ARQ.py` | Envia e inicia o programa. Deixe o `anatix.py` na mesma pasta. |
| `--csv ARQ.csv` | Grava métricas, eventos, estados e loop. |
| `--rate MS` / `--banda B` | Período dos relatórios e banda da telemetria. |

### Sem aplicativo nenhum

No terminal do Pybricks Code, digite `ANX PING` e as mensagens começam a chegar (elas param 2 s depois do último
PING). Ou use `anx.begin("Robo", require_handshake=False)` para transmitir sempre.

## Desempenho e limites

- **Banda.** O `print` do Pybricks pode esperar quando o link está cheio. Para o loop nunca travar, a biblioteca
  usa um balde de fichas: 4000 bytes/s por padrão (~100 frames/s). Se o contador de **descartes** subir, use
  `every=` nas métricas menos importantes ou conecte por USB.
- **Tempo.** As medições usam `utime.ticks_us()` quando o firmware oferece; senão, a resolução cai para 1 ms
  (as médias continuam boas, mas trechos muito curtos podem aparecer como 0).
- **Memória.** Cerca de 18 KB de código-fonte; o Pybricks compila para bytecode ao enviar. Os canais são limitados
  para o uso de RAM não crescer sem controle.

## Problemas comuns

| Sintoma | O que fazer |
|---|---|
| O hub não aparece na lista do Bluetooth | Feche o Pybricks Code (ou desconecte o hub nele). O hub aceita um aplicativo por vez. Confira se ele está ligado e com Pybricks. |
| Conecta, mas fica em "aguardando o Anatix" | O programa precisa estar rodando e chamar `anx.update()` (ou ter `anx.keep_alive()` no `multitask`). Confira o `from anatix import anx` e o `anx.begin()`. |
| `ImportError: no module named 'anatix'` | O arquivo no Pybricks Code precisa se chamar exatamente `anatix`, no mesmo projeto. |
| O cabo USB não aparece | O firmware precisa ter USB habilitado (versões beta do 4.x). No Windows, o driver também precisa ser WinUSB. Use o Bluetooth. |
| "Sem dados do robô" no meio da execução | O loop parou de chamar `anx.update()` (um `wait` longo, um movimento sem `await`) ou o programa travou. |
| Contador de descartes alto | Use `every=` nas métricas, diminua o número de `value()` por loop ou conecte por USB. |

## Protocolo

Texto simples, uma mensagem por linha, com checksum, idêntico ao da versão Arduino:

```
$ANX,V,1520,distancia_cm,23.400*23
```

O transporte é o stdout/stdin do Pybricks, levado pelo protocolo Pybricks por Bluetooth (GATT) ou USB (bulk).
Mensagens, comandos (incluindo a extensão `ANX BW`) e detalhes do transporte em
[`docs/PROTOCOLO.md`](docs/PROTOCOLO.md).

## Para quem vem do Arduino

| Arduino | Pybricks |
|---|---|
| `ANX_BEGIN(Serial, "nome")` | `anx.begin("nome", hub)` |
| `ANX_UPDATE()` | `anx.update()` ou `await anx.keep_alive()` |
| `ANX_VALUE(nome, v)` | `anx.value(nome, v)` |
| `ANX_VALUE_EVERY(nome, v, ms)` | `anx.value(nome, v, every=ms)` |
| `ANX_EVENT(nome)` / `ANX_EVENT_DATA(nome, n)` | `anx.event(nome)` / `anx.event(nome, n)` |
| `ANX_STATE(maquina, estado)` | `anx.state(maquina, estado)` |
| `ANX_SCOPE(nome)` | `with anx.scope(nome):` |
| `ANX_SECTION_BEGIN/END(nome)` | `anx.section_begin(nome)` / `anx.section_end(nome)` |
| `ANX_LOG(texto)` | `anx.log(texto)` |
| `#define ANATIX_DISABLE` | `anx.begin(..., enabled=False)` |
| `Anatix.setReportPeriod(ms)` | `anx.set_report_period(ms)` |
| `Anatix.setLineHandler(f)` | `anx.set_line_handler(f)` |

## Estrutura e testes

```
├── anatix.py                  biblioteca que roda no hub
├── examples/
│   ├── basico.py              IMU, botões, estado, seção, log
│   ├── seguidor_de_linha.py   PID + ultrassônico
│   └── missoes_fll.py         missões com await + anx.keep_alive() em paralelo
├── host/
│   ├── anatix_web.html        painel local: Bluetooth (Web Bluetooth) ou cabo (WebUSB)
│   ├── anatix_host.py         cliente de terminal (pybricksdev), com CSV
│   └── anatix_protocol.py     leitor do protocolo em Python
├── docs/PROTOCOLO.md          protocolo v1 + transporte Pybricks
├── tests/test_anatix.py       testes no PC com o Pybricks simulado
└── CHANGELOG.md
```

```bash
python tests/test_anatix.py
```

Os testes rodam a biblioteca no PC com um Pybricks simulado: handshake, frames e checksums, limite de frequência,
estados, seções, limite de banda, timeout, `RATE`/`STOP`, `enabled=False` e compatibilidade com o exemplo oficial
do protocolo.