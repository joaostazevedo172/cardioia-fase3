"""
CardioIA - Fase 3 - Ir Alem 1
Automacao de notificacao por e-mail em caso de alerta clinico.

O envio usa `smtplib` e `email.message` da biblioteca padrao, falando SMTP de
verdade com o servidor. Trocar para um provedor real significa mudar host,
porta e acrescentar `starttls()` e `login()` - a montagem da mensagem e o
disparo permanecem os mesmos.

DUAS DECISOES QUE IMPORTAM

Supressao de repeticao. Um episodio de taquicardia de dez minutos produz
dezenas de amostras em alerta. Notificar todas geraria dezenas de e-mails
identicos e a equipe passaria a ignorar a caixa de entrada - a mesma fadiga
de alarme que o firmware evita no nivel do sensor. Por isso um mesmo motivo
so volta a notificar depois de SUPRESSAO_SEGUNDOS.

Falha tecnica nao vira e-mail de emergencia. SINAL_AUSENTE significa eletrodo
solto. E registrado no relatorio e na API, mas nao aciona a notificacao
clinica, porque acordar o plantao por um eletrodo solto e o caminho mais
curto para que o proximo alerta real seja ignorado.
"""

import os
import smtplib
import sys
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg
import regras_risco as rr

ASSUNTO = {
    rr.QUEDA: "[EMERGENCIA] Queda detectada",
    rr.TAQUICARDIA: "[ALERTA] Taquicardia sustentada",
    rr.BRADICARDIA: "[ALERTA] Bradicardia sustentada",
    rr.IMOBILIDADE: "[ALERTA] Imobilidade com ritmo alterado",
    rr.HIPOTERMIA: "[ALERTA] Hipotermia",
    rr.FEBRE: "[ALERTA] Febre",
}


def _formatar_tempo(segundos):
    return f"{segundos // 60:02d}:{segundos % 60:02d}"


def montar_mensagem(evento):
    """Monta o EmailMessage de um evento clinico."""
    a = evento["amostra"]
    motivo = evento["motivo"]

    msg = EmailMessage()
    msg["From"] = cfg.REMETENTE
    msg["To"] = ", ".join(cfg.DESTINATARIOS)
    msg["Subject"] = f"{ASSUNTO.get(motivo, '[ALERTA] ' + motivo)} - {cfg.ID_PACIENTE}"
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="cardioia.local")
    msg["X-CardioIA-Paciente"] = cfg.ID_PACIENTE
    msg["X-CardioIA-Motivo"] = motivo
    msg["X-CardioIA-Gravidade"] = str(evento["gravidade"])

    corpo = f"""ALERTA CLINICO AUTOMATICO - CardioIA

Paciente .......... {cfg.ID_PACIENTE}
Dispositivo ....... {cfg.ID_DISPOSITIVO}
Momento ........... {_formatar_tempo(evento['t'])} de monitoramento
Motivo ............ {motivo}
Criterio .......... {evento['detalhe']}

{evento['mensagem']}

SINAIS VITAIS NO INSTANTE DO ALERTA

  Frequencia cardiaca .... {a['bpm']} bpm
  Temperatura ............ {a['temp']:.1f} C
  Umidade relativa ....... {a['umid']} %
  Movimento .............. {a['mov']} mg

LIMIARES EM VIGOR

  Taquicardia ............ acima de {cfg.FC_TAQUICARDIA} bpm
  Bradicardia ............ abaixo de {cfg.FC_BRADICARDIA} bpm
  Febre .................. acima de {cfg.TEMP_FEBRE:.1f} C
  Impacto ................ acima de {cfg.MOV_IMPACTO_MG} mg

Todos os alertas exigem {cfg.AMOSTRAS_HISTERESE} amostras consecutivas na
condicao, exceto impacto, que dispara de imediato.

--
Mensagem gerada automaticamente pelo servico CardioIA Telemetria
versao {cfg.VERSAO_SERVICO}. Nao responda a este endereco.
"""
    msg.set_content(corpo)
    return msg


class Notificador:
    """Dispara e-mails com supressao de repeticao por motivo."""

    def __init__(self, host=cfg.HOST_SMTP, porta=cfg.PORTA_SMTP,
                 supressao=cfg.SUPRESSAO_SEGUNDOS):
        self.host, self.porta = host, porta
        self.supressao = supressao
        self._ultimo_envio = {}     # motivo -> instante (t da serie)
        self.enviados = []
        self.suprimidos = []

    def deve_notificar(self, evento):
        """Decide se o evento merece e-mail, e explica o porque."""
        if not evento["clinico"]:
            return False, "falha tecnica, nao e alerta clinico"
        ultimo = self._ultimo_envio.get(evento["motivo"])
        if ultimo is not None and (evento["t"] - ultimo) < self.supressao:
            faltam = self.supressao - (evento["t"] - ultimo)
            return False, f"suprimido, mesmo motivo ha {evento['t'] - ultimo} s (janela {self.supressao} s, faltam {faltam} s)"
        return True, "primeiro do tipo na janela"

    def notificar(self, evento):
        """Envia o e-mail se a regra permitir. Devolve (enviado, motivo)."""
        enviar, razao = self.deve_notificar(evento)
        if not enviar:
            self.suprimidos.append({"t": evento["t"], "motivo": evento["motivo"],
                                    "razao": razao})
            return False, razao

        msg = montar_mensagem(evento)
        with smtplib.SMTP(self.host, self.porta, timeout=10) as s:
            s.send_message(msg)

        self._ultimo_envio[evento["motivo"]] = evento["t"]
        self.enviados.append({"t": evento["t"], "motivo": evento["motivo"],
                              "assunto": msg["Subject"]})
        return True, razao
