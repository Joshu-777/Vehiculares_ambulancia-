#!/usr/bin/env python3
"""
reto_ambulancias.py — Reto completo FINAL (SUMO 1.12 + traci 1.12).
"""
import os, sys, random, math, csv

os.environ.setdefault("DISPLAY", ":99")
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except AttributeError:
    pass

sys.path.append(os.path.join(os.environ.get("SUMO_HOME", "/usr/share/sumo"), "tools"))
import traci

# ═══════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════
SEED          = 42
SUMO_MODE     = "sumo-gui"
HORAS         = 3
T_END         = HORAS * 3600
N_POR_HORA    = 5
PSIN          = 0.25
T_ATENCION    = 120

# Detección MÁS AMPLIA
DIST_ACC      = 60
DIST_MISMA_C  = 100
DIST_MOTO     = 800      # 500 → 800
TIMEOUT_MOTO  = 150      # 240 → 150 (reintenta más rápido)
DIST_LLEGADA  = 50
DIST_COLA     = 300
T_ESPERA_COLA = 30
RETRY_DESP    = 30
RETRY_ACC     = 15       # Reintentar accidente tras 15s si falla

rng = random.Random(SEED)

HOSPITALES_DATA = {
    "VCM":         {"lon": -78.992923, "lat": -2.911098, "tipo": "publico"},
    "IESS_JCA":    {"lon": -78.970118, "lat": -2.898698, "tipo": "publico"},
    "MILITAR":     {"lon": -79.003968, "lat": -2.903146, "tipo": "publico"},
    "MUNI_PAT":    {"lon": -78.982263, "lat": -2.866103, "tipo": "publico"},
    "MUNI_VALLE":  {"lon": -78.961959, "lat": -2.919522, "tipo": "publico"},
    "MONTE_SINAI": {"lon": -79.007373, "lat": -2.908606, "tipo": "privado"},
    "DEL_RIO":     {"lon": -78.960796, "lat": -2.892939, "tipo": "privado"},
}

def generar_agenda():
    a = []
    for h in range(HORAS):
        inst = sorted(rng.uniform(h*3600 + 300, h*3600 + 3480) for _ in range(N_POR_HORA))
        a.extend(inst)
    return a

AGENDA = generar_agenda()

import heapq
pendientes = list(AGENDA)
heapq.heapify(pendientes)

def reprogramar(t, delay=5):
    heapq.heappush(pendientes, t + delay)

print("╔" + "═" * 68 + "╗")
print("║" + " " * 18 + "RETO AMBULANCIAS — VERSIÓN FINAL" + " " * 18 + "║")
print("╚" + "═" * 68 + "╝")
print(f"Semilla  : {SEED}")
print(f"Duración : {HORAS} h ({T_END} s)")
print(f"Agenda   : {len(AGENDA)} accidentes programados")

# ═══════════════════════════════════════════════════════════
#  ARRANCAR SUMO
# ═══════════════════════════════════════════════════════════
os.makedirs("salida", exist_ok=True)
print(f"\n▶ Arrancando SUMO (GUI)...")
try:
    traci.start([SUMO_MODE, "-c", "reto.sumocfg",
                 "--no-warnings", "true",
                 "--no-step-log", "true",
                 "--duration-log.disable", "true",
                 "--log", "salida/sumo.log"])
except Exception as e:
    print(f"\n❌ Error iniciando SUMO: {e}")
    print("   Verifica: TigerVNC conectado a 127.0.0.1:5901")
    sys.exit(1)

print("✅ Conectado a SUMO")

pasos = 0
while traci.vehicle.getIDCount() < 20 and pasos < 100:
    traci.simulationStep()
    pasos += 1

# ═══════════════════════════════════════════════════════════
#  HELPERS VISUALES
# ═══════════════════════════════════════════════════════════
def circulo(cx, cy, r, n=24):
    return [(cx + r*math.cos(2*math.pi*i/n), cy + r*math.sin(2*math.pi*i/n)) for i in range(n)]

def estrella(cx, cy, ri, re, n=8):
    pts = []
    for i in range(n*2):
        rr = re if i%2==0 else ri
        a = math.pi*i/n
        pts.append((cx + rr*math.cos(a), cy + rr*math.sin(a)))
    return pts

