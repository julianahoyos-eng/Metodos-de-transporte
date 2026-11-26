"""Presentación compartida de modelos, trazas y resultados."""

from decimal import Decimal, localcontext
from fractions import Fraction

from . import least_cost, northwest, vogel
from .models import Cell, Problem, Quantity, Solution, Step
from .modi import Iteration, ModiResult

METHODS = {
    "Esquina noroeste": northwest.solve,
    "Costo mínimo": least_cost.solve,
    "Vogel (VAM)": vogel.solve,
}
COMPARE = "Comparar los tres"
COMPARISON_NOTE = (
    "Estos porcentajes comparan soluciones iniciales; por sí solos no demuestran que "
    "un método sea superior en todos los problemas. La optimalidad debe demostrarse con MODI."
)
STATUS = {
    "unique": "Óptima única",
    "alternate": "Óptima con soluciones alternativas",
    "nonoptimal": "No óptima",
    "limit": "Límite de iteraciones. Optimalidad sin certificar.",
    "cycle": "Ciclado detectado. Optimalidad sin certificar.",
}
EXAMPLES = {
    "Cargar ejemplo del profesor (3x3)": (
        ((4, 6, 8), (5, 3, 4), (6, 4, 7)), (20, 30, 25), (30, 25, 20),
    ),
    "Cargar ejemplo 4x5": (
        ((18, 31, 37, 38, 85), (17, 30, 44, 40, 86), (17, 26, 37, 45, 90),
         (24, 37, 47, 33, 80)),
        (50, 85, 125, 90), (35, 40, 115, 125, 35),
    ),
}
STEP_HEADERS = (
    "Paso", "Ruta", "Cálculo", "Oferta restante", "Demanda restante",
    "Observaciones", "Penalizaciones",
)
COMPARISON_HEADERS = (
    "Método", "Costo total Z", "Diferencia frente al mejor", "% de ahorro", "Básicas",
    "¿Óptima según MODI?",
)
MODI_HEADERS = ("Método", "Z inicial", "Iteraciones de MODI", "Z óptimo", "¿Ya era óptima?")


