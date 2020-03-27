import pytest
import numpy as np

import tensorflow as tf
import tensorflow.contrib.slim as slim
from tensorflow.contrib.slim.nets import resnet_v2

from neuralmagicML.tensorflow.utils import analyze_module


def _a_sparse_filter(shape):
    w = np.zeros(shape)
    w[0, :] = 1
    return w


def simple_matmul_net(init_weights):
    tf.reset_default_graph()
    n_inputs = 28 * 28
    n_hidden1 = 300
    n_hidden2 = 100
    n_outputs = 10
    X = tf.placeholder(tf.float32, shape=(None, n_inputs), name="X")

    def neuron_layer(X, n_neurons, name, activation=None):
        with tf.name_scope(name):
            n_inputs = int(X.get_shape()[1])
            stddev = 2 / np.sqrt(n_inputs)
            init = tf.truncated_normal((n_inputs, n_neurons), stddev=stddev)
            W = tf.Variable(init, name="kernel")
            b = tf.Variable(tf.zeros([n_neurons]), name="bias")
            Z = tf.matmul(X, W) + b
            if activation is not None:
                return activation(Z)
            else:
                return Z

    with tf.name_scope("dnn"):
        hidden1 = neuron_layer(X, n_hidden1, name="hidden1", activation=tf.nn.relu)
        hidden2 = neuron_layer(
            hidden1, n_hidden2, name="hidden2", activation=tf.nn.relu
        )
        neuron_layer(hidden2, n_outputs, name="outputs")
        return tf.get_default_graph()


def simple_conv2d_net(init_weights):
    tf.reset_default_graph()
    X = tf.placeholder(tf.float32, [None, 32, 40, 1])
    W = tf.Variable(tf.convert_to_tensor(init_weights, dtype=tf.float32))
    b = tf.Variable(tf.random_normal([64]), dtype=tf.float32)
    conv1 = tf.nn.conv2d(X, W, strides=[1, 1, 1, 1], padding="VALID")
    conv1 = tf.nn.bias_add(conv1, b)
    conv1 = tf.nn.max_pool(
        conv1, ksize=[1, 1, 3, 1], strides=[1, 1, 1, 1], padding="VALID"
    )
    return tf.get_default_graph()


def resnet_v2_50(init_weights):
    tf.reset_default_graph()
    image_size = 224
    inputs = tf.random.normal([1, image_size, image_size, 3])
    with slim.arg_scope(resnet_v2.resnet_arg_scope()):
        logits, _ = resnet_v2.resnet_v2_50(inputs, 1000, is_training=False)
        return tf.get_default_graph()


@pytest.mark.parametrize(
    "model, init_weights, layer_name, params, zeroed_params, total_flops",
    [(simple_conv2d_net, np.zeros([20, 8, 1, 64]), "Conv2D", 10240, 10240, 8785920),
     (simple_conv2d_net, np.ones([20, 8, 1, 64]), "Conv2D", 10240, 0, 8785920),
     (simple_conv2d_net, _a_sparse_filter([20, 8, 1, 64]), "Conv2D", 10240, 9728, 8785920),
     (simple_matmul_net, None, "dnn/hidden1/MatMul", 235200, 0, 470400),
     (simple_matmul_net, None, "dnn/hidden2/MatMul", 30000, 0, 60000),
     (resnet_v2_50, None, "resnet_v2_50/conv1/Conv2D", 9408, 0, 236027904)]
)
def test_module_analyzer(model, init_weights, layer_name, params, zeroed_params, total_flops):
    g = model(init_weights)
    with tf.Session(graph=g) as sess:
        sess.run(tf.global_variables_initializer())
        desc_dict = analyze_module(sess, g, op_names=[layer_name])
        desc = desc_dict[layer_name]
        assert desc.params == params
        assert desc.zeroed_params == zeroed_params
        assert desc.total_flops == total_flops