# ═══════════════════════════════════════════════════════════
#  MAPEAR HOSPITALES — AHORA COMO POLÍGONOS VISIBLES
# ═══════════════════════════════════════════════════════════
hospitales = {}
for hid, info in HOSPITALES_DATA.items():
    edge, pos, _ = traci.simulation.convertRoad(
        info["lon"], info["lat"], isGeo=True, vClass="emergency")
    hospitales[hid] = {**info, "edge": edge, "pos": pos,
                       "stock_ini": 0, "despachos": 0, "retornos": 0,
                       "rechazos": 0, "seg_ocupado": 0}

    # Coordenadas de red
    try:
        px, py = traci.simulation.convertGeo(info["lon"], info["lat"], fromGeo=True)
    except Exception:
        continue

    # ─── POLÍGONO: círculo grande del hospital ───
    es_publico = info["tipo"] == "publico"
    color_relleno = (255, 0, 0, 100) if es_publico else (255, 140, 0, 100)
    color_borde   = (200, 0, 0, 255) if es_publico else (200, 100, 0, 255)

    try:
        # Círculo relleno (radio 80m — grande y visible)
        traci.polygon.add(f"hosp_{hid}", circulo(px, py, 80),
                          color_relleno, fill=True, layer=90)
        # Anillo borde (radio 85m)
        traci.polygon.add(f"hosp_borde_{hid}", circulo(px, py, 85),
                          color_borde, fill=False, layer=91)
        # Cruz roja (marca de hospital): horizontal
        traci.polygon.add(f"hosp_cruz_h_{hid}",
                          [(px-30, py-8), (px+30, py-8), (px+30, py+8), (px-30, py+8)],
                          (255, 255, 255, 255), fill=True, layer=92)
        # Cruz vertical
        traci.polygon.add(f"hosp_cruz_v_{hid}",
                          [(px-8, py-30), (px+8, py-30), (px+8, py+30), (px-8, py+30)],
                          (255, 255, 255, 255), fill=True, layer=92)
    except Exception as e:
        print(f"⚠ visual hospital {hid}: {e}")

# ═══════════════════════════════════════════════════════════
#  FLOTA ALEATORIA
# ═══════════════════════════════════════════════════════════
from collections import deque
flotas = {}
for hid, h in hospitales.items():
    n = rng.randint(1, 3) if h["tipo"] == "publico" else rng.randint(0, 1)
    flotas[hid] = deque(f"U_{hid}_{i+1:02d}" for i in range(n))
    h["stock_ini"] = n

print("\n── STOCK INICIAL ──")
for hid, h in hospitales.items():
    print(f"  {hid:<14} {h['tipo']:<10} stock={h['stock_ini']}")
print(f"  TOTAL: {sum(h['stock_ini'] for h in hospitales.values())}")

# ═══════════════════════════════════════════════════════════
#  ESTADO
# ═══════════════════════════════════════════════════════════
accidentes = {}
colisiones_vistas = set()
motos_armadas = {}
stock_snapshots = []

# ═══════════════════════════════════════════════════════════
#  HELPERS ACCIDENTES
# ═══════════════════════════════════════════════════════════
def marcar_visual(acc_id, x, y):
    try:
        traci.polygon.add(f"zona_{acc_id}", circulo(x,y,40), (255, 140, 0, 120), fill=True, layer=100)
        traci.polygon.add(f"anillo_{acc_id}", circulo(x,y,42), (255, 0, 0, 255), fill=False, layer=101)
        traci.polygon.add(f"estrella_{acc_id}", estrella(x,y,10,25), (255, 255, 0, 255), fill=True, layer=102)
        traci.poi.add(f"poi_{acc_id}", x, y, (255, 255, 0, 255), poiType="accidente", layer=104)
    except Exception:
        pass

def buscar_bus_apto():
    cands = []
    for vid in traci.vehicle.getIDList():
        try:
            if traci.vehicle.getTypeID(vid) != "bus": continue
            if traci.vehicle.getSpeed(vid) < 3: continue
            road = traci.vehicle.getRoadID(vid)
            if not road or road.startswith(":"): continue
            if traci.vehicle.getLanePosition(vid) < 40: continue
            cands.append(vid)
        except Exception: continue
    return rng.choice(cands) if cands else None

def buscar_moto_libre(bus_id):
    try: bx, by = traci.vehicle.getPosition(bus_id)
    except Exception: return None
    cerc, glob = [], []
    for vid in traci.vehicle.getIDList():
        try:
            if traci.vehicle.getTypeID(vid) != "moto": continue
            if vid in motos_armadas: continue
            if traci.vehicle.getSpeed(vid) < 2: continue
            mx, my = traci.vehicle.getPosition(vid)
            d = math.hypot(bx-mx, by-my)
            glob.append((d, vid))
            if d < DIST_MOTO: cerc.append((d, vid))
        except Exception: continue
    if cerc:
        cerc.sort(); return cerc[0][1], cerc[0][0]
    return None

