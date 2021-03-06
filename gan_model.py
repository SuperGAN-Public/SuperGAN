import os
from typing import Tuple

import numpy as np
from keras.engine.functional import Functional
from keras.models import Model, load_model, Functional
from numpy import ndarray
from sklearn.metrics import accuracy_score

import input_module
import models
import saving_module as save
import train_simple_lstm
import training_module
import training_module as train
import model_critique_functions as critique
import plotting_module
from data.model_data_storage import TrainingParameters, Weights, Names, ModelData, Empty
from input_module import InputModuleConfiguration
from training_module import train_tstr_classifier


class GanModel:
    feature_net: Functional
    discriminator_model: Functional
    discriminator: Functional
    generator: Functional
    num_classes: int
    input_shape: Tuple[int, int]
    num_channels: int
    seq_length: int
    num_seqs: int
    classifier: Functional
    write_train_results: bool
    request_save: bool
    model_save_directory: str
    class_label: int
    input_data: ndarray
    training_parameters: TrainingParameters

    def __init__(self, training_param: TrainingParameters,
                 weight: Weights,
                 name: Names,
                 model_data: ModelData,
                 config: str,
                 load_pretrained: bool = False,
                 ignore_classifier: bool = False,
                 ignore_sfd: bool = False):
        """
        Constructs a new GAN model from the given training parameters, weights, and names.

        :param training_param: The training parameters.
        :param weight: The weights.
        :param name: The name.
        :param config: The configuration file.
        :param load_pretrained: Whether to use a pretrained GAN
        :param ignore_classifier: Whether to ignore the effect of the classifier in training the GAN
        :param ignore_sfd: Whether to ignore the effect of SFD regularization in training the GAN
        """
        self.training_parameters = training_param
        self.weights: Weights = weight
        self.names: Names = name
        self.ignore_classifier: bool = ignore_classifier
        self.ignore_sfd: bool = ignore_sfd

        # grab the file data and relevant information
        input_file_config: InputModuleConfiguration = input_module.parse_input_file(config)
        self.class_label = input_file_config.class_label
        self.model_save_directory = input_file_config.save_directory
        self.request_save = input_file_config.request_save
        self.write_train_results = input_file_config.write_train_results
        self.generator_save_location = model_data.generator_filename
        self.discriminator_save_location = model_data.discriminator_filename

        y: ndarray
        y_onehot: ndarray
        self.input_data, y, y_onehot = input_module.load_data(input_file_config.data_file_path, self.class_label)

        # load the pre-trained classifier (note that we are not preparing it for training by compiling it)
        self.classifier = load_model(input_file_config.classifier_path,
                                     compile=False)
        self.classifier._name = self.names.classifier_name

        # set variables regarding the data shape
        self.num_seqs = self.input_data.shape[0]
        self.seq_length = self.input_data.shape[1]
        self.num_channels = self.input_data.shape[2]
        self.input_shape = (self.seq_length, self.num_channels)
        self.num_classes = y_onehot.shape[1]

        self.metric_classifier = train_simple_lstm.\
            create_classifier_model(self.num_classes)
        self.metric_classifier._name = "TSTR Classifier"

        # check whether or not there are models requested in the config file
        if isinstance(model_data, Empty) or not model_data.exists:
            # create the generator
            self.generator = self._create_generator()
            self.discriminator = self._create_discriminator()
        elif load_pretrained:
            self.generator, self.discriminator = self._load_pretrained_model(
                generator_path=model_data.generator_filename,
                discriminator_path=model_data.discriminator_filename,
                directory=model_data.directory)

        self.discriminator_model = models \
            .compile_discriminator_model(discriminator=self.discriminator,
                                         learning_rate=training_param.discriminator_learning_rate)

        # create the statistical feature network and compute the feature vector for the real data
        # this is used in the loss function
        self.feature_net = self._create_feature_net()
        self.synthetic_data_train = self._train_synthetic_data()
        self.synthetic_data_test = self._test_generated_data()
        self._create_architecture(discriminator_to_freeze=self.discriminator)

    def _create_generator(self) -> Functional:
        """
        Creates a generator.

        :return:A generator as a Keras Functional object.
        """
        return models.create_generator(seq_length=self.seq_length,
                                       num_channels=self.num_channels,
                                       latent_dim=self.training_parameters.latent_dimension)

    def _create_discriminator(self) -> Functional:
        """
        Creates a discriminator.

        :return: A discriminator as a Keras Functional object.
        """
        return models.create_discriminator(seq_length=self.seq_length, num_channels=self.num_channels)

    def _create_feature_net(self) -> Functional:
        """
        Creates the statistical feature net.

        :return: A statistical feature net as a Keras Functional object.
        """
        return models.create_statistical_feature_net(seq_length=self.seq_length,
                                                     num_channels=self.num_channels,
                                                     num_features=self.training_parameters.num_features)

    def _train_synthetic_data(self) -> ndarray:
        """
        Trains synthetic data.

        :return: A numpy array of trained synthetic data.
        """
        return np.repeat(
            np.reshape(
                np.mean(
                    self.feature_net.predict(
                        self.input_data,
                        self.training_parameters.batch_size
                    ),
                    axis=0),
                (1, self.num_channels * self.training_parameters.num_features)),
            self.training_parameters.batch_size, axis=0)

    def _test_generated_data(self) -> ndarray:
        """
        Tests the generated data.

        :return: A numpy array of tested data.
        """
        return np.repeat(
            np.reshape(
                np.mean(
                    self.feature_net.predict(
                        self.input_data,
                        self.training_parameters.batch_size
                    ),
                    axis=0),
                (1, self.num_channels * self.training_parameters.num_features)),
            self.training_parameters.test_size, axis=0)

    def _create_architecture(self, discriminator_to_freeze: Functional) -> None:
        """
        Creates the full architecture where the output of the generator is fed to the
        discriminator and the classifier.

        :param discriminator_to_freeze: The Keras model discriminator that will be "frozen" (I hope).
        :return: Nothing, since this is conceptually a void function in a reasonably typed language.
        """
        for discriminator_layer in discriminator_to_freeze.layers:
            discriminator_layer.trainable = False

        model_loss: dict = {'D': 'binary_crossentropy', 'C': 'categorical_crossentropy', 'SFN': critique.euc_dist_loss}

        if self.ignore_classifier:
            model_loss['C'] = train.null_loss

        if self.ignore_sfd:
            model_loss['SFN'] = train.null_loss

        self.GCD: Functional = Model(inputs=self.generator.input,
                                     outputs=[discriminator_to_freeze(self.generator.output),
                                              self.classifier(self.generator.output),
                                              self.feature_net(self.generator.output)])

        self.GCD.compile(loss=model_loss,
                         optimizer='adam', metrics={'D': 'accuracy', 'C': 'accuracy'},
                         loss_weights={'D': self.weights.discriminator_loss_weight,
                                       'C': self.weights.classifier_loss_weight,
                                       'SFN': self.weights.sfd_loss_weight})

    def train_discriminator(self) -> Tuple[np.float, np.float]:
        """
        Trains the discriminator. Mutates the discriminator and the generator.

        :return: The discriminator accuracy and the generator accuracy as a tuple in the following form
        (numpy array, numpy array).
        """
        discriminator_loss_vector: list = train \
            .train_discriminator(batch_size=self.training_parameters.batch_size,
                                 input_data=self.input_data,
                                 generator_model=self.generator,
                                 discriminator_model=self.discriminator_model,
                                 latent_dim=self.training_parameters.latent_dimension)

        GCD_loss_vec: list = train.train_generator(batch_size=self.training_parameters.batch_size,
                                                   input_data=self.input_data,
                                                   class_label=self.class_label,
                                                   actual_features=self.synthetic_data_train,
                                                   num_labels=self.num_classes,
                                                   model=self.GCD,
                                                   latent_dim=self.training_parameters.latent_dimension)

        # accuracy for the discriminator during its "turn" for training
        discriminator_accuracy: np.float = discriminator_loss_vector[1]

        # accuracy for the generator in tricking discriminator
        gen_accuracy: np.float = GCD_loss_vec[4]

        return discriminator_accuracy, gen_accuracy

    def generate_synthetic_data(self) -> Tuple[ndarray, float]:
        """
        Generates synthetic data.

        :return: Synthetic data that has been generated as a tuple containing the synthetic data
        and the accuracy of the generator class in the following form (numpy array, float).
        """
        syn_data: ndarray = train.generate_synthetic_data(size=self.training_parameters.test_size,
                                                          generator=self.generator,
                                                          latent_dim=self.training_parameters.latent_dimension,
                                                          time_steps=self.seq_length)

        pred: ndarray = np.argmax(self.classifier.predict(syn_data), axis=-1)
        true: list = [self.class_label] * self.training_parameters.test_size
        gen_class_acc: float = accuracy_score(true, pred)

        return syn_data, gen_class_acc

    def train_tstr_classifier(self, synthetic_data: np.ndarray):
        train_tstr_classifier(synthetic_data=synthetic_data,
                              classifier=self.metric_classifier,
                              class_label=self.class_label)


    def compute_rts_sts(self, syn_data: ndarray) -> Tuple[ndarray, ndarray]:
        """
        Computes the similarity metrics.

        :param syn_data: The synthetic data as a numpy array.
        :return: A tuple of the following form (numpy array, numpy array) containing
        the rts similarity metrics and the sts similarity metrics.
        """
        return train.compute_similarity_metrics(synthetic_input_data=syn_data,
                                                real_input_data=self.input_data,
                                                batch_size=self.training_parameters.test_size,
                                                real_synthetic_ratio=self.training_parameters.real_synthetic_ratio,
                                                synthetic_synthetic_ratio=
                                                self.training_parameters.synthetic_synthetic_ratio)

    def compute_statistical_feature_distance(self, syn_data: ndarray) -> ndarray:
        """
        Computes the statistical feature distance.

        :param syn_data: The synthetic data.
        :return: The statistical feature distance as a numpy array.
        """
        synthetic_features = self.feature_net.predict(syn_data, self.training_parameters.test_size, verbose=0)
        return critique.compute_statistical_feature_distance(synthetic_features, self.synthetic_data_test)

    def save_model_to_directory(self) -> None:
        """
        Saves the model to a directory.

        :return: Nothing, since this function is a void function.
        """
        save.save_keras_model(self.generator, self.model_save_directory, self.generator_save_location)
        save.save_keras_model(self.discriminator, self.model_save_directory, self.discriminator_save_location)

    def write_training_results(self,
                               current_epoch: int,
                               discriminator_accuracy: np.float,
                               generator_discriminator_acc: np.float,
                               generator_classifier_acc: np.float,
                               mean_rts_similarity: ndarray,
                               mean_sts_similarity: ndarray) -> None:
        """
        Writes the training results.

        :param current_epoch: The current epoch.
        :param discriminator_accuracy: The accuracy of the discriminator.
        :param generator_discriminator_acc: The generator discriminator accuracy.
        :param generator_classifier_acc: The generator classifier accuracy.
        :param mean_rts_similarity: The mean rts similarity.
        :param mean_sts_similarity: The mean sts similarity.
        :return: Nothing, since, well, its a void function, I hope at least. Maybe its not,
        and then the code will break one day.
        """
        save.write_results(current_epoch,
                           self.class_label,
                           discriminator_accuracy,
                           generator_discriminator_acc,
                           generator_classifier_acc,
                           mean_rts_similarity,
                           mean_sts_similarity)

    @staticmethod
    def _load_pretrained_model(generator_path: str,
                               discriminator_path: str,
                               directory: str) -> Tuple[Functional, Functional]:
        """
        Loads a pre-trained model.

        :return: Nothing.
        """
        generator_file_path = os.path.join(directory, generator_path)
        discriminator_file_path = os.path.join(directory, discriminator_path)
        return load_model(generator_file_path), load_model(discriminator_file_path)

    def compute_one_segment_real(self) -> ndarray:
        """
        Computes the one segment real.

        :return: A numpy array that corresponds with the calculated one segment real.
        """
        return np.reshape(self.input_data[np.random.randint(0, self.input_data.shape[0], 1)],
                          (self.seq_length, self.num_channels))
