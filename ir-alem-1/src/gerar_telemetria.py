"""
CardioIA - Fase 3 - Ir Alem 1
Gera a serie de telemetria que a API REST serve.

As amostras tem exatamente o mesmo formato do payload que o ESP32 publica
via MQTT na Fase 3, campo por campo. Assim o cliente REST deste Ir Alem
consome a mesma estrutura que o Node-RED consome, e trocar a fonte de dados
(broker MQTT ou API REST) nao exige mudar a logica de risco.

A serie e sintetica e reproduzivel: a semente e a mesma usada desde a Fase 1.
Nao ha aleatoriedade sem semente em nenhum ponto do projeto - e o que permite
que qualquer pessoa reproduza os mesmos alertas, nos mesmos instantes.

Rodar:  python src/gerar_telemetria.py
Saida:  dados/telemetria_card0056.json
"""

import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg

SEMENTE = 20260806
CADENCIA_S = 5          # mesma cadencia do firmware quando ha enlace
TOTAL_AMOSTRAS = 540    # 45 minutos de monitoramento

# Episodios inseridos de proposito, por indice de amostra. O roteiro foi
# desenhado para exercitar TODAS as regras de decisao, inclusive as que so
# aparecem em combinacao:
#
#   taquicardia A e B  dois episodios separados por uma queda breve do ritmo.
#                      Como ocorrem dentro da mesma janela de supressao, o
#                      segundo e detectado mas NAO gera novo e-mail - e assim
#                      que a regra anti-repeticao fica visivel no relatorio.
#   febre              temperatura sustentada acima de 38 C.
#   queda              impacto isolado, que dispara sem histerese.
#   imobilidade        paciente parado por mais de dez minutos apos a queda.
#   sincope            o ritmo cai abaixo de 50 bpm com o paciente ja imovel.
#                      A imobilidade dispara primeiro, porque a bradicardia
#                      ainda esta cumprindo as tres confirmacoes; dois ciclos
#                      depois a bradicardia confirma. Essa ordem e proposital:
#                      suspeita de sincope nao deve esperar histerese.
EPISODIOS = [
    # (inicio, fim, tipo)
    (96, 120, "taquicardia"),    # primeiro episodio
    (126, 160, "taquicardia"),   # recidiva dentro da janela de supressao
    (210, 246, "febre"),
    (300, 303, "queda"),
    (303, 540, "imobilidade"),
    (460, 540, "sincope"),       # sobrepoe a imobilidade
]


def faixas(i):
    """Devolve o conjunto de episodios ativos na amostra i (podem se sobrepor)."""
    return {tipo for ini, fim, tipo in EPISODIOS if ini <= i < fim}


def gerar():
    rng = random.Random(SEMENTE)
    amostras = []

    for i in range(TOTAL_AMOSTRAS):
        ativos = faixas(i)

        # --- frequencia cardiaca ---
        if "sincope" in ativos:
            bpm = int(rng.gauss(45, 2))             # abaixo do limiar de bradicardia
        elif "taquicardia" in ativos:
            # sobe acima de 120 e oscila, com variabilidade fisiologica
            bpm = int(rng.gauss(134, 7))
        elif ativos & {"queda", "imobilidade"}:
            bpm = int(rng.gauss(58, 3))             # baixo, mas ainda normal
        else:
            bpm = int(rng.gauss(74, 5))
        bpm = max(0, min(300, bpm))

        # --- temperatura ---
        if "febre" in ativos:
            prog = (i - 210) / 36
            temp = 37.2 + 1.4 * (1 - abs(2 * prog - 1)) + rng.gauss(0, 0.08)
        else:
            temp = rng.gauss(36.6, 0.12)
        temp = round(temp, 1)

        # --- movimento ---
        if "queda" in ativos:
            mov = int(rng.uniform(2600, 3400))      # impacto
        elif "imobilidade" in ativos:
            mov = int(abs(rng.gauss(18, 10)))       # praticamente parado
        else:
            mov = int(abs(rng.gauss(180, 90)))      # atividade normal

        amostras.append({
            "disp": cfg.ID_DISPOSITIVO,
            "pac": cfg.ID_PACIENTE,
            "t": i * CADENCIA_S,
            "bpm": bpm,
            "temp": temp,
            "umid": int(rng.gauss(55, 3)),
            "mov": mov,
            "origem": "live",
        })

    return amostras


if __name__ == "__main__":
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    destino = os.path.join(raiz, "dados", "telemetria_card0056.json")
    os.makedirs(os.path.dirname(destino), exist_ok=True)

    amostras = gerar()
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(amostras, f, ensure_ascii=False, indent=1)

    print(f"[ok] {len(amostras)} amostras gravadas em dados/telemetria_card0056.json")
    print(f"     cadencia de {CADENCIA_S} s, total de "
          f"{len(amostras) * CADENCIA_S / 60:.0f} minutos")
    print(f"     semente {SEMENTE} (a mesma desde a Fase 1)")
    print()
    print("     episodios inseridos:")
    for ini, fim, tipo in EPISODIOS:
        print(f"       {tipo:<13} amostras {ini:>3} a {fim:>3}  "
              f"({ini * CADENCIA_S // 60:>2}:{ini * CADENCIA_S % 60:02d} "
              f"a {fim * CADENCIA_S // 60:>2}:{fim * CADENCIA_S % 60:02d})")
