# Changelog

## 0.1.0

Primeira versão para Pybricks, a partir do Anatix para Arduino 0.1.0.

- Biblioteca `anatix.py` para o hub com a mesma API (métricas, `every=`, eventos, estados, seções, logs).
- `with anx.scope(...)`, `anx.keep_alive()` para multitarefa e `enabled=False` para a competição.
- Métrica automática `hub_bateria_v` e relatórios de loop, RAM livre e descartes.
- Limite de banda com descarte (não trava o loop) e comando de extensão `ANX BW`.
- Painel web com Bluetooth (Web Bluetooth) e cabo USB (WebUSB), gráfico, tempos, estados, eventos, console e CSV.
- Cliente de terminal em Python (pybricksdev), por BLE ou USB, com gravação em CSV.
- Protocolo v1 compatível com a versão Arduino ([docs/PROTOCOLO.md](docs/PROTOCOLO.md)).
