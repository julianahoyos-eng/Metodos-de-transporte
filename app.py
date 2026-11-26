"""Interfaz del Solucionador del Método de Transporte."""

from decimal import Decimal, InvalidOperation
from fractions import Fraction
from html import escape
from math import isfinite
from sys import float_info

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.balance import balance
from core.models import Problem, Quantity, Solution, make_solution
from core.modi import Iteration, ModiResult, analyze
from core.report import excel_report, pdf_report
from core.results import (
    COMPARISON_HEADERS, COMPARISON_NOTE, COMPARE, EXAMPLES, METHODS, MODI_HEADERS,
    STATUS, STEP_HEADERS, balance_message, batch_records, best_method, comparison,
    cost_expression, delta_records, destination_labels, equation_records, feasibility, fmt,
    management, model, optimal, origin_labels, route, step_record,
)

st.set_page_config(page_title="Solucionador del Método de Transporte", layout="wide")


def display_table(headers, records) -> None:
    rows = [
        [fmt(value) if isinstance(value, Fraction) else value for value in row]
        for row in records
    ]
    st.dataframe(pd.DataFrame(rows, columns=headers), hide_index=True, width="stretch")


def matrix(problem: Problem, solution: Solution | None = None, pivot=None) -> None:
    origins, destinations = origin_labels(problem), destination_labels(problem)
    table = ['<div class="transport-matrix"><table><thead><tr><th scope="col">Origen</th>']
    for j, label in enumerate(destinations):
        css = ' class="dummy"' if j == problem.dummy_destination else ""
        table.append(f'<th scope="col"{css}>{escape(label)}</th>')
    table.append('<th scope="col">Oferta</th></tr></thead><tbody>')
    cycle = {} if pivot is None else {
        cell: "+" if k % 2 == 0 else "−" for k, cell in enumerate(pivot.cycle)
    }
    for i, label in enumerate(origins):
        row_class = ' class="dummy"' if i == problem.dummy_origin else ""
        table.append(f'<tr><th scope="row"{row_class}>{escape(label)}</th>')
        for j, value in enumerate(problem.costs[i]):
            cell = (i, j)
            classes = []
            if i == problem.dummy_origin or j == problem.dummy_destination:
                classes.append("dummy")
            content = fmt(value)
            if solution is not None:
                basic = cell in solution.basis
                if basic:
                    classes.append("basic")
                content = f'<span class="unit-cost" title="Costo unitario">{fmt(value)}</span>'
                amount = fmt(solution.assignments[i][j]) if basic or cell in cycle else "·"
                if cell in cycle:
                    sign = cycle[cell]
                    classes.append("plus" if sign == "+" else "minus")
                    content += f'<strong class="cycle-sign">{sign}</strong>'
                content += f'<span class="shipment">{amount}</span>'
            table.append(f'<td class="{" ".join(classes)}">{content}</td>')
        table.append(f'<th>{fmt(problem.supply[i])}</th></tr>')
    table.append('<tr><th scope="row">Demanda</th>')
    for value in problem.demand:
        table.append(f'<th>{fmt(value)}</th>')
    table.append(f'<th>{fmt(sum(problem.demand))}</th></tr></tbody></table></div>')
    st.html("".join(table))


def reset_input(example=None) -> None:
    state = st.session_state
    state["example"] = example
    state["size_rows"] = len(example[1]) if example else 3
    state["size_cols"] = len(example[2]) if example else 3
    state["input_version"] = state.get("input_version", 0) + 1
    state.pop("base_tables", None)
    state.pop("live_tables", None)
    state.pop("run", None)


def resize_input() -> None:
    state = st.session_state
    state["input_version"] += 1
    state["base_tables"] = state.get("live_tables")


