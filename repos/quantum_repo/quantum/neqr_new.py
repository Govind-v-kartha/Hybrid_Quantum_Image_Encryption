from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
from qiskit import QuantumCircuit, QuantumRegister, transpile
from qiskit_aer import AerSimulator


@dataclass
class NEQRSpec:
    image_size: int
    n_pixels: int
    position_qubits: int
    grayscale_qubits: int
    total_qubits: int


@dataclass
class NEQREncoding:
    circuit: QuantumCircuit
    spec: NEQRSpec
    pixel_values: np.ndarray


def neqr_spec(image_size: int) -> NEQRSpec:
    if image_size <= 0 or (image_size & (image_size - 1)) != 0:
        raise ValueError("image_size must be a positive power of 2.")

    n = int(np.log2(image_size))
    position_qubits = 2 * n
    grayscale_qubits = 8
    n_pixels = image_size * image_size
    total_qubits = position_qubits + grayscale_qubits

    return NEQRSpec(
        image_size=image_size,
        n_pixels=n_pixels,
        position_qubits=position_qubits,
        grayscale_qubits=grayscale_qubits,
        total_qubits=total_qubits,
    )


class NEQRQuantumEncoder:
    """
    NEQR for 8-bit grayscale images.

    State idea:
        (1/sqrt(N)) sum_i |f(i)> |i>

    where |f(i)> is the 8-bit grayscale value of pixel i.
    """

    def __init__(self, image_size: int = 16) -> None:
        self.spec = neqr_spec(image_size=image_size)

    @staticmethod
    def _index_bits(index: int, width: int) -> List[int]:
        return [(index >> i) & 1 for i in range(width)]

    @staticmethod
    def _pixel_bits(pixel: int) -> List[int]:
        pixel = int(np.clip(pixel, 0, 255))
        return [(pixel >> i) & 1 for i in range(8)]

    def _apply_multi_controlled_x_for_index(
        self,
        qc: QuantumCircuit,
        position_qubits,
        target_qubit,
        pixel_index: int,
    ) -> None:
        bits = self._index_bits(pixel_index, len(position_qubits))

        for bit, q in zip(bits, position_qubits):
            if bit == 0:
                qc.x(q)

        qc.mcx(list(position_qubits), target_qubit, mode="noancilla")

        for bit, q in zip(bits, position_qubits):
            if bit == 0:
                qc.x(q)

    def encode(self, image: np.ndarray) -> NEQREncoding:
        image = np.asarray(image, dtype=np.float32)
        if image.shape != (self.spec.image_size, self.spec.image_size):
            raise ValueError(
                f"Expected image shape {(self.spec.image_size, self.spec.image_size)}, got {image.shape}"
            )

        flat = np.rint(np.clip(image, 0.0, 255.0)).astype(np.uint8).reshape(-1)

        p = QuantumRegister(self.spec.position_qubits, "p")
        g = QuantumRegister(self.spec.grayscale_qubits, "g")
        qc = QuantumCircuit(p, g, name="NEQR")

        # equal superposition over pixel positions
        qc.h(p)

        # encode each 8-bit grayscale value conditioned on position
        for idx, px in enumerate(flat):
            bits = self._pixel_bits(int(px))

            for bit_idx, bit_val in enumerate(bits):
                if bit_val == 1:
                    self._apply_multi_controlled_x_for_index(
                        qc=qc,
                        position_qubits=p,
                        target_qubit=g[bit_idx],
                        pixel_index=idx,
                    )

        return NEQREncoding(
            circuit=qc,
            spec=self.spec,
            pixel_values=flat.astype(np.int32),
        )

    @staticmethod
    def statevector(encoding: NEQREncoding) -> Statevector:
        return Statevector.from_instruction(encoding.circuit)

    @staticmethod
    def fidelity(enc_a: NEQREncoding, enc_b: NEQREncoding) -> float:
        psi = Statevector.from_instruction(enc_a.circuit)
        phi = Statevector.from_instruction(enc_b.circuit)
        return float(np.abs(np.vdot(psi.data, phi.data)) ** 2)

    @staticmethod
    def resource_report(encoding: NEQREncoding) -> Dict[str, object]:
        qc = encoding.circuit
        ops = qc.count_ops()

        one_qubit_gates = 0
        two_qubit_gates = 0
        multi_qubit_gates = 0

        for inst, count in ops.items():
            if inst in {"h", "x", "ry", "rz", "rx", "u", "u1", "u2", "u3", "p", "s", "sdg", "t", "tdg"}:
                one_qubit_gates += int(count)
            elif inst in {"cx", "cz", "swap", "cy", "ch", "crx", "cry", "crz", "cp"}:
                two_qubit_gates += int(count)
            else:
                multi_qubit_gates += int(count)

        return {
            "method": "NEQR",
            "image_size": encoding.spec.image_size,
            "n_pixels": encoding.spec.n_pixels,
            "position_qubits": encoding.spec.position_qubits,
            "grayscale_qubits": encoding.spec.grayscale_qubits,
            "total_qubits": encoding.spec.total_qubits,
            "depth": int(qc.depth()),
            "size": int(qc.size()),
            "width": int(qc.num_qubits),
            "count_ops": {str(k): int(v) for k, v in ops.items()},
            "one_qubit_gates": one_qubit_gates,
            "two_qubit_gates": two_qubit_gates,
            "multi_qubit_gates": multi_qubit_gates,
        }


