#!/usr/bin/env python3
"""mapear_hospitales_v4.py — Hospitales como polígonos (fix SUMO 1.12)."""
import os, sys, math, time
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

def circulo(cx, cy, radio, n=24):
    return [(cx + radio*math.cos(2*math.pi*i/n),
             cy + radio*math.sin(2*math.pi*i/n)) for i in range(n)]

traci.start(["sumo-gui", "-c", "reto.sumocfg"])
print("✅ SUMO conectado")

for _ in range(5):
    traci.simulationStep()

print()
print(f"{'ID':<13} {'Tipo':<9} {'Arista':<22} {'Dist(m)':>8}")
print("─" * 60)

for hid, info in HOSPITALES.items():
    edge, pos, _ = traci.simulation.convertRoad(
        info["lon"], info["lat"], isGeo=True, vClass="emergency")

    try:
        ex, ey = traci.simulation.convert2D(edge, pos)
        hx, hy = traci.simulation.convertGeo(info["lon"], info["lat"], fromGeo=True)
        dist = math.hypot(ex - hx, ey - hy)
    except Exception:
        dist = float("nan")

    info["edge"] = edge
    info["pos"]  = pos

    px, py = traci.simulation.convertGeo(info["lon"], info["lat"], fromGeo=True)

    # ── POI (aunque no se vea en GUI, queda registrado) ──
    color = (255, 0, 0, 255) if info["tipo"] == "publico" else (255, 140, 0, 255)
    try:
        traci.poi.add(f"hosp_{hid}", px, py, color, poiType="hospital", layer=100)
    except Exception:
        pass

    # ── POLÍGONO: círculo ──
    # Firma SUMO 1.12: add(id, shape, color, fill, polygonType, layer)
    shape = circulo(px, py, 120)  # radio 120 m
    fill_rgba = (255, 0, 0, 150) if info["tipo"] == "publico" else (255, 140, 0, 150)

    try:
        traci.polygon.add(f"circ_{hid}", shape, fill_rgba,
                          fill=True, layer=50)
    except Exception as e:
        print(f"  ❌ Polygon {hid}: {e}")

    # ── MARCADOR ANILLO: un contorno más grande sin relleno ──
    shape_borde = circulo(px, py, 150)
    borde_rgba = (200, 0, 0, 255) if info["tipo"] == "publico" else (200, 100, 0, 255)
    try:
        traci.polygon.add(f"ring_{hid}", shape_borde, borde_rgba,
                          fill=False, layer=51)
    except Exception:
        pass

    print(f"{hid:<13} {info['tipo']:<9} {edge:<22} {dist:>8.1f}")

# ── Zoom ──
xmin, ymin, xmax, ymax = 1e9, 1e9, -1e9, -1e9
for edge_id in traci.edge.getIDList():
    if edge_id.startswith(":"):
        continue
    try:
        for x, y in traci.lane.getShape(f"{edge_id}_0"):
            xmin, ymin = min(xmin, x), min(ymin, y)
            xmax, ymax = max(xmax, x), max(ymax, y)
    except Exception:
        pass

if xmin < xmax:
    try:
        traci.gui.setBoundary("View #0", xmin-200, ymin-200, xmax+200, ymax+200)
        print(f"\n✅ Zoom aplicado: ({xmin:.0f},{ymin:.0f}) → ({xmax:.0f},{ymax:.0f})")
    except Exception as e:
        print(f"⚠️  Zoom: {e}")

# ── Diagnóstico: ¿se añadieron los polígonos? ──
polys = traci.polygon.getIDList()
print(f"\n✅ Polígonos en SUMO: {len(polys)}")
for p in polys:
    print(f"   - {p}")

# ── Contar POIs también ──
pois = traci.poi.getIDList()
print(f"\n✅ POIs en SUMO: {len(pois)}")

print()
print("═" * 60)
print("  👉 Hospitales = CÍRCULOS rojos (públicos) / naranjas (privados)")
print("  👉 Si NO los ves en la GUI:")
print("     SUMO 1.12 usa el menú Settings, NO View.")
print("     Settings → View Settings → pestaña 'Polygons' → 'show'")
print("═" * 60)
print()
print("⏳ Simulación corriendo 30 s. Ctrl+C para salir.")
print()

try:
    for _ in range(300):
        traci.simulationStep()
        time.sleep(0.05)
except KeyboardInterrupt:
    print("\n⏹️  Detenido por el usuario")

traci.close()
print("Cerrado.")