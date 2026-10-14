"""
CardioIA - Fase 3 - Ir Alem 2
Os dois modelos comparados: regressao logistica e neuronio LIF.

A INTUICAO CENTRAL DESTE TRABALHO

O que separa um episodio arritmico de um artefato de movimento nao e o valor
da frequencia, e a PERSISTENCIA do desvio. Um pico isolado de 130 bpm e ruido;
130 bpm por quinze leituras seguidas e um evento clinico. O firmware da Fase 3
resolve isso com um contador de histerese explicito, em software.

Um neuronio integra-e-dispara com vazamento resolve o mesmo problema sem
contador nenhum, pela propria dinamica da membrana: a corrente de entrada
carrega o potencial, o vazamento o descarrega continuamente. Um pico isolado
carrega pouco e vaza antes de atingir o limiar; um desvio sustentado vence o
vazamento e dispara. A constante de tempo tau E a histerese, expressa em
tempo continuo em vez de contagem discreta.

E por isso que a comparacao vale a pena: nao e "um modelo acerta mais".
Sao duas formas diferentes de representar a mesma nocao de persistencia, com
consequencias praticas distintas de latencia e custo computacional.
"""

import numpy as np

# Limiares clinicos - os mesmos do firmware
FC_TAQUICARDIA = 120
FC_BRADICARDIA = 50


# =====================================================================
#  MODELO TRADICIONAL: atributos para a regressao logistica
# =====================================================================

def extrair_atributos(X, com_contagem=True):
    """
    Monta a matriz de atributos da regressao logistica.

    Sempre entrega as 36 leituras brutas mais quatro estatisticas de posicao e
    dispersao. O parametro `com_contagem` acrescenta quantas leituras caem
    fora da faixa clinica, e existe para uma comparacao deliberada.

    POR QUE DUAS VARIANTES

    A contagem de leituras fora da faixa nao e o rotulo - o rotulo exige
    CONSECUTIVIDADE, e contagem nao guarda ordem. Mas e um substituto muito
    bom: uma janela com quinze leituras altas quase certamente as tem em
    sequencia, e uma com duas quase certamente nao. A zona ambigua e estreita.

    Avaliar as duas variantes separa dois efeitos que de outro modo ficariam
    misturados: o que o modelo linear consegue extrair da serie crua, e o
    quanto uma unica estatistica bem escolhida pelo projetista resolve o
    problema. Sem essa separacao, "a regressao venceu" nao diria se o merito
    foi do modelo ou da engenharia de atributos.

    NAO entregamos o comprimento da maior sequencia consecutiva: esse
    atributo E a propria regra de rotulagem, e usa-lo seria vazamento.
    """
    base = [
        X,                                    # 36 leituras na ordem original
        X.mean(axis=1, keepdims=True),
        X.std(axis=1, keepdims=True),
        X.min(axis=1, keepdims=True),
        X.max(axis=1, keepdims=True),
    ]
    if com_contagem:
        base.append((X > FC_TAQUICARDIA).sum(axis=1, keepdims=True).astype(np.float32))
        base.append((X < FC_BRADICARDIA).sum(axis=1, keepdims=True).astype(np.float32))
    return np.hstack(base).astype(np.float32)


NOMES_ATRIBUTOS = ([f"t{i:02d}" for i in range(36)] +
                   ["media", "desvio", "minimo", "maximo", "n_acima", "n_abaixo"])


# =====================================================================
#  MODELO NEUROMORFICO: neuronio integra-e-dispara com vazamento (LIF)
# =====================================================================

def corrente_de_entrada(serie, ganho=1.0):
    """
    Converte frequencia cardiaca em corrente sinaptica.

    A corrente e proporcional ao quanto a leitura esta FORA da faixa clinica,
    e vale zero dentro dela. Nao ha treinamento aqui: a codificacao vem do
    conhecimento clinico, exatamente como os limiares do firmware. O neuronio
    nao precisa aprender o que e taquicardia; precisa aprender quanta
    persistencia justifica um disparo.
    """
    acima = np.maximum(0.0, serie - FC_TAQUICARDIA)
    abaixo = np.maximum(0.0, FC_BRADICARDIA - serie)
    return ganho * (acima + abaixo) / 10.0


