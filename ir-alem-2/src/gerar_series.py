"""
CardioIA - Fase 3 - Ir Alem 2
Geracao das series temporais de frequencia cardiaca.

CONTINUIDADE COM O RESTO DO PROJETO

As series saem do mesmo modelo do wearable da Fase 3, para o mesmo paciente
CARD-0056, com a mesma cadencia de 5 s e os mesmos limiares clinicos. Nao
importamos uma base externa de ECG de proposito: a pergunta deste Ir Alem e
se um classificador consegue reconhecer, na serie que o nosso dispositivo
produz, os mesmos episodios que o firmware detecta por regra. Trocar os dados
por uma base publica responderia outra pergunta.

O QUE E UMA AMOSTRA

Cada exemplo e uma janela de 36 leituras consecutivas de frequencia cardiaca
(3 minutos a 5 s por leitura). O rotulo e 1 quando a janela contem um episodio
arritmico sustentado - taquicardia ou bradicardia mantida por pelo menos
AMOSTRAS_HISTERESE leituras - e 0 caso contrario.

O DESAFIO FOI DEIXADO DIFICIL DE PROPOSITO

Um gerador ingenuo produziria janelas normais em torno de 74 bpm e janelas
anomalas em torno de 140 bpm, e qualquer classificador acertaria 100%. Isso
nao ensina nada e esconde a diferenca entre os metodos. Entao:

  - a frequencia basal varia de paciente para paciente (58 a 92 bpm), de modo
    que o valor absoluto sozinho nao separa as classes;
  - metade das janelas normais contem picos transitorios que cruzam o limiar
    por uma ou duas leituras, sem configurar episodio - sao exatamente os
    falsos positivos que a histerese do firmware evita;
  - os episodios anomalos comecam em posicoes aleatorias da janela e duram
    de 4 a 20 leituras, as vezes truncados pela borda;
  - ha ruido de medicao e artefatos de movimento.

Rodar:  python src/gerar_series.py
Saida:  dados/series_card0056.npz
"""

import os
import sys

import numpy as np

SEMENTE = 20260806
CADENCIA_S = 5
JANELA = 36                  # 36 x 5 s = 3 minutos
N_JANELAS = 1200
PROP_ANOMALA = 0.40

# Limiares clinicos: os mesmos do firmware (src/config.h da Fase 3)
FC_TAQUICARDIA = 120
FC_BRADICARDIA = 50
AMOSTRAS_HISTERESE = 3


def tem_episodio(serie):
    """
    Rotulo de referencia: aplica exatamente a regra do firmware a janela.
    Devolve True se houver AMOSTRAS_HISTERESE leituras CONSECUTIVAS fora da
    faixa. E a mesma logica de histerese do dispositivo, usada aqui como
    verdade de referencia para treinar e avaliar os modelos.
    """
    taq = bra = 0
    for v in serie:
        taq = taq + 1 if v > FC_TAQUICARDIA else 0
        bra = bra + 1 if v < FC_BRADICARDIA else 0
        if taq >= AMOSTRAS_HISTERESE or bra >= AMOSTRAS_HISTERESE:
            return True
    return False


def gerar(n_janelas=N_JANELAS, semente=SEMENTE):
    rng = np.random.default_rng(semente)
    X, y, meta = [], [], []

    while len(X) < n_janelas:
        # frequencia basal do paciente naquele periodo do dia
        basal = rng.uniform(58, 92)
        serie = basal + rng.normal(0, 3.2, JANELA)

        # artefatos de movimento: picos isolados em ate 3 posicoes
        for _ in range(rng.integers(0, 4)):
            i = rng.integers(0, JANELA)
            serie[i] += rng.normal(0, 14)

        anomala = rng.random() < PROP_ANOMALA

        if anomala:
            # episodio sustentado, posicao e duracao variaveis
            dur = int(rng.integers(4, 21))
            ini = int(rng.integers(0, JANELA - 3))
            fim = min(JANELA, ini + dur)
            if rng.random() < 0.72:
                alvo = rng.uniform(126, 160)       # taquicardia
            else:
                alvo = rng.uniform(32, 46)         # bradicardia
            rampa = np.linspace(serie[ini], alvo, max(2, (fim - ini) // 3))
            serie[ini:ini + len(rampa)] = rampa
            serie[ini + len(rampa):fim] = alvo + rng.normal(0, 3.0,
                                                            max(0, fim - ini - len(rampa)))
        else:
            # metade das normais recebe pico transitorio que cruza o limiar
            # por 1 ou 2 leituras, sem configurar episodio
            if rng.random() < 0.5:
                i = int(rng.integers(0, JANELA - 2))
                largura = int(rng.integers(1, 3))
                direcao = 1 if rng.random() < 0.72 else -1
                pico = (FC_TAQUICARDIA + rng.uniform(2, 18)) if direcao > 0 \
                    else (FC_BRADICARDIA - rng.uniform(2, 12))
                serie[i:i + largura] = pico + rng.normal(0, 2.0, largura)

        serie = np.clip(np.round(serie), 0, 300)

        # O rotulo e sempre apurado pela regra, nunca pela intencao do
        # gerador. Se um "pico transitorio" acabou durando tres leituras,
        # ele E um episodio, e o rotulo acompanha. Rotular pela intencao
        # criaria ruido de rotulo e puniria o modelo por acertar.
        rotulo = int(tem_episodio(serie))

        X.append(serie)
        y.append(rotulo)
        meta.append({"basal": round(basal, 1), "pretendida": int(anomala)})

    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.int8)
    return X, y, meta


if __name__ == "__main__":
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    destino = os.path.join(raiz, "dados", "series_card0056.npz")
    os.makedirs(os.path.dirname(destino), exist_ok=True)

    X, y, meta = gerar()
    np.savez_compressed(destino, X=X, y=y,
                        basal=np.array([m["basal"] for m in meta], dtype=np.float32),
                        pretendida=np.array([m["pretendida"] for m in meta], dtype=np.int8))

    pret = np.array([m["pretendida"] for m in meta])
    divergencia = int((pret != y).sum())

    print(f"[ok] {len(X)} janelas de {JANELA} leituras ({JANELA * CADENCIA_S // 60} min cada)")
    print(f"     gravadas em dados/series_card0056.npz")
    print(f"     semente {SEMENTE}")
    print()
    print(f"     classe 0 (sem episodio) ... {int((y == 0).sum()):>4}  ({(y == 0).mean():.1%})")
    print(f"     classe 1 (com episodio) ... {int((y == 1).sum()):>4}  ({(y == 1).mean():.1%})")
    print()
    print(f"     faixa de FC basal ......... {min(m['basal'] for m in meta):.0f} a "
          f"{max(m['basal'] for m in meta):.0f} bpm")
    print(f"     janelas em que a regra discordou da intencao do gerador: {divergencia}")
    print(f"     (picos transitorios que acabaram durando 3 leituras viraram episodio,")
    print(f"      e o rotulo acompanhou a regra - nunca a intencao)")
