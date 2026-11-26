# Solucionador del Método de Transporte

Proyecto de Programación Lineal de la Universidad de Córdoba. La aplicación resuelve un problema de transporte de costo mínimo, explica las asignaciones iniciales y comprueba su optimalidad con MODI.

## Ejecutar en Windows

Abre PowerShell en la carpeta del proyecto. Requiere Python 3.11 o posterior.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Abre [la aplicación local](http://localhost:8501) si Streamlit no abre el navegador. Con el entorno virtual activado también puedes usar `pip install -r requirements.txt` y `streamlit run app.py`.

## Ejecutar en Arch Linux

Si te falta Python o pip, instala los paquetes del sistema.

```bash
sudo pacman -S --needed python python-pip
```

Abre una terminal en la carpeta del proyecto y ejecuta los siguientes comandos. Si copiaste el proyecto desde Windows, crea el entorno virtual en Arch Linux dejando fuera la carpeta `.venv` de Windows.

```bash
python -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m streamlit run app.py
```

Abre [la aplicación local](http://localhost:8501). Para detenerla, pulsa **Ctrl+C** en la terminal.

## Uso

1. Carga uno de los ejemplos o elige de 2 a 10 orígenes y destinos. Ingresa los costos unitarios, la oferta y la demanda. Puedes escribir decimales con punto o coma.
2. Revisa la tabla balanceada. La aplicación agrega un origen ficticio si falta oferta o un destino ficticio si sobra, con costo unitario cero.
3. Selecciona un método o **Comparar los tres**. Pulsa **Resolver**. Activa **Mejorar hasta el óptimo si no lo es** para que MODI aplique ciclos de ajuste.
4. Consulta **Modelo**, **Solución paso a paso**, **MODI** y **Resumen comparativo**. Los reportes PDF y Excel incluyen los datos balanceados, los métodos calculados y las verificaciones ejecutadas.

| Ejemplo | Esquina noroeste | Costo mínimo | Vogel | Óptimo |
| --- | ---: | ---: | ---: | ---: |
| Profesor, 3×3 | 350 | 340 | 310 | 310 con planes alternativos |
| 4×5 | 14 285 | 13 350 | 13 230 | 13 230 con plan único |

## Cómo se calculan los resultados

- `core/models.py` guarda los datos, las soluciones y las trazas. `core/balance.py` completa la oferta o demanda ficticia. Los cálculos usan fracciones exactas para conservar los decimales ingresados.
- `core/initial.py` registra las asignaciones y completa la base. Los archivos `northwest.py`, `least_cost.py` y `vogel.py` deciden qué ruta usar en cada paso. Las rutas básicas forman un árbol de m + n − 1 aristas, incluidas las asignaciones básicas de cero.
- `core/modi.py` fija u₁ = 0, obtiene los potenciales del árbol y calcula Δᵢⱼ = uᵢ + vⱼ − cᵢⱼ. Para minimizar, un Δᵢⱼ positivo permite un pivote. La prueba de alternativas comprueba que el movimiento de costo cero admite un cambio efectivo de envíos. MODI detecta bases repetidas y aplica la regla de Bland. Si se alcanza el límite de iteraciones, conserva el último plan factible e indica que la optimalidad sigue sin certificar.
- `core/results.py` comparte textos y tablas entre `app.py` y los exportadores de `core/report.py`. Un origen ficticio representa demanda sin cubrir y un destino ficticio representa oferta sin despachar.

## Pruebas

En Windows

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

En Arch Linux

```bash
./.venv/bin/python -m pip install -r requirements-dev.txt
./.venv/bin/python -m pytest -q
```

La suite incluye ambos ejemplos, desempates, balance en ambos sentidos, degeneración, tamaños máximos, decimales y 200 problemas aleatorios reproducibles. SciPy sirve de referencia en las pruebas. La aplicación calcula sus soluciones con los algoritmos del proyecto.
