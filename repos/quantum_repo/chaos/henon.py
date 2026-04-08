from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
import numpy as np 

def henon_map(x0, y0, alpha=1.4, beta=0.3, n_iter=64):
    x = np.zeros(n_iter, dtype=np.float64)
    y = np.zeros(n_iter, dtype=np.float64)
    x[0], y[0] = x0, y0
    for i in range(1, n_iter):
        prev_x = float(np.clip(x[i - 1], -1e6, 1e6))
        prev_y = float(np.clip(y[i - 1], -1e6, 1e6))
        x[i] = 1.0 - alpha * (prev_x * prev_x) + prev_y
        y[i] = beta * prev_x
    return x, y