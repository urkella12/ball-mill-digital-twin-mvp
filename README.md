# Multiscale Ball Mill Digital Twin (DEM-CA) — MVP

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Pygame](https://img.shields.io/badge/Pygame-2.0+-green.svg)
![Pymunk](https://img.shields.io/badge/Pymunk-Physics-red.svg)
![NumPy](https://img.shields.io/badge/NumPy-Data-lightblue.svg)

## 📌 Overview
[cite_start]This project is a multiscale computational model for predicting nanoparticle synthesis in high-energy ball mills, integrating the Discrete Element Method (DEM) and Cellular Automata (CA)[cite: 38, 87]. 

[cite_start]Traditional mechanical alloying relies heavily on expensive, time-consuming "trial and error" approaches[cite: 40]. [cite_start]Without understanding micromechanisms, it is impossible to accurately predict when useful material fracture is replaced by unwanted cold welding[cite: 41]. [cite_start]This MVP serves as a digital twin to simulate and optimize grinding kinetics, bridging macroscopic kinematics with mesoscopic structural evolution[cite: 44, 45].

## ⚙️ Physics & Architecture

[cite_start]The system is built on a hybrid DEM-CA architecture, solving the scale-bridging problem[cite: 86]:

* [cite_start]**Macro-Level (DEM):** Calculates the kinematics of the grinding media (balls) and the drum[cite: 51]. [cite_start]It extracts collision energy spectra, impulse sums, and strong hit frequencies[cite: 88].
* [cite_start]**Meso-Level (CA):** Represents the Representative Volume Element (RVE) of the powder cluster using a 2D grid[cite: 91]. [cite_start]It calculates damage accumulation, fracture initiation (microcracks), and structural evolution[cite: 52, 92].
* [cite_start]**The Scale Bridge:** Translates macroscopic kinetic energy into localized probabilities for two competing mechanisms: **Fracture** (particle breakage) and **Cold Welding** (particle coalescence)[cite: 53, 77]. 

## ✨ MVP Features
* **Real-time Multiscale Simulation:** Watch the DEM physics (left) directly influence the CA micro-structure (right) in real-time.
* **Energy vs. Yield Economics:** Live tracking of rotational energy costs (kJ) plotted against the yield percentage of nano-dust.
* [cite_start]**Surfactant Simulation:** Toggle Surfactant (ПАВ) mode to block cold welding (coalescence) mechanisms and shift the process purely towards fracture[cite: 55, 84].
* [cite_start]**Dynamic UI:** Interactive sliders to adjust rotor speed and observe the transition from cascading (attrition) to cataracting (impact) regimes[cite: 82].

## 🚀 Installation & Usage

1. Clone the repository:
   ```bash
   git clone [https://github.com/urkella12/ball-mill-digital-twin-mvp.git](https://github.com/urkella12/ball-mill-digital-twin-mvp.git)
   cd ball-mill-digital-twin-mvp
