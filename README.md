# Reto: Accidentes Bus-Moto y Despacho de Ambulancias (SUMO + TraCI)

Este repositorio contiene el desarrollo del Reto de la Práctica 04 de la asignatura **Redes Vehiculares y Heterogéneas** (Universidad de Cuenca). El proyecto consiste en un gemelo digital de emergencias para la ciudad de Cuenca, construido sobre el simulador de tráfico SUMO y controlado mediante Python a través de la interfaz TraCI.

## 📋 Descripción del Proyecto

El escenario simula 3 horas de tráfico vehicular en la red de avenidas de Cuenca, incluyendo autos, buses y motocicletas. Durante la simulación, se provocan 5 accidentes bus-moto por hora alterando el modelo de seguimiento de Krauss. Un algoritmo de despacho detecta los siniestros y envía ambulancias desde el hospital más cercano con disponibilidad, gestionando la atención en el sitio y el retorno al hospital más próximo al accidente.


## 📂 Estructura del Repositorio

```text
/
├── escenario/
│   ├── cuenca_net.xml            # Red completa original
│   ├── cuenca_ciudad.net.xml     # Red de avenidas depurada
│   ├── vtypes.add.xml            # Definición de tipos de vehículo (car, bus, moto, ambulance)
│   ├── fondo_car.rou.xml         # Rutas de autos
│   ├── fondo_bus.rou.xml         # Rutas de buses
│   ├── fondo_moto.rou.xml        # Rutas de motos
│   └── reto.sumocfg              # Configuración de la simulación
├── scripts/
│   ├── reto_ambulancias.py       # Script principal (lógica TraCI de accidentes y despacho)
│   └── analisis.py               # Script para generar gráficos a partir de los CSVs
├── salidas/
│   ├── accidentes.csv            # Registro de accidentes y tiempos
│   ├── hospitales.csv            # Uso de la flota por hospital
│   ├── stock.csv                 # Evolución temporal del stock de ambulancias
│   └── *.png                     # Gráficos generados
└── README.md
