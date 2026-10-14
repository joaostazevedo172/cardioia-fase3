# Relatório — Ir Além 1
## Comunicação automatizada com REST e e-mail

**Projeto:** CardioIA — Fase 3 — **Grupo:** Purkinje — FIAP — Turma 2TIAOR-2026
**Integrantes:** Miriã Leal Mantovani (RM567811) · João Pedro Santos Azevedo (RM566701)
**Paciente monitorado:** CARD-0056 — **Dispositivo:** PURKINJE-WEAR-01

---

### 1. O que foi construído

Um serviço de monitoramento que fecha o ciclo entre o wearable da Fase 3 e a equipe clínica, por HTTP e e-mail. São cinco módulos, todos em Python, **sem nenhuma dependência externa**: a API REST, o cliente que a consome, a lógica de verificação de risco, o notificador por e-mail e um servidor SMTP de teste que recebe as mensagens.

A ausência de dependências é uma decisão, não uma limitação. O projeto roda com `python executar_demo.py` em qualquer máquina com Python 3.9 ou superior, sem `pip install`, sem ambiente virtual e sem credenciais. Para um trabalho que será avaliado por terceiros, reprodutibilidade em um comando vale mais do que o conforto de um framework.

### 2. Fluxo implementado

```
   dados/telemetria_card0056.json
              │
              ▼
   ┌──────────────────────┐   GET  /api/v1/.../telemetria   ┌─────────────────┐
   │  servidor_rest.py    │ ──────────────────────────────► │ cliente_rest.py │
   │  (http.server)       │ ◄────────────────────────────── │                 │
   └──────────────────────┘   POST /api/v1/.../telemetria   └────────┬────────┘
              ▲               POST /api/v1/.../alertas               │
              │                                                      ▼
              │                                          ┌───────────────────────┐
              │                                          │   regras_risco.py     │
              │                                          │  histerese, limiares  │
              │                                          └───────────┬───────────┘
              │                                                      │ evento clínico
              │                                                      ▼
              │                                          ┌───────────────────────┐
              └──────────── registro do alerta ───────── │ notificador_email.py  │
                                                         │   SMTP real           │
                                                         └───────────┬───────────┘
                                                                     ▼
                                                      servidor_smtp_teste.py
                                                            saída/*.eml
```

O cliente faz as duas direções que o enunciado pede. **Consome** a série de sinais vitais por `GET`, e **envia** em dois momentos: uma amostra nova por `POST /telemetria`, demonstrando ingestão, e cada alerta apurado por `POST /alertas`, devolvendo ao servidor a conclusão do processamento.

### 3. Lógica de verificação de risco

As regras são as mesmas do firmware do ESP32, reescritas em Python e aplicadas sobre a série recebida. Quatro propriedades foram preservadas deliberadamente:

| Propriedade | Comportamento | Por quê |
|---|---|---|
| Histerese | Taquicardia, bradicardia, febre e hipotermia exigem 3 amostras consecutivas | Uma leitura ruim isolada não pode acionar um alerta médico |
| Impacto imediato | Queda dispara na primeira amostra | Uma queda é evento único; esperar confirmação perderia o evento |
| Falha ≠ evento | FC zero vira `SINAL_AUSENTE`, nunca bradicardia | Eletrodo solto não é emergência; confundir os dois gera fadiga de alarme |
| Imobilidade condicional | Só alerta com ritmo alterado | Paciente parado com ritmo normal está dormindo, não desmaiado |

**Essa coerência é testada, não apenas afirmada.** O arquivo `testes/test_coerencia_firmware.py` lê o `config.h` do firmware e compara valor a valor com o `config.py` do serviço. Se alguém alterar o limiar de taquicardia no dispositivo e esquecer de alterar aqui, a suíte quebra. Sem esse teste a divergência seria silenciosa e perversa: o paciente veria o LED vermelho aceso no peito enquanto a central não receberia e-mail nenhum. Um sistema de monitoramento que discorda de si mesmo é pior que um que não monitora, porque produz confiança injustificada.

### 4. Automação de e-mail

O envio usa `smtplib` e fala SMTP de verdade — `EHLO`, `MAIL FROM`, `RCPT TO`, `DATA` — contra um servidor que implementamos em cerca de cinquenta linhas, porque o módulo `smtpd` da biblioteca padrão foi removido no Python 3.12 e `aiosmtpd` seria dependência externa. As mensagens recebidas são arquivadas em `.eml`, formato que qualquer cliente de e-mail abre. Migrar para um provedor real significa trocar host, porta e acrescentar `starttls()` e `login()`; a montagem e o disparo permanecem idênticos.

Duas regras governam quem recebe e-mail:

**Falha técnica não acorda o plantão.** `SINAL_AUSENTE` é registrado no relatório e na API, mas não gera notificação clínica.

**Repetição é suprimida por 300 segundos.** Um episódio de taquicardia de dez minutos produz dezenas de amostras em alerta; notificar todas geraria dezenas de e-mails idênticos e a equipe passaria a ignorar a caixa de entrada.

### 5. Resultado da execução

A série sintética de 45 minutos foi construída para exercitar todas as regras, inclusive as que só aparecem em combinação. Os números abaixo são a saída real de `executar_demo.py`:

| Métrica | Valor |
|---|---|
| Amostras consumidas | 540 |
| Requisições HTTP | 13 |
| Transições de estado detectadas | 10 |
| Alertas registrados na API | 10 |
| **E-mails enviados** | **5** |
| **Notificações suprimidas** | **5** |

| Momento | Motivo | Notificação |
|---|---|---|
| 08:10 | TAQUICARDIA | enviada |
| 10:40 · 11:55 · 12:30 | TAQUICARDIA | suprimidas (janela de 300 s) |
| 18:50 | FEBRE | enviada |
| 25:00 | QUEDA | enviada |
| 38:20 | IMOBILIDADE | enviada |
| 38:30 | BRADICARDIA | enviada |
| 43:05 · 43:15 | IMOBILIDADE · BRADICARDIA | suprimidas |

Metade dos eventos não virou e-mail. É exatamente o comportamento desejado: dez notificações para cinco situações clínicas distintas seria ruído.

### 6. Duas observações que a execução revelou

**A detecção oscila; a notificação não.** A frequência cardíaca durante a taquicardia transita em torno de 134 bpm e ocasionalmente cai abaixo de 120, o que zera o contador e produz uma nova transição de estado quando volta a subir. Daí as quatro detecções de taquicardia para dois episódios. A histerese protege contra o falso positivo de entrada, mas não impede esse tremor em torno do limiar — quem absorve isso é a janela de supressão do notificador. As duas camadas são complementares, e nenhuma delas sozinha resolveria.

**A imobilidade dispara antes da bradicardia.** Às 38:20 o paciente está imóvel há mais de dez minutos e o ritmo acabou de cair abaixo de 50 bpm. A bradicardia ainda está cumprindo as três confirmações, então quem alerta primeiro é a imobilidade; dez segundos depois a bradicardia confirma. Essa ordem é consequência da precedência das regras, e faz sentido clínico: suspeita de síncope não deve esperar histerese.

### 7. Limitações

A API mantém estado em memória, sem persistência — um banco seria exagero para um protótipo cujo objetivo é demonstrar o fluxo HTTP. Não há autenticação nas rotas, adequado para `127.0.0.1` e inadequado para qualquer uso real com dados de saúde, que são dados pessoais sensíveis pela LGPD. O SMTP é local e sem TLS. A série é sintética e reproduzível pela semente `20260806`, a mesma desde a Fase 1.

---

*Documento sob licença CC BY 4.0 — Grupo Purkinje, FIAP 2026.*
