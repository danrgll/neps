from abc import ABC


class BaseAcquisition(ABC):
    def __init__(self, surrogate_model, strategy, iters=0):
        self.surrogate_model = surrogate_model
        self.iters = iters
        self.strategy = strategy

        # Storage for the current evaluation on the acquisition function
        self.next_location = None
        self.next_acq_value = None

    def propose_location(self, *args):
        """Propose new locations for subsequent sampling
        This method should be overriden by respective acquisition function implementations."""
        raise NotImplementedError

    def optimize(self):
        """This is the method that user should call for the Bayesian optimisation main loop."""
        raise NotImplementedError

    def eval(self, x):
        """Evaluate the acquisition function at point x2. This should be overridden by respective acquisition
        function implementations"""
        raise NotImplementedError

    def __call__(self, *args, **kwargs):
        return self.eval(*args, **kwargs)
