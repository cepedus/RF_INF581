# code inspired from https://medium.com/swlh/genetic-artificial-neural-networks-d6b85578ba99
# Also from https://github.com/robertjankowski/ga-openai-gym/blob/491b7384dff4984367d526ce6f7fd02625128cc7/scripts/ga/individual.py#L82


# ======= Defining our Genetic Neural Network ======= #
import random

from keras.models import Sequential
from keras.layers import Dense, Dropout
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
import pandas as pd
import numpy as np
from tqdm import tqdm
from datetime import datetime
from time import time
from os import path


class GeneticNeuralNetwork(Sequential):
    # Constructor
    def __init__(self, layers_shapes, child_weights=None, dropout=0, discrete=True):
        # Initialize Sequential Model Super Class
        super().__init__()

        # Add layers_shape as a property of our Neural Network
        self.layers_shapes = layers_shapes
        self.fitness = 0
        self.dropout = dropout
        self.discrete = discrete

        # If no weights provided randomly generate them
        if child_weights is None:
            # Layers are created and randomly generated
            layers = [Dense(layers_shapes[1], input_shape=(layers_shapes[0],), activation='sigmoid'),
                      Dropout(dropout)]
            for shape in layers_shapes[2:-1]:
                layers.append(Dense(shape, activation='sigmoid'))
                layers.append(Dropout(dropout))
            layers.append(Dense(layers_shapes[-1], activation=('softmax' if discrete else None)))
        # If weights are provided set them within the layers
        else:
            # Set weights within the layers
            layers = [Dense(layers_shapes[1], input_shape=(layers_shapes[0],), activation='sigmoid',
                            weights=[child_weights[0], np.zeros(layers_shapes[1])]),
                      Dropout(dropout)]
            for i, shape in enumerate(layers_shapes[2:-1]):
                layers.append(Dense(shape, activation='sigmoid',
                                    weights=[child_weights[i + 1], np.zeros(shape)]))
                layers.append(Dropout(dropout))
            layers.append(Dense(layers_shapes[-1], activation=('softmax' if discrete else None),
                                weights=[child_weights[-1], np.zeros(layers_shapes[-1])]))
        for layer in layers:
            self.add(layer)

    def update_weights(self, network_weights):  # TODO we don't update bias
        count = 0
        for layer in self.layers:
            w = layer.get_weights()
            if w:
                layer.set_weights([network_weights[count], w[1]])
                count += 1

    # Function for foward propagating a row vector of a matrix
    def run_single(self, env, render=False):
        if self.discrete:
            obs = env.reset()
            fitness = 0
            while True:
                if render:
                    env.render()
                action_dist = self.predict(np.array([np.array(obs).reshape(-1, )]))[0]
                if np.isnan(action_dist).any():
                    break
                else:
                    action = np.random.choice(np.arange(env.action_space.n), p=action_dist)
                    # action = np.argmax(action_dist)  # ############################ TODO: take random action from distribution
                    obs, reward, done, _ = env.step(round(action.item()))
                    fitness += reward
                    if done:
                        break
            self.fitness = fitness
            return fitness
        else:
            raise NotImplementedError

    def save_model(self, output_folder):
        date = datetime.now().strftime('%m-%d-%Y_%H-%M')
        file_name = path.join(output_folder, date)
        # Save Weights
        self.save_weights(file_name + '-model.h5')

        # Save Layers shape and dropout
        np.save(file_name + '-parameters.npy', np.asarray([self.layers_shapes, self.dropout]))
        return

    @classmethod
    def load_model(cls, model_signature):
        '''

        :param model_signature: The signature of the model, by default it is the date '%m-%d-%Y_%H-%M'
        :param Class: Must be a GeneticNeuralNetwork (or its heritages)
        :return: a GNN with the weights and paremeters imported
        '''
        # Load layers_shape
        parameters = np.load(model_signature + '-parameters.npy')
        layers_shapes = parameters[0]
        dropout = parameters[1]

        # init a GNN Inherited Class
        gnn = cls(layers_shapes, dropout=dropout)

        # Load weights
        gnn.load_weights(model_signature + '-model.h5')
        return gnn


def mutation(network_weights, p_mutation=0.7, mutation_rate=5):
    # weights is a NxM matrix
    # for i, line in enumerate(weights):
    #     for j in range(len(line)):
    #         if random.uniform(0, 1) <= p_mutation:
    #             weights[i][j] *= random.uniform(2, 5)
    # return weights
    # for i, layer_weights in enumerate(network_weights):
    #     layer_weights = np.array(layer_weights)
    #     layer_weights[np.random.rand(*layer_weights.shape) < 0.5] *= 2
    #     network_weights[i] = layer_weights.tolist()
    # return network_weights
    
    for layer_weights in network_weights:
        for line in layer_weights:
            for j in range(len(line)):
                if random.uniform(0, 1) < p_mutation:
                    if np.isnan(line[j]):
                        print('hi')
                    line[j] *= random.uniform(-mutation_rate, mutation_rate)
    return network_weights


