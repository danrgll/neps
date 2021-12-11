import random
from typing import List, Union

import numpy as np

from .numerical import NumericalParameter


class CategoricalParameter(NumericalParameter):
    def __init__(self, choices: List[Union[float, int, str]]):
        super().__init__()
        self.choices = list(choices)
        self.num_choices = len(self.choices)
        self.probabilities = list(np.ones(self.num_choices) * (1.0 / self.num_choices))
        self.value = None

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return (
            self.name == other.name
            and self.choices == other.choices
            and self.value == other.value
        )

    def __hash__(self):
        return hash((self.name, tuple(self.choices), self.value))

    def __repr__(self):
        return f"Categorical, choices: {self.choices}, value: {self.value}"

    def __copy__(self):
        return self.__class__(choices=self.choices)

    def sample(self):
        idx = np.random.choice(a=self.num_choices, replace=True, p=self.probabilities)
        self.value = self.choices[int(idx)]

    def mutate(
        self,
        parent=None,
        mutation_rate: float = 1.0,  # pylint: disable=unused-argument
        mutation_strategy: str = "local_search",
    ):

        if parent is None:
            parent = self

        if mutation_strategy == "simple":
            child = self.__copy__()
            child.sample()
        elif mutation_strategy == "local_search":
            child = self._get_neighbours(num_neighbours=1)[0]
        else:
            raise NotImplementedError

        if parent.value == child.value:
            raise ValueError("Parent is the same as child!")

        return child

    def crossover(self, parent1, parent2=None):
        pass

    def _get_neighbours(self, num_neighbours: int = 1):
        neighbours = []

        idx = 0
        choices = self.choices.copy()
        random.shuffle(choices)

        while len(neighbours) < num_neighbours:
            if num_neighbours > self.num_choices - 1:
                choice = self.choices[np.random.randint(0, self.num_choices)]
            else:
                choice = choices[idx]
                idx += 1
            if choice == self.value:
                continue
            neighbour = self.__copy__()
            neighbour.value = choice
            neighbours.append(neighbour)

        return neighbours

    def _transform(self):
        self.value = self.choices.index(self.value) / self.num_choices

    def _inv_transform(self):
        self.value = self.choices[int(self.value * self.num_choices)]

    def create_from_id(self, identifier):
        self.value = identifier