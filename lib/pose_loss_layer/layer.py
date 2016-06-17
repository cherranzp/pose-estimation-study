'''
Created on Jan 8, 2016

@author: Daniel Onoro Rubio
'''

import caffe
from fast_rcnn.config import cfg
from roi_data_layer.minibatch import get_minibatch
import numpy as np
import yaml
from multiprocessing import Process, Queue

class PoseLossLayer(caffe.Layer):
    """ 
        Pose loss layer that computes the biternion loss.
    """
    def setup(self, bottom, top):
        # check input pair
        if len(bottom) != 3:
            raise Exception("Need two inputs to compute distance.")
        
        self.DEG2RAD_CONST = np.pi/180.0 

    def reshape(self, bottom, top):
        # check input dimensions match
        if bottom[0].count != (bottom[1].count*2):
            raise Exception("Pose prediction does not match with pose labels dimensions.")
        
        # To save inner products between pred and GT
        self.inner_prod = np.zeros( bottom[0].data.shape[0] )
        # Hold predicted modules
        self.pred_mod = np.zeros( bottom[0].data.shape[0] )
        # Hold polar labels
        self.pol_labels = np.zeros( (bottom[0].data.shape[0], 2) )
        
        # loss output is scalar
        top[0].reshape(1)

    def forward(self, bottom, top):
        '''
        Forward pass: 
            bottom[0]: predicted tuple (unnormalized)
            bottom[1]: pose angle labels (degrees)
            bottom[2]: class labels 
        '''
        cls_labels = bottom[2].data.astype(np.int32)    # Cast them to integer
        
        total_loss = 0
        for ix, cls in enumerate(cls_labels):
            # Cast labels into polar cordinates (cos x sin x)
            rad_labels = bottom[1].data[ix,cls]*self.DEG2RAD_CONST
            polar_labels = np.hstack( (np.cos(rad_labels), np.sin(rad_labels) ) ).reshape((1,2))
            polar_pred = bottom[0].data[ix, cls*2:cls*2+2].reshape((2,1))
        
            self.pol_labels[ix] = polar_labels
            self.inner_prod[ix] = np.dot(polar_labels,polar_pred)
            self.pred_mod[ix] = np.linalg.norm(polar_pred)
        
            loss = 1 - self.inner_prod[ix]/self.pred_mod[ix]
            
            total_loss += loss
        
        top[0].data[...] = total_loss/bottom[0].shape[0]


    def backward(self, top, propagate_down, bottom):
        # Reset gradients
        bottom[0].diff[...] = np.zeros_like(bottom[0].diff)
        
        # Get class labels
        cls_labels = bottom[2].data.astype(np.int32)    # Cast them to integer
        
        for ix, cls in enumerate(cls_labels):
            # First parameter
            bottom[0].diff[ix, cls*2] += self.inner_prod[ix]*bottom[0].data[ix, cls*2] / (self.pred_mod[ix]**3) \
                -self.pol_labels[ix, 0] / self.pred_mod[ix]
            
            # Second parameter
            bottom[0].diff[ix, cls*2 + 1] += self.inner_prod[ix]*bottom[0].data[ix, cls*2+1] / (self.pred_mod[ix]**3) \
                -self.pol_labels[ix, 1] / self.pred_mod[ix]            
        
        # Normalize output    
        bottom[0].diff[...] = bottom[0].diff[...] / bottom[0].num
            