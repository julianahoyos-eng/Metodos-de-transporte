# Prompt: App "Solucionador del Método de Transporte"

> Pega todo lo que está debajo de la línea en tu asistente de programación (Claude Code, Cursor, etc.).
> Si prefieres otra tecnología distinta a Python + Streamlit, cámbiala en la sección 0.

---

## ROL Y OBJETIVO

Actúa como ingeniero de software senior y experto en Investigación de Operaciones. Desarrolla una aplicación completa llamada **"Solucionador del Método de Transporte"** como proyecto final de Programación Lineal (Universidad de Córdoba). El usuario solo debe ingresar los datos y elegir un método; la app resuelve todo automáticamente, muestra el procedimiento paso a paso y verifica la optimalidad con MODI. Toda la interfaz y los textos van en español.

## 0. STACK

Python 3.11+ con Streamlit (cambia aquí si prefieres otro: ______). Librerías: numpy, pandas, plotly, openpyxl y reportlab. La lógica de cálculo va separada de la interfaz, y los algoritmos se implementan a mano (sin solvers). Debe correr con:

```
pip install -r requirements.txt
streamlit run app.py
```

## 1. ENTRADA DE DATOS

- Cantidad de orígenes **m** y destinos **n** (de 2 a 10) y nombres opcionales para cada uno.
- Tabla editable con costos c<sub>ij</sub>, ofertas s<sub>i</sub> y demandas d<sub>j</sub>.
- Validaciones con mensajes claros: valores numéricos, costos ≥ 0, ofertas y demandas ≥ 0, sin celdas vacías.
- Botones **"Cargar ejemplo del profesor (3x3)"**, **"Cargar ejemplo 4x5"** y **"Limpiar"**.
- Verificación de balance:
  - Oferta total = demanda total: balanceado.
  - Oferta > demanda: agregar un **destino ficticio** con costos 0 y demanda igual a la diferencia.
  - Demanda > oferta: agregar un **origen ficticio** con costos 0 y oferta igual a la diferencia.
  - Mostrar un aviso y la tabla ya balanceada, con las filas o columnas ficticias marcadas.

## 2. SELECTOR DE MÉTODO

Opciones: **Esquina noroeste | Costo mínimo | Vogel (VAM) | Comparar los tres**. Botón **"Resolver"**. Casilla **"Verificar con MODI"** (activa por defecto) y casilla **"Mejorar hasta el óptimo si no lo es"**.

## 3. ESPECIFICACIÓN DE LOS ALGORITMOS (siguiendo el material del profesor)

### 3.1 Esquina noroeste
Empieza en la celda (1,1), asigna min(oferta, demanda), ajusta ambas y avanza a la derecha si se satisfizo la demanda o hacia abajo si se agotó la oferta. No usa costos.

### 3.2 Costo mínimo
Elige la celda disponible de menor costo, asigna el mínimo, ajusta y elimina la fila o columna satisfecha. **Empate de costos:** se selecciona una de las rutas empatadas y se continúa con ella hasta agotar la oferta o satisfacer la demanda. Para que sea determinista, elegir la de menor fila y luego la de menor columna, y mostrar un mensaje cuando ocurra un empate.

### 3.3 Aproximación de Vogel (VAM)
- Penalización de cada fila y columna = diferencia entre sus dos menores costos disponibles.
- Se prioriza la fila o columna de mayor penalización y se asigna en su celda de menor costo.
- **Empate de penalizaciones:** escoger la fila o columna empatada cuya celda de menor costo tenga el valor más bajo; si persiste, elegir de forma consistente (fila antes que columna, y menor índice).
- Cuando solo queda una fila o una columna, completar las asignaciones restantes.
- Guardar las penalizaciones de cada iteración para mostrarlas.

### 3.4 Degeneración
Si en una asignación se agotan a la vez la oferta y la demanda (y no es la última), cerrar solo una de las dos y dejar la otra con una asignación de 0 como variable básica, de modo que siempre haya **m + n − 1** variables básicas. Avisar al usuario cuando ocurra.

## 4. SALIDAS DE CADA MÉTODO (mismo formato del PDF del profesor)

1. **Modelo matemático** generado automáticamente con los datos: variables x<sub>ij</sub>, función objetivo, restricciones de oferta y demanda, y no negatividad.
2. **Tabla paso a paso** con: paso, celda (Oi–Dj), cálculo "x<sub>ij</sub> = min(oferta, demanda) = q", oferta restante, demanda restante y observaciones (empates y penalizaciones). Un slider **"Ir al paso k"** para recorrer el proceso.
3. **Matriz final** con las celdas básicas sombreadas, el costo en la esquina de cada celda, y ofertas y demandas en los bordes.
4. **Costo total** con desglose: Z = q₁(c₁) + q₂(c₂) + ... = valor.
5. **Verificación de factibilidad:** sumas por fila y por columna, y número de variables básicas (m + n − 1).

## 5. MÉTODO MODI (verificación y mejora)

