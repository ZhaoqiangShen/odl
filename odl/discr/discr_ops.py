# Copyright 2014-2016 The ODL development group
#
# This file is part of ODL.
#
# ODL is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ODL is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ODL.  If not, see <http://www.gnu.org/licenses/>.

"""Operators defined on `DiscreteLp`."""

# Imports for common Python 2/3 codebase
from __future__ import print_function, division, absolute_import
from future import standard_library
standard_library.install_aliases()
from builtins import super

import numpy as np

# ODL imports
from odl.operator.operator import Operator
from odl.set.pspace import ProductSpace
from odl.discr.lp_discr import DiscreteLp


__all__ = ('PartialDerivative', 'Gradient', 'Divergence', 'Laplacian')


def finite_diff(f, out=None, axis=0, dx=1.0, method='forward', padding=None,
                edge_order=None):
    """Calculate the partial derivative of ``f`` along a given ``axis``.

    The partial derivative is computed using first-order accurate forward,
    first-order accurate backward, or second-order accurate central
    differences in the interior.

    With padding the same method is used on endpoints as in the interiors.
    Without padding one-sided forward or backward differences are used at
    the boundaries.

    The accuracy on the endpoints is determined by the method used in the
    interior. Without padding endpoint accuracy can be set by the edge order.

    The returned array has the same shape as the input array ``f``.

    Parameters
    ----------
    f : `array-like`
         An N-dimensional array
    out : `numpy.ndarray`, optional
         An N-dimensional array to which the output is written
    axis : `int`, optional
        The axis along which the partial derivative is evaluated
    dx : `float`, optional
        Scalar specifying the distance between sampling points along ``axis``
    method : {'central', 'forward', 'backward'}, optional
        Finite difference method which is used in the interior of the domain
         of ``f``.
    padding : `float` or 'replicate', optional
        `float` : Implicit padding. Assumes indices outside the domain of
            ``f`` to have the value ``padding``. If `None` forward or
              backward differences are used at the boundary instead of zero
              padding.
        'replicate' : Replicate values at the boundary. Thus forward or
        backward difference become zero on the endpoints.
    edge_order : {1, 2}, optional
        Edge-order accuracy at the boundaries if no padding is used. If
        `None` the edge-order accuracy at endpoints corresponds to the
        accuracy in the interior.

    Returns
    -------
    out : `numpy.ndarray`
        N-dimensional array of the same shape as ``f``. If ``out`` is
        provided, the returned object is a reference to it.

    Examples
    --------
    >>> f = np.array([ 0., 1., 2., 3., 4., 5., 6., 7., 8., 9.])

    # >>> finite_diff(f)
    array([ 1.,  1.,  1.,  1.,  1.,  1.,  1.,  1.,  1.,  1.])

    Without arguments the above defaults to:
    # >>> finite_diff(f, axis=0, dx=1.0, method='forward', padding=None,
    # ... edge_order=None)
    array([ 1.,  1.,  1.,  1.,  1.,  1.,  1.,  1.,  1.,  1.])

    # >>> finite_diff(f, dx=0.5)
    array([ 2.,  2.,  2.,  2.,  2.,  2.,  2.,  2.,  2.,  2.])
    >>> finite_diff(f, padding=0)
    array([ 1.,  1.,  1.,  1.,  1.,  1.,  1.,  1.,  1., -9.])

    Central differences and different edge orders
    TODO: Why is first entry -0?
    >>> finite_diff(1/2*f**2, method='central')
    array([-0.,  1.,  2.,  3.,  4.,  5.,  6.,  7.,  8.,  9.])
    >>> finite_diff(1/2*f**2, method='central', edge_order=1)
    array([ 0.5,  1. ,  2. ,  3. ,  4. ,  5. ,  6. ,  7. ,  8. ,  8.5])

    In-place evaluation:
    >>> out = f.copy()
    >>> out is finite_diff(f, out)
    True
    """
    # TODO: implement alternative boundary conditions

    f_arr = np.asarray(f)
    ndim = f_arr.ndim

    if f_arr.shape[axis] < 2:
        raise ValueError("shape ({0}) of array too small to calculate a "
                         "numerical gradient, at least two elements are "
                         "required.".format(f_arr.shape))

    if out is None:
        out = np.empty_like(f_arr)
    else:
        if out.shape != f.shape:
            raise ValueError(
                "shape of `out` array ({0}) does not match the shape of "
                "input array `f` ({1}).".format(out.shape, f.shape))

    if not 0 <= axis < ndim:
        raise IndexError("axis parameter ({0}) exceeds the number of "
                         "dimensions ({1}).".format(axis, ndim))

    if dx <= 0:
        raise ValueError("step length ({0}) not positive.".format(dx))
    else:
        dx = float(dx)

    method, method_in = str(method).lower(), method
    if method not in ('central', 'forward', 'backward'):
        raise ValueError('method {} is not central, forward or backward'
                         ''.format(method_in))

    if isinstance(padding, (int, float)) or padding in (None, 'replicate'):
        if isinstance(padding, int):
            padding = float(padding)
    else:
        raise ValueError('padding value ({}) not valid'.format(padding))

    if edge_order is None:
        if method == 'central':
            edge_order = 2
        else:
            edge_order = 1
    else:
        if edge_order not in [1, 2]:
            raise ValueError('edge order ({0}) not valid'.format(edge_order))

    if f_arr.shape[axis] == 2 and edge_order == 2:
        raise ValueError('shape ({0}) of array to small to use one-sided '
                         'second-order accurate edges'.format(f_arr.shape))

    if padding is not None:
        if method == 'central' and edge_order == 1:
            raise ValueError(
                'central differences with padding only use second-order '
                'accuracy at edges. Edge-order accuracy can only be '
                'triggered without padding for one-sided differences at '
                'edges')
        if method in ('forward', 'backward') and edge_order == 2:
            raise ValueError(
                'forward/backward difference with padding use the same '
                'accuracy on edges as in the interior. Edge-order accuracy '
                'can only be triggered without padding for one-sided '
                'differences at edges.')

    # create slice objects: initially all are [:, :, ..., :]

    # current slice
    slice_out = [slice(None)] * ndim

    # slices used to calculate finite differences
    slice_node1 = [slice(None)] * ndim
    slice_node2 = [slice(None)] * ndim
    slice_node3 = [slice(None)] * ndim

    # Interior

    if method == 'central':
        # 2nd order interior
        slice_out[axis] = slice(1, -1)
        slice_node1[axis] = slice(2, None)
        slice_node2[axis] = slice(None, -2)
        # 1D equivalent: out[1:-1] = (f[2:] - f[:-2])/2.0
        np.subtract(f_arr[slice_node1], f_arr[slice_node2], out[slice_out])
        out[slice_out] /= 2.0

    elif method == 'forward':
        # 1st order interior
        slice_out[axis] = slice(1, -1)
        slice_node1[axis] = slice(2, None)
        slice_node2[axis] = slice(1, -1)
        # 1D equivalent: out[1:-1] = (f[2:] - f[1:-1])
        np.subtract(f_arr[slice_node1], f_arr[slice_node2], out[slice_out])

    elif method == 'backward':
        # 1st order interior
        slice_out[axis] = slice(1, -1)
        slice_node1[axis] = slice(1, -1)
        slice_node2[axis] = slice(None, -2)
        # 1D equivalent: out[1:-1] = (f[1:-1] - f[:-2])
        np.subtract(f_arr[slice_node1], f_arr[slice_node2], out[slice_out])

    # Boundaries

    if isinstance(padding, float):
        # Assume constant value c for indices outside the domain of ``f``

        # The method used on endpoints is the same as in the interior

        if method == 'central':
            # 2nd-order lower edge
            slice_out[axis] = 0
            slice_node1[axis] = 1
            # 1D equivalent: out[0] = (f[1] - c)/2.0
            out[slice_out] = (f_arr[slice_node1] - padding) / 2.0

            # 2nd-order upper edge
            slice_out[axis] = -1
            slice_node2[axis] = -2
            # 1D equivalent: out[-1] = (c - f[-2])/2.0
            out[slice_out] = (padding - f_arr[slice_node2]) / 2.0

        elif method == 'forward':
            # 1st-oder lower edge
            slice_out[axis] = 0
            slice_node1[axis] = 1
            slice_node2[axis] = 0
            # 1D equivalent: out[0] = f[1] - f[0]
            out[slice_out] = f_arr[slice_node1] - f_arr[slice_node2]

            # 1st-oder upper edge
            slice_out[axis] = -1
            slice_node2[axis] = -1
            # 1D equivalent: out[-1] = c - f[-1]
            out[slice_out] = padding - f_arr[slice_node2]

        elif method == 'backward':
            # 1st-oder lower edge
            slice_out[axis] = 0
            slice_node1[axis] = 0
            # 1D equivalent: out[0] = f[0] - c
            out[slice_out] = f_arr[slice_node1] - padding

            # 1st-oder upper edge
            slice_out[axis] = -1
            slice_node1[axis] = -1
            slice_node2[axis] = -2
            # 1D equivalent: out[-1] = f[-1] - f[-2]
            out[slice_out] = f_arr[slice_node1] - f_arr[slice_node2]

    elif padding == 'replicate':
        # Values of indices outside the domain of ``f`` are replicate of the
        #  boundary values

        # The method used on endpoints is the same as in the interior

        if method == 'central':
            # 2nd-order lower edge
            slice_out[axis] = 0
            slice_node1[axis] = 1
            slice_node2[axis] = 0
            # 1D equivalent: out[0] = (f[1] - f[0])/2.0
            out[slice_out] = (f_arr[slice_node1] - f_arr[slice_node2]) / 2.0

            # 2nd-order upper edge
            slice_out[axis] = -1
            slice_node1[axis] = -1
            slice_node2[axis] = -2
            # 1D equivalent: out[-1] = (f[-1] - f[-2])/2.0
            out[slice_out] = (f_arr[slice_node1] - f_arr[slice_node2]) / 2.0

        elif method == 'forward':
            # 1st-oder lower edge
            slice_out[axis] = 0
            slice_node1[axis] = 1
            slice_node2[axis] = 0
            # 1D equivalent: out[0] = f[1] - f[0]
            out[slice_out] = f_arr[slice_node1] - f_arr[slice_node2]

            # 1st-oder upper edge
            slice_out[axis] = -1
            # 1D equivalent: out[-1] = f[-1] - f[-1] = 0
            out[slice_out] = 0

        elif method == 'backward':
            # 1st-oder lower edge
            slice_out[axis] = 0
            # 1D equivalent: out[0] = f[0] - f[0] = 0
            out[slice_out] = 0

            # 1st-oder upper edge
            slice_out[axis] = -1
            slice_node1[axis] = -1
            slice_node2[axis] = -2
            # 1D equivalent: out[-1] = f[-1] - f[-2]
            out[slice_out] = f_arr[slice_node1] - f_arr[slice_node2]

    # Use one-sided differences on the endpoints
    else:

        # Edge-order accuracy is triggered implicitly by the method used in
        #  the interior or explicitly using ``edge_order``

        # 1st order edges
        if edge_order == 1:
            # lower boundary
            slice_out[axis] = 0
            slice_node1[axis] = 1
            slice_node2[axis] = 0
            # 1D equivalent: out[0] = (f[1] - f[0])
            out[slice_out] = f_arr[slice_node1] - f_arr[slice_node2]

            # upper boundary
            slice_out[axis] = -1
            slice_node1[axis] = -1
            slice_node2[axis] = -2
            # 1D equivalent: out[-1] = (f[-1] - f[-2])
            out[slice_out] = f_arr[slice_node1] - f_arr[slice_node2]

        # 2nd order edges
        elif edge_order == 2:
            # lower boundary
            slice_out[axis] = 0
            slice_node1[axis] = 0
            slice_node2[axis] = 1
            slice_node3[axis] = 2
            # 1D equivalent: out[0] = -(3*f[0] - 4*f[1] + f[2]) / 2.0
            out[slice_out] = -(3.0 * f_arr[slice_node1] - 4.0 * f_arr[
                slice_node2] + f_arr[slice_node3]) / 2.0

            # upper boundary
            slice_out[axis] = -1
            slice_node1[axis] = -1
            slice_node2[axis] = -2
            slice_node3[axis] = -3
            # 1D equivalent: out[-1] = (3*f[-1] - 4*f[-2] + f[-3]) / 2.0
            out[slice_out] = (3.0 * f_arr[slice_node1] - 4.0 * f_arr[
                slice_node2] + f_arr[slice_node3]) / 2.0

    # divide by step size
    out /= dx

    return out


