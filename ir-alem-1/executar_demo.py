"""
CardioIA - Fase 3 - Ir Alem 1
Demonstracao de ponta a ponta, em um comando.

    python executar_demo.py

Sobe o servidor REST e o servidor SMTP de teste em threads, roda o cliente
contra a API, avalia o risco da serie recebida, devolve os alertas para a API
e dispara os e-mails. Ao final imprime o relatorio e grava:

    saida/alerta_NN_HHMMSS.eml       mensagens efetivamente entregues
    saida/relatorio_execucao.json    trilha completa da execucao

Nenhuma dependencia externa. Nenhuma credencial. Nada sai da maquina.
"""

import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "src"))

import config as cfg                      # noqa: E402
import gerar_telemetria                   # noqa: E402
import regras_risco as rr                 # noqa: E402
import servidor_rest                      # noqa: E402
from cliente_rest import ClienteCardioIA, ErroAPI   # noqa: E402
from notificador_email import Notificador           # noqa: E402
from servidor_smtp_teste import ServidorSMTPTeste   # noqa: E402

LARG = 74


def titulo(t):
    print()
    print("=" * LARG)
    print(f" {t}")
    print("=" * LARG)


def main():
    inicio = time.time()

    # ---------------------------------------------------------------- dados
    titulo("1. PREPARACAO DOS DADOS")
    destino = os.path.join(AQUI, "dados", "telemetria_card0056.json")
    if not os.path.exists(destino):
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "w", encoding="utf-8") as f:
            json.dump(gerar_telemetria.gerar(), f, ensure_ascii=False, indent=1)
        print(f"  telemetria gerada (semente {gerar_telemetria.SEMENTE})")
    else:
        print("  telemetria ja existente, reaproveitada")

    # ------------------------------------------------------------ servidores
    titulo("2. SUBINDO OS SERVICOS")
    smtp = ServidorSMTPTeste()
    smtp.start()
    print(f"  SMTP de teste  {cfg.HOST_SMTP}:{cfg.PORTA_SMTP}")

    api = servidor_rest.criar_servidor()
    import threading
    threading.Thread(target=api.serve_forever, daemon=True).start()
    print(f"  API REST       {cfg.URL_BASE}")
    time.sleep(0.4)

    cliente = ClienteCardioIA()
    try:
        saude = cliente.saude()
    except ErroAPI as e:
        smtp.encerrar()
        raise SystemExit(f"  falha ao contatar a API: {e}")
    print(f"  GET /saude     HTTP 200, {saude['amostras_disponiveis']} amostras")

    # -------------------------------------------------------------- consumo
    titulo("3. CONSUMO DA API (cliente REST)")
    amostras = cliente.obter_telemetria()
    print(f"  GET  /api/v1/pacientes/{cfg.ID_PACIENTE}/telemetria")
    print(f"       {len(amostras)} amostras, de t={amostras[0]['t']}s "
          f"a t={amostras[-1]['t']}s")
    bpms = [a["bpm"] for a in amostras]
    temps = [a["temp"] for a in amostras]
    print(f"       FC   min {min(bpms):>3} / med {sum(bpms)//len(bpms):>3} / max {max(bpms):>3} bpm")
    print(f"       Temp min {min(temps):.1f} / max {max(temps):.1f} C")

    # ----------------------------------------------------------------- envio
    titulo("4. ENVIO PARA A API (ingestao de amostra nova)")
    nova = {"t": amostras[-1]["t"] + 5, "bpm": 76, "temp": 36.7,
            "umid": 54, "mov": 150, "origem": "ingestao-demo"}
    codigo, corpo = cliente.enviar_amostra(nova)
    print(f"  POST /api/v1/pacientes/{cfg.ID_PACIENTE}/telemetria")
    print(f"       HTTP {codigo}, total no servidor agora: {corpo['total']}")

    # ------------------------------------------------------------ avaliacao
    titulo("5. VERIFICACAO DE RISCO")
    avaliador = rr.AvaliadorDeRisco()
    eventos = avaliador.avaliar_serie(amostras)
    print(f"  {len(eventos)} transicoes de estado detectadas na serie\n")
    print(f"  {'tempo':>7}  {'motivo':<15} {'tipo':<9} criterio")
    print("  " + "-" * (LARG - 4))
    for e in eventos:
        tipo = "clinico" if e["clinico"] else "tecnico"
        print(f"  {e['t'] // 60:>4}:{e['t'] % 60:02d}  {e['motivo']:<15} "
              f"{tipo:<9} {e['detalhe']}")

    # ------------------------------------------------------ registro na API
    titulo("6. REGISTRO DOS ALERTAS NA API")
    for e in eventos:
        codigo, corpo = cliente.registrar_alerta(e)
        print(f"  POST .../alertas  HTTP {codigo}  id={corpo['id']:<2} {corpo['motivo']}")

    # --------------------------------------------------------- notificacoes
    titulo("7. AUTOMACAO DE E-MAIL")
    notificador = Notificador()
    for e in eventos:
        enviado, razao = notificador.notificar(e)
        marca = "ENVIADO " if enviado else "suprimido"
        print(f"  {e['t'] // 60:>4}:{e['t'] % 60:02d}  {marca}  "
              f"{e['motivo']:<15} {razao}")

    time.sleep(0.5)

    # -------------------------------------------------------------- resumo
    titulo("8. RESULTADO")
    print(f"  Requisicoes HTTP .......... {len(cliente.chamadas)}")
    print(f"  Eventos detectados ........ {len(eventos)}")
    print(f"  Alertas registrados na API. {len(cliente.listar_alertas())}")
    print(f"  E-mails enviados .......... {len(notificador.enviados)}")
    print(f"  Notificacoes suprimidas ... {len(notificador.suprimidos)}")
    print(f"  Mensagens no servidor SMTP. {len(smtp.recebidas)}")
    print()
    for m in smtp.recebidas:
        print(f"    {m['arquivo']}  ({m['bytes']} bytes)")
        print(f"      {m['assunto']}")

    relatorio = {
        "paciente": cfg.ID_PACIENTE,
        "dispositivo": cfg.ID_DISPOSITIVO,
        "amostras_consumidas": len(amostras),
        "requisicoes_http": cliente.chamadas,
        "eventos": [{k: v for k, v in e.items() if k != "amostra"} for e in eventos],
        "emails_enviados": notificador.enviados,
        "notificacoes_suprimidas": notificador.suprimidos,
        "mensagens_smtp": smtp.recebidas,
        "duracao_s": round(time.time() - inicio, 2),
    }
    caminho = os.path.join(AQUI, cfg.PASTA_SAIDA, "relatorio_execucao.json")
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=1)

    print()
    print(f"  Relatorio completo em {cfg.PASTA_SAIDA}/relatorio_execucao.json")
    print(f"  Execucao concluida em {relatorio['duracao_s']} s")

    api.shutdown()
    smtp.encerrar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
