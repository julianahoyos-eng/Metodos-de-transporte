"""Construcción de planes iniciales y de su árbol de rutas básicas."""

from fractions import Fraction
from typing import Callable

from .models import Cell, Problem, Quantity, Solution, Step, make_solution

Penalties = tuple[tuple[int, Quantity], ...]
Choice = tuple[Cell, str, Penalties, Penalties]
Select = Callable[[Problem, list[int], list[int]], Choice]


def build(problem: Problem, select: Select) -> Solution:
    if sum(problem.supply) != sum(problem.demand):
        raise ValueError("Balancea la oferta y la demanda antes de resolver.")
    m, n = problem.shape
    zero = Fraction(0)
    supply, demand = list(problem.supply), list(problem.demand)
    assignments = [[zero for _ in range(n)] for _ in range(m)]
    steps: list[Step] = []
    basis: set[Cell] = set()
    components = list(range(m + n))

    def add(cell: Cell) -> bool:
        i, j = cell
        left, right = components[i], components[m + j]
        if left == right:
            return False
        components[:] = [left if value == right else value for value in components]
        basis.add(cell)
        return True

    rows = [i for i in range(m) if supply[i] > 0]
    columns = [j for j in range(n) if demand[j] > 0]
    while rows and columns:
        (i, j), observation, row_penalties, column_penalties = select(problem, rows, columns)
        offer, need = supply[i], demand[j]
        quantity = min(offer, need)
        assignments[i][j] = quantity
        supply[i] -= quantity
        demand[j] -= quantity
        add((i, j))
        if not supply[i]:
            rows.remove(i)
        if not demand[j]:
            columns.remove(j)
        if offer == need and rows and columns:
            observation = (
                f"{observation} Agotamiento simultáneo de oferta y demanda. "
                "Se registra una variable básica de valor cero."
            ).strip()
        steps.append(Step(
            (i, j), offer, need, quantity, tuple(supply), tuple(demand),
            observation, row_penalties, column_penalties,
        ))
        if offer == need and rows and columns:
            # Se mantiene temporalmente abierta la fila agotada para completar la base.
            for column in columns:
                if add((i, column)):
                    steps.append(Step(
                        (i, column), zero, demand[column], zero, tuple(supply), tuple(demand),
                        "Variable básica de valor cero por agotamiento simultáneo.",
                    ))
                    break

    # Las filas y columnas con cantidad inicial cero también deben conectarse.
    for i in range(m):
        for j in range(n):
            if add((i, j)):
                steps.append(Step(
                    (i, j), zero, zero, zero, tuple(supply), tuple(demand),
                    "Variable básica de valor cero para completar el árbol.",
                ))
    return make_solution(problem, assignments, tuple(steps), basis)
