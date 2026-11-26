"""Compensa la diferencia entre oferta y demanda con una ruta de costo cero."""

from dataclasses import replace

from .models import Problem


def balance(problem: Problem) -> Problem:
    difference = sum(problem.supply) - sum(problem.demand)
    m, n = problem.shape
    if difference > 0:
        return replace(
            problem, costs=tuple(row + (0,) for row in problem.costs),
            demand=problem.demand + (difference,), dummy_destination=n,
            destinations=problem.destinations + ("Destino ficticio",),
        )
    if difference < 0:
        return replace(
            problem, costs=problem.costs + ((0,) * n,),
            supply=problem.supply + (-difference,), dummy_origin=m,
            origins=problem.origins + ("Origen ficticio",),
        )
    return problem