def mutate_network(network, p_mutation=0.7):
    # Lists for respective weights
    nn_weights = []
    for layer in network.layers:
        w = layer.get_weights()
        if w:
            nn_weights.append(w[0])

    nn_weights = mutation(nn_weights, p_mutation)
    network.update_weights(nn_weights)
    return network


# Crossover traits between two Genetic Neural Networks
def dynamic_crossover(nn1, nn2, p_mutation=0.7, kind=0, p=0.1):
    # Assert both Neural Networks are of the same format
    assert nn1.layers_shapes == nn2.layers_shapes
    assert nn1.dropout == nn2.dropout
    assert nn1.__class__ == nn2.__class__

    # Lists for respective weights
    nn1_weights = []
    nn2_weights = []
    child_weights = []
    # Get all weights from all layers in the networks
    for layer_1 in nn1.layers:
        w = layer_1.get_weights()
        if w:
            nn1_weights.append(w[0])

    for layer_2 in nn2.layers:
        w = layer_2.get_weights()
        if w:
            nn2_weights.append(w[0])

    if kind == 0:
        for i in range(0, len(nn1_weights)):
            for j in range(np.shape(nn1_weights[i])[1] - 1):
                nn1_weights[i][:, j] = random.choice([nn1_weights[i][:, j], nn2_weights[i][:, j]])

            # After crossover add weights to child
            child_weights.append(nn1_weights[i])
            child_weights = child_weights

    if kind == 1:
        for i in range(0, len(nn1_weights)):
            for j in range(np.shape(nn1_weights[i])[1] - 1):
                nn1_weights[i][:, j] = random.choice([(nn1_weights[i][:, j]*p + nn2_weights[i][:, j]*(1-p)),
                                                      (nn1_weights[i][:, j]*(1-p) + nn2_weights[i][:, j]*p)])

            # After crossover add weights to child
            child_weights.append(nn1_weights[i])
            child_weights = child_weights


    # add a chance for mutation
    child_weights = mutation(child_weights, p_mutation)

    # Create and return child object
    return nn1.__class__(layers_shapes=nn1.layers_shapes, child_weights=child_weights, dropout=nn1.dropout)


def random_pick(population):
    fitnesses = np.array([gnn.fitness for gnn in population])
    fitnesses_abs = np.array([np.abs(gnn.fitness) for gnn in population])
    fitnesses = fitnesses / np.max(fitnesses_abs)

    selection_probabilities = np.exp(fitnesses) / sum(np.exp(fitnesses))

    # total_fitness = np.sum([gnn.fitness for gnn in population])
    # selection_probabilities = [gnn.fitness / total_fitness for gnn in population]
    pick_1 = np.random.choice(len(population), p=selection_probabilities)
    pick_2 = pick_1
    while pick_2 == pick_1:
        pick_2 = np.random.choice(len(population), p=selection_probabilities)
    return population[pick_1], population[pick_2]


def ranking_pick(population):
    sorted_population = sorted(population, key=lambda gnn: gnn.fitness, reverse=True)
    return sorted_population[:2]


def run_generation(env, old_population, new_population, p_mutation, random_selection=False):
    for i in range(0, len(old_population) - 1, 2):
        # Selection
        parent1, parent2 = random_pick(old_population) if random_selection else ranking_pick(old_population)

        # Crossover and Mutation
        child1 = dynamic_crossover(parent1, parent2, p_mutation)
        child2 = dynamic_crossover(parent1, parent2, p_mutation)

        # Run childs
        child1.run_single(env)
        child2.run_single(env)

        # If children fitness is greater than parents update population
        if child1.fitness + child2.fitness > parent1.fitness + parent2.fitness:
            new_population[i] = child1
            new_population[i + 1] = child2
        else:
            new_population[i] = parent1
            new_population[i + 1] = parent2


def baseline_init(agent, env, baseline, render=True):
    t0 = time()
    initial_fitness = agent.run_single(env)  # Get the initial fitness
    while initial_fitness < baseline:  # Mutate network until one individual achieves the baseline
        agent = mutate_network(agent, 0.8)
        initial_fitness = agent.run_single(env)
    print('Ancestral Fitness: ', initial_fitness, ' found in ', time() - t0, 'ms')
    agent.run_single(env, render=render)  # Show simulation for this optimized initialization
    return agent


def statistics(population):
    population_fitness = [individual.fitness for individual in population]
    return np.mean(population_fitness), np.min(population_fitness), np.max(population_fitness)
