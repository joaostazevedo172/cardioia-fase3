"""
CardioIA - Fase 3 - Ir Alem 1
Testes: coerencia com o firmware e comportamento das regras de risco.

O teste mais importante deste arquivo e o primeiro. Ele le o `config.h` do
firmware do ESP32 e compara, valor a valor, com o `config.py` deste servico.
Se alguem alterar o limiar de taquicardia no dispositivo e esquecer de
alterar aqui, a suite quebra.

Sem esse teste, a divergencia seria silenciosa e perversa: o paciente veria
o LED vermelho aceso no peito enquanto a central nao receberia e-mail nenhum,
ou o contrario. Um sistema de monitoramento que discorda de si mesmo e pior
que um sistema que nao monitora, porque produz confianca injustificada.

Rodar:  python testes/test_coerencia_firmware.py
"""

import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, os.path.join(RAIZ, "src"))

import config as cfg          # noqa: E402
import regras_risco as rr     # noqa: E402

FIRMWARE = os.path.join(os.path.dirname(RAIZ), "src", "config.h")

falhas = []


def checar(condicao, descricao):
    print(f"  [{'ok' if condicao else 'FALHA'}] {descricao}")
    if not condicao:
        falhas.append(descricao)


def ler_macro(texto, nome):
    m = re.search(rf"#define\s+{nome}\s+([\d.]+)", texto)
    return float(m.group(1)) if m else None


# ---------------------------------------------------------------------
print("\n1. COERENCIA COM O FIRMWARE (src/config.h)")

if not os.path.exists(FIRMWARE):
    checar(False, f"config.h do firmware encontrado em {FIRMWARE}")
else:
    fw = open(FIRMWARE, encoding="utf-8").read()
    pares = [
        ("FC_TAQUICARDIA", cfg.FC_TAQUICARDIA),
        ("FC_BRADICARDIA", cfg.FC_BRADICARDIA),
        ("TEMP_FEBRE", cfg.TEMP_FEBRE),
        ("TEMP_HIPOTERMIA", cfg.TEMP_HIPOTERMIA),
        ("MOV_IMPACTO_MG", cfg.MOV_IMPACTO_MG),
        ("MOV_REPOUSO_MG", cfg.MOV_REPOUSO_MG),
        ("AMOSTRAS_HISTERESE", cfg.AMOSTRAS_HISTERESE),
    ]
    for nome, valor_py in pares:
        valor_c = ler_macro(fw, nome)
        checar(valor_c is not None and float(valor_c) == float(valor_py),
               f"{nome}: firmware={valor_c} servico={valor_py}")

    # O identificador do paciente tambem precisa bater
    m = re.search(r'#define\s+ID_PACIENTE\s+"([^"]+)"', fw)
    checar(m is not None and m.group(1) == cfg.ID_PACIENTE,
           f"ID_PACIENTE: firmware={m.group(1) if m else None} servico={cfg.ID_PACIENTE}")

# ---------------------------------------------------------------------
print("\n2. HISTERESE")

a = rr.AvaliadorDeRisco()
seq = [a.avaliar({"bpm": 130, "temp": 36.6, "mov": 100})[0] for _ in range(5)]
checar(seq[:2] == [rr.NORMAL, rr.NORMAL], f"nao dispara antes da 3a amostra: {seq[:2]}")
checar(seq[2] == rr.TAQUICARDIA, f"dispara exatamente na 3a amostra: {seq[2]}")

a = rr.AvaliadorDeRisco()
alt = [a.avaliar({"bpm": 130 if i % 2 == 0 else 80, "temp": 36.6, "mov": 100})[0]
       for i in range(12)]
checar(rr.TAQUICARDIA not in alt, f"leituras alternadas nunca acumulam: {set(alt)}")

# ---------------------------------------------------------------------
print("\n3. IMPACTO SEM HISTERESE")

a = rr.AvaliadorDeRisco()
m, _ = a.avaliar({"bpm": 75, "temp": 36.6, "mov": cfg.MOV_IMPACTO_MG + 100})
checar(m == rr.QUEDA, f"queda dispara na primeira amostra: {m}")

# ---------------------------------------------------------------------
print("\n4. FALHA DE SENSOR NAO E EVENTO CLINICO")

a = rr.AvaliadorDeRisco()
sem = [a.avaliar({"bpm": 0, "temp": 36.6, "mov": 100})[0] for _ in range(6)]
checar(set(sem) == {rr.SINAL_AUSENTE}, f"pulso ausente -> SINAL_AUSENTE: {set(sem)}")
checar(rr.BRADICARDIA not in sem, "eletrodo solto nao vira bradicardia")
checar(not rr.e_alerta_clinico(rr.SINAL_AUSENTE),
       "SINAL_AUSENTE classificado como falha tecnica, nao clinica")

# ---------------------------------------------------------------------
print("\n5. IMOBILIDADE SO COM RITMO ALTERADO")

a = rr.AvaliadorDeRisco()
dormindo = [a.avaliar({"bpm": 72, "temp": 36.6, "mov": 10})[0]
            for _ in range(cfg.IMOBILIDADE_AMOSTRAS + 20)]
checar(rr.IMOBILIDADE not in dormindo,
       "paciente parado com ritmo normal nao gera alerta (esta dormindo)")

a = rr.AvaliadorDeRisco()
for _ in range(cfg.IMOBILIDADE_AMOSTRAS + 5):
    a.avaliar({"bpm": 72, "temp": 36.6, "mov": 10})
m, _ = a.avaliar({"bpm": 45, "temp": 36.6, "mov": 10})
checar(m == rr.IMOBILIDADE,
       f"parado + ritmo alterado -> IMOBILIDADE antes da bradicardia confirmar: {m}")

# ---------------------------------------------------------------------
print("\n6. SUPRESSAO DE REPETICAO NA NOTIFICACAO")

from notificador_email import Notificador      # noqa: E402

n = Notificador()
evento = {"t": 100, "motivo": rr.TAQUICARDIA, "clinico": True,
          "gravidade": 4, "detalhe": "teste", "mensagem": "",
          "amostra": {"bpm": 130, "temp": 36.6, "umid": 50, "mov": 100}}
ok1, _ = n.deve_notificar(evento)
checar(ok1, "primeiro evento do tipo passa")
n._ultimo_envio[rr.TAQUICARDIA] = 100
ok2, razao = n.deve_notificar({**evento, "t": 200})
checar(not ok2, f"repeticao dentro da janela e suprimida ({razao[:40]}...)")
ok3, _ = n.deve_notificar({**evento, "t": 100 + cfg.SUPRESSAO_SEGUNDOS + 1})
checar(ok3, "passada a janela, volta a notificar")

tecnico = {**evento, "motivo": rr.SINAL_AUSENTE, "clinico": False}
ok4, razao = n.deve_notificar(tecnico)
checar(not ok4, f"falha tecnica nao gera e-mail ({razao})")

# ---------------------------------------------------------------------
print("\n" + "=" * 62)
print(f"RESULTADO: {len(falhas)} falha(s)")
print("=" * 62)
sys.exit(1 if falhas else 0)
