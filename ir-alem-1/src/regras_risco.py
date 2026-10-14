"""
CardioIA - Fase 3 - Ir Alem 1
Logica de verificacao de risco sobre a serie de sinais vitais.

Esta e a mesma maquina de decisao do firmware, reescrita em Python e operando
sobre a serie que chega pela API REST. Tres propriedades foram preservadas
deliberadamente, porque sao o que separa um detector util de um gerador de
alarmes falsos:

1. HISTERESE. Taquicardia, bradicardia, febre e hipotermia exigem tres
   amostras consecutivas na condicao. O contador zera assim que a condicao
   deixa de valer, de modo que leituras alternadas nunca acumulam ate o
   limiar.

2. IMPACTO SEM HISTERESE. Uma queda e um evento unico e nao se repete na
   amostra seguinte; esperar confirmacao perderia justamente o evento.

3. FALHA DE SENSOR NAO E EVENTO CLINICO. Frequencia zero significa eletrodo
   solto, e e reportada como SINAL_AUSENTE - nunca como bradicardia.

A quarta regra, ausencia de movimento, e a que o enunciado deste Ir Alem pede
explicitamente. Ela so vira alerta quando acompanhada de ritmo alterado:
paciente parado com ritmo normal esta dormindo, nao desmaiado.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg

NORMAL = "NORMAL"
TAQUICARDIA = "TAQUICARDIA"
BRADICARDIA = "BRADICARDIA"
FEBRE = "FEBRE"
HIPOTERMIA = "HIPOTERMIA"
QUEDA = "QUEDA"
IMOBILIDADE = "IMOBILIDADE"
SINAL_AUSENTE = "SINAL_AUSENTE"

CLINICOS = {TAQUICARDIA, BRADICARDIA, FEBRE, HIPOTERMIA, QUEDA, IMOBILIDADE}

# Gravidade usada para ordenar o que vai para o e-mail quando ha mais de um
# alerta no mesmo lote. Nao altera a deteccao, so a prioridade de notificacao.
GRAVIDADE = {
    QUEDA: 5, TAQUICARDIA: 4, BRADICARDIA: 4,
    IMOBILIDADE: 3, HIPOTERMIA: 2, FEBRE: 2,
    SINAL_AUSENTE: 1, NORMAL: 0,
}

MENSAGEM = {
    TAQUICARDIA: "Frequencia cardiaca sustentada acima do limiar de taquicardia.",
    BRADICARDIA: "Frequencia cardiaca sustentada abaixo do limiar de bradicardia.",
    FEBRE: "Temperatura corporal sustentada acima de 38,0 C.",
    HIPOTERMIA: "Temperatura corporal sustentada abaixo de 35,0 C.",
    QUEDA: "Impacto compativel com queda detectado pelo acelerometro.",
    IMOBILIDADE: "Ausencia prolongada de movimento com ritmo cardiaco alterado.",
    SINAL_AUSENTE: "Sem leitura de pulso: provavel eletrodo solto (falha tecnica).",
}


def e_alerta_clinico(motivo):
    """Alerta clinico exige acao. Falha de sensor e registrada, nao alarmada."""
    return motivo in CLINICOS


class AvaliadorDeRisco:
    """Percorre a serie mantendo os contadores de histerese entre amostras."""

    def __init__(self):
        self.zerar()

    def zerar(self):
        self.cnt_taqui = 0
        self.cnt_bradi = 0
        self.cnt_febre = 0
        self.cnt_hipo = 0
        self.cnt_imovel = 0

    def avaliar(self, amostra):
        """Classifica uma amostra e devolve (motivo, detalhe)."""
        bpm = amostra.get("bpm", 0)
        temp = float(amostra.get("temp", 0.0))
        mov = amostra.get("mov", 0)

        # 1 - impacto nao tem histerese
        if mov >= cfg.MOV_IMPACTO_MG:
            self.cnt_imovel = 0
            return QUEDA, f"{mov} mg de aceleracao"

        sinal_ok = bpm > cfg.FC_SINAL_AUSENTE

        # 2 - contadores de histerese
        self.cnt_taqui = self.cnt_taqui + 1 if (sinal_ok and bpm > cfg.FC_TAQUICARDIA) else 0
        self.cnt_bradi = self.cnt_bradi + 1 if (sinal_ok and bpm < cfg.FC_BRADICARDIA) else 0
        self.cnt_febre = self.cnt_febre + 1 if temp > cfg.TEMP_FEBRE else 0
        self.cnt_hipo = self.cnt_hipo + 1 if temp < cfg.TEMP_HIPOTERMIA else 0
        self.cnt_imovel = self.cnt_imovel + 1 if mov < cfg.MOV_REPOUSO_MG else 0

        h = cfg.AMOSTRAS_HISTERESE
        if self.cnt_taqui >= h:
            return TAQUICARDIA, f"{bpm} bpm por {self.cnt_taqui} amostras"
        if self.cnt_bradi >= h:
            return BRADICARDIA, f"{bpm} bpm por {self.cnt_bradi} amostras"
        if self.cnt_febre >= h:
            return FEBRE, f"{temp:.1f} C por {self.cnt_febre} amostras"
        if self.cnt_hipo >= h:
            return HIPOTERMIA, f"{temp:.1f} C por {self.cnt_hipo} amostras"

        # 3 - ausencia de movimento, so com ritmo alterado
        if (self.cnt_imovel >= cfg.IMOBILIDADE_AMOSTRAS and sinal_ok
                and (bpm > cfg.FC_TAQUICARDIA or bpm < cfg.FC_BRADICARDIA)):
            return IMOBILIDADE, f"{self.cnt_imovel} amostras abaixo de {cfg.MOV_REPOUSO_MG} mg"

        if not sinal_ok:
            return SINAL_AUSENTE, "sem pulso detectado"
        return NORMAL, ""

    def avaliar_serie(self, amostras):
        """
        Aplica a avaliacao a uma serie inteira e devolve apenas as TRANSICOES
        de estado. Reportar toda amostra em alerta produziria centenas de
        eventos identicos; o que interessa clinicamente e quando o estado
        mudou, nao quantas vezes ele se manteve.
        """
        self.zerar()
        eventos = []
        anterior = NORMAL

        for a in amostras:
            motivo, detalhe = self.avaliar(a)
            if motivo != anterior:
                if e_alerta_clinico(motivo) or motivo == SINAL_AUSENTE:
                    eventos.append({
                        "t": a["t"],
                        "motivo": motivo,
                        "detalhe": detalhe,
                        "mensagem": MENSAGEM.get(motivo, ""),
                        "clinico": e_alerta_clinico(motivo),
                        "gravidade": GRAVIDADE.get(motivo, 0),
                        "amostra": a,
                    })
                anterior = motivo

        return eventos
