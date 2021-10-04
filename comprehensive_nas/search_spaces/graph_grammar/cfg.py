import itertools
import sys
from collections import defaultdict, deque
from typing import Tuple

import numpy as np
from nltk import CFG
from nltk.grammar import Nonterminal


class Grammar(CFG):
    """
    Extended context free grammar (CFG) class from the NLTK python package
    We have provided functionality to sample from the CFG.
    We have included generation capability within the class (before it was an external function)
    Also allow sampling to return whole trees (not just the string of terminals)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # store some extra quantities needed later
        non_unique_nonterminals = [str(prod.lhs()) for prod in self.productions()]
        self.nonterminals = list(set(non_unique_nonterminals))
        self.terminals = list(
            {str(individual) for prod in self.productions() for individual in prod.rhs()}
            - set(self.nonterminals)
        )
        # collect nonterminals that are worth swapping when doing genetic operations (i.e not those with a single production that leads to a terminal)
        self.swappable_nonterminals = list(
            {i for i in non_unique_nonterminals if non_unique_nonterminals.count(i) > 1}
        )

        self.max_sampling_level = 2

        self.convergent = False
        self.depth_constrained = False
        self.depth_constraints: dict = None

        self.check_grammar()

    def set_depth_constraints(self, depth_constraints):
        self.depth_constraints = depth_constraints
        self.depth_constrained = True
        self.convergent = False

    def is_depth_constrained(self):
        return self.depth_constrained

    def set_convergent(self):
        self.depth_constraints = None
        self.depth_constrained = False
        self.convergent = True

    def set_unconstrained(self):
        self.depth_constraints = None
        self.depth_constrained = False
        self.convergent = False

    def check_grammar(self):
        if len(set(self.terminals).intersection(set(self.nonterminals))) > 0:
            raise Exception(
                f"Same terminal and nonterminal symbol: {set(self.terminals).intersection(set(self.nonterminals))}!"
            )
        for nt in self.nonterminals:
            if len(self.productions(Nonterminal(nt))) == 0:
                raise Exception(f"There is no production for nonterminal {nt}")

    def generator(self, n=1, depth=5):
        # return the first n strings generated by the CFG of a maximum depth
        sequences = []
        for sentence in self._generate(n=n, depth=depth):
            sequences.append(" ".join(sentence))
        return sequences

    def sampler_restricted(self, n, max_length=5, cfactor=0.1, min_length=0):
        # sample n unqiue sequences from the CFG
        # such that the number of terminals is between min_length and max_length
        # cfactor controls the avg length of sampled sequence (see self.sampler)
        # setting smaller cfactor can reduce number of samples required to find n of specified size

        # store in a dict fr quick look up when seeing if its a unique sample
        sequences_dict = {}
        sequences = [[]] * n
        i = 0
        while i < n:
            sample = self._convergent_sampler(symbol=self.start(), cfactor=cfactor)
            # split up words, depth and num productions
            tree = sample[0] + ")"
            # count number of terminals
            length = 0
            for t in self.terminals:
                length += tree.count(t + ")")
            # check satisfies depth restrictions
            if (length <= max_length) and (length >= min_length):
                # check not already in samples
                if tree not in sequences_dict:
                    sequences_dict[tree] = "true"
                    sequences[i] = tree
                    i += 1
        return sequences

    def sampler(
        self,
        n=1,
        cfactor=0.1,
        depth_information: dict = None,
        start_symbol: str = None,
    ):
        # sample n sequences from the CFG
        # convergent: avoids very long sequences (we advise setting True)
        # cfactor: the factor to downweight productions (cfactor=1 returns to naive sampling strategy)
        #          smaller cfactor provides smaller sequences (on average)

        # Note that a simple recursive traversal of the grammar (setting convergent=False) where we choose
        # productions at random, often hits Python's max recursion depth as the longer a sequnce gets, the
        # less likely it is to terminate. Therefore, we set the default sampler (setting convergent=True) to
        # downweight frequent productions when traversing the grammar.
        # see https://eli.thegreenplace.net/2010/01/28/generating-random-sentences-from-a-context-free-236grammar
        if self.convergent and self.depth_constrained:
            raise Exception(f"Sample cannot be convergent and depth constrained")

        if start_symbol is None:
            start_symbol = self.start()
        else:
            start_symbol = Nonterminal(start_symbol)

        if self.convergent:
            return [
                f"{self._convergent_sampler(symbol=start_symbol, cfactor=cfactor)[0]})"
                for i in range(0, n)
            ]
        elif self.depth_constrained:
            if self.depth_constraints is None:
                raise ValueError("Depth constraints are not set!")
            if depth_information is None:
                depth_information = {}
            return [
                f"{self._depth_constrained_sampler(symbol=start_symbol, depth_information=depth_information)})"
                for i in range(0, n)
            ]
        else:
            return [f"{self._sampler(symbol=start_symbol)})" for i in range(0, n)]

    def compute_depth_information_for_pre(self, tree: str) -> dict:
        depth_information = {nt: 0 for nt in self.nonterminals}
        q_nonterminals = deque()
        for split in tree.split(" "):
            if split == "":
                continue
            elif split[0] == "(":
                q_nonterminals.append(split[1:])
                depth_information[split[1:]] += 1
                continue
            while split[-1] == ")":
                nt = q_nonterminals.pop()
                depth_information[nt] -= 1
                split = split[:-1]
        return depth_information

    def compute_depth_information(self, tree: str) -> list:
        split_tree = tree.split(" ")
        depth_information = [0] * len(split_tree)
        helper_dict = {nt: 0 for nt in self.nonterminals}
        q_nonterminals = deque()
        for i, split in enumerate(split_tree):
            if split == "":
                continue
            elif split[0] == "(":
                q_nonterminals.append(split[1:])
                depth_information[i] = helper_dict[split[1:]] + 1
                helper_dict[split[1:]] += 1
                continue
            while split[-1] == ")":
                nt = q_nonterminals.pop()
                helper_dict[nt] -= 1
                split = split[:-1]
        return depth_information

    def _depth_constrained_sampler(self, symbol=None, depth_information: dict = None):
        if depth_information is None:
            depth_information = {}
        # init the sequence
        tree = "(" + str(symbol)
        # collect possible productions from the starting symbol & filter if constraints are violated
        lhs = str(symbol)
        if lhs in depth_information.keys():
            depth_information[lhs] += 1
        else:
            depth_information[lhs] = 1
        if (
            lhs in self.depth_constraints.keys()
            and depth_information[lhs] > self.depth_constraints[lhs]
        ):
            productions = [
                production
                for production in self.productions(lhs=symbol)
                if lhs
                not in [str(sym) for sym in production.rhs() if not isinstance(sym, str)]
            ]
        else:
            productions = self.productions(lhs=symbol)

        if len(productions) == 0:
            raise Exception(
                f"There can be no word sampled! This is due to the grammar and/or constraints."
            )

        # sample
        production = choice(productions)
        for sym in production.rhs():
            if isinstance(sym, str):
                # if terminal then add string to sequence
                tree = tree + " " + sym
            else:
                tree = (
                    tree
                    + " "
                    + self._depth_constrained_sampler(sym, depth_information)
                    + ")"
                )
        depth_information[lhs] -= 1
        return tree

    def _sampler(self, symbol=None):
        # simple sampler where each production is sampled uniformly from all possible productions
        # Tree choses if return tree or list of terminals
        # recursive implementation

        # init the sequence
        tree = "(" + str(symbol)
        # collect possible productions from the starting symbol
        productions = self.productions(lhs=symbol)
        # sample
        production = choice(productions)
        for sym in production.rhs():
            if isinstance(sym, str):
                # if terminal then add string to sequence
                tree = tree + " " + sym
            else:
                tree = tree + " " + self._sampler(sym) + ")"
        return tree

    def sampler_maxMin_func(self, symbol: str = None, largest: bool = True):
        tree = "(" + str(symbol)
        # collect possible productions from the starting symbol
        productions = self.productions(lhs=symbol)
        # sample
        production = productions[-1 if largest else 0]
        for sym in production.rhs():
            if isinstance(sym, str):
                # if terminal then add string to sequence
                tree = tree + " " + sym
            else:
                tree = tree + " " + self.sampler_maxMin_func(sym, largest=largest) + ")"
        return tree

    def _convergent_sampler(
        self, cfactor, symbol=None, pcount=defaultdict(int)
    ):  # pylint: disable=dangerous-default-value
        # sampler that down-weights the probability of selcting the same production many times
        # ensuring that the sampled trees are not 'too' long (size to be controlled by cfactor)
        #
        # recursive implementation
        #:pcount: storage for the productions used in the current branch

        # init the sequence
        tree = "(" + str(symbol)
        # init counter of tree depth and number of production rules
        depth, num_prod = 1, 1
        # collect possible productions from the starting symbol
        productions = self.productions(lhs=symbol)
        # init sampling weights
        weights = []
        # calc weights for the possible productions
        for prod in productions:
            if prod in pcount:
                # if production already occured in branch then downweight
                weights.append(cfactor ** (pcount[prod]))
            else:
                # otherwise set to be 1
                weights.append(1.0)
        # normalize weights to get probabilities
        norm = sum(weights)
        probs = [weight / norm for weight in weights]
        # sample
        production = choice(productions, probs)
        # update counts
        pcount[production] += 1
        depths = []
        for sym in production.rhs():
            if isinstance(sym, str):
                # if terminal then add string to sequence
                tree = tree + " " + sym
            else:
                # otherwise keep generating the sequence
                recursion = self._convergent_sampler(
                    symbol=sym, cfactor=cfactor, pcount=pcount
                )
                depths.append(recursion[1])
                num_prod += recursion[2]
                tree = tree + " " + recursion[0] + ")"
        # count the maximum depth and update

        if len(depths) > 0:
            depth = max(depths) + 1
        # update counts
        pcount[production] -= 1
        return tree, depth, num_prod

    def _generate(self, start=None, depth=None, n=None):
        """
        see https://www.nltk.org/_modules/nltk/parse/generate.html
        Generates an iterator of all sentences from a CFG.

        :param grammar: The Grammar used to generate sentences.
        :param start: The Nonterminal from which to start generate sentences.
        :param depth: The maximal depth of the generated tree.
        :param n: The maximum number of sentences to return.
        :return: An iterator of lists of terminal tokens.
        """
        if not start:
            start = self.start()
        if depth is None:
            depth = sys.maxsize

        iter_prod = self._generate_all([start], depth)

        if n:
            iter_prod = itertools.islice(iter_prod, n)

        return iter_prod

    def _generate_all(self, items, depth):
        # see https://www.nltk.org/_modules/nltk/parse/generate.html
        if items:
            try:
                for frag1 in self._generate_one(items[0], depth):
                    for frag2 in self._generate_all(items[1:], depth):
                        yield frag1 + frag2
            except RuntimeError as _error:
                if _error.message == "maximum recursion depth exceeded":
                    # Helpful error message while still showing the recursion stack.
                    raise RuntimeError(
                        "The grammar has rule(s) that yield infinite recursion!!"
                    )
                else:
                    raise
        else:
            yield []

    def _generate_one(self, item, depth):
        # see https://www.nltk.org/_modules/nltk/parse/generate.html
        if depth > 0:
            if isinstance(item, Nonterminal):
                for prod in self.productions(lhs=item):
                    for frag in self._generate_all(prod.rhs(), depth - 1):
                        yield frag
            else:
                yield [item]

    def rand_subtree(self, tree: str) -> Tuple[str, int]:
        # helper function to choose a random subtree in a given tree
        # returning the parent node of the subtree and its index
        # single pass through tree (stored as string) to look for the location of swappable_non_terminmals
        split_tree = tree.split(" ")
        swappable_indices = [
            i
            for i in range(0, len(split_tree))
            if split_tree[i][1:] in self.swappable_nonterminals
        ]
        # randomly choose one of these non-terminals to replace its subtree
        r = np.random.randint(1, len(swappable_indices))
        chosen_non_terminal = split_tree[swappable_indices[r]][1:]
        chosen_non_terminal_index = swappable_indices[r]
        # return chosen node and its index
        return chosen_non_terminal, chosen_non_terminal_index

    def rand_subtree_fixed_head(
        self, tree: str, head_node: str, head_node_depth_constraint: int = 0
    ) -> int:
        # helper function to choose a random subtree from a given tree with a specific head node
        # if no such subtree then return False, otherwise return the index of the subtree

        # single pass through tree (stored as string) to look for the location of swappable_non_terminmals
        split_tree = tree.split(" ")
        if self.is_depth_constrained():
            depth_information = self.compute_depth_information(tree)
            swappable_indicies = [
                i
                for i in range(0, len(split_tree))
                if split_tree[i][1:] == head_node
                and depth_information[i] >= head_node_depth_constraint
            ]
        else:
            swappable_indicies = [
                i for i in range(0, len(split_tree)) if split_tree[i][1:] == head_node
            ]
        if len(swappable_indicies) == 0:
            # no such subtree
            return False
        else:
            # randomly choose one of these non-terminals
            r = (
                np.random.randint(1, len(swappable_indicies))
                if len(swappable_indicies) > 1
                else 0
            )
            chosen_non_terminal_index = swappable_indicies[r]
            return chosen_non_terminal_index

    @staticmethod
    def remove_subtree(tree, index) -> Tuple[str, str, str]:
        # helper function to remove a subtree from a tree (given its index)
        # returning the str before and after the subtree
        # i.e '(S (S (T 2)) (ADD +) (T 1))'
        # becomes '(S (S (T 2)) ', '(T 1))'  after removing (ADD +)

        split_tree = tree.split(" ")
        pre_subtree = " ".join(split_tree[:index]) + " "
        #  get chars to the right of split
        right = " ".join(split_tree[index + 1 :])
        # remove chosen subtree
        # single pass to find the bracket matching the start of the split
        counter, current_index = 1, 0
        for char in right:
            if char == "(":
                counter += 1
            elif char == ")":
                counter -= 1
            if counter == 0:
                break
            current_index += 1
        # retrun string after remover tree
        post_subtree = right[current_index + 1 :]
        # get removed tree
        removed = "".join(split_tree[index]) + " " + right[: current_index + 1]
        return (pre_subtree, removed, post_subtree)


# helper function for quickly getting a single sample from multinomial with probs
def choice(options, probs=None):
    x = np.random.rand()
    if probs is None:
        # then uniform probs
        num = len(options)
        probs = [1 / num] * num
    cum = 0
    choice = -1
    for i, p in enumerate(probs):
        cum += p
        if x < cum:
            choice = i
            break
    return options[choice]


if __name__ == "__main__":
    import os

    import matplotlib.pyplot as plt
    import networkx as nx
    from path import Path

    from comprehensive_nas.search_spaces.graph_grammar.graph_grammar import GraphGrammar

    g = GraphGrammar([])

    dir_path = Path(os.path.dirname(os.path.realpath(__file__)))

    # simple arithmetic grammar
    search_space_path = dir_path / ".." / "debug_grammars" / "simple_arithmetic.cfg"
    with open(search_space_path) as f:
        productions = f.read()

    grammar = Grammar.fromstring(productions)
    # sample a short sequences
    tree = grammar.sampler(1, cfactor=0.0001)
    print(tree)
    nxTree = g.from_stringTree_to_nxTree(tree[0], grammar, sym_name="sym")
    # nx.nx_agraph.write_dot(nxTree,'/home/schrodi/hierarchical_nas_benchmarks/test.dot')
    # pos=graphviz_layout(nxTree, prog='dot')
    nx.draw(
        nxTree, with_labels=True, labels={k: v["sym"] for k, v in nxTree.nodes.items()}
    )
    plt.savefig("/home/schrodi/hierarchical_nas_benchmarks/test.png")
    plt.close()
    # print first sequences of depth 10
    print(grammar.generator(1, 10))
    # print the allowed productions
    print(grammar.productions())

    # SMILES grammar
    search_space_path = dir_path / ".." / "debug_grammars" / "SMILES.cfg"
    with open(search_space_path) as f:
        productions = f.read()
    grammar = Grammar.fromstring(productions)
    # sample a short sequences
    print(grammar.sampler(1, cfactor=0.0001))
    # print first  sequences of depth 10
    print(grammar.generator(1, 10))
    # print the allowed productions
    print(grammar.productions())
