from .base_acqusition import *
from .ei import *
from .ucb import *

from functools import partial

AcquisitionMapping = {
    'EI': partial(ComprehensiveExpectedImprovement, in_fill='best', augmented_ei=False, ),
    #     # Uses the augmented EI heuristic and changed the in-fill criterion to the best test location with
    #     # the highest *posterior mean*, which are preferred when the optimisation is noisy.
    'AEI': partial(ComprehensiveExpectedImprovement, in_fill='posterior', augmented_ei=True, ),
    'UCB': partial(ComprehensiveUpperConfidentBound, ),
}