_cached_simulator = None


def _get_simulator():
    global _cached_simulator
    if _cached_simulator is None:
        _cached_simulator = AerSimulator()
    return _cached_simulator


def reconstruct_neqr_image(qc: QuantumCircuit, height: int, width: int, shots: int = 8192) -> np.ndarray:
    """Reconstruct an NEQR image by measuring the circuit with AerSimulator.

    The encoder uses a little-endian flat pixel index across the position qubits.
    This decoder samples that circuit and maps the measured flat index back to
    (row, col). Because this is shot-based, it is intentionally lossy and can
    leave some pixels unset when the sample budget is too small.
    """
    if height != width:
        raise ValueError(f"NEQR reconstruction expects a square image, got {height}x{width}")

    image_size = int(height)
    spec = neqr_spec(image_size=image_size)
    if qc.num_qubits < spec.total_qubits:
        raise ValueError(
            f"Circuit has {qc.num_qubits} qubits, expected at least {spec.total_qubits}"
        )

    recon_img = np.zeros((height, width), dtype=np.uint8)

    qc_measured = qc.copy()
    qc_measured.measure_all()

    simulator = _get_simulator()
    compiled = transpile(qc_measured, simulator, optimization_level=0)
    job = simulator.run(compiled, shots=shots)
    result = job.result()
    counts = result.get_counts()

    position_mask = (1 << spec.position_qubits) - 1
    intensity_shift = spec.position_qubits
    pixel_votes = {}

    for bitstring, count in counts.items():
        measured_bits = bitstring[::-1]
        pos_bits = measured_bits[:spec.position_qubits]
        intensity_bits = measured_bits[spec.position_qubits : spec.position_qubits + spec.grayscale_qubits]

        flat_idx = sum((int(bit) & 1) << bit_index for bit_index, bit in enumerate(pos_bits))
        if flat_idx >= spec.n_pixels:
            continue

        intensity_val = sum((int(bit) & 1) << bit_index for bit_index, bit in enumerate(intensity_bits))
        if flat_idx not in pixel_votes:
            pixel_votes[flat_idx] = {}
        pixel_votes[flat_idx][intensity_val] = pixel_votes[flat_idx].get(intensity_val, 0) + int(count)

    for flat_idx, votes in pixel_votes.items():
        intensity_val = max(votes.items(), key=lambda item: item[1])[0]
        row = flat_idx // width
        col = flat_idx % width
        recon_img[row, col] = intensity_val

    return recon_img