"""
CardioIA - Fase 3 - Ir Alem 1
Parametros do servico de monitoramento por REST e notificacao por e-mail.

Os limiares clinicos sao os mesmos do firmware do wearable (src/config.h da
Fase 3). Essa repeticao nao e descuido: e o ponto central da integracao. Se o
servico REST avaliasse risco com limiares diferentes dos do dispositivo, a
central receberia alertas que o paciente nao ve no proprio aparelho, ou o
contrario. Qualquer alteracao precisa acontecer nos dois lugares, e o teste
`testes/test_coerencia_firmware.py` falha se eles divergirem.
"""

# ---------------------------------------------------------------------
# Identidade (a mesma chave que atravessa as tres fases do CardioIA)
# ---------------------------------------------------------------------
ID_PACIENTE = "CARD-0056"
ID_DISPOSITIVO = "PURKINJE-WEAR-01"
VERSAO_SERVICO = "1.0.0"

# ---------------------------------------------------------------------
# Servidor REST
# ---------------------------------------------------------------------
HOST_API = "127.0.0.1"
PORTA_API = 8765
URL_BASE = f"http://{HOST_API}:{PORTA_API}"

# ---------------------------------------------------------------------
# Limiares clinicos - espelham src/config.h do firmware
# ---------------------------------------------------------------------
FC_TAQUICARDIA = 120      # bpm
FC_BRADICARDIA = 50       # bpm
TEMP_FEBRE = 38.0         # graus Celsius
TEMP_HIPOTERMIA = 35.0    # graus Celsius
MOV_IMPACTO_MG = 2500     # mili-g: pico compativel com queda
MOV_REPOUSO_MG = 60       # abaixo disso, consideramos imobilidade

# Confirmacoes consecutivas antes de disparar (histerese).
# O dispositivo usa 3; aqui usamos o mesmo criterio sobre a serie recebida.
AMOSTRAS_HISTERESE = 3

# Imobilidade: quantas amostras consecutivas abaixo de MOV_REPOUSO_MG.
# No firmware sao 40 amostras de 15 s (10 min). Aqui a serie chega com
# cadencia de 5 s, entao 10 min equivalem a 120 amostras.
IMOBILIDADE_AMOSTRAS = 120

# Se nenhum pulso chegar, tratamos como perda de sinal (eletrodo solto) e
# nao como bradicardia - a mesma distincao que o firmware faz.
FC_SINAL_AUSENTE = 0

# ---------------------------------------------------------------------
# Notificacao por e-mail
# ---------------------------------------------------------------------
HOST_SMTP = "127.0.0.1"
PORTA_SMTP = 8025
REMETENTE = "wearable@cardioia.local"
DESTINATARIOS = ["central.cardio@cardioia.local", "plantao@cardioia.local"]

# Janela de supressao: um mesmo motivo nao gera novo e-mail antes desse
# intervalo. Sem isso, um episodio de taquicardia de dez minutos produziria
# dezenas de mensagens identicas, e a equipe passaria a ignorar todas - a
# mesma fadiga de alarme que o firmware evita no nivel do sensor.
SUPRESSAO_SEGUNDOS = 300

# Onde as mensagens entregues sao arquivadas em formato .eml
PASTA_SAIDA = "saida"
