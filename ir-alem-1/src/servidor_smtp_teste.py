"""
CardioIA - Fase 3 - Ir Alem 1
Servidor SMTP minimo para receber e arquivar as notificacoes.

POR QUE UM SERVIDOR PROPRIO

O enunciado pede a simulacao do disparo de e-mail. Havia tres caminhos:

  (a) gravar um arquivo e chamar de "e-mail" - nao exercita protocolo nenhum;
  (b) usar uma conta real (Gmail, SendGrid) - exige credenciais no repositorio
      ou variaveis de ambiente que o avaliador nao tem;
  (c) subir um servidor SMTP local que recebe de verdade.

Escolhemos (c). O `notificador_email.py` fala SMTP de verdade, com EHLO,
MAIL FROM, RCPT TO e DATA, usando `smtplib` da biblioteca padrao. O que muda
em producao e o endereco do servidor e a autenticacao - a logica de envio
permanece identica. As mensagens recebidas sao arquivadas em `saida/` no
formato .eml, que qualquer cliente de e-mail abre.

O modulo `smtpd` da biblioteca padrao foi removido no Python 3.12, e
`aiosmtpd` e dependencia externa. Entao implementamos o minimo do RFC 5321
necessario para receber uma mensagem: cerca de cinquenta linhas.
"""

import os
import socket
import sys
import threading
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA = os.path.join(RAIZ, cfg.PASTA_SAIDA)


class ServidorSMTPTeste(threading.Thread):
    """Recebe mensagens SMTP e grava cada uma como um arquivo .eml."""

    daemon = True

    def __init__(self, host=cfg.HOST_SMTP, porta=cfg.PORTA_SMTP):
        super().__init__(name="smtp-teste")
        self.host, self.porta = host, porta
        self.recebidas = []
        self._parar = threading.Event()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.porta))
        self._sock.listen(8)
        self._sock.settimeout(0.4)
        os.makedirs(PASTA, exist_ok=True)

    # -------------------------------------------------------------- protocolo
    def _atender(self, conn):
        def envia(linha):
            conn.sendall((linha + "\r\n").encode("utf-8"))

        arquivo = conn.makefile("rb")
        envia("220 cardioia.local Servidor SMTP de teste")
        remetente, destinatarios, dados = None, [], []

        while True:
            linha = arquivo.readline()
            if not linha:
                break
            cmd = linha.decode("utf-8", "replace").strip()
            maiusc = cmd.upper()

            if maiusc.startswith(("HELO", "EHLO")):
                envia("250 cardioia.local")
            elif maiusc.startswith("MAIL FROM"):
                remetente = cmd.split(":", 1)[1].strip()
                envia("250 OK")
            elif maiusc.startswith("RCPT TO"):
                destinatarios.append(cmd.split(":", 1)[1].strip())
                envia("250 OK")
            elif maiusc == "DATA":
                envia("354 Fim com ponto isolado")
                while True:
                    l = arquivo.readline()
                    if not l or l.strip() == b".":
                        break
                    dados.append(l.decode("utf-8", "replace"))
                self._arquivar(remetente, destinatarios, "".join(dados))
                envia("250 Mensagem aceita")
                remetente, destinatarios, dados = None, [], []
            elif maiusc == "QUIT":
                envia("221 Ate logo")
                break
            elif maiusc == "RSET":
                remetente, destinatarios, dados = None, [], []
                envia("250 OK")
            elif maiusc == "NOOP":
                envia("250 OK")
            else:
                envia("500 Comando nao reconhecido")

        arquivo.close()
        conn.close()

    def _arquivar(self, remetente, destinatarios, bruto):
        indice = len(self.recebidas) + 1
        carimbo = datetime.now().strftime("%H%M%S")
        assunto = ""
        for linha in bruto.splitlines():
            if linha.lower().startswith("subject:"):
                assunto = linha.split(":", 1)[1].strip()
                break

        nome = f"alerta_{indice:02d}_{carimbo}.eml"
        with open(os.path.join(PASTA, nome), "w", encoding="utf-8") as f:
            f.write(bruto)

        self.recebidas.append({
            "indice": indice,
            "arquivo": nome,
            "de": remetente,
            "para": destinatarios,
            "assunto": assunto,
            "bytes": len(bruto),
        })

    # ------------------------------------------------------------------ laco
    def run(self):
        while not self._parar.is_set():
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                self._atender(conn)
            except Exception:
                try:
                    conn.close()
                except OSError:
                    pass

    def encerrar(self):
        self._parar.set()
        try:
            self._sock.close()
        except OSError:
            pass


if __name__ == "__main__":
    s = ServidorSMTPTeste()
    s.start()
    print(f"[SMTP] escutando em {cfg.HOST_SMTP}:{cfg.PORTA_SMTP}")
    print(f"[SMTP] mensagens serao gravadas em {cfg.PASTA_SAIDA}/")
    print("[SMTP] Ctrl+C para encerrar")
    try:
        s.join()
    except KeyboardInterrupt:
        s.encerrar()
        print(f"\n[SMTP] encerrado, {len(s.recebidas)} mensagens recebidas")