class PartialDerivative(Operator):
    """Calculate the discrete partial derivative along a given axis.

    Calls helper function `finite_diff` to calculate finite difference.
    Preserves the shape of the underlying grid.
    """
    # TODO: implement adjoint

    def __init__(self, space, axis=0, dx=None, method='forward',
                 padding=None, edge_order=None):
        """Initialize an operator instance.

        Parameters
        ----------
        space : `DiscreteLp`
            The space of elements which the operator is acting on
        axis : `int`, optional
            The axis along which the partial derivative is evaluated
        dx : `float`, optional
            Scalar specifying the distance between sampling points along
            ``axis``. If `None` uses the side length along the ``axis`` of
            a cell of ``space``
        method : {'central', 'forward', 'backward'}, optional
            Finite difference method which is used in the interior of the
            domain of ``f``
        padding : `float` or 'replicate', optional
            `float` : Implicit padding. Assumes indices outside the domain of
                ``f`` to have the value ``padding``. If `None` forward or
                backward differences are used at the boundary instead of zero
                padding.
            'replicate' : Replicate values at the boundary. Thus forward or
                backward difference become zero on the endpoints.
        edge_order : {1, 2}, optional
            Edge-order accuracy at the boundaries if no padding is used. If
            `None` the edge-order accuracy at endpoints corresponds to the
            accuracy in the interior.
        """

        if not isinstance(space, DiscreteLp):
            raise TypeError('space {!r} is not a `DiscreteLp` '
                            'instance.'.format(space))

        super().__init__(domain=space, range=space, linear=True)
        self.axis = axis
        if dx is None:
            self.dx = space.cell_sides[axis]
        else:
            self.dx = dx
        self.method = method
        self.padding = padding
        self.edge_order = edge_order

    def _call(self, x, out=None):
        """Apply gradient operator to ``x`` and store result in ``out``.

        Parameters
        ----------
        x : ``domain`` `element`
            Input vector to which the operator is applied to
        out : ``range`` element, optional
            Output vector to which the result is written

        Returns
        -------
        out : ``range`` `element`
            Result of the evaluation. If ``out`` is provided, the
            returned object is a reference to it.

        Examples
        --------
        >>> from odl import uniform_discr
        >>> data = np.array([[ 0.,  1.,  2.,  3.,  4.],
        ...                  [ 0.,  2.,  4.,  6.,  8.]])
        >>> discr = uniform_discr([0, 0], [2, 1], data.shape)
        >>> par_deriv = PartialDerivative(discr)
        >>> f = par_deriv.domain.element(data)
        >>> par_div_f = par_deriv(f)
        >>> print(par_div_f)
        [[0.0, 1.0, 2.0, 3.0, 4.0],
         [0.0, 1.0, 2.0, 3.0, 4.0]]
        """
        if out is None:
            out = self.range.element()

        # TODO: this pipes CUDA arrays through NumPy. Write native operator.
        out_arr = out.asarray()

        finite_diff(x.asarray(), out=out_arr, axis=self.axis, dx=self.dx,
                    method=self.method, padding=self.padding,
                    edge_order=self.edge_order)

        # self assignment: no overhead in the case asarray is a view
        out[:] = out_arr
        return out

    @property
    def adjoint(self):
        """Return the adjoint operator."""
        raise NotImplementedError('adjoint not implemented')