def armar_moto(moto_id, bus_id, t):
    try:
        traci.vehicle.changeTarget(moto_id, traci.vehicle.getRoadID(bus_id))
        traci.vehicle.setSpeedMode(moto_id, 0)
        traci.vehicle.setLaneChangeMode(moto_id, 0)
        traci.vehicle.setSpeed(moto_id, 25)
        traci.vehicle.setColor(moto_id, (255, 0, 255, 255))
        motos_armadas[moto_id] = {"bus": bus_id, "t_arma": t, "registrado": False}
        return True
    except Exception: return False

def buscar_bus_cerca(moto_id):
    try:
        mx, my = traci.vehicle.getPosition(moto_id)
        m_edge = traci.vehicle.getRoadID(moto_id)
    except Exception: return None
    for bus_id in traci.vehicle.getIDList():
        try:
            if traci.vehicle.getTypeID(bus_id) != "bus": continue
            bx, by = traci.vehicle.getPosition(bus_id)
            b_edge = traci.vehicle.getRoadID(bus_id)
            d = math.hypot(mx-bx, my-by)
            if d < DIST_ACC: return bus_id
            if m_edge == b_edge and d < DIST_MISMA_C: return bus_id
        except Exception: continue
    return None

def programar_accidente(t):
    bus = buscar_bus_apto()
    if not bus: return False
    r = buscar_moto_libre(bus)
    if not r: return False
    moto, dist = r
    if not armar_moto(moto, bus, t): return False
    print(f"[{t:6.0f}s] 🏍 {moto} → {bus} (dist={dist:.0f}m)")
    return True

def registrar_accidente(t, bus_id, moto_id):
    clave = tuple(sorted([bus_id, moto_id]))
    if clave in colisiones_vistas: return
    try:
        pos = traci.vehicle.getPosition(bus_id)
        edge = traci.vehicle.getRoadID(bus_id)
        lane_pos = traci.vehicle.getLanePosition(bus_id)
    except Exception:
        return
    if not edge or edge.startswith(":"):
        return
    colisiones_vistas.add(clave)

    acc_id = f"ACC{len(accidentes)+1:02d}"
    accidentes[acc_id] = {
        "id": acc_id, "t": t, "bus": bus_id, "moto": moto_id,
        "edge": edge, "pos": pos, "lane_pos": lane_pos,
        "estado": "waiting", "hospital_origen": None, "hospital_retorno": None,
        "ambulancia": None, "unidad": None,
        "t_despacho": None, "t_llegada": None, "t_atencion_fin": None,
        "t_retorno": None, "espera": 0, "intentos": 0, "last_attempt": 0,
        "stopped_near_since": None, "last_reroute": t,
    }
    if moto_id in motos_armadas:
        motos_armadas[moto_id]["registrado"] = True

    marcar_visual(acc_id, pos[0], pos[1])
    for vid in [bus_id, moto_id]:
        try:
            traci.vehicle.setSpeedMode(vid, 0)
            traci.vehicle.setSpeed(vid, 0)
        except Exception: pass
    traci.simulationStep()
    for vid in [bus_id, moto_id]:
        try:
            traci.vehicle.setSpeedMode(vid, 31)
            traci.vehicle.setSpeed(vid, 0)
            traci.vehicle.setColor(vid, (255, 255, 0, 255))
        except Exception: pass
    print(f"[{t:6.0f}s] 💥 {acc_id} | {bus_id} × {moto_id} en {edge}")

# ═══════════════════════════════════════════════════════════
#  HELPERS AMBULANCIA
# ═══════════════════════════════════════════════════════════
def hospital_mas_cercano_despacho(acc):
    cands = []
    for hid in hospitales:
        h = hospitales[hid]
        if not flotas[hid]: continue
        try:
            ruta = traci.simulation.findRoute(h["edge"], acc["edge"], vType="ambulance")
            if ruta.edges:
                cands.append((ruta.travelTime, hid))
        except Exception:
            try:
                hx, hy = traci.simulation.convert2D(h["edge"], h["pos"])
                ax, ay = acc["pos"]
                d = math.hypot(hx - ax, hy - ay)
                cands.append((d / 10.0, hid))
            except Exception:
                continue
    if not cands: return None
    cands.sort()
    for tt, hid in cands:
        if rng.random() < PSIN:
            hospitales[hid]["rechazos"] += 1
            print(f"           ⛔ {hid} NIEGA (psin)")
            continue
        return (tt, hid)
    return None

