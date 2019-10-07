"""Rescaling method for persistent homology."""
# License: Apache2.0

import itertools
import math as m

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.metrics import pairwise_distances
from sklearn.utils._joblib import Parallel, delayed
from sklearn.utils.validation import check_is_fitted
from ..utils.validation import validate_params


class ConsistentRescaling(BaseEstimator, TransformerMixin):
    r"""Transformer rescaling pairwise distances in data according to the
    ideas in `arXiv:1606.02353 <https://arxiv.org/abs/1606.02353>`_.
    The computation during ``transform``, for each entry in X, is:
    :math:`d_{\mathrm{consistent}}(\star_i, \star_j) = [d(\star_i,
    \star_{k_i}) d(\star_j, \star_{k_j})]^{-1/2}d(\star_i, \star_j)`
    where :math:`\star_i, \star_j` are the :math:`i`-th and :math:`j`-th data
    instances in that entry, :math:`d` is the original distance function, and
    :math:`k_i` is the index of the :math:`k`-th nearest neighbor to
    :math:`\star_i` according to :math:`d`.

    Parameters
    ----------
    metric : string or callable, optional, default: 'euclidean'
        If set to ``'precomputed'``, each entry in X along axis 0 is
        interpreted to be a distance matrix. Otherwise, entries are
        interpreted as feature arrays, and ``metric`` determines a rule with
        which to calculate distances between pairs of instances (i.e. rows)
        in these arrays.
        If ``metric`` is a string, it must be one of the options allowed by
        scipy.spatial.distance.pdist for its metric parameter, or a metric
        listed in pairwise.PAIRWISE_DISTANCE_FUNCTIONS, including
        "euclidean", "manhattan" or "cosine".
        If ``metric`` is a callable function, it is called on each pair of
        instances and the resulting value recorded. The callable should take
        two arrays from the entry in X as input, and return a value
        indicating the distance between them.

    metric_params : dict, optional, default: {}
        Additional keyword arguments for the metric function.

    n_neighbor : int, optional, default: 1
        Rank of the neighbors to be used to modify the metric structure
        according to the consistent rescaling procedure.

    n_jobs : int or None, optional, default: None
        The number of jobs to use for the computation. ``None`` means 1
        unless in a :obj:`joblib.parallel_backend` context. ``-1`` means
        using all processors.

    Examples
    --------
    >>> import numpy as np
    >>> from giotto.homology import ConsistentRescaling
    >>> X = np.array([[[0, 0], [1, 2], [5, 6]]])
    >>> cr = ConsistentRescaling()
    >>> cr.fit(X)
    >>> X_rescaled = cr.transform(X)
    >>> print(X_rescaled.shape)
    (1, 3, 3)

    """
    _hyperparameters = {'n_neighbor': [int, (1, np.inf)]}

    def __init__(self, metric='euclidean', metric_params={}, n_neighbor=1,
                 n_jobs=None):
        self.metric = metric
        self.metric_params = metric_params
        self.n_neighbor = n_neighbor
        self.n_jobs = n_jobs

    def _consistent_homology_distance(self, X):
        Xm = pairwise_distances(X, metric=self.metric, n_jobs=1,
                                **self.metric_params)

        indices_k_neighbor = np.argsort(X)[:, self.n_neighbor]
        distance_k_neighbor = Xm[np.arange(X.shape[0]),
                                 indices_k_neighbor]

        # Only calculate metric for upper triangle
        Xc = np.zeros(Xm.shape)
        iterator = itertools.combinations(range(Xm.shape[0]), 2)
        for i, j in iterator:
            Xc[i, j] = Xm[i, j] / (m.sqrt(distance_k_neighbor[i] *
                                          distance_k_neighbor[j]))
        return Xc + Xc.T

    def fit(self, X, y=None):
        """Do nothing and return the estimator unchanged.
        This method is just there to implement the usual API and hence
        work in pipelines.

        Parameters
        ----------
        X : ndarray, shape (n_samples, n_points, n_points) or (n_samples,
        n_points, n_features)
            Input data. If ``metric=='precomputed'``, the input should be an
            ndarray whose each entry along axis 0 is a distance matrix of shape
            (n_points, n_points). Otherwise, each such entry will be
            interpreted as an ndarray of n_points in Euclidean space of
            dimension n_features.

        y : None
            There is no need of a target in a transformer, yet the pipeline API
            requires this parameter.

        Returns
        -------
        self : object
            Returns self.

        """
        validate_params(self.get_params(), self._hyperparameters)

        self._is_fitted = True
        return self

    # @jit
    def transform(self, X, y=None):
        """For each entry in the input data array X, finds the metric structure
        after consistent rescaling and encodes it as a distance matrix. Then,
        arranges all results in a single ndarray of appropriate shape.

        Parameters
        ----------
        X : ndarray, shape (n_samples, n_points, n_points) or (n_samples,
        n_points, n_features)
            Input data. If ``metric=='precomputed'``, the input should be an
            ndarray whose each entry along axis 0 is a distance matrix of shape
            (n_points, n_points). Otherwise, each such entry will be
            interpreted as an ndarray of n_points in Euclidean space of
            dimension n_features.

        y : None
            There is no need of a target in a transformer, yet the pipeline API
            requires this parameter.

        Returns
        -------
        Xt : ndarray, shape (n_samples, n_points, n_points)
            Array containing (as entries along axis 0) the distance matrices
            after consistent rescaling.

        """
        # Check if fit had been called
        check_is_fitted(self, ['_is_fitted'])

        Xt = Parallel(n_jobs=self.n_jobs)(
            delayed(self._consistent_homology_distance)(X[i])
            for i in range(X.shape[0]))
        Xt = np.array(Xt)
        return Xt
