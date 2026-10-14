"""
CardioIA - Fase 3 - Ir Alem 2
Experimento completo: treina, avalia e compara os dois modelos.

Rodar:  python src/experimento.py
Saida:  resultados/metricas.json e as figuras em resultados/
"""

import json
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)

import modelos as md                                  # noqa: E402
from sklearn.linear_model import LogisticRegression   # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.preprocessing import StandardScaler      # noqa: E402
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, roc_auc_score, confusion_matrix)  # noqa: E402

SEMENTE = 20260806


def carregar():
    caminho = os.path.join(RAIZ, "dados", "series_card0056.npz")
    if not os.path.exists(caminho):
        raise SystemExit("dados/series_card0056.npz nao encontrado.\n"
                         "Rode antes:  python src/gerar_series.py")
    d = np.load(caminho)
    return d["X"], d["y"]


def avaliar(nome, y_true, y_pred, prob=None):
    cm = confusion_matrix(y_true, y_pred)
    vn, fp, fn, vp = cm.ravel()
    m = {
        "modelo": nome,
        "acuracia": round(float(accuracy_score(y_true, y_pred)), 4),
        "precisao": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "revocacao": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "verdadeiros_negativos": int(vn), "falsos_positivos": int(fp),
        "falsos_negativos": int(fn), "verdadeiros_positivos": int(vp),
    }
    if prob is not None:
        m["auc_roc"] = round(float(roc_auc_score(y_true, prob)), 4)
    return m