def hospital_mas_cercano_retorno(acc_edge):
    cands = []
    for hid, h in hospitales.items():
        try:
            ruta = traci.simulation.findRoute(acc_edge, h["edge"], vType="ambulance")
            if ruta.edges:
                cands.append((ruta.travelTime, hid))
        except Exception: continue
    if not cands: return None
    cands.sort()
    return cands[0][1]

def despachar(acc, t):
    acc["last_attempt"] = t
    resultado = hospital_mas_cercano_despacho(acc)
    if not resultado:
        acc["intentos"] += 1
        return False

    tt, hid = resultado
    h = hospitales[hid]
    unidad = flotas[hid].popleft()

    amb_id = f"amb_{unidad}_{acc['id']}"
    ruta = traci.simulation.findRoute(h["edge"], acc["edge"], vType="ambulance")
    rid = f"ruta_{amb_id}"
    try:
        traci.route.add(rid, ruta.edges)
        traci.vehicle.add(amb_id, rid, typeID="ambulance",
                          depart="now", departPos="0", departSpeed="0")
        traci.vehicle.setColor(amb_id, (0, 255, 255, 255))
    except Exception as e:
        print(f"           ❌ vehicle.add: {e}")
        flotas[hid].append(unidad)
        acc["intentos"] += 1
        return False

    acc.update({"estado": "en_route", "hospital_origen": hid,
                "ambulancia": amb_id, "unidad": unidad,
                "t_despacho": t, "espera": t - acc["t"]})
    h["despachos"] += 1
    print(f"[{t:6.0f}s] 🚑 DESPACHO {acc['id']} ← {hid} {unidad} | "
          f"ETA {ruta.travelTime:.0f}s | espera {acc['espera']:.0f}s")
    return True

def dist_amb_acc(amb_id, acc):
    try:
        amb_edge = traci.vehicle.getRoadID(amb_id)
        if not amb_edge or amb_edge.startswith(":"): return float("inf")
        amb_pos = traci.vehicle.getLanePosition(amb_id)
        if amb_edge == acc["edge"]:
            return abs(amb_pos - acc["lane_pos"])
        d = traci.simulation.getDistanceRoad(amb_edge, amb_pos,
                                              acc["edge"], acc["lane_pos"], isDriving=True)
        return d if d >= 0 else float("inf")
    except Exception:
        return float("inf")

def actualizar(t):
    for acc in list(accidentes.values()):
        est = acc["estado"]

        if est == "en_route":
            amb = acc["ambulancia"]
            if amb not in traci.vehicle.getIDList():
                if amb in traci.simulation.getArrivedIDList():
                    acc["estado"] = "attending"
                    acc["t_llegada"] = t
                    acc["t_atencion_fin"] = t + T_ATENCION
                continue
            d = dist_amb_acc(amb, acc)
            vel = traci.vehicle.getSpeed(amb)
            if t - acc["last_reroute"] >= 60 and d > DIST_LLEGADA:
                try:
                    traci.vehicle.rerouteTraveltime(amb)
                    acc["last_reroute"] = t
                except Exception: pass
            llegó = False
            if d < DIST_LLEGADA:
                llegó = True
            elif d < DIST_COLA and vel < 0.5:
                if acc["stopped_near_since"] is None:
                    acc["stopped_near_since"] = t
                elif t - acc["stopped_near_since"] >= T_ESPERA_COLA:
                    llegó = True
            else:
                acc["stopped_near_since"] = None
            if llegó:
                acc["estado"] = "attending"
                acc["t_llegada"] = t
                acc["t_atencion_fin"] = t + T_ATENCION
                try:
                    traci.vehicle.setSpeedMode(amb, 0)
                    traci.vehicle.setSpeed(amb, 0)
                except Exception: pass
                print(f"[{t:6.0f}s] 🚑 LLEGADA {acc['id']} | "
                      f"respuesta {t-acc['t_despacho']:.0f}s | "
                      f"total {t-acc['t']:.0f}s")

        elif est == "attending":
            if t >= acc["t_atencion_fin"]:
                for vid in [acc["bus"], acc["moto"]]:
                    try:
                        if vid in traci.vehicle.getIDList():
                            traci.vehicle.remove(vid)
                    except Exception: pass
                hid_ret = hospital_mas_cercano_retorno(acc["edge"])
                if not hid_ret:
                    acc["estado"] = "closed"
                    continue
                amb = acc["ambulancia"]
                acc["hospital_retorno"] = hid_ret
                acc["estado"] = "returning"
                acc["t_retorno"] = t
                try:
                    traci.vehicle.setSpeedMode(amb, 31)
                    traci.vehicle.setLaneChangeMode(amb, 1621)
                    traci.vehicle.setSpeed(amb, -1)
                    traci.vehicle.changeTarget(amb, hospitales[hid_ret]["edge"])
                except Exception as e:
                    print(f"           ⚠ return: {e}")
                print(f"[{t:6.0f}s] 🏥 RETORNO {acc['id']} → {hid_ret}")

        elif est == "returning":
            amb = acc["ambulancia"]
            if amb in traci.simulation.getArrivedIDList():
                hid = acc["hospital_retorno"]
                flotas[hid].append(acc["unidad"])
                hospitales[hid]["retornos"] += 1
                acc["estado"] = "closed"
                mision = t - acc["t_despacho"]
                if acc["hospital_origen"]:
                    hospitales[acc["hospital_origen"]]["seg_ocupado"] += mision
                print(f"[{t:6.0f}s] ✅ DISPONIBLE {acc['unidad']} en {hid} | "
                      f"misión {mision:.0f}s")

