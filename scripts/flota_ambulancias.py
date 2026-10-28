#!/usr/bin/env python3
"""flota_ambulancias.py — Fase 2B: flota aleatoria + test VCM→IESS."""
import os, sys, random
from collections import deque
sys.path.append(os.path.join(os.environ.get("SUMO_HOME", "/usr/share/sumo"), "tools"))
import traci

HOSPITALES = {
    "VCM":         {"lon": -78.992923, "lat": -2.911098, "tipo": "publico"},
    "IESS_JCA":    {"lon": -78.970118, "lat": -2.898698, "tipo": "publico"},
    "MILITAR":     {"lon": -79.003968, "lat": -2.903146, "tipo": "publico"},
    "MUNI_PAT":    {"lon": -78.982263, "lat": -2.866103, "tipo": "publico"},
    "MUNI_VALLE":  {"lon": -78.961959, "lat": -2.919522, "tipo": "publico"},
    "MONTE_SINAI": {"lon": -79.007373, "lat": -2.908606, "tipo": "privado"},
    "DEL_RIO":     {"lon": -78.960796, "lat": -2.892939, "tipo": "privado"},
}

SEED = 42
PSIN = 0.25
rng  = random.Random(SEED)

traci.start(["sumo", "-c", "reto.sumocfg"])  # headless (sin GUI)
print(f"✅ SUMO conectado (semilla {SEED})")
traci.simulationStep()

# ── Mapear hospitales ──
for hid, info in HOSPITALES.items():
    edge, pos, _ = traci.simulation.convertRoad(
        info["lon"], info["lat"], isGeo=True, vClass="emergency")
    info["edge"] = edge
    info["pos"]  = pos

# ── Stock inicial aleatorio ──
print()
print("── Stock inicial de ambulancias ──")
flotas = {}
total = 0
for hid, info in HOSPITALES.items():
    if info["tipo"] == "publico":
        n = rng.randint(1, 3)
    else:
        n = rng.randint(0, 1)
    flotas[hid] = deque(f"U_{hid}_{i+1:02d}" for i in range(n))
    total += n
    marca = "  ⚠️  stock=0" if n == 0 else ""
    print(f"  {hid:<14} {info['tipo']:<10} stock={n}{marca}")
print(f"  TOTAL: {total} ambulancias")

# ── Pedir unidad con probabilidad de negativa ──
def pedir(hid):
    if not flotas[hid]:
        return None, "cola vacía"
    if rng.random() < PSIN:
        return None, f"negada (psin={PSIN})"
    return flotas[hid].popleft(), "OK"

print()
print(f"── Primer sorteo (con psin={PSIN}) ──")
for hid in HOSPITALES:
    u, motivo = pedir(hid)
    if u:
        print(f"  {hid:<14} → OK  {u}")
    else:
        print(f"  {hid:<14} → NO  ({motivo})")

# ── Test VCM → IESS a t=120s ──
print()
print("── Test ambulancia VCM → IESS (t=120s) ──")
while traci.simulation.getTime() < 120:
    traci.simulationStep()

# Asegurar una unidad en VCM
if not flotas["VCM"]:
    flotas["VCM"].append("U_VCM_TEST")
unidad = flotas["VCM"].popleft()

origen  = HOSPITALES["VCM"]
destino = HOSPITALES["IESS_JCA"]

# Encontrar ruta
ruta = traci.simulation.findRoute(origen["edge"], destino["edge"],
                                  vType="ambulance")
if not ruta.edges:
    print("  ❌ No hay ruta VCM → IESS")
    traci.close()
    sys.exit(1)

print(f"  findRoute: {len(ruta.edges)} aristas, "
      f"{ruta.length:.0f} m, ETA={ruta.travelTime:.0f}s")

# Insertar ambulancia
rid = "ruta_test"
traci.route.add(rid, ruta.edges)
traci.vehicle.add("amb_test", rid, typeID="ambulance",
                  depart="now", departPos=origen["pos"], departSpeed="max")
print(f"  Ambulancia amb_test insertada en {origen['edge']}")

# Esperar llegada
t0 = traci.simulation.getTime()
while True:
    traci.simulationStep()
    if "amb_test" in traci.simulation.getArrivedIDList():
        t1 = traci.simulation.getTime()
        dur = t1 - t0
        print(f"  ✅ Llegó a IESS en {dur:.0f}s "
              f"(ETA estimada: {ruta.travelTime:.0f}s, "
              f"diferencia: {dur - ruta.travelTime:+.0f}s)")
        break
    if traci.simulation.getTime() - t0 > 900:
        print("  ⚠️  Timeout a 900s")
        break

traci.close()
print()
print("✅ Fase 2B completa")
