# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the PyMVPA package for the
#   copyright and license terms.
#
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Unit tests for PyMVPA SVD mapper"""


import unittest
from mvpa.support.copy import deepcopy
import numpy as N
from mvpa.datasets.base import dataset_wizard
from mvpa.mappers.svd import SVDMapper


class SVDMapperTests(unittest.TestCase):

    def setUp(self):
        # data: 40 sample feature line in 20d space (40x20; samples x features)
        self.ndlin = N.concatenate([N.arange(40)
                                        for i in range(20)]).reshape(20,-1).T

        # data: 10 sample feature line in 40d space
        #       (10x40; samples x features)
        self.largefeat = N.concatenate([N.arange(10)
                                        for i in range(40)]).reshape(40,-1).T


    def testSimpleSVD(self):
        pm = SVDMapper()
        # train SVD
        pm.train(self.ndlin)

        self.failUnlessEqual(pm.proj.shape, (20, 20))

        # now project data into PCA space
        p = pm.forward(self.ndlin)

        # only first eigenvalue significant
        self.failUnless(pm.sv[:1] > 1.0)
        self.failUnless((pm.sv[1:] < 0.0001).all())

        # only variance of first component significant
        var = p.var(axis=0)

       # test that only one component has variance
        self.failUnless(var[:1] > 1.0)
        self.failUnless((var[1:] < 0.0001).all())

        # check that the mapped data can be fully recovered by 'reverse()'
        pr = pm.reverse(p)

        self.failUnlessEqual(pr.shape, (40,20))
        self.failUnless(N.abs(pm.reverse(p) - self.ndlin).sum() < 0.0001)


    def testMoreSVD(self):
        pm = SVDMapper()
        # train SVD
        pm.train(self.largefeat)

        # mixing matrix cannot be square
        self.failUnlessEqual(pm.proj.shape, (40, 10))

        # only first singular value significant
        self.failUnless(pm.sv[:1] > 10)
        self.failUnless((pm.sv[1:] < 10).all())

        # now project data into SVD space
        p = pm.forward(self.largefeat)

        # only variance of first component significant
        var = p.var(axis=0)

        # test that only one component has variance
        self.failUnless(var[:1] > 1.0)
        self.failUnless((var[1:] < 0.0001).all())

        # check that the mapped data can be fully recovered by 'reverse()'
        rp = pm.reverse(p)
        self.failUnlessEqual(rp.shape, self.largefeat.shape)
        self.failUnless((N.round(rp) == self.largefeat).all())

        # copy mapper
        pm2 = deepcopy(pm)

        # now make new random data and do forward->reverse check
        data = N.random.normal(size=(98,40))
        data_f = pm.forward(data)

        self.failUnlessEqual(data_f.shape, (98,10))

        data_r = pm.reverse(data_f)
        self.failUnlessEqual(data_r.shape, (98,40))



def suite():
    return unittest.makeSuite(SVDMapperTests)


if __name__ == '__main__':
    import runner