class Gradient(Operator):
    """Spatial gradient operator for `DiscreteLp` spaces.

    Calls helper function `finite_diff` to calculate each component of the
    resulting product space vector. For the adjoint of the `Gradient`
    operator to match the negative `Divergence` operator zero padding is
    assumed.
    """

    def __init__(self, space, method='forward'):
        """Initialize a `Gradient` operator instance.

        Zero padding is assumed for the adjoint of the `Gradient`
        operator to match  negative `Divergence` operator.

        Parameters
        ----------
        space : `DiscreteLp`
            The space of elements which the operator is acting on.
        method : {'central', 'forward', 'backward'}, optional
            Finite difference method to be used
        """

        if not isinstance(space, DiscreteLp):
            raise TypeError('space {!r} is not a `DiscreteLp` '
                            'instance.'.format(space))

        self.method = method
        super().__init__(
            domain=space, range=ProductSpace(space, space.ndim), linear=True)

    def _call(self, x, out=None):
        """Calculate the spatial gradient of ``x``.

        Parameters
        ----------
        x : ``domain`` `element`
            Input vector to which the `Gradient` operator is applied
        out : ``range`` `element`, optional
            Output vector to which the result is written

        Returns
        -------
        out : ``range`` `element`
            Result of the evaluation. If ``out`` is provided, the returned
            object is a reference to it.

        Examples
        --------
        >>> from odl import uniform_discr
        >>> data = np.array([[ 0., 1., 2., 3., 4.],
        ...                  [ 0., 2., 4., 6., 8.]])
        >>> discr = uniform_discr([0, 0], [2, 5], data.shape)
        >>> f = discr.element(data)
        >>> grad = Gradient(discr)
        >>> grad_f = grad(f)
        >>> print(grad_f[0])
        [[0.0, 1.0, 2.0, 3.0, 4.0],
         [0.0, -2.0, -4.0, -6.0, -8.0]]
        >>> print(grad_f[1])
        [[1.0, 1.0, 1.0, 1.0, -4.0],
         [2.0, 2.0, 2.0, 2.0, -8.0]]

        Verify adjoint:
        >>> g = grad.range.element((data, data ** 2))
        >>> adj_g = grad.adjoint(g)
        >>> print(adj_g)
        [[0.0, -2.0, -5.0, -8.0, -11.0],
         [0.0, -5.0, -14.0, -23.0, -32.0]]
        >>> g.inner(grad_f) / f.inner(adj_g)
        1.0
        """
        if out is None:
            out = self.range.element()

        x_arr = x.asarray()
        ndim = self.domain.ndim
        dx = self.domain.cell_sides

        for axis in range(ndim):
            out_arr = out[axis].asarray()

            finite_diff(x_arr, out=out_arr, axis=axis, dx=dx[axis],
                        method=self.method, padding=0)

            out[axis][:] = out_arr

        return out

    @property
    def adjoint(self):
        """Return the adjoint operator.

        Assuming implicit zero padding, the adjoint operator is given by the
        negative of the `Divergence` operator.

        Note that the ``space`` argument of the `Divergence` operator is not
        the range but the domain of the `Gradient` operator.
        """
        if self.method == 'central':
            return - Divergence(self.domain, 'central')
        elif self.method == 'forward':
            return - Divergence(self.domain, 'backward')
        elif self.method == 'backward':
            return - Divergence(self.domain, 'forward')
        else:
            return super().adjoint


