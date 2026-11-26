"""Verificación y mejora mediante el símplex de transporte (MODI)."""

from collections import deque
from dataclasses import dataclass, replace
from fractions import Fraction

from .models import Cell, Problem, Quantity, Solution, make_solution


@dataclass(frozen=True)
class Pivot:
    entering: Cell
    leaving: Cell
    cycle: tuple[Cell, ...]
    theta: Quantity
    new_cost: Quantity
    reduction: Quantity
    bland: bool


@dataclass(frozen=True)
class Iteration:
    solution: Solution
    u: tuple[Quantity, ...]
    v: tuple[Quantity, ...]
    equations: tuple[tuple[Cell, str, Quantity, Quantity], ...]
    deltas: dict[Cell, Quantity]
    pivot: Pivot | None = None


@dataclass(frozen=True)
class ModiResult:
    solution: Solution
    status: str
    iterations: tuple[Iteration, ...]

    @property
    def pivots(self) -> int:
        return len(self.iterations) - 1


def _path(graph: list[list[int]], start: int, end: int) -> tuple[int, ...]:
    pending = deque([start])
    parents = {start: start}
    while pending and end not in parents:
        node = pending.popleft()
        for neighbor in graph[node]:
            if neighbor not in parents:
                parents[neighbor] = node
                pending.append(neighbor)
    if end not in parents:
        return ()
    path = [end]
    while path[-1] != start:
        path.append(parents[path[-1]])
    return tuple(reversed(path))


def _evaluate(problem: Problem, solution: Solution) -> tuple[Iteration, list[list[int]]]:
    m, n = problem.shape
    graph: list[list[int]] = [[] for _ in range(m + n)]
    if len(solution.basis) != m + n - 1:
        raise ValueError("MODI requiere m + n − 1 rutas básicas.")
    for i, j in sorted(solution.basis):
        graph[i].append(m + j)
        graph[m + j].append(i)

    potentials = {0: Fraction(0)}
    equations = []
    pending = deque([0])
    while pending:
        node = pending.popleft()
        for neighbor in graph[node]:
            if neighbor in potentials:
                continue
            if node < m:
                i, j = node, neighbor - m
                variable = f"v{j + 1}"
            else:
                i, j = neighbor, node - m
                variable = f"u{i + 1}"
            value = problem.costs[i][j] - potentials[node]
            potentials[neighbor] = value
            equations.append(((i, j), variable, potentials[node], value))
            pending.append(neighbor)
    if len(potentials) != m + n:
        raise ValueError("MODI requiere que la base forme un árbol conexo.")

    u = tuple(potentials[i] for i in range(m))
    v = tuple(potentials[m + j] for j in range(n))
    deltas = {
        (i, j): u[i] + v[j] - problem.costs[i][j]
        for i in range(m) for j in range(n) if (i, j) not in solution.basis
    }
    return Iteration(solution, u, v, tuple(equations), deltas), graph


def _has_alternative(problem: Problem, snapshot: Iteration) -> bool:
    # Un ciclo de costo cero permite aumentar y reducir flujos sin cambiar Z.
    # Solo se puede reducir una ruta si actualmente transporta una cantidad positiva.
    m, n = problem.shape
    residual: list[list[int]] = [[] for _ in range(m + n)]
    zero_routes = [cell for cell, delta in snapshot.deltas.items() if delta == 0]
    for i, j in (*snapshot.solution.basis, *zero_routes):
        residual[i].append(m + j)
        if snapshot.solution.assignments[i][j] > 0:
            residual[m + j].append(i)
    return any(_path(residual, m + j, i) for i, j in zero_routes)


def analyze(
    problem: Problem, solution: Solution, improve: bool = False, max_iterations: int = 1000
) -> ModiResult:
    if max_iterations < 0:
        raise ValueError("El límite de iteraciones no puede ser negativo.")
    iterations: list[Iteration] = []
    visited: set[frozenset[Cell]] = set()
    bland = False

    while True:
        snapshot, graph = _evaluate(problem, solution)
        iterations.append(snapshot)
        improving = [cell for cell, delta in snapshot.deltas.items() if delta > 0]
        if not improving:
            status = "alternate" if _has_alternative(problem, snapshot) else "unique"
            return ModiResult(solution, status, tuple(iterations))
        if not improve:
            return ModiResult(solution, "nonoptimal", tuple(iterations))
        if len(iterations) - 1 == max_iterations:
            return ModiResult(solution, "limit", tuple(iterations))
        if solution.basis in visited:
            if bland:
                return ModiResult(solution, "cycle", tuple(iterations))
            bland = True
            visited.clear()
        visited.add(solution.basis)

        # Mayor mejora por unidad. Si se repite una base, Bland evita nuevos ciclos.
        entering = min(improving) if bland else min(
            improving, key=lambda cell: (-snapshot.deltas[cell], cell)
        )
        i, j = entering
        m, _ = problem.shape
        path = _path(graph, m + j, i)
        cycle = (entering,) + tuple(
            (a, b - m) if a < m else (b, a - m) for a, b in zip(path, path[1:])
        )
        minus = cycle[1::2]
        theta, leaving = min((solution.assignments[r][c], (r, c)) for r, c in minus)
        amounts = [list(row) for row in solution.assignments]
        for index, (r, c) in enumerate(cycle):
            amounts[r][c] += theta if index % 2 == 0 else -theta
        basis = (solution.basis | {entering}) - {leaving}
        next_solution = make_solution(problem, amounts, solution.steps, basis)
        pivot = Pivot(
            entering, leaving, cycle, theta, next_solution.total_cost,
            solution.total_cost - next_solution.total_cost, bland,
        )
        iterations[-1] = replace(snapshot, pivot=pivot)
        solution = next_solution
