"""
Block Content Analysis for Adaptive Encryption Strategy.

Analyzes each ROI block's content (black pixel percentage, entropy) to determine
whether to use heavyweight Quantum encryption or lightweight AES encryption.

Decision Logic:
    - If black_pixel_percentage > threshold (default 90%) → AES (fast)
    - If content entropy < threshold (default 0.1) → AES (fast)
    - Otherwise → Quantum NEQR (secure)
"""

import numpy as np
from typing import List, Tuple, Dict

from utils.logger import setup_logger, get_config_path

logger = setup_logger("BLOCK_ANALYSIS", get_config_path())


class BlockAnalyzer:
    """Analyze block content and classify encryption strategy."""

    def __init__(
        self,
        black_pixel_threshold: float = 0.90,
        black_intensity_cutoff: int = 30,
        entropy_threshold: float = 0.1,
    ):
        """
        Args:
            black_pixel_threshold: Fraction (0-1) of black pixels above which
                                   the block is considered "mostly black" → AES.
            black_intensity_cutoff: Pixel intensity below this is considered black (0-255).
            entropy_threshold: Normalized entropy below this → AES.
        """
        self.black_pixel_threshold = black_pixel_threshold
        self.black_intensity_cutoff = black_intensity_cutoff
        self.entropy_threshold = entropy_threshold

    def get_black_pixel_percentage(self, block: np.ndarray) -> float:
        """
        Calculate fraction of black (near-zero intensity) pixels in a block.

        Args:
            block: Image block (H, W, 3) or (H, W).

        Returns:
            Fraction of black pixels (0.0 to 1.0).
        """
        if block.ndim == 3:
            gray = np.mean(block, axis=2).astype(np.uint8)
        else:
            gray = block.astype(np.uint8)

        black_pixels = np.sum(gray < self.black_intensity_cutoff)
        total_pixels = gray.size
        return black_pixels / total_pixels

    def get_content_entropy(self, block: np.ndarray) -> float:
        """
        Calculate normalized Shannon entropy (0 = uniform, 1 = max complexity).

        Args:
            block: Image block.

        Returns:
            Normalized entropy in [0, 1].
        """
        if block.ndim == 3:
            gray = np.mean(block, axis=2).astype(np.uint8)
        else:
            gray = block.astype(np.uint8)

        hist, _ = np.histogram(gray, bins=256, range=(0, 256))
        hist = hist / hist.sum()
        nonzero = hist[hist > 0]
        entropy = -np.sum(nonzero * np.log2(nonzero))
        return entropy / 8.0  # max entropy for 8-bit = 8

    def classify_block(self, block: np.ndarray, block_id: int = -1) -> Dict:
        """
        Classify a single block into 'quantum' or 'aes'.

        Returns:
            Dict with encryption_type, black_percentage, entropy, reason.
        """
        black_pct = self.get_black_pixel_percentage(block)
        entropy = self.get_content_entropy(block)

        if black_pct >= self.black_pixel_threshold:
            enc_type = "aes"
            reason = (
                f"High black pixel ratio ({black_pct*100:.1f}% >= "
                f"{self.black_pixel_threshold*100:.0f}%) → lightweight AES"
            )
        elif entropy < self.entropy_threshold:
            enc_type = "aes"
            reason = (
                f"Low entropy ({entropy:.4f} < {self.entropy_threshold}) "
                f"→ uniform content → lightweight AES"
            )
        else:
            enc_type = "quantum"
            reason = (
                f"Complex content (entropy={entropy:.4f}, "
                f"black={black_pct*100:.1f}%) → full quantum encryption"
            )

        return {
            "block_id": block_id,
            "encryption_type": enc_type,
            "black_percentage": black_pct,
            "entropy": entropy,
            "reason": reason,
        }

    def analyze_all_blocks(
        self, blocks: List[np.ndarray]
    ) -> Tuple[List[Dict], Dict]:
        """
        Classify every block and return per-block info plus a summary.

        Args:
            blocks: List of image blocks.

        Returns:
            (classifications, summary)
        """
        classifications = []
        quantum_count = 0
        aes_count = 0
        black_pcts = []
        entropies = []

        for idx, block in enumerate(blocks):
            cls = self.classify_block(block, block_id=idx)
            classifications.append(cls)
            if cls["encryption_type"] == "quantum":
                quantum_count += 1
            else:
                aes_count += 1
            black_pcts.append(cls["black_percentage"])
            entropies.append(cls["entropy"])

        n = len(blocks)
        summary = {
            "total_blocks": n,
            "quantum_blocks": quantum_count,
            "aes_blocks": aes_count,
            "quantum_percentage": (quantum_count / n * 100) if n else 0,
            "aes_percentage": (aes_count / n * 100) if n else 0,
            "avg_black_percentage": float(np.mean(black_pcts)) if n else 0,
            "avg_entropy": float(np.mean(entropies)) if n else 0,
            "min_entropy": float(np.min(entropies)) if n else 0,
            "max_entropy": float(np.max(entropies)) if n else 0,
            "black_pixel_threshold": self.black_pixel_threshold,
            "entropy_threshold": self.entropy_threshold,
        }

        logger.info(
            f"Block analysis complete: {quantum_count} quantum, "
            f"{aes_count} AES out of {n} total blocks"
        )
        return classifications, summary