class Divergence(Operator):
    """Divergence operator for `DiscreteLp` spaces.

    Calls helper function `finite_diff` for each component of the input
    product space vector. For the adjoint of the `Divergence` operator to
    match the negative `Gradient` operator implicit zero is assumed.
    """

    def __init__(self, space, method='forward'):
        """Initialize a `Divergence` operator instance.

        Zero padding is assumed for the adjoint of the `Divergence`
        operator to match negative `Gradient` operator.

        Parameters
        ----------
        space : `DiscreteLp`
            The space of elements which the operator is acting on
        method : {'central', 'forward', 'backward'}, optional
            Finite difference method to be used
        """
        if not isinstance(space, DiscreteLp):
            raise TypeError('space {!r} is not a `DiscreteLp` '
                            'instance.'.format(space))

        self.method = method
        super().__init__(domain=ProductSpace(space, space.ndim),
                         range=space, linear=True)

    def _call(self, x, out=None):
        """Calculate the divergence of ``x``.

        Parameters
        ----------
        x : ``domain`` `element`
            `ProductSpaceVector` to which the divergence operator
            is applied
        out : ``range`` `element`, optional
            Output vector to which the result is written

        Returns
        -------
        out : ``range`` `element`
            Result of the evaluation. If ``out`` is provided, the returned
            object is a reference to it.

        Examples
        --------
        >>> from odl import uniform_discr
        >>> data = np.array([[0., 1., 2., 3., 4.],
        ...                  [1., 2., 3., 4., 5.],
        ...                  [2., 3., 4., 5., 6.]])
        >>> space = uniform_discr([0, 0], [3, 5], data.shape)
        >>> div = Divergence(space)
        >>> f = div.domain.element([data, data])
        >>> div_f = div(f)
        >>> print(div_f)
        [[2.0, 2.0, 2.0, 2.0, -3.0],
         [2.0, 2.0, 2.0, 2.0, -4.0],
         [-1.0, -2.0, -3.0, -4.0, -12.0]]

        Verify adjoint:
        >>> g = div.range.element(data ** 2)
        >>> adj_div_g = div.adjoint(g)
        >>> g.inner(div_f) / f.inner(adj_div_g)
        1.0
        """
        if out is None:
            out = self.range.element()

        ndim = self.range.ndim
        dx = self.range.cell_sides

        out_arr = out.asarray()
        tmp = np.empty(out.shape, out.dtype, order=out.space.order)
        for axis in range(ndim):
            finite_diff(x[axis], out=tmp, axis=axis, dx=dx[axis],
                        method=self.method, padding=0)
            if axis == 0:
                out_arr[:] = tmp
            else:
                out_arr += tmp

        # self assignment: no overhead in the case asarray is a view
        out[:] = out_arr
        return out

    @property
    def adjoint(self):
        """Return the adjoint operator.

        Assuming implicit zero padding, the adjoint operator is given by the
        negative of the `Gradient` operator.
        """
        if self.method == 'central':
            return - Gradient(self.range, 'central')
        elif self.method == 'forward':
            return - Gradient(self.range, 'backward')
        elif self.method == 'backward':
            return - Gradient(self.range, 'forward')
        else:
            return super().adjoint


