#!/usr/bin/env python3
"""analisis.py — 3 gráficos + resumen estadístico."""
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="whitegrid", context="notebook")
plt.rcParams.update({"figure.dpi": 120, "savefig.dpi": 150, "savefig.bbox": "tight"})
os.makedirs("salida", exist_ok=True)

acc = pd.read_csv("salida/accidentes.csv")
hosp = pd.read_csv("salida/hospitales.csv")
stock = pd.read_csv("salida/stock.csv")

acc_ok = acc[acc["respuesta"].notna()].copy() if "respuesta" in acc.columns else acc.iloc[0:0]

# ─── Fig 1: tiempo de respuesta ───
if len(acc_ok) > 0:
    fig, ax = plt.subplots(figsize=(13, 6))
    x = range(len(acc_ok))
    ax.bar(x, acc_ok["respuesta"], color="steelblue", edgecolor="white")
    med = acc_ok["respuesta"].median()
    p90 = acc_ok["respuesta"].quantile(0.90)
    ax.axhline(med, color="green", ls="--", lw=2, label=f"Mediana {med:.0f}s")
    ax.axhline(p90, color="crimson", ls=":", lw=2, label=f"p90 {p90:.0f}s")
    ax.set_xticks(x); ax.set_xticklabels(acc_ok["id"], rotation=45)
    ax.set_ylabel("Tiempo de respuesta (s)", fontweight="bold")
    ax.set_title(f"Tiempo de respuesta por accidente (N={len(acc_ok)})")
    ax.legend()
    plt.tight_layout(); plt.savefig("salida/fig1_respuesta.png"); plt.close()
    print(f"✅ fig1_respuesta.png | mediana={med:.0f}s, p90={p90:.0f}s")

# ─── Fig 2: uso por hospital ───
fig, ax = plt.subplots(figsize=(13, 6))
x = range(len(hosp)); w = 0.25
ax.bar([i-w for i in x], hosp["stock_ini"], w, label="Stock inicial", color="lightgray")
ax.bar(x,                hosp["despachos"], w, label="Despachos",   color="navy")
ax.bar([i+w for i in x], hosp["retornos"],  w, label="Retornos",    color="steelblue")
ax.set_xticks(x); ax.set_xticklabels(hosp["id"], rotation=45)
ax.set_ylabel("Unidades", fontweight="bold")
ax.set_title("Uso de ambulancias por hospital (3 h)")
ax.legend()
plt.tight_layout(); plt.savefig("salida/fig2_uso_hospitales.png"); plt.close()
print("✅ fig2_uso_hospitales.png")

# ─── Fig 3: stock en el tiempo ───
fig, ax = plt.subplots(figsize=(13, 6))
for hid in stock.columns[1:]:
    ax.plot(stock["t"]/60, stock[hid], label=hid, marker="o", ms=3)
ax.set_xlabel("Tiempo (min)", fontweight="bold")
ax.set_ylabel("Stock disponible", fontweight="bold")
ax.set_title("Stock de ambulancias en el tiempo")
ax.legend(ncol=2, fontsize=9)
plt.tight_layout(); plt.savefig("salida/fig3_stock_tiempo.png"); plt.close()
print("✅ fig3_stock_tiempo.png")

# ─── Resumen ───
print()
print("═══ RESUMEN ANALÍTICO ═══")
if len(acc_ok) > 0:
    print(f"Accidentes atendidos: {len(acc_ok)}")
    print(f"  Tiempo de respuesta (despacho → llegada):")
    print(f"    mediana = {acc_ok['respuesta'].median():.0f} s")
    print(f"    media   = {acc_ok['respuesta'].mean():.0f} s")
    print(f"    p90     = {acc_ok['respuesta'].quantile(0.90):.0f} s")
    print(f"    máx     = {acc_ok['respuesta'].max():.0f} s")
print()
print(f"  {'Hospital':<14} {'Desp':>5} {'Ret':>4} {'Rech':>5} {'Util%':>7}")
print("  " + "─" * 40)
for _, r in hosp.iterrows():
    print(f"  {r['id']:<14} {r['despachos']:>5} {r['retornos']:>4} "
          f"{r['rechazos']:>5} {r['utilizacion']:>6.1f}%")