def base_tables(m: int, n: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    origins = [f"O{i + 1}" for i in range(m)]
    destinations = [f"D{j + 1}" for j in range(n)]
    costs = pd.DataFrame("", index=origins, columns=destinations)
    supply = pd.DataFrame({"Nombre": [""] * m, "Oferta": [""] * m}, index=origins)
    demand = pd.DataFrame({"Nombre": [""] * n, "Demanda": [""] * n}, index=destinations)
    previous = st.session_state.get("base_tables")
    example = st.session_state.get("example")
    if previous is not None:
        return tuple(
            old.reindex(index=new.index, columns=new.columns, fill_value="")
            for old, new in zip(previous, (costs, supply, demand))
        )
    if example:
        c, s, d = example
        costs.iloc[:, :] = [[str(value) for value in row] for row in c]
        supply["Oferta"] = list(map(str, s))
        demand["Demanda"] = list(map(str, d))
    return costs, supply, demand


def read_number(value: str, label: str) -> Quantity:
    raw = "" if value is None else str(value).strip().replace(",", ".")
    if not raw:
        raise ValueError(f"{label} está vacío.")
    try:
        decimal = Decimal(raw)
        numeric = float(decimal)
        if not isfinite(numeric) or (numeric == 0 and decimal != 0):
            raise ValueError
        quantity = Fraction(decimal) if numeric else Fraction(0)
    except (InvalidOperation, ValueError, OverflowError) as error:
        raise ValueError(f"{label} debe ser un número finito no negativo.") from error
    if quantity < 0:
        raise ValueError(f"{label} debe ser no negativo.")
    return quantity


def data_panel() -> tuple[Problem | None, str, bool, bool, bool]:
    if "size_rows" not in st.session_state:
        reset_input(next(iter(EXAMPLES.values())))
    buttons = st.columns([2, 2, 1])
    for column, (label, example) in zip(buttons, EXAMPLES.items()):
        column.button(label, on_click=reset_input, args=(example,))
    buttons[-1].button("Limpiar", on_click=reset_input)
    sizes = st.columns(2)
    m = sizes[0].number_input("Cantidad de orígenes", 2, 10, key="size_rows", on_change=resize_input)
    n = sizes[1].number_input("Cantidad de destinos", 2, 10, key="size_cols", on_change=resize_input)
    c_base, s_base, d_base = base_tables(m, n)
    version = st.session_state["input_version"]
    st.subheader("Costos unitarios")
    st.caption("Usa punto o coma decimal. Los nombres de orígenes y destinos son opcionales.")
    costs = st.data_editor(
        c_base, key=f"costs_{version}", width="stretch",
        column_config={"_index": st.column_config.TextColumn("Origen")},
    )
    left, right = st.columns(2)
    with left:
        st.subheader("Ofertas")
        supply = st.data_editor(
            s_base, key=f"supply_{version}", width="stretch",
            column_config={"_index": st.column_config.TextColumn("Origen")},
        )
    with right:
        st.subheader("Demandas")
        demand = st.data_editor(
            d_base, key=f"demand_{version}", width="stretch",
            column_config={"_index": st.column_config.TextColumn("Destino")},
        )
    st.session_state["live_tables"] = costs, supply, demand

    problem = None
    try:
        problem = Problem(
            tuple(tuple(
                read_number(costs.iat[i, j], f"El costo O{i + 1}–D{j + 1}") for j in range(n)
            ) for i in range(m)),
            tuple(read_number(value, f"La oferta O{i + 1}") for i, value in enumerate(supply["Oferta"])),
            tuple(read_number(value, f"La demanda D{j + 1}") for j, value in enumerate(demand["Demanda"])),
            tuple(str(name or "") for name in supply["Nombre"]),
            tuple(str(name or "") for name in demand["Nombre"]),
        )
    except ValueError as error:
        st.warning(str(error))

    if problem is not None:
        balanced = balance(problem)
        st.subheader("Balance del problema")
        if balanced == problem:
            st.success(balance_message(balanced))
        else:
            st.info(balance_message(balanced))
        matrix(balanced)

    st.subheader("Método de solución")
    method = st.selectbox("Método", (*METHODS, COMPARE))
    options = st.columns(2)
    verify = options[0].checkbox("Verificar con MODI", value=True)
    improve = options[1].checkbox("Mejorar hasta el óptimo si no lo es", disabled=not verify)
    solve = st.button("Resolver", type="primary", disabled=problem is None)
    return problem, method, verify, improve and verify, solve


def model_panel(problem: Problem) -> None:
    st.subheader("Modelo matemático")
    st.write("Cada variable representa la cantidad enviada por una ruta Oᵢ–Dⱼ.")
    objective, supply, demand = model(problem, latex=True)
    lines = [" + ".join(objective[i:i + 5]) for i in range(0, len(objective), 5)]
    st.latex(r"\begin{aligned}\min\; Z &= " + r"\\ &\quad + ".join(lines) + r"\end{aligned}")
    for label, rows in (("Restricciones de oferta", supply), ("Restricciones de demanda", demand)):
        st.markdown(f"**{label}**")
        st.latex(r"\begin{gathered}" + r"\\".join(rows) + r"\end{gathered}")
    st.markdown("**No negatividad**")
    m, n = problem.shape
    st.latex(rf"x_{{i,j}} \ge 0,\qquad i=1,\ldots,{m},\quad j=1,\ldots,{n}")


def solution_panel(problem: Problem, name: str, solution: Solution) -> None:
    procedure, summary = st.tabs(("Procedimiento", "Resumen"))
    with procedure:
        records = [step_record(k, step) for k, step in enumerate(solution.steps, 1)]
        selected = (
            st.slider("Ir al paso k", 1, len(records), key=f"step::{name}")
            if len(records) > 1 else 1
        )
        st.markdown(f"**Paso {selected} de {len(records)}**")
        step = records[selected - 1]
        st.write(step[2])
        st.write(f"Oferta restante: {step[3]}  ·  Demanda restante: {step[4]}")
        if step[5] != "—":
            st.info(step[5])
        if step[6] != "—":
            st.write(f"Penalizaciones: {step[6]}")
        if selected < len(records):
            m, n = problem.shape
            amounts = [[Fraction(0) for _ in range(n)] for _ in range(m)]
            visited = set()
            for item in solution.steps[:selected]:
                i, j = item.cell
                visited.add(item.cell)
                amounts[i][j] = item.quantity
            with st.expander(f"Matriz al paso {selected}", expanded=True):
                matrix(problem, make_solution(problem, amounts, (), visited))
        display_table(STEP_HEADERS, records)
        st.subheader("Matriz de asignaciones")
        st.caption("Las celdas azules son básicas. En la esquina se indica el costo unitario.")
        matrix(problem, solution)
        st.metric("Costo total inicial (Z)", fmt(solution.total_cost))
        st.write(cost_expression(problem, solution))
        rows, columns, valid = feasibility(problem, solution)
        st.subheader("Verificación de factibilidad")
        left, right = st.columns(2)
        with left:
            display_table(("Origen", "Suma de envíos", "Oferta"), rows)
        with right:
            display_table(("Destino", "Suma recibida", "Demanda"), columns)
        m, n = problem.shape
        notify = st.success if valid else st.error
        notify(f"{len(solution.basis)} variables básicas de {m} + {n} − 1 = {m + n - 1} requeridas.")

    with summary:
        st.subheader("Mercancía recibida por destino")
        origins, destinations = origin_labels(problem), destination_labels(problem)
        shipments = []
        for j, destination in enumerate(destinations):
            for i, origin in enumerate(origins):
                quantity = solution.assignments[i][j]
                if quantity > 0:
                    source = origin
                    if i == problem.dummy_origin:
                        source += " (origen ficticio: demanda no cubierta)"
                    if j == problem.dummy_destination:
                        destination_label = destination + " (destino ficticio: oferta no despachada)"
                    else:
                        destination_label = destination
                    shipments.append((
                        destination_label, source, fmt(quantity), fmt(problem.demand[j]),
                    ))
        if shipments:
            display_table(
                ("Destino", "Origen de procedencia", "Unidades", "Demanda del destino"),
                shipments,
            )
        else:
            st.info("El plan no contiene envíos positivos.")

        if problem.dummy_origin is not None:
            st.info("Los envíos desde el origen ficticio representan demanda que no puede cubrirse "
                    "con la oferta disponible.")
        if problem.dummy_destination is not None:
            st.info("Los envíos al destino ficticio representan oferta excedente que queda sin despachar.")

        _, _, valid = feasibility(problem, solution)
        st.subheader("Conclusiones")
        if valid:
            st.write("La asignación satisface las ofertas y demandas del modelo balanceado.")
        else:
            st.warning("La asignación no satisface todas las condiciones de factibilidad.")
        st.write(f"El costo total de esta solución de {name} es Z = {fmt(solution.total_cost)}.")
        st.write("Este es el costo del plan inicial; consulta la pestaña MODI para verificar "
                 "si es óptimo o si puede mejorarse.")


def iteration_panel(problem: Problem, iteration: Iteration) -> None:
    st.write("Cálculo de potenciales a partir de u₁ = 0.")
    display_table(("Orden", "Ruta básica", "Ecuación", "Potencial obtenido"),
                  equation_records(problem, iteration))
    st.write(f"u = ({', '.join(map(fmt, iteration.u))})")
    st.write(f"v = ({', '.join(map(fmt, iteration.v))})")
    deltas = pd.DataFrame(
        [(label, calculation, fmt(value), "Mejora posible" if value > 0 else
          "Costo reducido cero" if value == 0 else "Sin mejora")
         for label, calculation, value in delta_records(problem, iteration)],
        columns=("Ruta no básica", "Cálculo", "Δ", "Interpretación"),
    )

    def color(value: str) -> str:
        delta = Fraction(value)
        if delta > 0:
            return "background-color: #FDE8E7; color: #942625"
        if delta == 0:
            return "background-color: #FFF3CD; color: #754B00"
        return "background-color: #E0F3E9; color: #195B39"

    st.dataframe(deltas.style.map(color, subset=["Δ"]), hide_index=True, width="stretch")
    st.latex(r"\Delta_{ij}=u_i+v_j-c_{ij},\qquad\text{criterio de optimalidad: }\Delta_{ij}\le 0")
    pivot = iteration.pivot
    if pivot:
        st.markdown("**Ciclo de mejora**")
        sequence = " → ".join(
            f"{'+' if k % 2 == 0 else '−'} {route(cell)}" for k, cell in enumerate(pivot.cycle)
        )
        st.write(sequence)
        st.write(f"Entra {route(pivot.entering)} y sale {route(pivot.leaving)}.")
        minus = ", ".join(fmt(iteration.solution.assignments[i][j]) for i, j in pivot.cycle[1::2])
        st.write(f"θ = min({minus}) = {fmt(pivot.theta)}.")
        st.write(f"Nuevo Z = {fmt(pivot.new_cost)}. Reducción de costo = {fmt(pivot.reduction)}.")
        if pivot.bland:
            st.info("Se aplica la regla de Bland para evitar que se repita una base.")
        if pivot.theta == 0:
            st.info("Pivote degenerado. Cambia la base con la misma cantidad de envíos.")
    matrix(problem, iteration.solution, pivot)


def modi_panel(problem: Problem, result: ModiResult, context: str) -> None:
    if optimal(result):
        st.success(STATUS[result.status])
    else:
        st.warning(STATUS[result.status])
    if result.status == "unique" and any(delta == 0 for delta in result.iterations[-1].deltas.values()):
        st.caption("Los costos reducidos cero no admiten un ajuste positivo del plan de envíos.")
    index = 0
    if result.pivots:
        index = st.slider(
            "Iteración de MODI", 0, result.pivots, key=f"modi::{context}",
            help="La iteración 0 corresponde a la solución inicial.",
        )
    st.markdown(f"**Iteración {index} de {result.pivots}**")
    iteration_panel(problem, result.iterations[index])
    if result.pivots or optimal(result):
        st.subheader("Plan óptimo de envíos" if optimal(result) else "Último plan factible")
        st.metric("Costo óptimo" if optimal(result) else "Costo del último plan",
                  fmt(result.solution.total_cost))
        matrix(problem, result.solution)
        st.write(cost_expression(problem, result.solution))


def comparison_panel(problem: Problem, solutions: dict, checks: dict, batch: dict) -> None:
    st.subheader("Costos de las soluciones iniciales")
    rows, formulas, narrative = comparison(solutions, checks | batch)
    display_table(COMPARISON_HEADERS, rows)
    costs = [item.total_cost for item in solutions.values()]
    max_cost = max(costs)
    as_ratio = max_cost > float_info.max or 0 < max_cost < float_info.min
    figure = go.Figure(go.Bar(
        x=list(solutions), y=[float(cost / max_cost if as_ratio else cost) for cost in costs],
        text=[fmt(cost) for cost in costs], textposition="outside",
        hovertemplate="%{x}<br>Z = %{text}<extra></extra>",
        marker_color=["#6B94C3", "#447BB7", "#1858A3"],
    ))
    figure.update_layout(yaxis_title="Proporción del costo mayor" if as_ratio else "Costo total Z",
                         yaxis_rangemode="tozero", height=330,
                         margin=dict(l=10, r=15, t=30, b=10))
    st.plotly_chart(figure, width="stretch")
    with st.expander("Cálculo del porcentaje de ahorro"):
        display_table(("Método", "Cálculo"), formulas)
    matrices = st.tabs(list(solutions))
    for tab, (name, solution) in zip(matrices, solutions.items()):
        with tab:
            matrix(problem, solution)
    st.write(narrative)
    st.caption(COMPARISON_NOTE)
    st.subheader("Plan para la gerencia")
    for line in management(problem, solutions):
        st.text(line)

    st.subheader("Verificación con MODI")
    selected = st.selectbox("Verificar con MODI la solución de:",
                            ("La de menor costo", *solutions))
    name = best_method(solutions) if selected == "La de menor costo" else selected
    if batch:
        display_table(MODI_HEADERS, batch_records(solutions, batch))
    result = batch.get(name) or checks.get(name)
    if result is not None:
        st.markdown(f"**{name}**")
        modi_panel(problem, result, f"comparar::{name}::{bool(batch)}")
    else:
        st.info("Activa «Verificar con MODI» al resolver o verifica los tres métodos desde esta pestaña.")


def help_panel() -> None:
    st.subheader("Ayuda y teoría")
    st.write("El problema de transporte asigna envíos de varios orígenes a varios destinos "
             "para satisfacer la demanda con el menor costo total.")
    display_table(
        ("Método", "Cuándo usarlo y qué hace", "Límite"),
        [
            ("Esquina noroeste", "Construye rápidamente un plan factible desde la primera celda.",
             "Puede elegir rutas costosas porque ignora los costos."),
            ("Costo mínimo", "Prioriza las rutas disponibles de menor costo unitario.",
             "Una elección barata puede obligar a usar rutas caras más adelante."),
            ("Vogel (VAM)", "Prioriza la fila o columna que más pierde al dejar pasar su ruta más barata.",
             "Suele producir un buen plan inicial y requiere recalcular penalizaciones."),
            ("MODI", "Comprueba la optimalidad de una base y mejora el plan mediante ciclos.",
             "Requiere una base conexa con m + n − 1 rutas."),
        ],
    )
    st.markdown("**Ejemplo 3×3**")
    st.write("Carga el ejemplo del profesor y selecciona «Comparar los tres». "
             "Los costos iniciales son 350, 340 y 310. MODI certifica el óptimo de 310 "
             "y detecta que se puede redistribuir el envío entre rutas de igual costo total.")
    st.markdown("**Rutas ficticias y degeneración**")
    st.write("Un destino ficticio identifica oferta sobrante. Un origen ficticio identifica demanda "
             "sin cubrir. Una ruta básica de valor cero conecta la base sin generar un envío.")


@st.cache_data(show_spinner=False, max_entries=6)
def reports(problem: Problem, solutions: dict, checks: dict, batch: dict) -> tuple[bytes, bytes]:
    return pdf_report(problem, solutions, checks, batch), excel_report(problem, solutions, checks, batch)


def main() -> None:
    st.html("""
    <style>
    .transport-matrix { overflow-x: auto; margin: .35rem 0 .9rem; }
    .transport-matrix table { border-collapse: collapse; width: 100%; font-size: .9rem; }
    .transport-matrix th, .transport-matrix td { border: 1px solid #cfdaea; text-align: center;
      padding: .55rem .65rem; position: relative; min-width: 4.2rem; }
    .transport-matrix th { background: #eff5fc; color: #183c64; font-weight: 650; }
    .transport-matrix th:first-child { text-align: left; min-width: 6rem; overflow-wrap: anywhere; }
    .transport-matrix .dummy { background: #fff3da; }
    .transport-matrix .basic { background: #deedff; }
    .transport-matrix .dummy.basic { background: #f3eddc; box-shadow: inset 0 0 0 2px #aac8eb; }
    .transport-matrix .unit-cost { font-size: .65rem; color: #3d5674; position: absolute;
      right: .25rem; top: .12rem; }
    .transport-matrix .shipment { display: inline-block; padding-top: .45rem; font-weight: 700; }
    .transport-matrix .plus { background: #dcf3e7; }
    .transport-matrix .minus { background: #fce6e6; }
    .transport-matrix .cycle-sign { position: absolute; left: .23rem; top: .12rem; }
    </style>
    """)
    st.title("Solucionador del Método de Transporte")
    st.caption("Programación Lineal · Universidad de Córdoba")
    data, model_tab, steps, modi, compare, help_tab = st.tabs(
        ("Datos", "Modelo", "Solución paso a paso", "MODI", "Resumen comparativo", "Ayuda y teoría")
    )
    with data:
        raw, method, verify, improve, solve = data_panel()

    signature = (raw, method, verify, improve)
    stored = st.session_state.get("run")
    if stored is not None and stored["signature"] != signature:
        st.session_state.pop("run")
        stored = None
    if solve and raw is not None:
        problem = balance(raw)
        names = METHODS if method == COMPARE else (method,)
        solutions = {name: METHODS[name](problem) for name in names}
        checks = {name: analyze(problem, plan, improve) for name, plan in solutions.items()} if verify else {}
        stored = {"signature": signature, "problem": problem, "solutions": solutions,
                  "checks": checks, "batch": {}, "serial": st.session_state.get("serial", 0) + 1}
        st.session_state["serial"] = stored["serial"]
        st.session_state["run"] = stored
        with data:
            st.success("Solución lista. Abre «Solución paso a paso» para ver el procedimiento.")

    if stored:
        problem, solutions, checks = (stored[key] for key in ("problem", "solutions", "checks"))
        with compare:
            if method == COMPARE and st.button(
                "Verificar las tres con MODI", help="Mejora cada solución hasta certificar el óptimo."
            ):
                stored["batch"] = {
                    name: checks[name] if name in checks and optimal(checks[name])
                    else analyze(problem, plan, improve=True)
                    for name, plan in solutions.items()
                }
        batch = stored["batch"]
        with model_tab:
            model_panel(problem)
        with steps:
            if len(solutions) > 1:
                step_name = st.selectbox("Método inicial", list(solutions))
            else:
                step_name = next(iter(solutions))
                st.subheader(step_name)
            solution_panel(problem, f'{stored["serial"]}::{step_name}', solutions[step_name])
        with modi:
            name = best_method(solutions)
            result = batch.get(name) or checks.get(name)
            if result is None:
                st.info("Activa «Verificar con MODI» en Datos y vuelve a resolver.")
            else:
                st.subheader(name)
                if len(solutions) > 1:
                    st.caption("Selecciona otro método desde «Resumen comparativo».")
                modi_panel(problem, result, f'principal::{stored["serial"]}::{bool(batch)}')
        with compare:
            if len(solutions) > 1:
                comparison_panel(problem, solutions, checks, batch)
            else:
                st.info("Selecciona «Comparar los tres» en Datos y resuelve el problema.")
        st.subheader("Reportes")
        pdf, excel = reports(problem, solutions, checks, batch)
        left, right = st.columns(2)
        left.download_button("Exportar PDF", pdf, "reporte_transporte.pdf", "application/pdf")
        right.download_button(
            "Exportar Excel", excel, "reporte_transporte.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        for panel in (model_tab, steps, modi, compare):
            with panel:
                st.info("Completa los datos y pulsa «Resolver».")
    with help_tab:
        help_panel()


main()
