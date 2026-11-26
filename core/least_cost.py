"""Método de costo mínimo, con desempate por fila y columna."""

from .initial import Choice, build
from .models import Problem, Solution


def _select(problem: Problem, rows: list[int], columns: list[int]) -> Choice:
    cheapest = min(problem.costs[i][j] for i in rows for j in columns)
    tied = [(i, j) for i in rows for j in columns if problem.costs[i][j] == cheapest]
    observation = ""
    if len(tied) > 1:
        routes = ", ".join(f"O{i + 1}–D{j + 1}" for i, j in tied)
        observation = f"Empate de costo entre {routes}. Se elige la primera por fila y columna."
    return tied[0], observation, (), ()


def solve(problem: Problem) -> Solution:
    return build(problem, _select)