class NeuronioLIF:
    """
    Integra-e-dispara com vazamento, em tempo discreto.

        V[t+1] = V[t] * (1 - dt/tau) + I[t] * dt
        se V > limiar:  dispara, V volta a 0

    Quatro parametros, todos com significado fisico direto:

      tau      constante de vazamento. Alta = memoria longa = mais tolerante
               a interrupcoes no episodio. Baixa = esquece rapido.
      limiar   quanto potencial acumulado justifica um disparo.
      ganho    sensibilidade da codificacao de entrada.
      minimo   quantos disparos na janela caracterizam episodio.
    """

    def __init__(self, tau=4.0, limiar=1.2, ganho=1.0, minimo_disparos=1, dt=1.0):
        self.tau = tau
        self.limiar = limiar
        self.ganho = ganho
        self.minimo_disparos = minimo_disparos
        self.dt = dt

    def simular(self, serie):
        """
        Roda a dinamica sobre uma janela.
        Devolve (potenciais, instantes_de_disparo).
        """
        corrente = corrente_de_entrada(serie, self.ganho)
        v = 0.0
        potenciais = np.empty(len(serie), dtype=np.float32)
        disparos = []
        vazamento = 1.0 - self.dt / self.tau

        for i, inj in enumerate(corrente):
            v = v * vazamento + inj * self.dt
            if v > self.limiar:
                disparos.append(i)
                v = 0.0
            potenciais[i] = v

        return potenciais, disparos

    def prever_um(self, serie):
        """Devolve (rotulo, instante_do_primeiro_disparo_ou_None)."""
        _, disparos = self.simular(serie)
        if len(disparos) >= self.minimo_disparos:
            return 1, disparos[self.minimo_disparos - 1]
        return 0, None

    def prever(self, X):
        return np.array([self.prever_um(s)[0] for s in X], dtype=np.int8)

    def latencias(self, X, y):
        """Em quantas leituras o neuronio reconhece cada episodio verdadeiro."""
        out = []
        for serie, rotulo in zip(X, y):
            if rotulo != 1:
                continue
            pred, quando = self.prever_um(serie)
            if pred == 1:
                out.append(quando + 1)       # +1: leituras consumidas
        return np.array(out)

    def contagem_disparos(self, X):
        return np.array([len(self.simular(s)[1]) for s in X])

    def __repr__(self):
        return (f"NeuronioLIF(tau={self.tau:.1f}, limiar={self.limiar:.2f}, "
                f"ganho={self.ganho:.1f}, minimo_disparos={self.minimo_disparos})")


def ajustar_lif(X, y, grade=None, metrica="f1"):
    """
    Busca em grade sobre os quatro parametros.

    Nao ha gradiente aqui: o disparo e uma descontinuidade, e a rede tem
    quatro parametros. Treinar por retropropagacao exigiria substitutos
    derivaveis (surrogate gradients), maquinaria desproporcional para o
    tamanho do problema. A busca exaustiva cobre o espaco inteiro em segundos
    e deixa explicito o que foi explorado - o que para um trabalho academico
    vale mais que um otimizador opaco.
    """
    from sklearn.metrics import f1_score, recall_score, accuracy_score

    pontuar = {"f1": f1_score, "recall": recall_score,
               "acuracia": accuracy_score}[metrica]

    if grade is None:
        grade = {
            "tau": [2.0, 3.0, 4.0, 6.0, 9.0],
            "limiar": [0.4, 0.8, 1.2, 1.8, 2.6, 3.6],
            "ganho": [0.6, 1.0, 1.6],
            "minimo_disparos": [1, 2],
        }

    melhor, melhor_nota, historico = None, -1.0, []
    for tau in grade["tau"]:
        for limiar in grade["limiar"]:
            for ganho in grade["ganho"]:
                for minimo in grade["minimo_disparos"]:
                    n = NeuronioLIF(tau, limiar, ganho, minimo)
                    nota = pontuar(y, n.prever(X))
                    historico.append({"tau": tau, "limiar": limiar, "ganho": ganho,
                                      "minimo_disparos": minimo, metrica: round(float(nota), 4)})
                    if nota > melhor_nota:
                        melhor_nota, melhor = nota, n

    return melhor, float(melhor_nota), historico