class Laplacian(Operator):
    """Spatial Laplacian operator for `DiscreteLp` spaces.

    Calls helper function `finite_diff` to calculate each component of the
    resulting product space vector.

    Outside the domain zero padding is assumed.
    """

    def __init__(self, space):
        """Initialize a `Laplacian` operator instance.

        Parameters
        ----------
        space : `DiscreteLp`
            The space of elements which the operator is acting on
        """

        if not isinstance(space, DiscreteLp):
            raise TypeError('space {!r} is not a `DiscreteLp` '
                            'instance.'.format(space))

        super().__init__(domain=space, range=space, linear=True)

    def _call(self, x, out=None):
        """Calculate the spatial Laplacian of ``x``.

        Parameters
        ----------
        x : ``domain`` `element`
            Input vector to which the `Laplacian` operator is
            applied
        out : ``range`` `element`, optional
            Output vector to which the result is written

        Returns
        -------
        out : ``range`` `element`
            Result of the evaluation. If ``out`` is provided, the returned
            object is a reference to it.

        Examples
        --------
        >>> from odl import uniform_discr
        >>> data = np.array([[ 0., 0., 0.],
        ...                  [ 0., 1., 0.],
        ...                  [ 0., 0., 0.]])
        >>> space = uniform_discr([0, 0], [3, 3], data.shape)
        >>> f = space.element(data)
        >>> lap = Laplacian(space)
        >>> print(lap(f))
        [[0.0, 1.0, 0.0],
         [1.0, -4.0, 1.0],
         [0.0, 1.0, 0.0]]
        """
        if out is None:
            out = self.range.zero()
        else:
            out.set_zero()

        x_arr = x.asarray()
        out_arr = out.asarray()
        tmp = np.empty(out.shape, out.dtype, order=out.space.order)

        ndim = self.domain.ndim
        dx = self.domain.cell_sides

        for axis in range(ndim):
            # TODO: this can be optimized

            finite_diff(x_arr, out=tmp, axis=axis, dx=dx[axis] ** 2,
                        method='forward', padding=0)

            out_arr[:] += tmp

            finite_diff(x_arr, out=tmp, axis=axis, dx=dx[axis] ** 2,
                        method='backward', padding=0)

            out_arr[:] -= tmp

        out[:] = out_arr
        return out

    @property
    def adjoint(self):
        """Return the adjoint operator.

        The laplacian is self-adjoint, so this returns ``self``.
        """
        return self


if __name__ == '__main__':
    from doctest import testmod, NORMALIZE_WHITESPACE
    testmod(optionflags=NORMALIZE_WHITESPACE)
