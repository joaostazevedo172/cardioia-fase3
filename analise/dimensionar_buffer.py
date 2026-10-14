"""
CardioIA - Fase 3 - Dimensionamento do buffer de resiliencia offline
Grupo Purkinje - FIAP 2TIAOR-2026

O enunciado pede que o grupo escolha "uma estrategia de armazenamento
limitado alinhada com o modelo de negocio do seu projeto". Este script
transforma essa escolha em numero: ele percorre o espaco de configuracoes
possiveis, aplica as restricoes de memoria do ESP32 e devolve a
configuracao adotada no firmware, junto da simulacao de uma queda de
enlace de 18 horas que demonstra por que os buffers sao separados.

Rodar:  python dimensionar_buffer.py
Saida:  tabela no terminal + analise/dimensionamento.csv
"""

import csv
import os
import random

# ---------------------------------------------------------------------
# Restricoes de hardware e do modelo de negocio
# ---------------------------------------------------------------------
SRAM_TOTAL_KB = 520        # ESP32-WROOM-32: SRAM interna
SRAM_RESERVADA_KB = 160    # pilha Wi-Fi + TLS + heap do PubSubClient
ORCAMENTO_KB = 48          # teto que nos impusemos para o buffer
BYTES_POR_AMOSTRA = 12     # struct Amostra: 4+2+2+2+1+1

CADENCIA_OFFLINE_S = 15    # amostragem degradada quando sem enlace
CADENCIA_ONLINE_S = 5

# Janela de indisponibilidade que o produto precisa cobrir. Monitoramento
# domiciliar: a falha tipica e queda de energia ou de link residencial,
# resolvida dentro de um turno de trabalho.
AUTONOMIA_ALVO_H = 12

# Fracao do buffer dedicada a eventos clinicos. Um episodio arritmico
# sustentado raramente passa de duas horas sem intervencao; alem disso,
# o paciente ja estaria sob cuidado presencial.
FRACAO_CRITICA = 1 / 6


def avaliar(n_amostras: int) -> dict:
    """Metricas de uma configuracao de buffer de n_amostras registros."""
    kb = n_amostras * BYTES_POR_AMOSTRA / 1024
    horas_offline = n_amostras * CADENCIA_OFFLINE_S / 3600
    horas_online = n_amostras * CADENCIA_ONLINE_S / 3600
    return {
        "amostras": n_amostras,
        "kb": round(kb, 1),
        "pct_sram": round(100 * kb / SRAM_TOTAL_KB, 2),
        "autonomia_offline_h": round(horas_offline, 1),
        "autonomia_cadencia_online_h": round(horas_online, 1),
        "cabe_no_orcamento": kb <= ORCAMENTO_KB,
        "atinge_alvo": horas_offline >= AUTONOMIA_ALVO_H,
    }


def simular_queda(duracao_h: float, prob_alerta: float, semente: int = 20260806):
    """
    Simula uma queda de enlace mais longa que a autonomia projetada e
    compara duas estrategias de buffer com a MESMA memoria total.

      A) buffer unico circular FIFO
      B) dois buffers separados por prioridade clinica (o adotado)

    O que interessa nao e quantas amostras sobrevivem - e quantas
    amostras EM ALERTA sobrevivem, porque sao elas que sustentam o
    diagnostico posterior.
    """
    rng = random.Random(semente)
    total = int(duracao_h * 3600 / CADENCIA_OFFLINE_S)

    cap_total = CAP_ROTINA + CAP_CRITICO
    unico, rotina, critico = [], [], []

    for i in range(total):
        alerta = rng.random() < prob_alerta

        # A) FIFO unico: o mais antigo sai, seja ele qual for
        unico.append(alerta)
        if len(unico) > cap_total:
            unico.pop(0)

        # B) prioridade clinica: filas independentes
        if alerta:
            critico.append(True)
            if len(critico) > CAP_CRITICO:
                critico.pop(0)
        else:
            rotina.append(False)
            if len(rotina) > CAP_ROTINA:
                rotina.pop(0)

    alertas_gerados = int(round(total * prob_alerta))

    return {
        "duracao_h": duracao_h,
        "amostras_geradas": total,
        "alertas_gerados_aprox": alertas_gerados,
        "alertas_salvos_fifo_unico": sum(unico),
        "alertas_salvos_prioridade": len(critico),
        "rotina_salva_prioridade": len(rotina),
    }


