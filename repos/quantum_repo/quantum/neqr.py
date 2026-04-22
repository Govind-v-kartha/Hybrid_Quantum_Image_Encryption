import numpy as np
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.circuit.library import RYGate, MCXGate
from qiskit_aer import AerSimulator
from qiskit import transpile

# Module-level cached simulator instance (avoid recreating per-block)
_cached_simulator = None

def _get_simulator():
    global _cached_simulator
    if _cached_simulator is None:
        _cached_simulator = AerSimulator()
    return _cached_simulator


def encode_neqr(image: np.ndarray) -> QuantumCircuit:
    image = np.asarray(image, dtype=np.uint8)
    if image.ndim != 2:
        raise ValueError(f"encode_neqr expects 2D grayscale image, got shape {image.shape}")

    height, width = image.shape
    if height != width:
        raise ValueError(f"NEQR expects square image, got {height}x{width}")
    if height == 0 or (height & (height - 1)) != 0:
        raise ValueError(f"Image size must be power of 2, got {height}")

    n = int(np.log2(height))
    num_position_qubits = 2 * n
    num_intensity_qubits = 8
    total_qubits = num_position_qubits + num_intensity_qubits

    qr = QuantumRegister(total_qubits, "q")
    qc = QuantumCircuit(qr)

    # Step 1 — Superposition over positions
    for i in range(num_position_qubits):
        qc.h(qr[i])

    # Step 2 — Encode intensity per pixel
    for i in range(height):
        for j in range(width):
            pixel_value = int(np.clip(image[i, j], 0, 255))
            if pixel_value == 0:
                continue

            x_bin = format(i, f"0{n}b")
            y_bin = format(j, f"0{n}b")
            position_bin = x_bin + y_bin

            for bit_pos, bit in enumerate(position_bin):
                if bit == "0":
                    qc.x(qr[bit_pos])

            intensity_bin = format(pixel_value, "08b")
            controls = [qr[k] for k in range(num_position_qubits)]

            for bit_idx, bit in enumerate(intensity_bin[::-1]):  # LSB first
                if bit == "1":
                    target = qr[num_position_qubits + bit_idx]
                    qc.append(MCXGate(len(controls)), controls + [target])

            for bit_pos, bit in enumerate(position_bin):
                if bit == "0":
                    qc.x(qr[bit_pos])

    return qc

def reconstruct_neqr_image(qc, height, width, shots=8192):
    """
    Reconstruct image from NEQR quantum circuit using majority-vote
    shot-based measurement for lossless reconstruction.

    For each pixel position (i, j), we accumulate the measurement counts
    for every observed intensity value and select the intensity with the
    highest count. This guarantees correctness for deterministic NEQR
    circuits and provides robustness against measurement noise.

    If any position is not sampled (extremely unlikely with sufficient
    shots), additional measurement rounds are performed until all
    positions are covered.
    """
    n = int(np.log2(height))
    num_position_qubits = 2 * n
    num_intensity_qubits = 8
    total_positions = height * width

    qc_measured = qc.copy()
    qc_measured.measure_all()

    simulator = _get_simulator()
    compiled = transpile(qc_measured, simulator, optimization_level=0)

    # Accumulator: for each (i, j) → {intensity_val: total_count}
    vote_map = {}

    remaining_shots = shots
    max_retries = 3
    attempt = 0

    while remaining_shots > 0 and attempt <= max_retries:
        run_shots = remaining_shots if attempt == 0 else max(remaining_shots, shots)
        job = simulator.run(compiled, shots=run_shots)
        result = job.result()
        counts = result.get_counts()

        for bitstring, count in counts.items():
            bitstring = bitstring[::-1]   # endian fix

            pos_bits = bitstring[:num_position_qubits]
            intensity_bits = bitstring[
                num_position_qubits : num_position_qubits + num_intensity_qubits
            ]

            i = int(pos_bits[:n], 2)
            j = int(pos_bits[n:], 2)

            if i < height and j < width:
                intensity_val = int(intensity_bits[::-1], 2)  # LSB first
                key = (i, j)
                if key not in vote_map:
                    vote_map[key] = {}
                vote_map[key][intensity_val] = (
                    vote_map[key].get(intensity_val, 0) + count
                )

        # Check completeness
        if len(vote_map) >= total_positions:
            break

        # Some positions unsampled — retry with more shots
        attempt += 1
        remaining_shots = shots  # full batch for retry

    # Build image from majority votes
    recon_img = np.zeros((height, width), dtype=np.uint8)
    for (i, j), intensity_counts in vote_map.items():
        # Pick intensity with highest count (majority vote)
        best_intensity = max(intensity_counts, key=intensity_counts.get)
        recon_img[i, j] = best_intensity

    return recon_img