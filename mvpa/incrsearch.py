### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#    PyMVPA: Incremental feature search algorithm
#
#    Copyright (C) 2007 by
#    Michael Hanke <michael.hanke@gmail.com>
#
#    This package is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Lesser General Public
#    License as published by the Free Software Foundation; either
#    version 2 of the License, or (at your option) any later version.
#
#    This package is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Lesser General Public License for more details.
#
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##

import numpy as np
import crossval
import sys
import stats
import copy

class IncrementalFeatureSearch( object ):
    """ Tell me what this is!

    Two major methods: selectFeatures(), selectROIs()
    """
    def __init__( self, pattern,
                        mask,
                        cvtype = 1,
                        metacvtype = 1,
                        break_crit = 0.001,
                        **kwargs ):

        """
        Parameters:
            pattern:      MVPAPattern object with the data to be analyzed.
            mask:         A mask which's size matches the origshape of the
                          patterns. This mask determines which features are
                          considered for inclusion. Depending on the used
                          algorithm the mask values have different meanings.
                          When calling selectFeatures() each nonzero mask
                          element indicates an individual selection candidate
                          feature.
                          When using selectROIs() all mask elements with a
                          common value are assumed to form a single ROI that
                          is treated as a single feature set and is included
                          at once by the algorithm.
            cvtype:       Type of cross-validation that is used. 1 means
                          N-1 cross-validation.
            break_crit:   Stop searching if the next to-be-included feature
                          provides less than this amount of increased
                          classification performance.
            **kwargs:     Additional arguments that are passed to the
                          constructor of the CrossValidation class.
        """
        self.__pattern = pattern
        self.__mask = mask
        self.__cvtype = cvtype
        self.__metacvtype = metacvtype
        self.__break_crit = break_crit
        self.__cvargs = kwargs

        if not mask.shape == pattern.origshape:
            raise ValueError, 'Mask shape has to match the pattern origshape.'

        self.__clearResults()


    def __clearResults( self ):
        """ Internal method used the clear a analysis results prior to the
        next run.
        """
        # init the result maps
        self.__perfs = []
        self.__selection_masks = []
        self.__metacv_origins = []


    def __doCrossValidation( self, pattern, clf, clfargs ):
        """ Internal method to perform a cross-validation on a pattern set.

        Calls CrossValidation.run() and returns the CrossValidation object.
        """
        # now do cross-validation with the current feature set
        cv = crossval.CrossValidation( pattern, **(self.__cvargs) )
        cv.run( clf, cvtype=self.__cvtype, **(clfargs) )

        return cv


    def __selectByFeatureId( self, selected, candidate ):
        """ Internal method: ignore! """
        return selected + [candidate]


    def __selectByMaskValue( self, selected, candidate ):
        """ Internal method: ignore! """
        return np.logical_or( selected, self.mask == candidate )


    def __doCVSelection( self, clf, clfargs, featureselector,
                         selected, candidates, verbose ):
        # get the list of all combinations of to be excluded folds
        self.__metacv_origins = crossval.getUniqueLengthNCombinations(
                                      self.__pattern.originlabels,
                                      self.__metacvtype )

        # list for the results of all CV folds
        cv_features = []
        cv_rois = []

        # meta crossvalidation
        for i, exclude in enumerate(self.__metacv_origins):
            if verbose:
                print "Meta cross-validation fold:", i

            # split data for meta cross-validation
            meta_train, meta_test = \
                crossval.CrossValidation.splitTrainTestData( self.pattern, 
                                                             exclude )

            # call the backend method that returns a list of the selected
            # features and the cross-validation object with the best feature set
            # that can be used to query more detailed results
            selected_features, selected_rois = \
                 self.__doSelection( meta_train,
                                     clf, clfargs,
                                     featureselector,
                                     selected,
                                     candidates,
                                     verbose )

            # now take the selected features of this meta CV fold and test
            # their performance on the meta test patterns
            bestfeature_pat = self.pattern.selectFeatures( selected_features )
            classifier, predictions = \
                crossval.CrossValidation.getClassification( 
                        clf,
                        bestfeature_pat,
                        meta_test.selectFeatures( selected_features ),
                        **(clfargs) )

            # store results
            self.perfs.append ( ( predictions == meta_test.reg ).mean() )
            cv_features.append( selected_features )
            cv_rois.append( selected_rois )

        return cv_features, cv_rois


    def __doSelection( self, pattern, clf, clfargs, featureselector,
                       selected, candidates, verbose ):
        """ Backend method for selectFeatures() and selectROIs.
        """
        # make a copy of the candidates otherwise repeated calls will cause
        # trouble
        feat_cand = copy.copy( candidates )
        
        # yes, it is exactly that
        best_performance_ever = 0.0

        # contains the number of selected candidates
        selection_counter = 0

        # list of best canidate ids
        # in case of a simple feature selection, this is redundant with
        # the 'selected' list
        best_ids = []

        # as long as there are candidates left
        # the loop might get broken earlier if the generalization
        # error does not go down when a new ROI is selected
        while len( feat_cand ):
            # holds the performance value of each candidate
            candidate_rating = []

            # for all possible candidates
            for candidate in feat_cand:
                # display some status output about the progress if requested
                if verbose:
                    print "\rTested %i; nselected %i; mean performance: %.3f" \
                        % ( len(candidate_rating),
                            selection_counter,
                            best_performance_ever ),
                    sys.stdout.flush()

                # take the new candidate and all already selected features
                features = featureselector( selected, candidate )

                # select the feature subset from the dataset
                temp_pat = pattern.selectFeatures( features )

                # now do cross-validation with the current feature set
                cv = self.__doCrossValidation( temp_pat,
                                               clf,
                                               clfargs )

                # store the generalization performance for this feature set
                candidate_rating.append( np.mean(cv.perf) )

            # I like arrays!
            rating_array = np.array( candidate_rating )

            # determine the best performing additonal candidate (get its id)
            best_id = feat_cand[ rating_array.argmax() ]

            # check if the new candidate brings no value
            # if this is the case we are done.
            if rating_array.max() - best_performance_ever < self.__break_crit:
                break

            # the new candidate adds value, because the generalization error
            # went down, therefore add it to the list of selected features
            selected = featureselector( selected, best_id )
            best_ids.append( best_id )

            # and remove it from the candidate features
            # otherwise the while loop could run forever
            feat_cand.remove( best_id )

            # update the latest best performance
            best_performance_ever = rating_array.max()

            # and look for the next best thing (TM)
            selection_counter += 1

        # if no candidates are left or the generalization performance
        # went down
        if verbose:
            # end pending line
            print ''

        return selected, best_ids



    def selectROIs( self, classifier, verbose=False, **kwargs ):
        """ Select the best set of ROIs from a mask that maximizes the
        generalization performance.

        The method works exactly like selectFeatures(), but instead of choosing
        single features from a mask it works on ROIs (sets of features).

        An ROI (region of interest) are all features sharing a common value in
        the mask.

        The method returns the list of selected ROI ids (mask values). A
        boolean mask with all selected feature from all selected ROIs is
        available via the selectionmask property.

        By setting 'verbose' to True one can enable some status messages that
        inform about the progress.

        The 'classifier' argument specifies a class that is used to perform
        the classification. Additional keyword are passed to the classifier's
        contructor.
        """
        # cleanup prior runs first
        self.__clearResults()

        # get all different mask values
        mask_values = np.unique( self.mask ).tolist()

        # selected features are stored in a mask array with the same shape
        # as the original feature mask
        selected_features = np.zeros( self.mask.shape, dtype='bool' )

        # call the backend method that returns a list of the selected
        # features and the cross-validation object with the best feature set
        # that can be used to query more detailed results
        feature_mask, selected_rois = \
             self.__doCVSelection( classifier, kwargs,
                                   self.__selectByMaskValue,
                                   selected_features,
                                   mask_values,
                                   verbose )

        # store results
        self.__selection_masks = feature_mask

        return selected_rois


    def selectFeatures( self, classifier, verbose=False, **kwargs ):
        """
        Select the subset of features from the feature mask that maximizes
        the classification performance on the generalization test set.

        The alorithm tests all available features in serial order with
        respect to their individiual classification performance. Only the best
        performing feature is selected. Next, each remaining feature is tested
        again whether it provides the most additional information with respect
        to classification performance. This procedure continues until a
        to-be-selected feature does not reduce the generalization error.

        By setting 'verbose' to True one can enable some status messages that
        inform about the progress.

        The 'classifier' argument specifies a class that is used to perform
        the classification. Additional keyword arguments are passed to the
        classifier's contructor.

        Returns the list of selected feature ids. Additional results are
        available via several class properties.
        """
        # cleanup prior runs first
        self.__clearResults()

        # initially empty list of selected features
        selected_features = []

        # transform coordinates of nonzero mask elements into feature ids
        cand_features = [ self.pattern.getFeatureId(coord)
                          for coord in np.transpose( self.mask.nonzero() ) ]

        # call the backend method that returns a list of the selected
        # features and the cross-validation object with the best feature set
        # that can be used to query more detailed results
        selected_features, dummy = \
             self.__doCVSelection( classifier, kwargs,
                                   self.__selectByFeatureId,
                                   selected_features,
                                   cand_features,
                                   verbose )

        # store results
        self.__selection_masks = \
            [ self.pattern.features2origmask( f ) for f in selected_features ]

        return selected_features


    def getMeanSelectionMask( self ):
        if len( self.__selection_masks ) < 1:
            return None

        return np.array(self.__selection_masks).mean(axis=0)


    # access to the results
    selectionmasks = property( fget=lambda self: self.__selection_masks )
    perfs = property( fget=lambda self: self.__perfs )

    # other data access
    pattern = property( fget=lambda self: self.__pattern )
    mask = property( fget=lambda self: self.__mask )
    cvtype = property( fget=lambda self: self.__cvtype )

