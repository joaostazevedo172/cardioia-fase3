# Ir Além 1 — Comunicação automatizada com REST e e-mail

**CardioIA — Fase 3 — Grupo Purkinje — FIAP 2TIAOR-2026**

Serviço que consome e envia sinais vitais por uma API REST, detecta risco clínico e dispara notificação por e-mail automaticamente.

**🎥 Vídeo:** <https://www.youtube.com/watch?v=2YEolRwrxQs>

> O enunciado não exige vídeo para este Ir Além. Este foi gravado como material complementar.

## Rodar

```bash
cd ir-alem-1
python executar_demo.py
```

Sobe a API, o servidor SMTP de teste, roda o cliente, avalia o risco, registra os alertas e envia os e-mails. **Nenhuma dependência externa, nenhuma credencial, nada sai da máquina.**

Para rodar as partes separadamente, em dois terminais:

```bash
python src/servidor_rest.py        # terminal 1
python src/cliente_rest.py         # terminal 2
```

E a suíte de testes:

```bash
python testes/test_coerencia_firmware.py
```

## O que o enunciado pede e onde está

| Entregável | Arquivo |
|---|---|
| Cliente REST para envio e recebimento | `src/cliente_rest.py` |
| Lógica de verificação de risco | `src/regras_risco.py` |
| Disparo de e-mail automatizado | `src/notificador_email.py` |
| Relatório (1 a 2 páginas) | `docs/RELATORIO_IR_ALEM_1.md` |

## Rotas da API

```
GET  /saude                                    estado do serviço
GET  /api/v1/pacientes/<id>/telemetria         série de sinais vitais
     ?desde=<segundos>&limite=<n>
POST /api/v1/pacientes/<id>/telemetria         ingestão de amostra nova
GET  /api/v1/pacientes/<id>/alertas            alertas registrados
POST /api/v1/pacientes/<id>/alertas            registro de alerta apurado
```

O payload é idêntico ao que o ESP32 publica via MQTT na Fase 3, campo por campo. Trocar a fonte de dados entre broker e API REST não exige mudar a lógica de risco.

## Regras de risco

| Condição | Limiar | Confirmações |
|---|---|---|
| Taquicardia | acima de 120 bpm | 3 amostras |
| Bradicardia | abaixo de 50 bpm | 3 amostras |
| Febre | acima de 38,0 °C | 3 amostras |
| Hipotermia | abaixo de 35,0 °C | 3 amostras |
| Queda | impacto acima de 2500 mg | imediata |
| Imobilidade | abaixo de 60 mg por 10 min **com ritmo alterado** | 120 amostras |
| Sinal ausente | sem pulso | imediata, **não é alerta clínico** |

Os limiares são os mesmos do firmware (`../src/config.h`), e isso é **verificado por teste**: `testes/test_coerencia_firmware.py` lê o arquivo C e compara valor a valor. Se os dois divergirem, a suíte quebra.

## Por que sem framework

Flask ou FastAPI seriam escolhas naturais, e em produção seriam as certas. Aqui a prioridade é que o avaliador execute com um comando, sem instalar nada. O custo é rotear as URLs à mão, o que cabe em trinta linhas e fica visível em vez de escondido atrás de decoradores.

Pelo mesmo motivo o servidor SMTP é nosso: o módulo `smtpd` da biblioteca padrão foi removido no Python 3.12 e `aiosmtpd` é dependência externa. O `notificador_email.py` fala SMTP de verdade — o que muda em produção é o endereço e a autenticação.

## Estrutura

```
ir-alem-1/
├── executar_demo.py              # demonstração de ponta a ponta
├── src/
│   ├── config.py                 # limiares, espelhando o firmware
│   ├── gerar_telemetria.py       # série sintética reproduzível
│   ├── servidor_rest.py          # API REST
│   ├── cliente_rest.py           # cliente que consome e envia
│   ├── regras_risco.py           # verificação de risco
│   ├── notificador_email.py      # automação de e-mail
│   └── servidor_smtp_teste.py    # servidor SMTP que arquiva as mensagens
├── testes/
│   └── test_coerencia_firmware.py
├── dados/telemetria_card0056.json
├── saida/                        # .eml entregues + relatório da execução
└── docs/RELATORIO_IR_ALEM_1.md
```

## Resultado da última execução

540 amostras consumidas · 13 requisições HTTP · 10 eventos detectados · **5 e-mails enviados, 5 suprimidos**.

Metade dos eventos não virou e-mail, e é esse o comportamento desejado: dez notificações para cinco situações clínicas distintas seria ruído.
