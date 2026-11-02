"""Leitor do protocolo Anatix v1 (lado do computador)."""


def checksum(body: str) -> int:
    ck = 0
    for b in body.encode():
        ck ^= b
    return ck


def parse_line(line: str) -> dict:
    """Interpreta uma linha recebida do robô.

    Retorna um dict com:
      kind   "frame", "console" (saída comum do print) ou "invalid"
      type   H, V, E, S, T, L ou M        (só em frames)
      ms     tempo do robô em ms          (só em frames)
      fields campos após <ms>; em M, um único campo com o texto inteiro
    """
    line = line.rstrip("\r\n")
    i = line.find("$ANX,")
    if i < 0:
        return {"kind": "console", "text": line}
    j = line.rfind("*")
    if j < i or len(line) < j + 3:
        return {"kind": "invalid", "text": line}
    body = line[i + 1 : j]
    try:
        expected = int(line[j + 1 : j + 3], 16)
    except ValueError:
        return {"kind": "invalid", "text": line}
    if checksum(body) != expected:
        return {"kind": "invalid", "text": line}
    parts = body.split(",", 3 if body[4:5] == "M" else -1)
    if len(parts) < 3:
        return {"kind": "invalid", "text": line}
    try:
        ms = int(parts[2])
    except ValueError:
        return {"kind": "invalid", "text": line}
    return {"kind": "frame", "type": parts[1], "ms": ms, "fields": parts[3:]}
