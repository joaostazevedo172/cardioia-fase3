"""
CardioIA - Fase 3 - Ir Alem 1
API REST que expoe a telemetria do paciente e recebe os alertas apurados.

POR QUE SEM FRAMEWORK

A API usa apenas `http.server`, da biblioteca padrao. Flask e FastAPI seriam
escolhas naturais, e em producao seriam as certas - mas aqui a prioridade e
que o avaliador clone o repositorio e execute com um comando, sem instalar
nada e sem ambiente virtual. Nao ha `pip install` neste projeto. O custo e
termos de rotear as URLs a mao, o que cabe em trinta linhas e fica visivel
em vez de escondido atras de decoradores.

ROTAS

  GET  /saude                                  estado do servico
  GET  /api/v1/pacientes/<id>/telemetria       serie de sinais vitais
       ?desde=<segundos>&limite=<n>
  POST /api/v1/pacientes/<id>/telemetria       ingestao de uma amostra nova
  GET  /api/v1/pacientes/<id>/alertas          alertas ja registrados
  POST /api/v1/pacientes/<id>/alertas          registro de um alerta apurado

Rodar:  python src/servidor_rest.py
"""

import json
import os
import re
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO_TELEMETRIA = os.path.join(RAIZ, "dados", "telemetria_card0056.json")

# Estado em memoria. Um banco seria exagero para um prototipo cujo objetivo e
# demonstrar o fluxo HTTP; o lock existe porque ThreadingHTTPServer atende
# requisicoes concorrentes e duas escritas simultaneas corromperiam a lista.
_trava = threading.Lock()
_telemetria = []
_alertas = []


def carregar_telemetria():
    global _telemetria
    if not os.path.exists(ARQUIVO_TELEMETRIA):
        raise SystemExit(
            "dados/telemetria_card0056.json nao encontrado.\n"
            "Rode antes:  python src/gerar_telemetria.py")
    with open(ARQUIVO_TELEMETRIA, encoding="utf-8") as f:
        _telemetria = json.load(f)


def agora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Manipulador(BaseHTTPRequestHandler):
    server_version = f"CardioIA/{cfg.VERSAO_SERVICO}"

    # ----------------------------------------------------------------- infra
    def _responder(self, codigo, corpo):
        dados = json.dumps(corpo, ensure_ascii=False, indent=1).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def _corpo_json(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        if not tamanho:
            return None
        try:
            return json.loads(self.rfile.read(tamanho).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    def log_message(self, formato, *args):
        # silencia o log padrao; a demo imprime o que interessa
        pass

    # ------------------------------------------------------------------ GET
    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)

        if url.path == "/saude":
            return self._responder(200, {
                "estado": "ok",
                "servico": "CardioIA Telemetria",
                "versao": cfg.VERSAO_SERVICO,
                "amostras_disponiveis": len(_telemetria),
                "alertas_registrados": len(_alertas),
                "instante": agora(),
            })

        m = re.fullmatch(r"/api/v1/pacientes/([A-Z]+-\d+)/telemetria", url.path)
        if m:
            if m.group(1) != cfg.ID_PACIENTE:
                return self._responder(404, {"erro": "paciente nao encontrado",
                                             "paciente": m.group(1)})
            desde = int(q.get("desde", [0])[0])
            limite = int(q.get("limite", [10_000])[0])
            with _trava:
                sel = [a for a in _telemetria if a["t"] >= desde][:limite]
            return self._responder(200, {
                "paciente": cfg.ID_PACIENTE,
                "dispositivo": cfg.ID_DISPOSITIVO,
                "total": len(sel),
                "desde": desde,
                "amostras": sel,
            })

        m = re.fullmatch(r"/api/v1/pacientes/([A-Z]+-\d+)/alertas", url.path)
        if m:
            with _trava:
                return self._responder(200, {
                    "paciente": m.group(1),
                    "total": len(_alertas),
                    "alertas": list(_alertas),
                })

        return self._responder(404, {"erro": "rota nao encontrada", "caminho": url.path})

    # ----------------------------------------------------------------- POST
    def do_POST(self):
        url = urlparse(self.path)
        corpo = self._corpo_json()
        if corpo is None:
            return self._responder(400, {"erro": "corpo JSON ausente ou invalido"})

        m = re.fullmatch(r"/api/v1/pacientes/([A-Z]+-\d+)/telemetria", url.path)
        if m:
            faltando = [c for c in ("t", "bpm", "temp", "mov") if c not in corpo]
            if faltando:
                return self._responder(422, {"erro": "campos obrigatorios ausentes",
                                             "campos": faltando})
            corpo.setdefault("pac", m.group(1))
            corpo.setdefault("origem", "ingestao")
            with _trava:
                _telemetria.append(corpo)
                total = len(_telemetria)
            return self._responder(201, {"criado": True, "total": total,
                                         "instante": agora()})

        m = re.fullmatch(r"/api/v1/pacientes/([A-Z]+-\d+)/alertas", url.path)
        if m:
            if "motivo" not in corpo:
                return self._responder(422, {"erro": "campo 'motivo' obrigatorio"})
            registro = dict(corpo)
            registro["paciente"] = m.group(1)
            registro["registrado_em"] = agora()
            with _trava:
                registro["id"] = len(_alertas) + 1
                _alertas.append(registro)
            return self._responder(201, {"criado": True, "id": registro["id"],
                                         "motivo": registro["motivo"]})

        return self._responder(404, {"erro": "rota nao encontrada", "caminho": url.path})


def criar_servidor():
    carregar_telemetria()
    return ThreadingHTTPServer((cfg.HOST_API, cfg.PORTA_API), Manipulador)


if __name__ == "__main__":
    s = criar_servidor()
    print(f"[API ] CardioIA Telemetria em {cfg.URL_BASE}")
    print(f"[API ] {len(_telemetria)} amostras do paciente {cfg.ID_PACIENTE}")
    print("[API ] Ctrl+C para encerrar")
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        print("\n[API ] encerrado")
