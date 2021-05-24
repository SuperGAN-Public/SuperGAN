'''
Contains models used in EMBC paper. For further applications, users can
easily add any generator or discriminator architectures that they are interested in testing.
'''

from keras.models import Model
from keras.layers import Dense, LSTM, Dropout, Input, Lambda
from keras.optimizers import SGD
from keras import backend as K
import tensorflow as tf

#CREATES DISCRIMINATOR ARCHITECTURE USED IN EMBC PAPER
def create_D(seq_length, num_channels):
    D_input_shape = (seq_length, num_channels)
    D_in = Input(shape=D_input_shape)
    D = Dropout(.5)(D_in)
    D = LSTM(100, activation="tanh")(D)
    D = Dense(1, activation="sigmoid")(D)
    D = Model(inputs=D_in, outputs=D, name="D")
    return D

#CREATES GENERATOR ARCHITECTURE USED IN EMBC PAPER
def create_G(seq_length, num_channels, latent_dim):
    G_input_shape = (seq_length, latent_dim)
    G_in = Input(shape=G_input_shape)
    G = Dropout(.5)(G_in)
    G = LSTM(128, return_sequences=True, activation="tanh")(G)
    G = Dropout(.5)(G)
    G = Dense(num_channels, activation="tanh")(G)
    G = Model(inputs=G_in, outputs=G)
    return G

#CREATES CUSTOM LAYER FOR COMPUTING STATISTICAL FEATURE VECTOR PROPOSED IN SDM PAPER (OLD)
def compute_stats_o(x):
    mean = K.mean(x, axis=1, keepdims=True)
    std = K.std(x, axis=1, keepdims=True)
    var = K.var(x, axis=1, keepdims=True)
    xmax = K.reshape(K.max(x, axis=1),(-1,1,3))
    xmin = K.reshape(K.min(x, axis=1), (-1,1,3))
    p2p = tf.subtract(xmax, xmin)
    amp = tf.subtract(xmax, mean)
    rms = K.reshape(K.sqrt(tf.reduce_sum(K.pow(x, 2),1)),(-1,1,3))
    s2e = K.reshape(tf.subtract(x[:,124,:], x[:,0,:]),(-1,1,3))

    full_vec = K.concatenate((mean,std))
    full_vec = K.concatenate((full_vec,var))
    full_vec = K.concatenate((full_vec,xmax))
    full_vec = K.concatenate((full_vec,xmin))
    full_vec = K.concatenate((full_vec,p2p))
    full_vec = K.concatenate((full_vec,amp))
    full_vec = K.concatenate((full_vec,rms))
    full_vec = K.concatenate((full_vec,s2e))
    full_vec = K.reshape(full_vec, (-1,27))
    return full_vec

#RETURNS THE SHAPE OF THE STATISTICAL COMPUTATION LAYER, NECESSARY FOR BUILDING CUSTOM LAYER (OLD)
def output_of_stat_layer_o(input_shape):
    return (input_shape[0], input_shape[2]*9) #9 represents the number of features

#CREATE FULL NETWORK FOR COMPUTING STATISTICAL FEATURE VECTOR
#DEFINED COMPUTE_STATS FUNCTION WITHIN HERE TO MAKE IT FLEXIBLE BASED ON SEQ LENGTH AND NUM FEATURES
#WITHOUT CAUSING ERRORS BY PASSING NON TENSOR PARAMETERS
def create_statistical_feature_net(seq_length, num_channels, num_features):

    def compute_stats(x):
        mean = K.mean(x, axis=1, keepdims=True)
        std = K.std(x, axis=1, keepdims=True)
        var = K.var(x, axis=1, keepdims=True)
        xmax = K.reshape(K.max(x, axis=1),(-1,1,3))
        xmin = K.reshape(K.min(x, axis=1), (-1,1,3))
        p2p = tf.subtract(xmax, xmin)
        amp = tf.subtract(xmax, mean)
        rms = K.reshape(K.sqrt(tf.reduce_sum(K.pow(x, 2),1)),(-1,1,3))
        s2e = K.reshape(tf.subtract(x[:,seq_length-1,:], x[:,0,:]),(-1,1,3))

        full_vec = K.concatenate((mean,std))
        full_vec = K.concatenate((full_vec,var))
        full_vec = K.concatenate((full_vec,xmax))
        full_vec = K.concatenate((full_vec,xmin))
        full_vec = K.concatenate((full_vec,p2p))
        full_vec = K.concatenate((full_vec,amp))
        full_vec = K.concatenate((full_vec,rms))
        full_vec = K.concatenate((full_vec,s2e))
        full_vec = K.reshape(full_vec, (-1,num_features*num_channels))
        return full_vec

    def output_of_stat_layer(input_shape):
        return (input_shape[0], input_shape[2]*num_features) 

    shape = (seq_length, num_channels)
    model_in = Input(shape=shape)
    model_out = Lambda(compute_stats, output_shape=output_of_stat_layer)(model_in)

    model = Model(inputs=model_in, outputs=model_out, name="SFN")
    return model

#COMPILES DISCRIMINATOR MODEL TO TRAINED IN SUPERVISED GENERATIVE FRAMEWORK
def compile_discriminator_model(D, lr):
    optimizer = SGD(lr=lr)
    model = Model(inputs=D.input, outputs=D.output)
    model.compile(loss='binary_crossentropy', optimizer=optimizer, metrics=['accuracy'])
    model.summary()
    return model