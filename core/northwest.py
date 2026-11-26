"""Método de esquina noroeste."""

from .initial import Choice, build
from .models import Problem, Solution


def _select(problem: Problem, rows: list[int], columns: list[int]) -> Choice:
    return (rows[0], columns[0]), "", (), ()


def solve(problem: Problem) -> Solution:
    return build(problem, _select)