- Parte de la solución básica factible de cualquier método (por defecto la del método elegido).
- Fija **u₁ = 0** y resuelve u<sub>i</sub> + v<sub>j</sub> = c<sub>ij</sub> para las variables básicas, mostrando la tabla de ecuaciones en el orden en que se resuelven.
- Para cada variable no básica calcula **Δ<sub>ij</sub> = u<sub>i</sub> + v<sub>j</sub> − c<sub>ij</sub>** y muestra el cálculo, por ejemplo "0 + 2 − 6 = −4".
- **Criterio de optimalidad (minimización):** la solución es óptima si todos los Δ<sub>ij</sub> ≤ 0.
- Colores: Δ > 0 en rojo, Δ = 0 en ámbar (indica soluciones óptimas alternativas), Δ < 0 en verde.
- Dictamen automático: **"óptima única"** (todos < 0), **"óptima con soluciones alternativas"** (algún 0) o **"no óptima"**.
- Si no es óptima y la opción de mejorar está activa:
  - Entra la variable con mayor Δ positivo (desempate: menor fila, luego menor columna).
  - Se busca el ciclo cerrado alternando signos + y −.
  - θ = mínimo de las celdas con signo −.
  - Se actualiza la solución y se repite.
  - Mostrar en cada iteración: tabla, ciclo, θ, nuevo Z y reducción de costo.
  - Poner un límite de iteraciones y detectar ciclado.
- Resultado final: costo óptimo y plan óptimo de envíos.

## 6. APARTADO COMPARATIVO (pestaña "Resumen comparativo")

Disponible cuando el usuario elige **"Comparar los tres"**:

- **Tabla:** método | costo total Z | diferencia frente al mejor | % de ahorro | variables básicas | ¿óptima según MODI?
- **Fórmula del ahorro:** (Z_otro − Z_mejor) / Z_otro × 100, mostrando el cálculo.
- **Gráfico de barras** con los tres costos y las tres matrices en pestañas o lado a lado.
- **Selector "Verificar con MODI la solución de:"** [Esquina noroeste | Costo mínimo | Vogel | La de menor costo]. Al elegir una, mostrar todo el desarrollo de MODI de la sección 5.
- Botón **"Verificar las tres con MODI"** que muestre: método | Z inicial | iteraciones de MODI | Z óptimo | ¿ya era óptima?
- **Análisis automático en texto:** cuál fue mejor, cuánto ahorró y si coincide con el óptimo.
- **Nota fija:** "Estos porcentajes comparan soluciones iniciales; por sí solos no demuestran que un método sea superior en todos los problemas. La optimalidad debe demostrarse con MODI."
- **"Plan para la gerencia":** texto generado automáticamente en lenguaje natural, por ejemplo "La planta X envía q unidades al destino Y...", con el costo total y el ahorro frente a las otras soluciones.

## 7. INTERFAZ

Pestañas: **Datos | Modelo | Solución paso a paso | MODI | Resumen comparativo | Ayuda y teoría** (explicación breve de cada método, cuándo usarlo, ventajas y límites, con un ejemplo). Estilo limpio con azul institucional y tablas legibles. Botones para exportar el reporte completo a **PDF** y a **Excel**.

## 8. ARQUITECTURA

```
app.py                  # interfaz
core/
  models.py             # dataclasses Problem, Step, Solution
  balance.py
  northwest.py
  least_cost.py
  vogel.py
  modi.py
  report.py
tests/test_core.py
README.md
requirements.txt
```

Funciones puras y tipadas. Cada método devuelve `Solution(asignaciones, pasos, costo_total)`. Código comentado en español para poder sustentarlo.

## 9. CASOS DE PRUEBA DE ACEPTACIÓN (pytest, sin resultados hardcodeados en el código)

**Caso A (PDF del profesor):**
- Costos `[[4,6,8],[5,3,4],[6,4,7]]`, oferta `[20,30,25]`, demanda `[30,25,20]`.
- Esperado: esquina noroeste **350**, costo mínimo **340**, Vogel **310**.
- Vogel asigna x₁₁=20, x₂₂=10, x₂₃=20, x₃₁=10, x₃₂=15.
- MODI: u = (0, 1, 2), v = (4, 2, 3), Δ₁₂ = −4, Δ₁₃ = −5, Δ₂₁ = 0, Δ₃₃ = −2 → óptima con Z = 310 (el Δ = 0 indica una alternativa).

**Caso B (4x5):**
- Costos `[[18,31,37,38,85],[17,30,44,40,86],[17,26,37,45,90],[24,37,47,33,80]]`, oferta `[50,85,125,90]`, demanda `[35,40,115,125,35]`.
- Esperado: esquina noroeste **14285**, costo mínimo **13350**, Vogel **13230**.
- MODI sobre Vogel: u = (0, 2, 0, −5), v = (15, 26, 37, 38, 84), todos los Δ < 0 → óptimo único **Z = 13230**.

**Caso C:** problema no balanceado (oferta > demanda y viceversa) con fila o columna ficticia; el óptimo no debe cambiar.

**Caso D:** problema degenerado; no debe fallar y debe tener m + n − 1 variables básicas.

**Prueba aleatoria:** para 200 problemas aleatorios de hasta 6x6, el costo final de MODI debe coincidir con `scipy.optimize.linprog` (solo en los tests, nunca en la app).

## 10. CRITERIOS DE CALIDAD

- Funciona de 2x2 a 10x10 y no se rompe con datos inválidos.
- Cada paso es explicable.
- La salida se parece al formato del material del profesor (tablas por paso, cálculo del costo y comparación).

## ENTREGA

Primero propón la arquitectura y espera confirmación. Luego implementa el `core/` con sus pruebas, después la interfaz, ejecuta los tests y entrégame las instrucciones de ejecución y un README.