# ═══════════════════════════════════════════════════════════
#  BUCLE PRINCIPAL
# ═══════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("  SIMULACIÓN EN VIVO")
print("  👉 Ctrl+Shift+F = vista completa | Ctrl+rueda = zoom")
print("  👉 Hospitales = círculos rojos/naranjas con cruz blanca")
print("  👉 Accidentes = zona naranja + estrella amarilla")
print("─" * 70 + "\n")

idx_ag = 0
paso = 0
t_actual = traci.simulation.getTime()
prox_stock = 60

try:
    while traci.simulation.getMinExpectedNumber() > 0 and paso < T_END:
        traci.simulationStep()
        paso += 1
        t_actual = traci.simulation.getTime()

        # 1) Agenda — con REINTENTO RÁPIDO (15s)
        if pendientes and t_actual >= pendientes[0]:
            heapq.heappop(pendientes)
            if not programar_accidente(t_actual):
                heapq.heappush(pendientes, t_actual + RETRY_ACC)


        # 2) Detección accidentes
        ids = set(traci.vehicle.getIDList())
        for moto_id, info in list(motos_armadas.items()):
            if info["registrado"]:
                continue
            bus_id = info["bus"]

            # moto o bus desaparecieron: reprogramar
            if moto_id not in ids or bus_id not in ids:
                if moto_id in ids:
                    try:
                        traci.vehicle.setSpeedMode(moto_id, 31)
                        traci.vehicle.setLaneChangeMode(moto_id, 1621)
                        traci.vehicle.setSpeed(moto_id, -1)
                    except Exception: pass
                reprogramar(t_actual)
                del motos_armadas[moto_id]; continue

            # timeout: reprogramar
            if t_actual - info["t_arma"] > TIMEOUT_MOTO:
                try:
                    traci.vehicle.setSpeedMode(moto_id, 31)
                    traci.vehicle.setLaneChangeMode(moto_id, 1621)
                    traci.vehicle.setSpeed(moto_id, -1)
                except Exception: pass
                reprogramar(t_actual)
                del motos_armadas[moto_id]; continue

            # perseguir al bus: actualizar destino cada 5 s
            if int(t_actual) % 5 == 0:
                try:
                    r = traci.vehicle.getRoadID(bus_id)
                    if r and not r.startswith(":"):
                        traci.vehicle.changeTarget(moto_id, r)
                except Exception: pass

            # detección: ahora contra SU bus, no cualquier bus
            try:
                mx, my = traci.vehicle.getPosition(moto_id)
                bx, by = traci.vehicle.getPosition(bus_id)
                d = math.hypot(mx - bx, my - by)
                misma = traci.vehicle.getRoadID(moto_id) == traci.vehicle.getRoadID(bus_id)
                if d < DIST_ACC or (misma and d < DIST_MISMA_C):
                    registrar_accidente(t_actual, bus_id, moto_id)
            except Exception: pass

        # 3) Despachos
        for acc in accidentes.values():
            if acc["estado"] != "waiting": continue
            if t_actual - acc["last_attempt"] >= RETRY_DESP:
                despachar(acc, t_actual)

        # 4) Actualizar
        actualizar(t_actual)

        # 5) Stock
        if t_actual >= prox_stock:
            snap = {"t": int(t_actual)}
            for hid in hospitales:
                snap[hid] = len(flotas[hid])
            stock_snapshots.append(snap)
            prox_stock += 60

        # 6) Progreso
        if paso % 600 == 0:
            ests = {}
            for a in accidentes.values():
                ests[a["estado"]] = ests.get(a["estado"], 0) + 1
            print(f"── t={t_actual:5.0f}s veh={traci.vehicle.getIDCount():3d} "
                  f"acc={len(accidentes)} {ests} ──")