# ---------------------------------------------------------------------
# 1. Varredura de configuracoes
# ---------------------------------------------------------------------
CANDIDATOS = [720, 1440, 2160, 2880, 3600, 4320, 5760]

print("=" * 78)
print(" CardioIA Fase 3 - dimensionamento do buffer de resiliencia")
print("=" * 78)
print(f" Orcamento de memoria ....... {ORCAMENTO_KB} KB "
      f"(SRAM livre estimada: {SRAM_TOTAL_KB - SRAM_RESERVADA_KB} KB)")
print(f" Tamanho da amostra ......... {BYTES_POR_AMOSTRA} bytes")
print(f" Cadencia offline ........... {CADENCIA_OFFLINE_S} s")
print(f" Autonomia alvo ............. {AUTONOMIA_ALVO_H} h")
print()
print(f"{'amostras':>9} {'KB':>7} {'% SRAM':>8} {'autonomia':>11} "
      f"{'cabe':>6} {'alvo':>6}")
print("-" * 78)

escolhida = None
for n in CANDIDATOS:
    m = avaliar(n)
    marca = ""
    if m["cabe_no_orcamento"] and m["atinge_alvo"] and escolhida is None:
        escolhida = m
        marca = "  <== adotada (menor que satisfaz as duas restricoes)"
    print(f"{m['amostras']:>9} {m['kb']:>7} {m['pct_sram']:>7}% "
          f"{m['autonomia_offline_h']:>9} h "
          f"{'sim' if m['cabe_no_orcamento'] else 'NAO':>6} "
          f"{'sim' if m['atinge_alvo'] else 'NAO':>6}{marca}")

CAP_TOTAL = escolhida["amostras"]
CAP_CRITICO = int(CAP_TOTAL * FRACAO_CRITICA)
CAP_ROTINA = CAP_TOTAL - CAP_CRITICO

print("-" * 78)
print(f" Configuracao adotada no firmware (config.h):")
print(f"   CAPACIDADE_ROTINA  = {CAP_ROTINA}")
print(f"   CAPACIDADE_CRITICO = {CAP_CRITICO}")
print(f"   total = {CAP_TOTAL} amostras = {escolhida['kb']} KB = "
      f"{escolhida['pct_sram']}% da SRAM")
print(f"   autonomia offline = {escolhida['autonomia_offline_h']} h a "
      f"{CADENCIA_OFFLINE_S} s/amostra")
print(f"   o buffer critico sozinho cobre "
      f"{round(CAP_CRITICO * CADENCIA_OFFLINE_S / 3600, 1)} h de evento continuo")
print()

# ---------------------------------------------------------------------
# 2. Por que separar os buffers
# ---------------------------------------------------------------------
print("=" * 78)
print(" Queda de enlace de 18 h (50% alem da autonomia projetada)")
print(" Mesma memoria total nas duas estrategias.")
print("=" * 78)
print(f"{'prob. alerta':>13} {'amostras':>10} {'alertas':>9} "
      f"{'salvos FIFO':>13} {'salvos prior.':>14}")
print("-" * 78)

for p in (0.02, 0.05, 0.10):
    r = simular_queda(18, p)
    print(f"{p:>12.0%} {r['amostras_geradas']:>10} "
          f"{r['alertas_gerados_aprox']:>9} "
          f"{r['alertas_salvos_fifo_unico']:>13} "
          f"{r['alertas_salvos_prioridade']:>14}")

print("-" * 78)
print(" Leitura: com um unico buffer FIFO, uma queda longa descarta os")
print(" alertas mais antigos junto com a rotina - justamente o inicio do")
print(" episodio, que e a parte diagnostica mais valiosa. Separando as")
print(" filas, a rotina absorve a perda e o historico clinico sobrevive.")
print()

# ---------------------------------------------------------------------
# 3. CSV para o relatorio
# ---------------------------------------------------------------------
destino = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "dimensionamento.csv")
with open(destino, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(avaliar(CANDIDATOS[0]).keys()))
    w.writeheader()
    for n in CANDIDATOS:
        w.writerow(avaliar(n))

print(f"[ok] tabela salva em {destino}")
