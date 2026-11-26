"""Método de aproximación de Vogel, con registro de penalizaciones."""

from .initial import Choice, build
from .models import Cell, Problem, Quantity, Solution


def _select(problem: Problem, rows: list[int], columns: list[int]) -> Choice:
    if len(rows) == 1 or len(columns) == 1:
        return (rows[0], columns[0]), "Se completa la fila o columna restante.", (), ()

    def candidate(cells: list[Cell]) -> tuple[Quantity, Quantity, Cell]:
        ordered = sorted((problem.costs[i][j], (i, j)) for i, j in cells)
        (cost, cell), (second, _) = ordered[:2]
        return second - cost, cost, cell

    row_options = [(i, candidate([(i, j) for j in columns])) for i in rows]
    column_options = [(j, candidate([(i, j) for i in rows])) for j in columns]
    options = [
        (-penalty, cost, axis, index, cell)
        for axis, entries in enumerate((row_options, column_options))
        for index, (penalty, cost, cell) in entries
    ]
    best_penalty, best_cost, axis, index, cell = min(options)
    group = f"fila O{index + 1}" if axis == 0 else f"columna D{index + 1}"
    observation = f"Penalización mayor en la {group}."
    if sum(option[0] == best_penalty for option in options) > 1:
        observation = f"Empate de penalizaciones. Se elige la {group} por menor costo."
        if sum(option[:2] == (best_penalty, best_cost) for option in options) > 1:
            observation += " Persiste el empate y se aplica prioridad de fila y menor índice."
    i, j = cell
    available = [problem.costs[i][col] for col in columns] if axis == 0 else [
        problem.costs[row][j] for row in rows
    ]
    if available.count(best_cost) > 1:
        observation += " Empate de rutas dentro de la línea, resuelto por menor índice."
    return (
        cell, observation, tuple((i, p) for i, (p, _, _) in row_options),
        tuple((j, p) for j, (p, _, _) in column_options),
    )


def solve(problem: Problem) -> Solution:
    return build(problem, _select)