def gerar_figuras(X_te, y_te, lif, m_cru, m_rl, m_lif, lat,
                  pred_cru, pred_rl, pred_lif):
    """Tres figuras: a intuicao do LIF, o comparativo e a latencia."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    destino = os.path.join(RAIZ, "resultados")
    os.makedirs(destino, exist_ok=True)
    VERM, AZUL, CINZA = "#B3221E", "#0563C1", "#888888"

    # --- Figura 1: por que o vazamento funciona -----------------------
    # Uma janela normal com pico transitorio e uma com episodio sustentado.
    idx_norm = next(i for i in range(len(X_te))
                    if y_te[i] == 0 and (X_te[i] > md.FC_TAQUICARDIA).sum() > 0)
    idx_anom = next(i for i in range(len(X_te)) if y_te[i] == 1)

    fig, eixos = plt.subplots(2, 2, figsize=(11, 6), sharex=True)
    for col, (idx, titulo) in enumerate([
            (idx_norm, "Normal com artefato transitório"),
            (idx_anom, "Episódio sustentado")]):
        serie = X_te[idx]
        pot, disp = lif.simular(serie)

        ax = eixos[0, col]
        ax.plot(serie, color=VERM, lw=1.6)
        ax.axhline(md.FC_TAQUICARDIA, color=CINZA, ls="--", lw=1)
        ax.axhline(md.FC_BRADICARDIA, color=CINZA, ls="--", lw=1)
        ax.set_title(titulo, fontsize=11, fontweight="bold")
        ax.set_ylabel("FC (bpm)")
        ax.set_ylim(20, 180)

        ax = eixos[1, col]
        ax.plot(pot, color=AZUL, lw=1.6)
        ax.axhline(lif.limiar, color=VERM, ls="--", lw=1.2, label="limiar")
        for d in disp:
            ax.axvline(d, color=VERM, lw=2.2, alpha=0.55)
        ax.set_ylabel("Potencial de membrana")
        ax.set_xlabel("Leitura da janela")
        ax.legend(fontsize=8, loc="upper left")
        ax.set_title(f"{len(disp)} disparo(s)", fontsize=10)

    fig.suptitle("O vazamento do neurônio LIF descarta o artefato e acumula o episódio",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(destino, "fig1_intuicao_lif.png"), dpi=130)
    plt.close(fig)
    print("    fig1_intuicao_lif.png")

    # --- Figura 2: comparativo de metricas ----------------------------
    nomes = ["Regressão\n(série crua)", "Regressão\n(com contagem)", "Neurônio LIF"]
    metricas = ["acuracia", "precisao", "revocacao", "f1"]
    rotulos = ["Acurácia", "Precisão", "Revocação", "F1"]
    dados = [[m[k] for k in metricas] for m in (m_cru, m_rl, m_lif)]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    larg, pos = 0.26, np.arange(len(metricas))
    for i, (nome, vals) in enumerate(zip(nomes, dados)):
        ax.bar(pos + i * larg, vals, larg, label=nome,
               color=[CINZA, AZUL, VERM][i], alpha=0.9)
        for p, v in zip(pos + i * larg, vals):
            ax.text(p, v + 0.012, f"{v:.3f}", ha="center", fontsize=7.5)
    ax.set_xticks(pos + larg)
    ax.set_xticklabels(rotulos)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("Valor no conjunto de teste")
    ax.set_title("Comparação entre os métodos", fontweight="bold")
    ax.legend(fontsize=9, ncol=3, loc="lower center")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(destino, "fig2_comparativo.png"), dpi=130)
    plt.close(fig)
    print("    fig2_comparativo.png")

    # --- Figura 3: latencia de deteccao -------------------------------
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.hist(lat, bins=range(0, 38, 2), color=AZUL, alpha=0.85,
            edgecolor="white", label="LIF (primeiro disparo)")
    ax.axvline(float(np.mean(lat)), color=AZUL, ls="-", lw=2,
               label=f"média LIF: {np.mean(lat):.1f} leituras")
    ax.axvline(X_te.shape[1], color=VERM, ls="--", lw=2.2,
               label=f"regressão: {X_te.shape[1]} leituras (janela inteira)")
    ax.set_xlabel("Leituras consumidas até reconhecer o episódio")
    ax.set_ylabel("Janelas")
    ax.set_title("Latência de detecção: a vantagem estrutural do modelo orientado a evento",
                 fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(destino, "fig3_latencia.png"), dpi=130)
    plt.close(fig)
    print("    fig3_latencia.png")


def main():
    X, y = carregar()
    print(f"[dados] {len(X)} janelas de {X.shape[1]} leituras")
    print(f"[dados] classe 1: {y.mean():.1%}")

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.30, random_state=SEMENTE, stratify=y)
    print(f"[dados] treino {len(X_tr)} / teste {len(X_te)}\n")

    # ---------------------------------------------------- regressao logistica
    def treinar_rl(nome, com_contagem):
        A_tr = md.extrair_atributos(X_tr, com_contagem)
        A_te = md.extrair_atributos(X_te, com_contagem)
        esc = StandardScaler().fit(A_tr)
        clf = LogisticRegression(max_iter=4000, C=1.0, random_state=SEMENTE)
        clf.fit(esc.transform(A_tr), y_tr)
        pred = clf.predict(esc.transform(A_te))
        prob = clf.predict_proba(esc.transform(A_te))[:, 1]
        m = avaliar(nome, y_te, pred, prob)
        m["n_atributos"] = int(A_te.shape[1])
        print(f"    acuracia {m['acuracia']:.3f}  revocacao {m['revocacao']:.3f}  "
              f"F1 {m['f1']:.3f}  AUC {m['auc_roc']:.3f}  ({m['n_atributos']} atributos)")
        return clf, pred, m

    print("[1a] Regressao logistica - apenas a serie crua e estatisticas basicas")
    rl_cru, pred_cru, m_cru = treinar_rl("Regressao logistica (serie crua)", False)

    print("\n[1b] Regressao logistica - com a contagem de leituras fora da faixa")
    rl, pred_rl, m_rl = treinar_rl("Regressao logistica (com contagem)", True)
    A_te = md.extrair_atributos(X_te, True)

    # --------------------------------------------------------- neuronio LIF
    print("\n[2] Neuronio LIF (ajuste por busca em grade no treino)")
    lif, nota_tr, historico = md.ajustar_lif(X_tr, y_tr, metrica="f1")
    print(f"    melhor configuracao: {lif}")
    print(f"    F1 no treino: {nota_tr:.3f}  ({len(historico)} combinacoes avaliadas)")

    pred_lif = lif.prever(X_te)
    disparos_te = lif.contagem_disparos(X_te)
    m_lif = avaliar("Neuronio LIF", y_te, pred_lif, disparos_te.astype(float))
    print(f"    acuracia {m_lif['acuracia']:.3f}  revocacao {m_lif['revocacao']:.3f}  "
          f"F1 {m_lif['f1']:.3f}  AUC {m_lif['auc_roc']:.3f}")

    # -------------------------------------------------------------- latencia
    print("\n[3] Latencia de deteccao")
    lat = lif.latencias(X_te, y_te)
    lat_media = float(lat.mean()) if len(lat) else float("nan")
    print(f"    LIF ........... {lat_media:.1f} leituras em media "
          f"(mediana {np.median(lat):.0f}, minimo {lat.min()}, maximo {lat.max()})")
    print(f"    Regressao ..... {X.shape[1]} leituras (precisa da janela inteira)")
    print(f"    vantagem do LIF: {X.shape[1] - lat_media:.1f} leituras "
          f"= {(X.shape[1] - lat_media) * 5:.0f} segundos")

    # ---------------------------------------------------------------- custo
    n_atrib = A_te.shape[1]
    ops_rl = n_atrib * 2                       # produto escalar + vies
    ops_lif = X.shape[1] * 3                   # vazamento, soma, comparacao
    print("\n[4] Custo por janela (operacoes aritmeticas)")
    print(f"    Regressao ..... {ops_rl} (sobre {n_atrib} atributos, ao fim da janela)")
    print(f"    LIF ........... {ops_lif} (3 por leitura, incremental)")

    # ------------------------------------------------------------- robustez
    print("\n[5] Robustez a artefato: janelas normais COM pico transitorio")
    picos = np.array([
        (((s > md.FC_TAQUICARDIA) | (s < md.FC_BRADICARDIA)).sum() > 0)
        for s in X_te])
    dificeis = (y_te == 0) & picos
    n_dif = int(dificeis.sum())
    if n_dif:
        fp_cru = int((pred_cru[dificeis] == 1).sum())
        fp_rl = int((pred_rl[dificeis] == 1).sum())
        fp_lif = int((pred_lif[dificeis] == 1).sum())
        print(f"    {n_dif} janelas normais contem leitura fora da faixa")
        print(f"    falsos positivos - regressao crua ...: {fp_cru} ({fp_cru / n_dif:.1%})")
        print(f"    falsos positivos - regressao+contagem: {fp_rl} ({fp_rl / n_dif:.1%})")
        print(f"    falsos positivos - LIF ..............: {fp_lif} ({fp_lif / n_dif:.1%})")
    else:
        fp_cru = fp_rl = fp_lif = 0

    # --------------------------------------------------------------- figuras
    print("\n[6] Figuras")
    gerar_figuras(X_te, y_te, lif, m_cru, m_rl, m_lif, lat,
                  pred_cru, pred_rl, pred_lif)

    # --------------------------------------------------------------- saida
    resultados = {
        "semente": SEMENTE,
        "janelas_total": int(len(X)),
        "janelas_treino": int(len(X_tr)),
        "janelas_teste": int(len(X_te)),
        "proporcao_classe_1": round(float(y.mean()), 4),
        "regressao_serie_crua": m_cru,
        "regressao_logistica": m_rl,
        "neuronio_lif": m_lif,
        "falsos_positivos_dificeis_regressao_crua": fp_cru,
        "lif_parametros": {"tau": lif.tau, "limiar": lif.limiar,
                           "ganho": lif.ganho, "minimo_disparos": lif.minimo_disparos},
        "lif_f1_treino": round(nota_tr, 4),
        "lif_combinacoes_avaliadas": len(historico),
        "latencia_lif_leituras": round(lat_media, 2),
        "latencia_lif_segundos": round(lat_media * 5, 1),
        "latencia_regressao_leituras": int(X.shape[1]),
        "latencia_regressao_segundos": int(X.shape[1] * 5),
        "operacoes_regressao": int(ops_rl),
        "operacoes_lif": int(ops_lif),
        "janelas_dificeis": n_dif,
        "falsos_positivos_dificeis_regressao": fp_rl,
        "falsos_positivos_dificeis_lif": fp_lif,
    }

    destino = os.path.join(RAIZ, "resultados")
    os.makedirs(destino, exist_ok=True)
    with open(os.path.join(destino, "metricas.json"), "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=1)

    print(f"\n[ok] metricas em resultados/metricas.json")
    return resultados


if __name__ == "__main__":
    main()