except KeyboardInterrupt:
    print("\n⏹ Detenido")
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback; traceback.print_exc()
finally:
    try: traci.close()
    except Exception: pass

# ═══════════════════════════════════════════════════════════
#  CSVs
# ═══════════════════════════════════════════════════════════
os.makedirs("salida", exist_ok=True)

with open("salida/accidentes.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id","t","bus","moto","edge","hospital_origen","hospital_retorno",
                "ambulancia","t_despacho","t_llegada","t_atencion_fin","t_retorno",
                "espera","respuesta","total","mision","estado"])
    for a in accidentes.values():
        resp = (a["t_llegada"] - a["t_despacho"]) if a["t_llegada"] and a["t_despacho"] else ""
        tot  = (a["t_llegada"] - a["t"]) if a["t_llegada"] else ""
        mis  = (a["t_retorno"] - a["t_despacho"]) if a["t_retorno"] and a["t_despacho"] else ""
        w.writerow([a["id"], f"{a['t']:.1f}", a["bus"], a["moto"], a["edge"],
                    a["hospital_origen"] or "", a["hospital_retorno"] or "",
                    a["ambulancia"] or "",
                    f"{a['t_despacho']:.1f}" if a["t_despacho"] else "",
                    f"{a['t_llegada']:.1f}" if a["t_llegada"] else "",
                    f"{a['t_atencion_fin']:.1f}" if a["t_atencion_fin"] else "",
                    f"{a['t_retorno']:.1f}" if a["t_retorno"] else "",
                    f"{a['espera']:.0f}",
                    f"{resp:.0f}" if resp != "" else "",
                    f"{tot:.0f}"  if tot != ""  else "",
                    f"{mis:.0f}"  if mis != ""  else "",
                    a["estado"]])

with open("salida/hospitales.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id","tipo","stock_ini","stock_fin","despachos","retornos",
                "rechazos","seg_ocupado","utilizacion"])
    for hid, h in hospitales.items():
        sf = len(flotas[hid])
        util = (h["seg_ocupado"] / (T_END * max(1, h["stock_ini"]))) * 100 if h["stock_ini"] > 0 else 0
        w.writerow([hid, h["tipo"], h["stock_ini"], sf,
                    h["despachos"], h["retornos"], h["rechazos"],
                    f"{h['seg_ocupado']:.0f}", f"{util:.2f}"])

with open("salida/stock.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["t"] + list(hospitales.keys()))
    for s in stock_snapshots:
        w.writerow([s["t"]] + [s[h] for h in hospitales])

# ═══════════════════════════════════════════════════════════
#  RESUMEN
# ═══════════════════════════════════════════════════════════
print("\n" + "═" * 70)
print("  RESUMEN FINAL")
print("═" * 70)
cerrados = sum(1 for a in accidentes.values() if a["estado"]=="closed")
print(f"  Accidentes: {len(accidentes)} | Cerrados: {cerrados}")
print()
print(f"  {'Hospital':<14} {'Tipo':<10} {'Ini':>4} {'Fin':>4} "
      f"{'Desp':>5} {'Ret':>4} {'Rech':>5} {'Util%':>6}")
print("  " + "─" * 65)
for hid, h in hospitales.items():
    sf = len(flotas[hid])
    util = (h["seg_ocupado"] / (T_END * max(1, h["stock_ini"]))) * 100 if h["stock_ini"] > 0 else 0
    print(f"  {hid:<14} {h['tipo']:<10} {h['stock_ini']:>4} {sf:>4} "
          f"{h['despachos']:>5} {h['retornos']:>4} {h['rechazos']:>5} {util:>5.1f}%")
print("═" * 70)
print("\n✅ CSVs en salida/")
print("   Gráficos: python3 analisis.py")