def fmt(value: Quantity | int, places: int | None = None) -> str:
    fraction = Fraction(value)
    with localcontext() as context:
        context.prec = max(28, len(str(fraction.numerator)) + len(str(fraction.denominator)))
        decimal = Decimal(fraction.numerator) / Decimal(fraction.denominator)
        if places is not None:
            return f"{decimal:.{places}f}"
        text = format(decimal, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text


def route(cell: Cell) -> str:
    i, j = cell
    return f"O{i + 1}–D{j + 1}"


def variable(i: int, j: int, latex: bool = False) -> str:
    return f"x_{{{i + 1},{j + 1}}}" if latex else f"x[{i + 1},{j + 1}]"


def balance_message(problem: Problem) -> str:
    if problem.dummy_destination is not None:
        return (
            "La oferta supera la demanda. Se agregó un destino ficticio con demanda "
            f"{fmt(problem.demand[problem.dummy_destination])} y costo cero."
        )
    if problem.dummy_origin is not None:
        return (
            "La demanda supera la oferta. Se agregó un origen ficticio con oferta "
            f"{fmt(problem.supply[problem.dummy_origin])} y costo cero."
        )
    return "La oferta total es igual a la demanda total."


def origin_labels(problem: Problem) -> tuple[str, ...]:
    return tuple(
        f"O{i + 1} · {name}" if name != f"O{i + 1}" else name
        for i, name in enumerate(problem.origins)
    )


def destination_labels(problem: Problem) -> tuple[str, ...]:
    return tuple(
        f"D{j + 1} · {name}" if name != f"D{j + 1}" else name
        for j, name in enumerate(problem.destinations)
    )


def model(problem: Problem, latex: bool = False) -> tuple[list[str], list[str], list[str]]:
    m, n = problem.shape
    times = r"\," if latex else " · "
    objective = [
        f"{fmt(problem.costs[i][j])}{times}{variable(i, j, latex)}"
        for i in range(m) for j in range(n)
    ]
    supply = [
        " + ".join(variable(i, j, latex) for j in range(n)) + f" = {fmt(problem.supply[i])}"
        for i in range(m)
    ]
    demand = [
        " + ".join(variable(i, j, latex) for i in range(m)) + f" = {fmt(problem.demand[j])}"
        for j in range(n)
    ]
    return objective, supply, demand


def cost_expression(problem: Problem, solution: Solution) -> str:
    terms = [
        f"{fmt(quantity)}({fmt(problem.costs[i][j])})"
        for i, row in enumerate(solution.assignments) for j, quantity in enumerate(row)
        if quantity > 0
    ]
    return "Z = " + (" + ".join(terms) if terms else "0") + f" = {fmt(solution.total_cost)}"


def step_record(index: int, step: Step) -> tuple:
    i, j = step.cell
    calculation = (
        f"{variable(i, j)} = min({fmt(step.offer)}, {fmt(step.need)}) = {fmt(step.quantity)}"
    )
    penalties = [
        f"{axis}{i + 1} = {fmt(value)}"
        for axis, entries in (("O", step.row_penalties), ("D", step.column_penalties))
        for i, value in entries
    ]
    return (
        index, route(step.cell), calculation, ", ".join(map(fmt, step.supply_left)),
        ", ".join(map(fmt, step.demand_left)), step.observation or "—",
        ", ".join(penalties) or "—",
    )


def feasibility(problem: Problem, solution: Solution) -> tuple[list[tuple], list[tuple], bool]:
    columns = tuple(map(sum, zip(*solution.assignments)))
    rows = [
        (label, sum(row), target)
        for label, row, target in zip(origin_labels(problem), solution.assignments, problem.supply)
    ]
    cols = list(zip(destination_labels(problem), columns, problem.demand))
    m, n = problem.shape
    valid = (
        len(solution.basis) == m + n - 1 and all(actual == goal for _, actual, goal in rows + cols)
        and all(quantity >= 0 for row in solution.assignments for quantity in row)
    )
    return rows, cols, valid


def equation_records(problem: Problem, iteration: Iteration) -> list[tuple]:
    return [
        (order, route((i, j)), f"u{i + 1} + v{j + 1} = {fmt(problem.costs[i][j])}",
         f"{variable_name} = {fmt(problem.costs[i][j])} − ({fmt(known)}) = {fmt(value)}")
        for order, ((i, j), variable_name, known, value) in enumerate(iteration.equations, 1)
    ]


def delta_records(problem: Problem, iteration: Iteration) -> list[tuple]:
    return [
        (route((i, j)), f"{fmt(iteration.u[i])} + ({fmt(iteration.v[j])}) "
         f"− {fmt(problem.costs[i][j])} = {fmt(delta)}", delta)
        for (i, j), delta in iteration.deltas.items()
    ]


def optimal(result: ModiResult) -> bool:
    return result.status in ("unique", "alternate")


def best_method(solutions: dict[str, Solution]) -> str:
    return min(solutions, key=lambda name: solutions[name].total_cost)


def savings(cost: Quantity, best: Quantity) -> tuple[str, str]:
    if cost == 0:
        return "No aplica", "Costo de referencia igual a cero."
    percent = fmt((cost - best) * 100 / cost, 2)
    return f"{percent} %", f"({fmt(cost)} − {fmt(best)}) / {fmt(cost)} × 100 = {percent} %"


def comparison(
    solutions: dict[str, Solution], checks: dict[str, ModiResult],
) -> tuple[list[tuple], list[tuple], str]:
    best = solutions[best_method(solutions)].total_cost
    rows = []
    formulas = []
    winners = []
    verified = [result.solution.total_cost for result in checks.values() if optimal(result)]
    for name, solution in solutions.items():
        cost = solution.total_cost
        percent, formula = savings(cost, best)
        check = checks.get(name)
        initial = "Pendiente"
        if check is not None:
            initial = "No óptima" if any(delta > 0 for delta in check.iterations[0].deltas.values()) else (
                STATUS[check.status]
            )
        rows.append((name, cost, cost - best, percent, len(solution.basis), initial))
        formulas.append((name, formula))
        if cost == best:
            winners.append(name)
    methods = ", ".join(winners)
    if len(winners) == 1:
        analysis = f"{methods} obtuvo el menor costo inicial, con Z = {fmt(best)}."
    else:
        analysis = f"{methods} empataron en el menor costo inicial, con Z = {fmt(best)}."
    differences = [
        f"{fmt(cost - best)} frente a {name} ({percent})"
        for name, cost, _, percent, _, _ in rows if cost > best
    ]
    if differences:
        analysis += f" El ahorro fue de {' y de '.join(differences)}."
    if verified:
        if best == min(verified):
            analysis += " El menor costo inicial coincide con el óptimo verificado."
        else:
            analysis += f" MODI verificó un óptimo de {fmt(min(verified))}."
    else:
        analysis += " La coincidencia con el óptimo está pendiente de verificación."
    return rows, formulas, analysis


def batch_records(
    solutions: dict[str, Solution], results: dict[str, ModiResult],
) -> list[tuple]:
    return [
        (name, solutions[name].total_cost, result.pivots,
         result.solution.total_cost if optimal(result) else "Sin certificar",
         "Sí" if optimal(result) and result.pivots == 0 else "No")
        for name, result in results.items()
    ]


def management(problem: Problem, solutions: dict[str, Solution]) -> list[str]:
    name = best_method(solutions)
    plan = solutions[name]
    sentences = [f"Plan inicial de {name}. Costo total {fmt(plan.total_cost)}."]
    for i, row in enumerate(plan.assignments):
        for j, quantity in enumerate(row):
            if not quantity:
                continue
            if i == problem.dummy_origin:
                line = f"La demanda sin cubrir en {problem.destinations[j]} es de {fmt(quantity)} unidades."
            elif j == problem.dummy_destination:
                line = f"Quedan {fmt(quantity)} unidades sin despachar en {problem.origins[i]}."
            else:
                line = f"{problem.origins[i]} envía {fmt(quantity)} unidades a {problem.destinations[j]}."
            sentences.append(line)
    for other, candidate in solutions.items():
        if other != name:
            percent, _ = savings(candidate.total_cost, plan.total_cost)
            difference = fmt(candidate.total_cost - plan.total_cost)
            suffix = f" ({percent})" if percent != "No aplica" else ""
            sentences.append(f"Ahorro frente a {other}: {difference}{suffix}.")
    return sentences
