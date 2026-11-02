# Protocolo Anatix — versão 1 (Pybricks)

As mensagens são **idênticas** às da versão Arduino: texto ASCII, uma por linha.
Um leitor feito para o Anatix do Arduino entende o Anatix do Pybricks sem mudanças;
só o **transporte** (como os bytes chegam ao computador) é diferente.

## Robô → computador

```
$ANX,<tipo>,<ms>,<campos...>*<CK>
```

- `<ms>` é o tempo do robô em milissegundos (um `StopWatch` iniciado ao importar `anatix`).
- `<CK>` é o XOR de todos os bytes entre `$` e `*` (exclusive), em hexadecimal, 2 dígitos maiúsculos.
- Linhas que não começam com `$ANX,` são saída comum do `print()` e devem ir para o console.
- Frames com checksum inválido devem ser descartados.
- O fim de linha pode chegar como `\n` ou `\r\n`; ignore o `\r`.

| Tipo | Nome | Campos após `<ms>` | Observações |
|---|---|---|---|
| `H` | hello | versão, robô, placa, período_ms | `placa` vem de `pybricks.version[0]` (`primehub`, `technichub`, `essentialhub`...) |
| `V` | valor | nome, valor | decimal com 3 casas, inteiro, `nan`, `inf` ou `-inf` |
| `E` | evento | nome, dado | dado inteiro (0 se omitido) |
| `S` | estado | máquina, estado | só quando muda; reenviado após reconectar |
| `T` | tempo | seção, execuções, média_µs, máx_µs | agregado a cada período |
| `L` | loop | loops_por_s, média_µs, máx_µs, ram_livre, descartes | `ram_livre = -1` se indisponível |
| `M` | mensagem | texto | o texto pode conter vírgulas (é o último campo) |

Métrica automática: se `anx.begin()` recebe o hub, é enviado `V` com o nome
`hub_bateria_v` (tensão da bateria em volts) a cada 1000 ms.

## Computador → robô

Escritos no **stdin** do programa do hub, uma linha cada:

| Comando | Efeito |
|---|---|
| `ANX PING` | conecta (na primeira vez) e mantém a conexão viva |
| `ANX HELLO` | pede o frame `H` novamente |
| `ANX STOP` | para de transmitir |
| `ANX RATE <ms>` | muda o período dos frames `L` e `T` (20 a 10000) |
| `ANX RESET` | zera as estatísticas agregadas |
| `ANX BW <bytes/s>` | **extensão Pybricks:** banda máxima da telemetria (200 a 100000) |

Envie `ANX PING` a cada ~500 ms. Sem PING por 2000 ms, o robô para de transmitir.
Linhas que não começam com `ANX ` vão para `anx.set_line_handler()`.

## Transporte no Pybricks

O programa do hub só usa `print`/stdout e stdin. Quem leva esses bytes é o
protocolo Pybricks, igual por Bluetooth e por USB:

| | Bluetooth (BLE) | Cabo USB |
|---|---|---|
| Hubs | todos com firmware Pybricks ≥ 3.3 | SPIKE Prime, SPIKE Essential, Robot Inventor, com firmware Pybricks que tenha USB habilitado |
| Descoberta | serviço `c5f50001-8280-46da-89f4-6d8051e4aeef` | VID `0x0694`, PID `0x0009` / `0x000D` / `0x0010`, produto termina em "Pybricks" |
| Comandos e eventos | característica `c5f50002-…` (write with response + notify) | endpoint bulk OUT / IN da interface Pybricks |
| Envelope | nenhum | OUT: `0x01` = assinar eventos (`01 01`), `0x02` = comando. IN: `0x01` = resposta (status 32 bits LE), `0x02` = evento |
| Tamanho máx. de escrita | característica `c5f50003-…`, bytes 0–1 (uint16 LE) | `packetSize` do endpoint OUT − 1 |

Dentro desse transporte:

| Mensagem | Bytes |
|---|---|
| comando parar programa | `00` |
| comando iniciar programa | `01` (ou `01 <slot>` se o hub tem slots) |
| comando escrever no stdin | `06 <bytes…>` (quebre em pedaços de tamanho máx. − 1) |
| evento status | `00 <flags uint32 LE> <programa> <slot>`; bit 6 = programa rodando |
| evento stdout | `01 <bytes…>` → junte e quebre em linhas |

Só envie `ANX PING` enquanto o bit 6 (programa rodando) estiver ligado.

## Leitura de referência (pseudocódigo)

```
para cada linha do stdout:
    i = posição de "$ANX," na linha; se não houver → console
    j = última posição de "*"
    corpo = linha[i+1 .. j-1]
    se XOR(corpo) != hex(linha[j+1 .. j+2]) → descartar
    campos = corpo separado por ","   (em M, junte tudo depois do 3º campo)
    tipo = campos[1], t = campos[2]
```

Implementações prontas: `host/anatix_protocol.py` (Python) e `parseLine()` em `host/anatix_web.html` (JavaScript).
