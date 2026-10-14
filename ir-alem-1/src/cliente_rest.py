"""
CardioIA - Fase 3 - Ir Alem 1
Cliente REST: consome a telemetria e devolve os alertas apurados.

O enunciado pede um cliente que "consuma e envie" dados. Sao as duas direcoes:

  consumir  GET  /api/v1/pacientes/<id>/telemetria
  enviar    POST /api/v1/pacientes/<id>/telemetria   (ingestao de amostra)
            POST /api/v1/pacientes/<id>/alertas      (alerta apurado)

Usa `urllib.request`, da biblioteca padrao. `requests` seria mais confortavel,
mas manteria o projeto dependente de instalacao - e a diferenca, em um cliente
deste tamanho, e um gerenciador de contexto a mais.

O tratamento de erro e explicito: codigo HTTP fora da faixa de sucesso vira
excecao com o corpo da resposta anexado, porque "falhou" sem o motivo obriga
quem depura a reproduzir o problema para descobrir o que o servidor disse.
"""

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg


class ErroAPI(Exception):
    """Falha de comunicacao ou resposta de erro da API."""

    def __init__(self, metodo, url, codigo, corpo):
        self.codigo = codigo
        self.corpo = corpo
        super().__init__(f"{metodo} {url} devolveu HTTP {codigo}: {corpo}")


class ClienteCardioIA:
    def __init__(self, url_base=cfg.URL_BASE, paciente=cfg.ID_PACIENTE, timeout=10):
        self.url_base = url_base.rstrip("/")
        self.paciente = paciente
        self.timeout = timeout
        self.chamadas = []        # trilha de auditoria das requisicoes

    # ----------------------------------------------------------------- infra
    def _requisitar(self, metodo, caminho, corpo=None):
        url = f"{self.url_base}{caminho}"
        dados = None
        cabecalhos = {"Accept": "application/json",
                      "User-Agent": f"CardioIA-Cliente/{cfg.VERSAO_SERVICO}"}
        if corpo is not None:
            dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
            cabecalhos["Content-Type"] = "application/json; charset=utf-8"

        req = urllib.request.Request(url, data=dados, headers=cabecalhos, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                texto = r.read().decode("utf-8")
                self.chamadas.append({"metodo": metodo, "caminho": caminho,
                                      "codigo": r.status})
                return r.status, (json.loads(texto) if texto else None)
        except urllib.error.HTTPError as e:
            texto = e.read().decode("utf-8", "replace")
            self.chamadas.append({"metodo": metodo, "caminho": caminho,
                                  "codigo": e.code})
            raise ErroAPI(metodo, url, e.code, texto) from None
        except urllib.error.URLError as e:
            raise ErroAPI(metodo, url, 0, f"servidor inacessivel: {e.reason}") from None

    # ----------------------------------------------------------------- rotas
    def saude(self):
        _, corpo = self._requisitar("GET", "/saude")
        return corpo

    def obter_telemetria(self, desde=0, limite=10_000):
        caminho = (f"/api/v1/pacientes/{self.paciente}/telemetria"
                   f"?desde={desde}&limite={limite}")
        _, corpo = self._requisitar("GET", caminho)
        return corpo["amostras"]

    def enviar_amostra(self, amostra):
        caminho = f"/api/v1/pacientes/{self.paciente}/telemetria"
        codigo, corpo = self._requisitar("POST", caminho, amostra)
        return codigo, corpo

    def registrar_alerta(self, evento):
        caminho = f"/api/v1/pacientes/{self.paciente}/alertas"
        carga = {
            "t": evento["t"],
            "motivo": evento["motivo"],
            "detalhe": evento["detalhe"],
            "gravidade": evento["gravidade"],
            "clinico": evento["clinico"],
            "bpm": evento["amostra"]["bpm"],
            "temp": evento["amostra"]["temp"],
            "mov": evento["amostra"]["mov"],
        }
        codigo, corpo = self._requisitar("POST", caminho, carga)
        return codigo, corpo

    def listar_alertas(self):
        caminho = f"/api/v1/pacientes/{self.paciente}/alertas"
        _, corpo = self._requisitar("GET", caminho)
        return corpo["alertas"]


if __name__ == "__main__":
    # Uso isolado: exige o servidor ja rodando em outro terminal.
    c = ClienteCardioIA()
    try:
        s = c.saude()
    except ErroAPI as e:
        raise SystemExit(f"API indisponivel. Suba antes:  python src/servidor_rest.py\n{e}")

    print(f"[cliente] servico {s['servico']} v{s['versao']}")
    amostras = c.obter_telemetria()
    print(f"[cliente] {len(amostras)} amostras recebidas de {c.paciente}")
    print(f"[cliente] primeira: {amostras[0]}")
    print(f"[cliente] ultima:   {amostras[-1]}")
