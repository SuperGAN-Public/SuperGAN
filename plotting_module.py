"""
Contains functions for displaying and saving plots of both real and generated
data (currently written for tri-axial data but could be easily modified for
applications with a different number of sensor channels)
"""

import matplotlib.patches as mpl_patches
import matplotlib.pyplot as plt
import matplotlib
import tkinter
import numpy as np
from typing import List

matplotlib.use('tkagg')


def save_grid_plot(input_data: np.ndarray,
                   output_data: np.ndarray,
                   seq_length: int,
                   sampling_rate: float,
                   real: bool,
                   file_name: str) -> None:
    """
    A utility function for saving the images of plotted data.

    :param input_data: The input data as a numpy array.
    :param output_data: The output data as a numpy array.
    :param seq_length: The sequence length.
    :param sampling_rate: The sampling rate.
    :param real: Whether or not this is real or fake.
    :param file_name: The file name as a string.
    :return: Nothing.
    """
    plot = configure_plot(input_data,
                          output_data,
                          seq_length,
                          sampling_rate,
                          real)
    plot.savefig(file_name)


# FUNCTION FOR DISPLAYING IMAGES OF PLOTTED DATA
def display_grid_plot(input_data: np.ndarray,
                      output_data: np.ndarray,
                      seq_length: int,
                      sampling_rate: float,
                      real: bool) -> None:
    """
    A utility function for displaying the images of plotted data.

    :param input_data: The input data as a numpy array.
    :param output_data: The output data as a numpy array.
    :param seq_length: The sequence length.
    :param sampling_rate: The sampling rate.
    :param real: Whether or not this is real or fake.
    :return: Nothing.
    """
    plot = configure_plot(input_data,
                          output_data,
                          seq_length,
                          sampling_rate,
                          real)
    plot.show()


def configure_plot(input_data: np.ndarray,
                   class_name: str,
                   seq_length: int,
                   sampling_rate: float,
                   real: bool) -> plt:
    """
    A helper function that configures the plot, so that there is as little
    redundancy as possible in the plot code.

    :param input_data: The input data as a numpy array.
    :param seq_length: The sequence length.
    :param sampling_rate: The sampling rate.
    :param real: Whether or not this is real or fake.
    :return: A configured and mutated plot for the given data.
    """
    hz = 1.0 / sampling_rate
    title = f'Real Data for label class {classname}'
    if not real:
        title = f'Synthetic Data for label class {classname}'
    t = np.arange(0, seq_length * hz, hz)
    x_patch = mpl_patches.Patch(color='blue', label='x axis')
    y_patch = mpl_patches.Patch(color='red', label='y axis')
    z_patch = mpl_patches.Patch(color='green', label='z axis')
    x = input_data[:, 0]
    output_data = input_data[:, 1]
    z = input_data[:, 2]
    f, (ax1, ax2, ax3) = plt.subplots(3, sharex='all', sharey='all')
    ax1.plot(t, x, 'b-')
    ax1.set_title(title)
    ax2.plot(t, output_data, 'r-', label="y")
    ax3.plot(t, z, 'g-', label="z")
    plt.xlabel("Seconds")
    plt.legend(handles=[x_patch, y_patch, z_patch], loc=4)
    f.subplots_adjust(hspace=0)
    return plt


def plot_results(epochs: List[int],
                 class_acc: List[float],
                 disc_acc: List[float],
                 gen_acc: List[float]):
    plt.figure(figsize=(12, 9))
    plt.style.use('fivethirtyeight')
    plt.xticks(fontsize=15)
    plt.yticks(fontsize=15)
    ax = plt.subplot(111)
    ax.set_title('GAN Accuracy Progression')
    ax.set_xlabel('Epochs')
    ax.set_ylabel('Model Accuracy')
    ax.set_yticks(np.arange(0, 101, 10))
    ax.set_xticks(np.arange(0, len(epochs) + 1))
    ax.plot(epochs, convert_dec_to_percent(class_acc),
            label='Classifier Accuracy')
    ax.plot(epochs, convert_dec_to_percent(disc_acc),
            label='Discriminator Accuracy')
    ax.plot(epochs, convert_dec_to_percent(gen_acc),
            label='Generator-Trick-Discriminator Accuracy')
    vals = ax.get_yticks()
    ax.set_yticklabels(['{}%'.format(x) for x in vals])
    plt.legend()
    plt.show()


def convert_dec_to_percent(decimal_list: List[float]) -> List[float]:
    return list(map(lambda x: x * 100, decimal_list))
